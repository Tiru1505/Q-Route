"""
Dynamic rerouting — noticing that the plan has gone stale, and fixing it.

THE POINT MOST IMPLEMENTATIONS MISS
-----------------------------------
You cannot reroute a journey from its origin. If the driver is 40% of the way
along, that 40% is already behind them; the only thing still decidable is the
road ahead. So the comparison that matters is:

    remaining time on the CURRENT route, under the NEW traffic
        vs
    time on the BEST route from where the driver is NOW

Comparing full-journey times instead would credit the reroute with savings on
road already travelled, and would happily suggest a "better" route that starts
back at the depot.

WHAT TRIGGERS A RECOMPUTE
-------------------------
Not every change. Recomputing on every traffic tick is wasteful and, worse,
makes the route flap between near-identical options. We recompute when the
remaining journey has degraded materially against what was promised — the
`degradation_threshold`. Everything downstream (whether to actually tell the
driver) is the alert engine's job, deliberately kept separate: this module
decides what is TRUE, the alert engine decides what is WORTH SAYING.

WHICH OPTIMISER
---------------
Single destination -> Dijkstra. It is provably optimal for that problem and
responds in under a second, which is what live rerouting needs. Using a
metaheuristic there would be slower and no better, and claiming otherwise would
be dishonest.

Multiple remaining stops -> QPSO. Re-optimising the ORDER of the stops that are
still outstanding is the NP-hard problem from Phase 6, and it is where QPSO
genuinely earns its place. This is the case worth demonstrating.
"""
import math
import time
from dataclasses import dataclass, field

from graph.edge_weights import edge_components, is_closed
from routing.route import Route, evaluate_route


@dataclass
class ActiveTrip:
    """A journey in progress: the planned route plus how far along it we are."""

    route: Route
    position: int = 0              # index into route.nodes of the current location
    planned_time_s: float = 0.0    # ETA promised when the route was issued
    started_at: float = field(default_factory=time.time)
    remaining_stops: list = field(default_factory=list)   # multi-stop only

    def __post_init__(self):
        if not self.planned_time_s:
            self.planned_time_s = self.route.time_s

    @property
    def current_node(self):
        return self.route.nodes[min(self.position, len(self.route.nodes) - 1)]

    @property
    def destination(self):
        return self.route.nodes[-1]

    @property
    def remaining_nodes(self):
        return self.route.nodes[self.position:]

    @property
    def progress(self):
        n = max(len(self.route.nodes) - 1, 1)
        return min(self.position / n, 1.0)

    def advance_to_fraction(self, fraction):
        """Move the driver along the planned route. Used to stage the demo."""
        self.position = int(min(max(fraction, 0.0), 1.0) * (len(self.route.nodes) - 1))
        return self

    def stops_ahead(self, stop_nodes):
        """
        Which of the planned stops are still outstanding.

        Necessary, and easy to get wrong: re-optimising over every stop would
        send the van back to deliveries it has already made. A stop counts as
        done once the driver has passed its position in the planned route.
        """
        ahead = []
        for stop in stop_nodes:
            try:
                idx = self.route.nodes.index(stop)
            except ValueError:
                ahead.append(stop)          # not on the planned path at all
                continue
            if idx > self.position:
                ahead.append(stop)
        return ahead

    def remaining_on_current_route(self, G, cost_model):
        """
        Cost of finishing on the CURRENT route under whatever traffic exists now.

        Returns None if the road ahead has since been closed — which is itself a
        reason to reroute, and one the caller must handle.
        """
        nodes = self.remaining_nodes
        if len(nodes) < 2:
            return Route(nodes=nodes, algorithm="current (arrived)", valid=True)

        for u, v in zip(nodes, nodes[1:]):
            if not G.has_edge(u, v):
                return None
            if all(is_closed(d) for d in G[u][v].values()):
                return None

        return evaluate_route(G, nodes, cost_model, algorithm="current route")


@dataclass
class RerouteDecision:
    """The factual comparison. Whether to SAY anything is decided elsewhere."""

    should_reroute: bool = False
    reason: str = ""
    current_route: Route = None          # remaining portion of the current plan
    new_route: Route = None              # proposed replacement, from here on
    current_eta_min: float = 0.0
    new_eta_min: float = 0.0
    time_saved_min: float = 0.0
    saved_pct: float = 0.0
    degradation_pct: float = 0.0         # how much worse than originally promised
    blocked: bool = False                # road ahead is closed
    computed_ms: float = 0.0
    algorithm: str = ""
    stop_order_changed: bool = False

    def summary(self):
        if not self.should_reroute:
            return f"no reroute — {self.reason}"
        return (f"reroute via {self.algorithm}: {self.current_eta_min:.1f} -> "
                f"{self.new_eta_min:.1f} min "
                f"(saves {self.time_saved_min:.1f} min, {self.saved_pct:.0f}%)")


