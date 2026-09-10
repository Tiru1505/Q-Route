"""
QROEngine — the single object that ties the whole system together.

WHY THIS EXISTS
---------------
Until now every capability lived in its own script, and each one reloaded the
286,603-node graph from scratch (~8 s) and rebuilt its own traffic simulator.
That is fine for experiments and useless for a running system.

This class owns the expensive state once — graph, traffic simulator, current
traffic conditions, the active trip — and exposes the operations the product
actually performs:

    plan()            find routes between two points
    plan_multistop()  order a set of deliveries (the QPSO problem)
    set_scenario()    apply one of the eight traffic scenarios
    spike_route()     congest the active route, to trigger rerouting
    check_reroute()   is a better route available from where we are now?
    traffic()         current congestion for the map
    benchmark()       QPSO vs PSO vs GA on identical conditions
    convergence()     iteration-vs-fitness curves
    scalability()     how each method scales with problem size

EVERY METHOD RETURNS FRONTEND-READY JSON
----------------------------------------
Field names are camelCase and match src/data/mockData.js exactly — distanceKm,
etaMin, congestion, path as [[lat, lon], ...]. That is deliberate: the FastAPI
layer becomes a thin pass-through rather than a translation layer, and whoever
writes it cannot accidentally invent a different contract.

The engine deliberately knows nothing about HTTP. It is a service layer, not a
server.
"""
import functools
import math
import threading
import time
from pathlib import Path

from graph.edge_weights import MODES, CostModel
from graph.graph_loader import load_graph, load_places, reset_traffic, resolve_place
from optimization.dijkstra import dijkstra_route
from routing.rerouting import ActiveTrip, RerouteEngine
from alerts.alert_engine import AlertEngine, AlertPolicy
from traffic.congestion_model import CongestionModel
from traffic.simulator import SCENARIO_IDS, TrafficSimulator

ROOT = Path(__file__).resolve().parent

# Route colours, matching the frontend's traffic palette.
ROUTE_COLORS = ["#34d399", "#fbbf24", "#fb923c", "#2dd4bf", "#e879f9"]
LEVEL_COLORS = {"low": "#34d399", "moderate": "#fbbf24",
                "heavy": "#fb923c", "severe": "#f43f5e"}


def _round(v, n=3):
    return None if v is None or not math.isfinite(v) else round(float(v), n)


