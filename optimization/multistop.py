"""
Multi-stop routing — the problem where classical shortest-path methods stop
being applicable at all.

THE PROBLEM
-----------
    "Start at the depot, visit these N stops in any order, end wherever the
     last stop is (or return to the depot). Minimise total cost under current
     traffic."

A delivery van, an ambulance with several pickups, a waste-collection round.
This is the Vehicle Routing Problem — the exact thing the SIH problem statement
names when it says classical optimisation struggles because the problem is
NP-hard.

WHY DIJKSTRA AND LAGRANGIAN RELAXATION CANNOT DO THIS
-----------------------------------------------------
Not "do it badly" — cannot express it.

Dijkstra answers "cheapest path from A to B". It has no notion of ORDER. Given
five stops it cannot tell you which to visit first, because that question does
not exist in its formulation. Lagrangian relaxation does not help either: it
also only ever handles two endpoints; it merely reweights the edges between
them.

The number of orders is N! — 120 for five stops, 40,320 for eight, 3.6 million
for ten. That combinatorial explosion is the whole point, and it is where
metaheuristics are the appropriate tool rather than an ornament.

ENCODING: RANDOM KEYS
---------------------
Continuous optimisers cannot output a permutation directly. The standard bridge
is random-key encoding (Bean, 1994):

    vector      [0.72, 0.13, 0.55, 0.91, 0.30]
    argsort  -> [1, 4, 2, 0, 3]                  <- visit order

Sort the numbers; their ORIGINAL indices, in sorted order, are the tour. Every
vector in [0,1]^N maps to a valid permutation, so — as with the waypoint
encoding — there are no invalid candidates to repair.

It also means QPSO, PSO and GA all search exactly the same [0,1]^N box with the
same decoding. No algorithm gets an encoding advantage, which is what makes the
comparison fair.

SPEED
-----
Evaluating a tour needs the cost of travelling between stops. Those costs do
not change during a run, so we precompute the full stop-to-stop matrix once
with N+1 Dijkstra runs. After that, scoring a tour is N table lookups —
microseconds. This makes multi-stop far cheaper to set up than the single-pair
corridor encoding, not more expensive.
"""
import heapq
import math
import time
from dataclasses import dataclass

import numpy as np

from graph.edge_weights import is_closed
from optimization.problem import EvalResult, Problem
from routing.route import Route


@dataclass
class Leg:
    """A precomputed stop-to-stop connection."""
    nodes: list
    time_s: float
    distance_m: float
    congested_m: float
    cost: float                      # cost-model value, used for routing


class StopMatrix:
    """
    All-pairs costs between the depot and the stops.

    Built with one Dijkstra per stop, each stopping as soon as every other stop
    has been settled.
    """

    def __init__(self, G, cost_model, stops, verbose=False):
        self.G = G
        self.cost_model = cost_model
        self.stops = list(stops)             # stops[0] is the depot
        self.n = len(self.stops)
        self.legs = {}                       # (i, j) -> Leg
        self.unreachable = []

        t0 = time.perf_counter()
        target_set = set(self.stops)
        for i, src in enumerate(self.stops):
            prev = self._tree(src, target_set - {src})
            for j, dst in enumerate(self.stops):
                if i == j:
                    continue
                leg = self._extract(prev, src, dst)
                if leg is None:
                    self.unreachable.append((i, j))
                else:
                    self.legs[(i, j)] = leg

        self.build_ms = (time.perf_counter() - t0) * 1000
        if verbose:
            print(f"[stops] {self.n} stops | {len(self.legs)} legs | "
                  f"built in {self.build_ms / 1000:.1f}s"
                  + (f" | {len(self.unreachable)} unreachable" if self.unreachable else ""))

    def _tree(self, root, targets):
        G, cm = self.G, self.cost_model
        dist = {root: 0.0}
        prev = {}
        heap = [(0.0, root)]
        settled = set()
        remaining = set(targets)

        while heap:
            d, node = heapq.heappop(heap)
            if node in settled:
                continue
            settled.add(node)
            remaining.discard(node)
            if not remaining:
                break
            for nbr in G.successors(node):
                if nbr in settled:
                    continue
                _data, step = cm.best_edge(G, node, nbr)
                if not math.isfinite(step):
                    continue
                nd = d + step
                if nd < dist.get(nbr, math.inf):
                    dist[nbr] = nd
                    prev[nbr] = node
                    heapq.heappush(heap, (nd, nbr))
        return prev

    def _extract(self, prev, src, dst):
        if dst not in prev:
            return None
        nodes, cur = [dst], dst
        while cur != src:
            cur = prev.get(cur)
            if cur is None:
                return None
            nodes.append(cur)
        nodes.reverse()

        t = d = c = cost = 0.0
        for u, v in zip(nodes, nodes[1:]):
            data, step = self.cost_model.best_edge(self.G, u, v)
            if data is None or is_closed(data):
                return None
            ti, di, ci = self.cost_model.components(data)
            t += ti
            d += di
            c += ci
            cost += step
        return Leg(nodes=nodes, time_s=t, distance_m=d, congested_m=c, cost=cost)

    def leg(self, i, j):
        return self.legs.get((i, j))

    def complete(self):
        """True when every ordered pair is reachable — required for any tour."""
        return not self.unreachable


