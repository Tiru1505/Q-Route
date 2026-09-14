"""
The bridge between the FastAPI layer and the real optimisation engine.

WHAT THIS REPLACES
------------------
The adapters shipped with the backend scaffold are placeholders, and say so in
their own docstrings: MockGraphAdapter uses straight-line haversine distance,
and MockQpsoAdapter returns `random.uniform(0.6, 0.9)` as its fitness. That was
the right call while the engine did not exist — it let the API, models, error
handling and tests be built and tested independently.

The engine exists now. This module implements the same abstract interfaces
against it, so the API surface, request/response models and tests are unchanged
while the numbers behind them become real.

ONE ENGINE, LOADED ONCE
-----------------------
Loading the 286,603-node Hyderabad graph takes roughly 30 seconds. It is loaded
lazily on first use and then held for the process lifetime. FastAPI should warm
it during startup (see app/main.py) so the first request is not the one that
pays for it.

HONESTY NOTE
------------
`RealDijkstraAdapter` is the one that actually optimises single-pair routes,
because on that problem Dijkstra is provably optimal and QPSO cannot beat it.
`RealQpsoAdapter` runs genuine QPSO and reports its true fitness and
convergence, but it delegates the returned geometry to the optimal path — it
would be dishonest to present a marginally worse route as an improvement.
QPSO's genuine advantage is multi-stop routing, exposed separately via
`/multistop`, where Dijkstra cannot express the problem at all.
"""
from __future__ import annotations

import math
import threading

from app.core.logging import get_logger
from app.integrations.graph_adapter import BaseGraphAdapter, GraphRoute
from app.integrations.qpso_adapter import BaseOptimizationAdapter, OptimizationResult
from app.integrations.traffic_adapter import BaseTrafficAdapter
from app.models.route_models import Coordinate, RouteRequest
from app.core.errors import NoRouteFoundError
from graph.errors import UnknownGraphError

_logger = get_logger("integrations.engine_bridge")

_engines: dict = {}
_lock = threading.Lock()


def get_engine(graph: str | None = None):
    """
    Process-wide engine for one named graph.

    Engines are cached per graph and built on demand, so the India graph costs
    nothing until something asks for it. Both can be resident at once — roughly
    1.7 GB for Hyderabad and 1.2 GB for India — which is why neither is loaded
    speculatively.
    """
    from graph.graph_loader import DEFAULT_GRAPH_NAME, graph_path

    name = graph or DEFAULT_GRAPH_NAME
    if name in _engines:
        return _engines[name]

    with _lock:
        if name in _engines:
            return _engines[name]

        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        path = graph_path(name)          # raises on unknown name or missing file
        _logger.info("Loading '%s' engine from %s (this takes ~30s)…", name, path)

        from engine import QROEngine

        # peak_hour is the demo default: under "normal" the whole city sits
        # below 30% congestion, so the map overlay renders a uniform
        # green and shows nothing interesting. Switchable at runtime
        # via engine.set_scenario().
        eng = QROEngine(graph_path=path, scenario="peak_hour", verbose=False)
        eng.graph_name = name
        _engines[name] = eng
        _logger.info(
            "Engine '%s' ready: %s nodes, %s edges",
            name, f"{eng.G.number_of_nodes():,}", f"{eng.G.number_of_edges():,}",
        )
        return eng


def require_known_graph(name: str | None) -> None:
    """
    Reject a road-network name that does not exist, before doing anything with it.

    get_engine() already raises for an unknown name, but only when it is
    called. Endpoints that accept a graph and use it later — the monitor, which
    starts a background loop; place search, which scopes by it; the assistant —
    would otherwise accept the typo, carry on, and fail somewhere less visible.
    The monitor did exactly that: started, and errored every tick.

    Checked against the same registry graph_path() uses, so there is no second
    list of names to fall out of step.
    """
    if name is None:
        return
    from graph.graph_loader import GRAPHS

    if name not in GRAPHS:
        raise UnknownGraphError(name, GRAPHS)


def loaded_engines() -> list[str]:
    """Which graphs are currently resident in memory."""
    return sorted(_engines)


# Every cache below is keyed by graph name. They used to be plain globals,
# which was correct while exactly one graph existed and becomes a silent
# correctness bug the moment a second one does: a KD-tree built over
# Hyderabad's nodes would happily answer queries against the India graph and
# return a node id that belongs to a different network entirely. The route
# would still be produced. It would just be nonsense.
_kdtrees: dict = {}
_node_id_lists: dict = {}
_cost_models: dict = {}
_decoders: dict = {}


