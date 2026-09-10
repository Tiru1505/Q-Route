"""
Constrained routing — the experiment that justifies using a metaheuristic.

THE PROBLEM
-----------
    minimise    travel time
    subject to  congestion exposure <= B

"Congestion exposure" is metres weighted by congestion: driving 2 km on a road
that is 50% congested counts as 1 km of exposure. It is already tracked on
every Route as `congested_m`, so nothing new has to be measured.

Read the constraint as a driver's instruction: "get me there as fast as you
can, but I am not willing to sit in more than about 4 km worth of jam."

WHY DIJKSTRA CANNOT DO THIS
---------------------------
Dijkstra is optimal because of one property: the best route to a node is always
part of the best route through it. So once it settles a node it never looks at
that node again.

A budget destroys that property. Suppose there are two ways to reach
Mehdipatnam:

    route P   12 minutes, uses 3.5 km of the budget
    route Q   14 minutes, uses 0.8 km of the budget

Dijkstra settles Mehdipatnam with P — it is faster — and discards Q forever.
But if the remaining leg needs 2 km of budget, P leads to a dead end and Q was
the correct choice. Dijkstra has already thrown it away.

Formally this is the Resource-Constrained Shortest Path problem, and it is
NP-hard. This is the class of problem metaheuristics exist for.

THE HONEST BASELINE
-------------------
We do NOT compare QPSO against a strawman. The standard classical attack is
Lagrangian relaxation: fold the constraint into the edge weights as

    weight(e) = time(e) + lambda * congestion_exposure(e)

and sweep lambda. Each lambda gives an ordinary Dijkstra problem, and large
lambda buys feasibility at the cost of time. We run that sweep and keep the
best feasible route it finds.

That is a genuinely strong baseline. It cannot guarantee optimality — the best
solution reachable by ANY lambda can still be worse than the true constrained
optimum, and that shortfall is the duality gap — but a guarantee is not the
same as a large gap in practice.

MEASURED RESULT: LAGRANGIAN WINS. REPORT IT THAT WAY.
-----------------------------------------------------
Hitec City -> Charminar, peak_hour, 8 QPSO trials per budget:

    budget    Lagrangian    QPSO best    QPSO feasible    winner
    8.82 km      4.9967     no route          0/8         Lagrangian
    9.13 km      4.9967     no route          0/8         Lagrangian
    9.54 km      3.9096       4.6571          5/8         Lagrangian
   10.06 km      3.9096       4.4922          8/8         Lagrangian

Lagrangian relaxation beat QPSO at every budget level, by 15-19% on objective,
and at tight budgets QPSO could not find a feasible route at all.

Two things are nonetheless established, and both matter:

  1. PLAIN Dijkstra genuinely cannot solve this. It returns the fastest route,
     which breaks the budget, and has no mechanism to trade time for exposure.
     That part of the argument holds.

  2. But "Dijkstra cannot solve it" is not the same as "classical methods
     cannot solve it". Lagrangian relaxation is classical, cheap to implement,
     and on this instance class its duality gap is small enough that it
     dominates.

The cause of QPSO's shortfall is the waypoint encoding, characterised in
optimization/encoding.py: it already sits ~10% above the unconstrained optimum
under congestion, so it cannot be expected to win a constrained variant of the
same problem.

DO NOT present this as a QPSO victory. A negative result, honestly reported
with its cause identified, is worth more than a fabricated positive one — and
is what the project brief explicitly asks for.
"""
import math
from dataclasses import dataclass

import networkx as nx



@dataclass
class RouteConstraints:
    """
    A hard budget on congestion exposure, plus the penalty used to enforce it.

    penalty_weight must be large enough that ANY feasible route scores better
    than ANY infeasible one — otherwise the optimiser will happily return a
    fast route that breaks the budget. The graded violation term on top keeps
    a gradient among infeasible candidates so the swarm can find its way back
    into the feasible region rather than wandering blind.
    """

    max_congested_m: float = math.inf
    penalty_weight: float = 10.0

    def is_feasible(self, route):
        return route is not None and route.valid and \
            route.congested_m <= self.max_congested_m + 1e-9

    def violation(self, route):
        """Absolute overshoot in metres. Zero when feasible."""
        if route is None or not route.valid:
            return math.inf
        return max(0.0, route.congested_m - self.max_congested_m)

    def violation_ratio(self, route):
        if not math.isfinite(self.max_congested_m) or self.max_congested_m <= 0:
            return 0.0
        return self.violation(route) / self.max_congested_m

    def objective(self, route, cost_model):
        """
        The quantity being minimised: normalised travel time.

        Deliberately NOT the multi-objective fitness. The constrained
        experiment asks a sharper question — fastest route subject to a
        congestion budget — and mixing congestion into the objective as well
        as the constraint would double-count it.
        """
        if route is None or not route.valid:
            return math.inf
        return route.time_s / cost_model.ref_time_s

    def penalised(self, route, cost_model):
        """Objective plus penalty. This is what the optimiser actually sees."""
        base = self.objective(route, cost_model)
        if not math.isfinite(base):
            return math.inf
        if self.is_feasible(route):
            return base
        return base + self.penalty_weight * (1.0 + self.violation_ratio(route))