class RerouteEngine:
    """
    Watches a trip and decides whether a better route now exists.

    degradation_threshold  recompute once the remaining journey is this much
                           worse than promised (0.15 = 15%). Below it we do not
                           even look, which keeps the system quiet under normal
                           traffic noise.
    min_improvement        ignore a new route that is not at least this much
                           better. Prevents flapping between near-identical
                           options whose ranking flips on rounding.
    """

    def __init__(self, G, cost_model, degradation_threshold=0.15,
                 min_improvement=0.05):
        self.G = G
        self.cost_model = cost_model
        self.degradation_threshold = degradation_threshold
        self.min_improvement = min_improvement

    # ------------------------------------------------------------ single
    def evaluate(self, trip, force=False):
        """Single-destination rerouting, using Dijkstra from the current node."""
        from optimization.dijkstra import dijkstra_route

        t0 = time.perf_counter()
        decision = RerouteDecision(algorithm="Dijkstra")

        current = trip.remaining_on_current_route(self.G, self.cost_model)

        # Road ahead closed: reroute unconditionally, there is no choice.
        if current is None:
            decision.blocked = True
            new = dijkstra_route(self.G, trip.current_node, trip.destination,
                                 self.cost_model)
            decision.new_route = new if new.valid else None
            decision.should_reroute = new.valid
            decision.reason = ("road ahead is closed" if new.valid
                               else "road ahead closed and no alternative exists")
            decision.new_eta_min = new.time_min if new.valid else math.inf
            decision.computed_ms = (time.perf_counter() - t0) * 1000
            return decision

        decision.current_route = current
        decision.current_eta_min = current.time_min

        # How much worse is the rest of the trip than when we promised it?
        promised_remaining = trip.planned_time_s * (1.0 - trip.progress)
        if promised_remaining > 0:
            decision.degradation_pct = (current.time_s / promised_remaining - 1) * 100

        if not force and decision.degradation_pct < self.degradation_threshold * 100:
            decision.reason = (f"remaining journey only "
                               f"{decision.degradation_pct:+.1f}% off plan")
            decision.computed_ms = (time.perf_counter() - t0) * 1000
            return decision

        new = dijkstra_route(self.G, trip.current_node, trip.destination,
                             self.cost_model)
        if not new.valid:
            decision.reason = "no alternative route found"
            decision.computed_ms = (time.perf_counter() - t0) * 1000
            return decision

        decision.new_route = new
        decision.new_eta_min = new.time_min
        decision.time_saved_min = current.time_min - new.time_min
        if current.time_min > 0:
            decision.saved_pct = decision.time_saved_min / current.time_min * 100

        if decision.time_saved_min <= 0:
            decision.reason = "current route is still the best available"
        elif decision.saved_pct < self.min_improvement * 100:
            decision.reason = (f"alternative only {decision.saved_pct:.1f}% better "
                               f"— not worth switching")
        else:
            decision.should_reroute = True
            decision.reason = (f"congestion ahead: remaining journey is "
                               f"{decision.degradation_pct:+.0f}% off plan")

        decision.computed_ms = (time.perf_counter() - t0) * 1000
        return decision

    # -------------------------------------------------------- multi-stop
    def evaluate_multistop(self, trip, remaining_stop_nodes, trials=3, force=False):
        """
        Re-optimise the ORDER of the stops still outstanding, using QPSO.

        This is the case that justifies the project's algorithm. Traffic has
        changed, so the sequence that was best when the van left the depot may
        no longer be — and finding the new best order is the NP-hard problem
        from Phase 6, which Dijkstra cannot express.
        """
        from benchmarking.benchmark import Budget, qpso_runner
        from optimization.multistop import MultiStopProblem

        t0 = time.perf_counter()
        decision = RerouteDecision(algorithm="QPSO")

        if len(remaining_stop_nodes) < 2:
            decision.reason = "fewer than two stops remain — nothing to reorder"
            return decision

        current = trip.remaining_on_current_route(self.G, self.cost_model)
        decision.current_route = current
        decision.current_eta_min = current.time_min if current else math.inf
        decision.blocked = current is None

        problem = MultiStopProblem(self.G, self.cost_model, trip.current_node,
                                   remaining_stop_nodes)
        if not problem.matrix.complete():
            decision.reason = "some remaining stops are unreachable"
            return decision

        budget = Budget()
        best = None
        for k in range(trials):
            stats = qpso_runner(problem, budget, 4242 + k)
            if best is None or stats.best_fitness < best.best_fitness:
                best = stats

        new = best.best_solution
        if new is None:
            decision.reason = "optimiser found no valid tour"
            return decision

        new.algorithm = "QPSO (re-ordered)"
        decision.new_route = new
        decision.new_eta_min = new.time_min

        if current is not None:
            decision.time_saved_min = current.time_min - new.time_min
            if current.time_min > 0:
                decision.saved_pct = decision.time_saved_min / current.time_min * 100
            decision.stop_order_changed = tuple(new.nodes) != tuple(current.nodes)

        if decision.blocked:
            decision.should_reroute = True
            decision.reason = "road ahead is closed — resequencing remaining stops"
        elif decision.time_saved_min <= 0:
            decision.reason = "current stop order is still the best"
        elif decision.saved_pct < self.min_improvement * 100:
            decision.reason = (f"resequencing saves only "
                               f"{decision.saved_pct:.1f}% — not worth it")
        else:
            decision.should_reroute = True
            decision.reason = (f"traffic has changed; a different stop order is "
                               f"now {decision.saved_pct:.0f}% faster")

        decision.computed_ms = (time.perf_counter() - t0) * 1000
        return decision