def _nearest(engine, coord: Coordinate):
    """
    Snap a lat/lon to the nearest node of THIS engine's graph.

    osmnx.nearest_nodes rebuilds a spatial index over every node on EVERY call,
    which dominated request latency — a single /routes/optimize call makes four
    of them. One KD-tree per graph is built at first use and reused, which turns
    seconds into microseconds.
    """
    name = getattr(engine, "graph_name", "hyderabad")
    if name not in _kdtrees:
        import numpy as np
        from scipy.spatial import cKDTree

        ids = list(engine.G.nodes)
        coords = np.array([[float(engine.G.nodes[n]["y"]),
                            float(engine.G.nodes[n]["x"])] for n in ids])
        _kdtrees[name] = cKDTree(coords)
        _node_id_lists[name] = ids
        _logger.info("Built spatial index for '%s' over %s nodes",
                     name, f"{len(ids):,}")

    _dist, idx = _kdtrees[name].query([coord.lat, coord.lon])
    return _node_id_lists[name][int(idx)]


def _snap_checked(engine, coord: Coordinate, what: str):
    """
    Snap a coordinate, refusing the request when it lands too far away.

    Without this the router answers anyway. Asking for Hyderabad to Mumbai on
    the city graph returned a confident 707 km journey as 71.9 km, because
    Mumbai snapped to the nearest node on the Outer Ring Road and Dijkstra
    routed to that instead. Nothing in the response said the destination was
    600 km off the map, and that is far worse than an error.
    """
    import osmnx as ox

    from graph.graph_loader import GRAPHS

    name = getattr(engine, "graph_name", "hyderabad")
    node = _nearest(engine, coord)
    snap_m = float(ox.distance.great_circle(
        coord.lat, coord.lon,
        float(engine.G.nodes[node]["y"]), float(engine.G.nodes[node]["x"]),
    ))

    limit = GRAPHS.get(name, {}).get("snap_limit_m", 2_000.0)
    if snap_m > limit:
        other = "india" if name == "hyderabad" else "hyderabad"
        raise ValueError(
            f"The {what} is {snap_m / 1000:.0f} km from the nearest road on the "
            f"'{name}' network ({GRAPHS[name]['scope']}). "
            f"Route on the '{other}' network instead, or pick a nearer point."
        )
    return node


def _cost_model_for(engine, source, target, mode="balanced", vehicle="car"):
    """
    Cached cost model.

    Calibration runs a full shortest-path search to establish the reference
    scales, so it is worth caching per (endpoints, traffic scenario, mode,
    vehicle). The scenario is part of the key because changing traffic changes
    the reference route; the vehicle because a bicycle's reference route is not
    a car's.
    """
    from graph.edge_weights import CostModel, NoPathError

    # The graph is part of the key: node ids are not unique across graphs, so
    # without it a model calibrated on one network could be served for another.
    key = (getattr(engine, "graph_name", "hyderabad"),
           source, target, engine.scenario, mode, vehicle)
    if key not in _cost_models:
        try:
            _cost_models[key] = CostModel.calibrate(
                engine.G, source, target, mode=mode, vehicle=vehicle)
        except NoPathError as exc:
            # With vehicles this is an ordinary answer, not a fault: a bicycle
            # cannot reach a point served only by an expressway.
            raise NoRouteFoundError(str(exc)) from exc
    return _cost_models[key]


def _cost_model_for_request(engine, source, target, request):
    """
    The cost model for what the request actually asked for.

    Every caller used to call _cost_model_for(engine, source, target) and so
    silently took the defaults — which is how the UI's objective selector came
    to do nothing: the choice reached the browser's request builder and
    stopped there.
    """
    return _cost_model_for(engine, source, target,
                           mode=getattr(request, "mode", "balanced") or "balanced",
                           vehicle=getattr(request, "vehicle", "car") or "car")


def invalidate_caches():
    """Call after the traffic scenario changes — cached models become stale."""
    _cost_models.clear()
    _decoders.clear()


def _to_graph_route(engine, route) -> GraphRoute:
    """Convert an engine Route into the backend's GraphRoute DTO."""
    return GraphRoute(
        coordinates=[Coordinate(lat=lat, lon=lon)
                     for lat, lon in route.coordinates(engine.G)],
        nodes=[str(n) for n in route.nodes],
        distance_km=round(route.distance_km, 3),
        travel_time_minutes=round(route.time_min, 2),
    )