def min_exposure_route(G, source, target, cost_model):
    """
    The route with the least congestion exposure, ignoring time entirely.

    This is the FLOOR: no route can do better, so any budget below its exposure
    is infeasible and the whole experiment is void.
    """
    from routing.route import evaluate_route

    def weight(_u, _v, keydict):
        best = math.inf
        for d in keydict.values():
            if not cost_model.usable(d):
                continue
            _t, length, cong = cost_model.components(d)
            # Tiny length term breaks ties between equally uncongested routes,
            # which otherwise all score 0 and produce an absurd detour.
            best = min(best, cong + 1e-6 * length)
        return best if math.isfinite(best) else None

    try:
        nodes = nx.shortest_path(G, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    return evaluate_route(G, nodes, cost_model, algorithm="Dijkstra (min exposure)")


def suggest_budget(G, source, target, cost_model, ratio=0.6):
    """
    Pick a budget that is both FEASIBLE and BINDING.

    Naively taking a fraction of the fastest route's exposure does not work.
    Measured on Hitec City -> Charminar under peak_hour: the fastest route has
    10.58 km of exposure, but the least-exposure route still has ~9 km, because
    at peak the whole city is congested. A budget of 60% (6.35 km) is below the
    floor, so NOTHING can satisfy it — every algorithm fails and the experiment
    says nothing.

    So anchor the budget between the two extremes:

        budget = min_exposure + ratio * (fastest_exposure - min_exposure)

    ratio = 1.0 is the fastest route (constraint inactive), ratio = 0.0 is the
    least-exposure route (feasible but slow). Anything in between forces a
    genuine trade-off, which is exactly the problem we want to pose.
    """
    fastest = time_optimal_route(G, source, target, cost_model)
    if fastest is None or not fastest.valid:
        raise ValueError("No route exists between these points.")

    cleanest = min_exposure_route(G, source, target, cost_model)
    floor = cleanest.congested_m if cleanest is not None else 0.0
    span = max(fastest.congested_m - floor, 0.0)
    budget = floor + ratio * span

    return budget, fastest, cleanest


def time_optimal_route(G, source, target, cost_model):
    """
    Fastest route ignoring the budget. Two roles:
      * the lower bound on travel time — no feasible route can beat it
      * the reference for choosing a budget that binds
    """
    from routing.route import evaluate_route

    def weight(_u, _v, keydict):
        best = math.inf
        for d in keydict.values():
            if not cost_model.usable(d):
                continue
            best = min(best, cost_model.components(d)[0])
        return best if math.isfinite(best) else None

    try:
        nodes = nx.shortest_path(G, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    return evaluate_route(G, nodes, cost_model, algorithm="Dijkstra (time only)")


def lagrangian_dijkstra(G, source, target, cost_model, constraints,
                        lambdas=None, verbose=False):
    """
    The strong classical baseline: Lagrangian relaxation.

    For each lambda, solve an ordinary shortest-path problem with

        weight(e) = time(e) + lambda * congestion_exposure(e)

    Small lambda ignores the budget and gives the fastest (often infeasible)
    route; large lambda avoids congestion at any cost in time. Somewhere
    between, feasible routes appear. We return the fastest feasible one found.

    Returns (best_feasible_route, trace) where trace records every lambda tried
    so the sweep can be plotted and inspected.
    """
    from routing.route import evaluate_route

    if lambdas is None:
        # Geometric sweep: the useful range spans orders of magnitude, and a
        # linear sweep wastes nearly all its samples at one end.
        lambdas = [0.0] + [10 ** (e / 4.0) for e in range(-12, 21)]

    best_route, best_obj = None, math.inf
    trace = []

    for lam in lambdas:
        def weight(_u, _v, keydict, _lam=lam):
            best = math.inf
            for d in keydict.values():
                if not cost_model.usable(d):
                    continue
                t, _length, cong = cost_model.components(d)
                best = min(best, t + _lam * cong)
            return best if math.isfinite(best) else None

        try:
            nodes = nx.shortest_path(G, source, target, weight=weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

        route = evaluate_route(G, nodes, cost_model,
                               algorithm=f"Lagrangian-Dijkstra")
        feasible = constraints.is_feasible(route)
        obj = constraints.objective(route, cost_model)
        trace.append({
            "lambda": lam,
            "time_min": route.time_min,
            "congested_m": route.congested_m,
            "feasible": feasible,
            "objective": obj,
        })

        if feasible and obj < best_obj:
            best_obj, best_route = obj, route

        if verbose:
            print(f"    lambda={lam:9.4f}  {route.time_min:6.1f} min  "
                  f"exposure {route.congested_m / 1000:6.2f} km  "
                  f"{'FEASIBLE' if feasible else 'over budget'}")

    if best_route is not None:
        best_route.algorithm = "Dijkstra + Lagrangian"
    return best_route, trace