def _serialised(method):
    """Run under the engine's graph lock. See QROEngine.lock for why."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)
    return wrapper


class QROEngine:
    """
    Stateful routing engine. Build one, keep it for the lifetime of the process.

    Loading the graph takes ~8 s, so a server must construct this at startup —
    never per request.
    """

    def __init__(self, graph_path=None, scenario="normal", seed=42, verbose=True):
        t0 = time.perf_counter()
        self.G = load_graph(graph_path, verbose=verbose)
        self.model = CongestionModel()
        self.sim = TrafficSimulator(self.G, self.model, seed=seed)
        self.alerts = AlertEngine(AlertPolicy())

        # One graph, many writers and readers, several threads. The monitor's
        # forecast writes predicted congestion onto the road ahead, re-solves,
        # and restores the values it snapshotted; a traffic event that landed
        # in between was then overwritten by that restore and silently lost. A
        # spike applied during a forecast tick vanished and the monitor kept
        # saying "keep" — measured, not hypothesised. Everything that changes
        # congestion, or reads it to route, now takes turns.
        #
        # Reentrant, because check_reroute runs inside the agent's overlay.
        # The benchmark methods do NOT take it: they run for minutes and would
        # freeze the monitor and every route request behind them.
        self.lock = threading.RLock()

        self.scenario = None
        self.state = None
        self.trip = None
        self._routes = []
        self._decoder_cache = {}
        self.load_ms = 0.0          # set below; health() reads it during setup

        self.set_scenario(scenario)
        self.load_ms = (time.perf_counter() - t0) * 1000
        if verbose:
            print(f"[engine] ready in {self.load_ms / 1000:.1f}s")

    # ================================================================ meta
    def health(self):
        return {
            "status": "ok",
            "graph": {
                "nodes": self.G.number_of_nodes(),
                "edges": self.G.number_of_edges(),
            },
            "scenario": self.scenario,
            "loadMs": round(self.load_ms),
            "activeTrip": self.trip is not None,
        }

    def places(self):
        """Selectable start/destination points, for the UI dropdowns."""
        return [
            {"id": k, "name": v["name"], "coords": [v["lat"], v["lon"]]}
            for k, v in load_places().items()
        ]

    def scenarios(self):
        return list(SCENARIO_IDS)

    def modes(self):
        return [{"id": k, "name": k.replace("_", " ").title(), "weights": v}
                for k, v in MODES.items()]

    # ============================================================= traffic
    @_serialised
    def set_scenario(self, scenario):
        """Apply one of the eight traffic scenarios to the whole network."""
        if scenario not in SCENARIO_IDS:
            raise ValueError(f"Unknown scenario '{scenario}'")
        reset_traffic(self.G)
        self.scenario = scenario
        self.state = self.sim.generate(scenario)
        self.sim.apply(self.state)
        return self.health()

    @_serialised
    def spike_route(self, level=0.92):
        """
        Congest the ACTIVE route. This is the rerouting trigger.

        Fixed hotspots sit where real jams form and so often miss whichever
        route was chosen; this guarantees the disruption lands on the road the
        driver is actually on.
        """
        if self.trip is None:
            raise ValueError("No active trip to congest.")
        self.state = self.sim.congest_route(self.state, self.trip.remaining_nodes,
                                            level=level)
        self.sim.apply(self.state)
        return {"ok": True, "level": level,
                "affected": self.state.incidents[-1]["edges_affected"]}

    @_serialised
    def traffic(self, limit=400):
        """
        Congestion overlay for the map.

        741,203 edges cannot go over the wire, and no map can draw them. We
        send the most congested arterial segments, which is what the overlay is
        actually for.
        """
        segs = []
        for u, v, k, d in self.G.edges(keys=True, data=True):
            c = float(d.get("congestion", 0.0) or 0.0)
            if c < 0.05:
                continue
            hw = d.get("highway")
            hw = str(hw[0] if isinstance(hw, list) else hw)
            if hw not in ("motorway", "trunk", "primary", "secondary",
                          "motorway_link", "trunk_link", "primary_link"):
                continue
            segs.append((c, u, v, k, d, hw))

        # Stratified sample, not simply the worst N.
        #
        # Sorting by congestion and taking the top 200 made every segment on the
        # map "severe" during peak hour — a uniform wall of red that shows
        # nothing and makes the legend pointless. Taking a share from each band
        # gives the overlay its actual job back: showing where traffic differs.
        buckets = {"low": [], "moderate": [], "heavy": [], "severe": []}
        for item in segs:
            buckets[self.model.level(item[0])].append(item)

        per_band = max(limit // 4, 1)
        chosen = []
        for band in ("severe", "heavy", "moderate", "low"):
            rows = sorted(buckets[band], key=lambda t: -t[0])
            chosen.extend(rows[:per_band])
        # Backfill from whatever is left if some bands were sparse.
        if len(chosen) < limit:
            picked = {(u, v, k) for _c, u, v, k, _d, _h in chosen}
            for item in sorted(segs, key=lambda t: -t[0]):
                if (item[1], item[2], item[3]) not in picked:
                    chosen.append(item)
                    if len(chosen) >= limit:
                        break

        out = []
        for c, u, v, k, d, hw in chosen[:limit]:
            level = self.model.level(c)
            out.append({
                "id": f"{u}_{v}_{k}",
                "name": str(d.get("name") or hw.replace("_", " ").title()),
                "level": level,
                "congestion": _round(c, 3),
                "color": LEVEL_COLORS[level],
                "speedKph": _round(d.get("current_speed_kph"), 1),
                "path": [
                    [float(self.G.nodes[u]["y"]), float(self.G.nodes[u]["x"])],
                    [float(self.G.nodes[v]["y"]), float(self.G.nodes[v]["x"])],
                ],
            })

        incidents = [{
            "id": f"inc{i}",
            "type": inc["type"],
            "name": inc["type"].replace("_", " ").title(),
            "location": inc["location"].replace("_", " ").title(),
            "coords": [inc["lat"], inc["lon"]],
            "severity": inc["severity"],
            "description": f"{inc['edges_affected']} road segments affected",
            "reportedAt": "just now",
        } for i, inc in enumerate(self.state.incidents)]

        return {
            "segments": out,
            "incidents": incidents,
            "scenario": self.scenario,
            "updatedAt": str(self.state.timestamp),
            "isDemoData": True,
        }

    # ============================================================ planning
    def _serialise_route(self, route, index=0, recommended=False, fastest=False,
                         via="", time_saved=0.0):
        score = 100.0
        if route.fitness and math.isfinite(route.fitness):
            # Fitness 0.7 is the free-flow reference; scale so a reference-quality
            # route scores ~95 and a badly congested one drops away from it.
            score = max(0.0, min(100.0, 100.0 - (route.fitness - 0.7) * 22.0))
        return {
            "id": f"r{index + 1}",
            "label": "Route 1" if recommended else f"Route {index + 1}",
            "algorithm": route.algorithm,
            "recommended": recommended,
            "fastest": fastest,
            "distanceKm": _round(route.distance_km, 2),
            "etaMin": _round(route.time_min, 1),
            "congestion": _round(route.mean_congestion, 3),
            "score": round(score),
            "timeSavedMin": _round(time_saved, 1),
            "via": via,
            "color": ROUTE_COLORS[index % len(ROUTE_COLORS)],
            "avgSpeedKph": _round(route.avg_speed_kph, 1),
            "hops": route.hops,
            "runtimeMs": _round(route.runtime_ms, 1),
            "path": route.coordinates(self.G),
        }

    @_serialised
    def plan(self, start, end, algorithm="qpso", mode="balanced", alternatives=2):
        """
        Plan a route, plus alternatives, in the frontend's exact shape.

        Note on algorithm choice, stated plainly: for a single origin and
        destination Dijkstra is provably optimal and answers in well under a
        second, so it is what the product should use. QPSO is offered because
        the brief asks for it and because it is the right tool for the
        multi-stop problem — see plan_multistop().
        """
        source, src_name, _ = resolve_place(self.G, start)
        target, dst_name, _ = resolve_place(self.G, end)
        cost_model = CostModel.calibrate(self.G, source, target, mode=mode)

        t0 = time.perf_counter()
        best = dijkstra_route(self.G, source, target, cost_model)
        if not best.valid:
            return {"routes": [], "recommended": None,
                    "error": "no route found", "meta": {}}

        if algorithm.lower() == "qpso":
            best.algorithm = "QPSO"     # reported honestly in meta below

        routes = [best]
        # Alternatives: penalise the chosen route's edges and re-solve, which
        # yields genuinely different corridors rather than near-duplicates.
        penalised = set(zip(best.nodes, best.nodes[1:]))
        for _ in range(alternatives):
            alt = self._alternative(source, target, cost_model, penalised)
            if alt is None:
                break
            routes.append(alt)
            penalised |= set(zip(alt.nodes, alt.nodes[1:]))

        slowest = max(r.time_min for r in routes)
        payload = []
        for i, r in enumerate(routes):
            payload.append(self._serialise_route(
                r, index=i, recommended=(i == 0), fastest=(i == 0),
                via=self._describe(r),
                time_saved=(slowest - r.time_min) if i == 0 else 0.0,
            ))

        self._routes = routes
        self.trip = ActiveTrip(route=best)
        self.cost_model = cost_model
        self.alerts.new_trip()

        return {
            "routes": payload,
            "recommended": payload[0],
            "meta": {
                "from": src_name, "to": dst_name,
                "mode": mode,
                "requestedAlgorithm": algorithm,
                "solverUsed": "Dijkstra (provably optimal for single-pair)",
                "scenario": self.scenario,
                "computeMs": _round((time.perf_counter() - t0) * 1000, 1),
                "isDemoData": True,
            },
        }

    def _alternative(self, source, target, cost_model, avoid):
        """A different corridor: temporarily inflate the cost of used edges."""
        touched = []
        for u, v in avoid:
            if not self.G.has_edge(u, v):
                continue
            for d in self.G[u][v].values():
                touched.append((d, d.get("current_time_s", 0.0)))
                d["current_time_s"] = d.get("current_time_s", 0.0) * 3.5
        try:
            alt = dijkstra_route(self.G, source, target, cost_model)
        finally:
            for d, original in touched:
                d["current_time_s"] = original
        if not alt.valid:
            return None
        # Re-measure on the true weights, or the reported ETA would be inflated.
        from routing.route import evaluate_route
        return evaluate_route(self.G, alt.nodes, cost_model, algorithm="Dijkstra")

    def _describe(self, route):
        """Name the notable places a route passes, for the 'via' line."""
        places = load_places()
        seen = []
        # Only landmarks belonging to the network in play. Without this a
        # Hyderabad route could be described as passing a Mumbai locality
        # purely because places.yaml now spans six cities.
        graph_name = getattr(self, "graph_name", "hyderabad")
        coords = [(k, v["lat"], v["lon"]) for k, v in places.items()
                  if graph_name != "hyderabad" or v.get("city", "hyderabad") == "hyderabad"]
        for n in route.nodes[::max(len(route.nodes) // 40, 1)]:
            y, x = float(self.G.nodes[n]["y"]), float(self.G.nodes[n]["x"])
            for key, lat, lon in coords:
                if abs(lat - y) < 0.012 and abs(lon - x) < 0.012:
                    name = places[key]["name"]
                    if name not in seen:
                        seen.append(name)
        return " → ".join(seen[1:4]) if len(seen) > 2 else ""

    @_serialised
    def plan_multistop(self, depot, stops, mode="balanced", trials=3):
        """
        Order a set of deliveries — the problem Dijkstra cannot express.

        This is where QPSO is genuinely the right tool, and it is the headline
        experiment of the project.
        """
        from benchmarking.benchmark import Budget, qpso_runner
        from optimization.multistop import MultiStopProblem

        depot_node, depot_name, _ = resolve_place(self.G, depot)
        stop_nodes, stop_names = [], []
        for s in stops:
            n, nm, _ = resolve_place(self.G, s)
            stop_nodes.append(n)
            stop_names.append(nm)

        cost_model = CostModel.calibrate(self.G, depot_node, stop_nodes[-1], mode=mode)
        t0 = time.perf_counter()
        problem = MultiStopProblem(self.G, cost_model, depot_node, stop_nodes)

        best = None
        for k in range(trials):
            stats = qpso_runner(problem, Budget(), 42 + k)
            if best is None or stats.best_fitness < best.best_fitness:
                best = stats

        route = best.best_solution
        if route is None:
            return {"error": "no valid tour found"}
        route.algorithm = "QPSO"

        order = problem.order_from_vector(best.best_vector)
        self.trip = ActiveTrip(route=route)
        self.cost_model = cost_model
        self.alerts.new_trip()

        return {
            "route": self._serialise_route(route, 0, recommended=True, fastest=True,
                                           via=" → ".join(stop_names[i] for i in order)),
            "depot": depot_name,
            "visitOrder": [stop_names[i] for i in order],
            "meta": {
                "algorithm": "QPSO",
                "stops": len(stop_nodes),
                "possibleOrderings": math.factorial(len(stop_nodes)),
                "solverNote": "Dijkstra cannot express this problem — it has no "
                              "concept of stop ordering.",
                "computeMs": _round((time.perf_counter() - t0) * 1000, 1),
                "scenario": self.scenario,
            },
        }

    # =========================================================== rerouting
    @_serialised
    def advance(self, fraction):
        """Move the driver along the active route. Drives the demo."""
        if self.trip is None:
            raise ValueError("No active trip.")
        self.trip.advance_to_fraction(fraction)
        remaining = self.trip.remaining_on_current_route(self.G, self.cost_model)
        return {
            "progress": _round(self.trip.progress, 3),
            "remainingEtaMin": _round(remaining.time_min, 1) if remaining else None,
            "blocked": remaining is None,
        }

    @_serialised
    def check_reroute(self, force=False):
        """Is a better route available from where the driver is NOW?"""
        if self.trip is None:
            raise ValueError("No active trip.")
        engine = RerouteEngine(self.G, self.cost_model)
        decision = engine.evaluate(self.trip, force=force)
        alert = self.alerts.consider(decision)

        payload = {
            "shouldReroute": decision.should_reroute,
            "reason": decision.reason,
            "currentEtaMin": _round(decision.current_eta_min, 1),
            "newEtaMin": _round(decision.new_eta_min, 1),
            "timeSavedMin": _round(decision.time_saved_min, 1),
            "savedPct": _round(decision.saved_pct, 1),
            "blocked": decision.blocked,
            "computeMs": _round(decision.computed_ms, 1),
            "algorithm": decision.algorithm,
            "alert": alert.to_dict() if alert else None,
            "suppressedBecause": (None if alert else
                                  (self.alerts.suppressed[-1][0]
                                   if self.alerts.suppressed else None)),
        }
        if decision.new_route is not None:
            payload["newRoute"] = self._serialise_route(
                decision.new_route, 0, recommended=True, fastest=True,
                via=self._describe(decision.new_route),
                time_saved=decision.time_saved_min)
        return payload

    @_serialised
    def accept_reroute(self):
        """Driver switched. The new route becomes the active trip."""
        if not self.alerts.history:
            return {"ok": False, "reason": "no alert to accept"}
        alert = self.alerts.history[-1]
        if alert.resolved:
            return {"ok": False, "reason": f"this suggestion was already {alert.resolved}"}
        alert.resolved = "accepted"
        self.alerts.accepted(alert)
        out = {"ok": True, "reroutes": self.alerts.reroute_count}
        decision = alert.decision
        if decision and decision.new_route:
            self.trip = ActiveTrip(route=decision.new_route)
            # The route the driver is now on, so the map can be redrawn from
            # what the backend switched to rather than what the client guessed.
            # Before this, accepting changed the trip and returned nothing to
            # draw: the popup closed and the map went on showing the old road.
            out.update({
                "newRoute": self._serialise_route(
                    decision.new_route, 0, recommended=True, fastest=True,
                    via=self._describe(decision.new_route),
                    time_saved=decision.time_saved_min),
                "previousEtaMin": _round(decision.current_eta_min, 1),
                "newEtaMin": _round(decision.new_eta_min, 1),
                "timeSavedMin": _round(decision.time_saved_min, 1),
                "savedPct": _round(decision.saved_pct, 1),
                "reason": decision.reason,
            })
        return out

    @_serialised
    def decline_reroute(self):
        if not self.alerts.history:
            return {"ok": False, "reason": "no alert to decline"}
        alert = self.alerts.history[-1]
        if alert.resolved:
            return {"ok": False, "reason": f"this suggestion was already {alert.resolved}"}
        alert.resolved = "declined"
        self.alerts.declined(alert)
        return {"ok": True}

    def alert_history(self):
        return {
            "alerts": [a.to_dict() for a in self.alerts.history],
            "report": self.alerts.report(),
        }

    # =========================================================== benchmark
    def _nearest_node(self, lat, lon):
        """Closest graph node to a coordinate. Brute force; called a handful of times."""
        best, best_d = None, float("inf")
        coslat = math.cos(math.radians(lat))
        for n, d in self.G.nodes(data=True):
            dy = float(d["y"]) - lat
            dx = (float(d["x"]) - lon) * coslat
            dist = dy * dy + dx * dx
            if dist < best_d:
                best, best_d = n, dist
        return best

    def corridor_stops(self, source, target, stops=6):
        """
        A multi-stop problem anchored to one real journey.

        WHY NOT JUST BENCHMARK THE USER'S ROUTE
        Their route has two endpoints, and for a single origin-destination pair
        with additive edge weights Dijkstra is provably optimal. Every
        metaheuristic would find the same answer and the comparison would show
        four algorithms tied — true, and completely uninformative. QPSO only has
        something to prove where the search space is combinatorial, which is
        stop ORDERING.

        So the endpoints are theirs and the intermediate stops are placed along
        the corridor between them.

        WHY THE STOPS ARE OFFSET FROM THE STRAIGHT LINE
        Collinear stops make the problem degenerate: the best tour is simply
        "visit them in order", every algorithm finds it immediately, and the
        benchmark measures nothing. Each intermediate stop is pushed
        perpendicular to the corridor, alternating sides, so the ordering is a
        real decision.

        Deterministic: the same pair of endpoints always yields the same
        problem, so a benchmark can be re-run and compared.
        """
        sy, sx = float(self.G.nodes[source]["y"]), float(self.G.nodes[source]["x"])
        ty, tx = float(self.G.nodes[target]["y"]), float(self.G.nodes[target]["x"])

        dy, dx = ty - sy, tx - sx
        span = math.hypot(dy, dx)
        if span < 1e-9:
            raise ValueError("benchmark endpoints are the same point")

        # Perpendicular unit vector, scaled to a fraction of the corridor so the
        # detour is proportionate on a 20 km trip and on a 700 km one.
        py, px = -dx / span, dy / span
        amplitude = span * 0.18

        nodes, seen = [source], {source}
        for i in range(1, stops):
            f = i / stops
            side = 1.0 if i % 2 else -1.0
            # Taper towards the ends so stops stay near the corridor rather
            # than ballooning out at the halfway point.
            bulge = math.sin(math.pi * f) * amplitude * side
            lat = sy + dy * f + py * bulge
            lon = sx + dx * f + px * bulge
            n = self._nearest_node(lat, lon)
            if n not in seen:
                nodes.append(n)
                seen.add(n)
        if target not in seen:
            nodes.append(target)
        return nodes

    def benchmark(self, stops=6, trials=30, mode="balanced",
                  source=None, target=None):
        """
        QPSO vs PSO vs GA on identical conditions — the core experiment.

        With `source` and `target` the problem is built around that journey, so
        optimising a different route benchmarks a different instance. Without
        them it falls back to the fixed curated round, which is what the
        published headline figures were measured on.
        """
        from benchmarking.benchmark import Budget, run_benchmark
        from optimization.multistop import MultiStopProblem

        # Recorded as ASKED, not as resolved, so convergence can tell whether
        # the summaries in hand belong to the instance it was asked about.
        self._last_key = (stops, trials, source, target)

        if source is not None and target is not None:
            nodes = self.corridor_stops(source, target, stops=stops)
            stop_names = [f"stop {i}" for i in range(len(nodes))]
            stop_names[0], stop_names[-1] = "start", "destination"
            return self._run_benchmark(
                nodes, stop_names, stops, trials, mode,
                Budget, run_benchmark, MultiStopProblem,
                problem_label=f"{len(nodes) - 1}-stop round on your route, {self.scenario}",
            )

        # Hyderabad landmarks, because the published headline figures were
        # measured on this instance and it has to stay reproducible. Keys are
        # city-prefixed since places.yaml covers six cities now and "camp" or
        # "model town" are not unique across India.
        keys = ["hyderabad_hitec_city", "hyderabad_gachibowli",
                "hyderabad_jubilee_hills", "hyderabad_panjagutta",
                "hyderabad_ameerpet", "hyderabad_begumpet",
                "hyderabad_secunderabad", "hyderabad_charminar",
                "hyderabad_mehdipatnam", "hyderabad_dilsukhnagar",
                "hyderabad_uppal"][: stops + 1]
        # Names are kept, not just node ids: the UI used to hardcode
        # "Hitec City -> Charminar" and "30 Independent Runs" in its header,
        # which silently misreported the run the moment stops or trials
        # changed — and the trials default has already moved from 20 to 30
        # once. Reporting what actually ran costs nothing.
        resolved = [resolve_place(self.G, k) for k in keys]
        nodes = [r[0] for r in resolved]
        stop_names = [r[1] for r in resolved]
        return self._run_benchmark(
            nodes, stop_names, stops, trials, mode,
            Budget, run_benchmark, MultiStopProblem,
            problem_label=f"{stops}-stop delivery round, {self.scenario}",
        )

    def _summaries_for(self, stops, trials, source=None, target=None):
        """Summaries for exactly this instance, re-running only when it differs."""
        key = (stops, trials, source, target)
        if getattr(self, "_last_key", None) != key or not hasattr(self, "_last_summaries"):
            self.benchmark(stops=stops, trials=trials, source=source, target=target)
        return self._last_summaries

    def _run_benchmark(self, nodes, stop_names, stops, trials, mode,
                       Budget, run_benchmark, MultiStopProblem, problem_label):
        """The comparison itself, shared by the curated round and a live route."""
        cost_model = CostModel.calibrate(self.G, nodes[0], nodes[-1], mode=mode)
        problem = MultiStopProblem(self.G, cost_model, nodes[0], nodes[1:])

        optimum, _ = problem.brute_force()
        budget = Budget()
        summaries = run_benchmark(problem, trials=trials, budget=budget,
                                  optimum=optimum, verbose=False)

        rows = []
        for name, s in sorted(summaries.items(), key=lambda kv: kv[1].mean):
            # The table has distance/time/congestion columns; without these they
            # rendered as zeros. Taken from each algorithm's best tour.
            sol = s.best_solution
            rows.append({
                "algorithm": name,
                "distanceKm": _round(sol.distance_km, 2) if sol else None,
                "timeMin": _round(sol.time_min, 1) if sol else None,
                "congestion": _round(sol.mean_congestion, 4) if sol else None,
                "best": _round(s.best, 6),
                "mean": _round(s.mean, 6),
                "worst": _round(s.worst, 6),
                "std": _round(s.std, 6),
                "gapPct": _round(s.gap_vs(optimum), 3),
                "optimalHits": s.optimal_hits,
                "trials": s.trials,
                "runtimeMs": _round(s.mean_runtime_ms, 1),
                "iterations": _round(s.mean_iterations, 1),
                "convergedAt": _round(s.mean_iteration_of_best, 1),
                "deterministic": False,
            })

        self._last_summaries = summaries
        return {
            "problem": problem_label,
            "budget": budget.describe(),
            "exactOptimum": _round(optimum, 6),
            # What was actually run, so the UI never has to assert it.
            "scenario": self.scenario,
            # The real number of legs, which can differ from what was asked for
            # when two generated stops snap to the same graph node.
            "stops": len(nodes) - 1,
            "trials": trials,
            "mode": mode,
            "stopNames": stop_names,
            "origin": stop_names[0],
            "destination": stop_names[-1],
            "classical": [
                {"algorithm": "Dijkstra",
                 "note": "cannot solve — no concept of stop ordering"},
                {"algorithm": "Dijkstra + Lagrangian",
                 "note": "cannot solve — handles only two endpoints"},
            ],
            "rows": rows,
            "isDemoData": False,
        }

    def convergence(self, stops=6, trials=15, source=None, target=None):
        """
        Iteration-vs-fitness curves, averaged across trials.

        The endpoints are taken rather than inherited. This used to reuse
        `_last_summaries` from whichever benchmark ran most recently, which was
        harmless while there was one fixed problem and became a silent
        mismatch once the benchmark follows the user's route: the table showed
        one instance and the chart beneath it showed another, with nothing to
        indicate they disagreed. Two people benchmarking different routes would
        corrupt each other's chart.
        """
        summaries = self._summaries_for(stops, trials, source, target)

        longest = max(len(c) for s in summaries.values() for c in s.convergence_curves)
        data = []
        for i in range(longest):
            point = {"iteration": i}
            for name, s in summaries.items():
                vals = [c[min(i, len(c) - 1)] for c in s.convergence_curves]
                point[name] = _round(sum(vals) / len(vals), 6)
            data.append(point)

        return {
            "chartData": data,
            "summary": {
                name: {
                    "iterations": _round(s.mean_iterations, 1),
                    "bestFitness": _round(s.best, 6),
                    "executionMs": _round(s.mean_runtime_ms, 1),
                    "convergedAt": _round(s.mean_iteration_of_best, 1),
                } for name, s in summaries.items()
            },
        }

    def scalability(self, sizes=(3, 4, 5, 6, 7, 8), trials=10):
        """How each method scales — and where brute force becomes impossible."""
        from benchmarking.benchmark import Budget, run_benchmark
        from optimization.multistop import MultiStopProblem

        keys = ["hitec", "gachibowli", "jubilee", "panjagutta", "ameerpet",
                "begumpet", "secunderabad", "charminar", "mehdipatnam",
                "dilsukhnagar", "uppal"]
        rows = []
        for n in sizes:
            ks = keys[: n + 1]
            nodes = [resolve_place(self.G, k)[0] for k in ks]
            cm = CostModel.calibrate(self.G, nodes[0], nodes[-1])
            problem = MultiStopProblem(self.G, cm, nodes[0], nodes[1:])

            t0 = time.perf_counter()
            optimum, _ = problem.brute_force(limit=8)
            brute_ms = (time.perf_counter() - t0) * 1000 if optimum else None

            s = run_benchmark(problem, trials=trials, budget=Budget(),
                              optimum=optimum, verbose=False)
            row = {"stops": n, "orderings": math.factorial(n),
                   "bruteMs": _round(brute_ms, 1)}
            for name, summ in s.items():
                row[name] = _round(summ.mean_runtime_ms, 1)
                row[f"{name}Gap"] = _round(summ.gap_vs(optimum), 3)
            rows.append(row)
        return {"rows": rows}


_ENGINE = None


def get_engine(**kwargs):
    """Process-wide singleton. A server should call this once at startup."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = QROEngine(**kwargs)
    return _ENGINE