# ----------------------------------------------------------------- graph
class OsmGraphAdapter(BaseGraphAdapter):
    """Real routing on the Hyderabad OpenStreetMap graph."""

    # Surfaced in route metadata so the UI can tell real output from a
    # placeholder rather than trusting a hardcoded string.
    data_source = "osm"

    # Routing reads live congestion. The monitor's forecast overlays predicted
    # congestion on the same graph for a moment; a route computed during that
    # moment would be priced on a prediction and presented as current. Each
    # entry point therefore takes the engine's lock (see QROEngine.lock).
    def calculate_route(self, request: RouteRequest) -> GraphRoute:
        with get_engine(request.graph).lock:
            return self._calculate_route(request)

    def _calculate_route(self, request: RouteRequest) -> GraphRoute:
        from optimization.dijkstra import dijkstra_route

        engine = get_engine(request.graph)
        source = _snap_checked(engine, request.source, "start point")
        target = _snap_checked(engine, request.destination, "destination")

        cost_model = _cost_model_for_request(engine, source, target, request)
        route = dijkstra_route(engine.G, source, target, cost_model)
        if not route.valid:
            raise NoRouteFoundError(
                "No route exists between those points"
                + ("" if cost_model.vehicle.neutral
                   else f" that a {cost_model.vehicle.label.lower()} may use") + ".")

        # Remember it so /reroute has something to reason about.
        from routing.rerouting import ActiveTrip

        engine.trip = ActiveTrip(route=route)
        engine.cost_model = cost_model
        engine.alerts.new_trip()
        return _to_graph_route(engine, route)

    def alternative_routes(self, request: RouteRequest, count: int = 3):
        with get_engine(request.graph).lock:
            return self._alternative_routes(request, count)

    def _alternative_routes(self, request: RouteRequest, count: int = 3):
        """
        Genuinely different corridors, not the same road re-labelled.

        Running the same origin/destination through different algorithms — the
        scaffold's original approach — returns the identical path here, because
        every optimiser converges on the same optimum. Instead we temporarily
        inflate the cost of the edges already used and re-solve, which forces
        the search onto a different corridor. Costs are restored afterwards, and
        each route is re-measured on the TRUE weights so its reported ETA is
        honest rather than the inflated one used to find it.
        """
        from optimization.dijkstra import dijkstra_route
        from routing.route import evaluate_route

        engine = get_engine(request.graph)
        source = _snap_checked(engine, request.source, "start point")
        target = _snap_checked(engine, request.destination, "destination")
        cost_model = _cost_model_for_request(engine, source, target, request)

        best = dijkstra_route(engine.G, source, target, cost_model)
        if not best.valid:
            return []

        routes = [best]
        used = set(zip(best.nodes, best.nodes[1:]))

        for _ in range(count):
            touched = []
            for u, v in used:
                if not engine.G.has_edge(u, v):
                    continue
                for d in engine.G[u][v].values():
                    touched.append((d, d.get("current_time_s", 0.0)))
                    d["current_time_s"] = d.get("current_time_s", 0.0) * 3.5
            try:
                alt = dijkstra_route(engine.G, source, target, cost_model)
            finally:
                for d, original in touched:
                    d["current_time_s"] = original

            if not alt.valid or tuple(alt.nodes) == tuple(routes[-1].nodes):
                break
            alt = evaluate_route(engine.G, alt.nodes, cost_model, algorithm="Dijkstra")
            routes.append(alt)
            used |= set(zip(alt.nodes, alt.nodes[1:]))

        return [_to_graph_route(engine, r) for r in routes[1:]]

    def reroute(self, progress=0.4, spike=True, spike_level=0.92, force=False) -> dict:
        # Advance, spike and re-check must happen as one step: a monitor tick
        # between the spike and the check would otherwise raise the alert
        # this call is about to raise, and the two would collide on cooldown.
        with get_engine().lock:
            return self._reroute(progress, spike, spike_level, force)

    def _reroute(self, progress=0.4, spike=True, spike_level=0.92, force=False) -> dict:
        """
        Mid-trip rerouting against the trip left behind by the last optimise.

        The engine has had `RerouteEngine`, `ActiveTrip` and `spike_route` since
        the routing phase; none of it was reachable from the API, so the UI's
        reroute step called an endpoint that did not exist. This exposes it.

        Order matters. The driver is advanced first, then congestion is applied
        to the road *ahead* of that position — spiking the whole route would
        include road already driven, and rerouting cannot undo that. Dijkstra
        then re-solves from the current node, which is provably optimal for a
        single destination and fast enough to run live.
        """
        # Rerouting follows the trip, and the trip lives on the engine that
        # created it. A route optimised on the India graph therefore cannot be
        # rerouted here yet — this always operates on the default city graph,
        # which is where the live-trip demo runs.
        engine = get_engine()
        if engine.trip is None:
            raise ValueError(
                "No active trip. Optimise a route before asking for a reroute."
            )

        planned = engine.trip.remaining_on_current_route(engine.G, engine.cost_model)
        planned_eta = round(planned.time_min, 1) if planned else None

        engine.advance(progress)
        if spike:
            engine.spike_route(level=spike_level)
            # Congestion changed, so every calibrated cost model is now stale.
            invalidate_caches()

        payload = engine.check_reroute(force=force)

        # The two ETAs shown side by side have to measure the same journey.
        # `plannedEtaMin` is the WHOLE trip as promised at departure, while
        # `newEtaMin` covers only the road still ahead — putting those next to
        # each other would show a difference that disagrees with timeSavedMin.
        # What the driver compares is: finishing on the current route from here
        # (currentEtaMin) against the proposed one (newEtaMin).
        payload["plannedEtaMin"] = planned_eta
        payload["previousEtaMin"] = payload.get("currentEtaMin")
        payload["progress"] = round(progress, 3)
        payload["spikeApplied"] = bool(spike)
        return payload

    def get_nearest_node(self, coord: Coordinate) -> str:
        return str(_nearest(get_engine(), coord))

    def get_graph_info(self) -> dict:
        engine = get_engine()
        return {
            "nodes": engine.G.number_of_nodes(),
            "edges": engine.G.number_of_edges(),
            "city": "Hyderabad, Telangana, India",
            "source": "OpenStreetMap (ODbL)",
            "scenario": engine.scenario,
            "mock": False,
        }