class MultiStopProblem(Problem):
    """
    Visit every stop once, starting at the depot.

    Random-key encoded, so it is a plain box-constrained continuous problem
    from the optimiser's point of view.
    """

    name = "multi-stop routing"

    def __init__(self, G, cost_model, depot, stops, matrix=None,
                 return_to_depot=False, verbose=False):
        self.G = G
        self.cost_model = cost_model
        self.depot = depot
        self.stop_nodes = list(stops)
        self.return_to_depot = return_to_depot
        self.dimensions = len(self.stop_nodes)

        self.matrix = matrix or StopMatrix(
            G, cost_model, [depot] + self.stop_nodes, verbose=verbose
        )
        self._cache = {}
        self.evaluations = 0

    # ------------------------------------------------------------ decode
    @staticmethod
    def order_from_vector(vector):
        """Random keys -> visit order. Every vector yields a valid permutation."""
        return list(np.argsort(np.asarray(vector, dtype=float)))

    def tour_indices(self, order):
        """Matrix indices for the full tour (depot is index 0)."""
        seq = [0] + [i + 1 for i in order]
        if self.return_to_depot:
            seq.append(0)
        return seq

    # ---------------------------------------------------------- evaluate
    def evaluate(self, vector):
        order = self.order_from_vector(vector)
        key = tuple(order)
        if key in self._cache:
            return self._cache[key]

        self.evaluations += 1
        seq = self.tour_indices(order)

        nodes, t, d, c = [], 0.0, 0.0, 0.0
        for a, b in zip(seq, seq[1:]):
            leg = self.matrix.leg(a, b)
            if leg is None:
                result = EvalResult(math.inf, None, False)
                self._cache[key] = result
                return result
            nodes.extend(leg.nodes if not nodes else leg.nodes[1:])
            t += leg.time_s
            d += leg.distance_m
            c += leg.congested_m

        route = Route(
            nodes=nodes, algorithm="multi-stop",
            time_s=t, distance_m=d, congested_m=c,
            fitness=self.cost_model.fitness(t, d, c), valid=True,
        )
        result = EvalResult(route.fitness, route, True)
        self._cache[key] = result
        return result

    # ------------------------------------------------------------- brute
    def brute_force(self, limit=9):
        """
        Exhaustive search over every ordering — the true optimum.

        Only tractable to about 9 stops (9! = 362,880). Above that it is
        omitted, which is precisely why a metaheuristic is needed and is worth
        showing in the results table.
        """
        from itertools import permutations

        if self.dimensions > limit:
            return None, None

        best, best_order = math.inf, None
        for perm in permutations(range(self.dimensions)):
            vec = np.empty(self.dimensions)
            for rank, idx in enumerate(perm):
                vec[idx] = rank / max(self.dimensions, 1)
            res = self.evaluate(vec)
            if res.fitness < best:
                best, best_order = res.fitness, perm
        return best, best_order

    def describe(self):
        return (f"{self.name}: depot + {self.dimensions} stops "
                f"({math.factorial(self.dimensions):,} possible orders)")