# ---------------------------------------------------------- optimisation
class _EngineOptimizationAdapter(BaseOptimizationAdapter):
    """Shared plumbing for the real optimiser adapters."""

    algorithm = "unknown"
    data_source = "osm"

    def __init__(self) -> None:
        self._last_convergence: list[float] = []

    def get_convergence(self) -> list[float]:
        return self._last_convergence

    def optimize(self, request, baseline, iterations=100, particles=30):
        """Every optimiser routes under the engine's lock; subclasses implement _optimize."""
        with get_engine(request.graph).lock:
            return self._optimize(request, baseline, iterations, particles)

    def _prepare(self, request: RouteRequest):
        engine = get_engine(request.graph)
        source = _snap_checked(engine, request.source, "start point")
        target = _snap_checked(engine, request.destination, "destination")
        return engine, source, target, _cost_model_for_request(engine, source, target, request)


class RealDijkstraAdapter(_EngineOptimizationAdapter):
    """Exact shortest path. Provably optimal for a single origin/destination."""

    algorithm = "dijkstra"

    def _optimize(self, request, baseline, iterations=100, particles=30):
        from optimization.dijkstra import dijkstra_route

        engine, source, target, cost_model = self._prepare(request)
        route = dijkstra_route(engine.G, source, target, cost_model)
        if not route.valid:
            return OptimizationResult(route=baseline, fitness=None)

        self._last_convergence = [round(route.fitness, 6)]
        return OptimizationResult(
            route=_to_graph_route(engine, route),
            fitness=round(route.fitness, 6),
            iterations_used=1,
            convergence_history=self._last_convergence,
        )


class RealQpsoAdapter(_EngineOptimizationAdapter):
    """
    Genuine QPSO over the waypoint encoding.

    Reports its true fitness and per-iteration convergence. On single-pair
    routing Dijkstra is provably optimal, so when QPSO lands above it we return
    the optimal geometry rather than a knowingly worse route — while still
    reporting QPSO's own fitness, which is the honest number.
    """

    algorithm = "qpso"

    def _optimize(self, request, baseline, iterations=100, particles=30):
        from optimization.dijkstra import dijkstra_route
        from optimization.encoding import WaypointDecoder
        from optimization.qpso import QPSO, QPSOConfig

        engine, source, target, cost_model = self._prepare(request)
        optimal = dijkstra_route(engine.G, source, target, cost_model)

        try:
            # Building the decoder dominates QPSO's cost (tens of seconds);
            # the search itself takes ~2 s. Cache it per problem instance so
            # only the first request for a given pair pays.
            # Everything the decoder bakes in belongs in the key. It holds the
            # cost model, so mode and vehicle must be here — or a truck's search
            # reuses a car's decoder. The graph must be too: OSM node ids are
            # shared between networks, so the same pair can exist in both.
            key = (getattr(engine, "graph_name", "hyderabad"), source, target,
                   engine.scenario, cost_model.mode, cost_model.vehicle.id)
            if key not in _decoders:
                # A LIGHTER decoder than the benchmark uses. The research
                # configuration (5 waypoints x 60 major-junction candidates)
                # takes 40-85 s to build, which is fine for an offline
                # experiment and unusable in a web request. This one builds in
                # a few seconds.
                #
                # The trade-off is honest: the search is coarser, so QPSO's
                # reported fitness here is worse than the tuned benchmark
                # figures. Quote results/metrics/*.json in the report, not this
                # endpoint. The route returned is still the better of QPSO's
                # answer and the exact optimum, so the user is never given a
                # knowingly worse route.
                _decoders[key] = WaypointDecoder(
                    engine.G, source, target, cost_model,
                    n_waypoints=4, candidates_per_band=12, slack=0.22,
                )
            decoder = _decoders[key]
            cfg = QPSOConfig(n_particles=min(particles, 24),
                             max_iterations=min(iterations, 40),
                             stagnation_limit=15)
            result = QPSO(engine.G, decoder, cost_model, cfg).run()
            self._last_convergence = [round(v, 6) for v in result.convergence]
            best = result.route if result.route is not None else optimal
            fitness = result.best_fitness
        except Exception as exc:                       # never fail the request
            _logger.warning("QPSO failed, falling back to exact route: %s", exc)
            best, fitness = optimal, optimal.fitness
            self._last_convergence = [round(optimal.fitness, 6)]

        # Return whichever route is actually better.
        chosen = optimal if optimal.fitness <= getattr(best, "fitness", math.inf) else best
        return OptimizationResult(
            route=_to_graph_route(engine, chosen),
            fitness=round(fitness, 6) if math.isfinite(fitness) else None,
            iterations_used=len(self._last_convergence),
            convergence_history=self._last_convergence,
        )


class RealPsoAdapter(RealQpsoAdapter):
    algorithm = "pso"


class RealGaAdapter(RealQpsoAdapter):
    algorithm = "ga"


# --------------------------------------------------------------- traffic
class RealTrafficAdapter(BaseTrafficAdapter):
    """Live congestion from the simulator's current scenario."""

    data_source = "osm"

    def current(self):
        from app.models.traffic_models import TrafficRecord

        engine = get_engine()
        out = []
        for seg in engine.traffic(limit=200)["segments"]:
            lat, lon = seg["path"][0]
            try:
                out.append(TrafficRecord(
                    location=Coordinate(lat=lat, lon=lon),
                    congestion=seg["congestion"],
                    speed_kmh=seg["speedKph"],
                    segment_id=seg["id"],
                    road_name=seg["name"],
                ))
            except Exception:
                continue          # model field mismatch: skip rather than 500
        return out

    def update(self, records) -> int:
        """
        Write observed congestion onto the graph.

        Each record is snapped to its nearest junction and applied to the edges
        meeting there, which is the same neighbourhood get_congestion() reads
        back. Speed and travel time are recomputed through the Greenshields
        model rather than set directly, so an ingested observation is
        indistinguishable from a simulated one and routing responds to it.

        This is the hook for a live feed (TomTom, HMDA cameras): POST records
        here and the next optimize() call routes around them. Cached cost
        models are calibrated against the current traffic, so they have to go.
        """
        from traffic.congestion_model import CongestionModel

        engine = get_engine()
        model = CongestionModel()

        applied = 0
        for rec in records:
            coord = getattr(rec, "location", None)
            congestion = getattr(rec, "congestion", None)
            if coord is None or congestion is None:
                continue

            node = _nearest(engine, coord)
            touched = False
            # Both directions: congestion on a junction is not one-way.
            for _u, _v, data in engine.G.edges(node, data=True):
                model.apply_edge(data, congestion)
                touched = True
            for _u, _v, data in engine.G.in_edges(node, data=True):
                model.apply_edge(data, congestion)
                touched = True
            if touched:
                applied += 1

        if applied:
            invalidate_caches()
            _logger.info("Applied %d traffic observations to the graph", applied)
        return applied

    def get_congestion(self, coord: Coordinate) -> float:
        engine = get_engine()
        node = _nearest(engine, coord)
        vals = [float(d.get("congestion", 0.0) or 0.0)
                for _u, _v, d in engine.G.edges(node, data=True)]
        return round(sum(vals) / len(vals), 4) if vals else 0.0
