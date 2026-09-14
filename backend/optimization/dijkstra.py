"""
Dijkstra's algorithm — the exact baseline.

WHY THIS IS THE BASELINE
------------------------
Our objective is a sum of non-negative per-edge costs (see graph/edge_weights).
Under exactly that condition Dijkstra is *provably optimal*: no algorithm can
find a cheaper route. That gives the project ground truth. When QPSO returns a
route we can state precisely how far from optimal it is, instead of guessing.

Be honest about the consequence: on this problem class a metaheuristic cannot
beat Dijkstra, only match it. That is the expected result and it is worth
reporting plainly. Metaheuristics earn their place on problems where this
optimality guarantee breaks — a hard cost budget, multiple waypoints, or a
non-additive objective.

HOW IT WORKS (for the viva)
---------------------------
Keep a tentative distance to every node, initially infinity except the source
at 0. Repeatedly take the unvisited node with the smallest tentative distance,
mark it settled, and relax its outgoing edges: if reaching a neighbour through
this node is cheaper than the neighbour's current best, update it. Once a node
is settled its distance is final — because all edge costs are non-negative, no
later path can arrive more cheaply.

We stop the moment the target is settled ("early exit"). On a 286k-node graph
that typically explores a small fraction of the network.
"""
import heapq
import math
import time

import networkx as nx

from routing.route import evaluate_route


def dijkstra_route(G, source, target, cost_model, max_cost=None):
    """
    Our own Dijkstra. Returns a Route.

    max_cost prunes any branch whose cost already exceeds the budget. Note this
    is only a speed-up on the *scalarised* objective — it is NOT the same as
    solving the constrained shortest-path problem, which is NP-hard and is
    where the metaheuristics become genuinely useful.
    """
    t0 = time.perf_counter()

    if source == target:
        route = evaluate_route(G, [source], cost_model, algorithm="Dijkstra")
        route.runtime_ms = (time.perf_counter() - t0) * 1000
        return route

    dist = {source: 0.0}
    previous = {}
    settled = set()
    # heap entries: (cost_so_far, node)
    heap = [(0.0, source)]

    while heap:
        cost, node = heapq.heappop(heap)

        # Stale entry: we already settled this node via a cheaper path.
        if node in settled:
            continue
        settled.add(node)

        if node == target:
            break                                   # early exit — distance is final

        for neighbour in G.successors(node):
            if neighbour in settled:
                continue
            _data, step = cost_model.best_edge(G, node, neighbour)
            if not math.isfinite(step):             # closed road
                continue
            new_cost = cost + step
            if max_cost is not None and new_cost > max_cost:
                continue
            if new_cost < dist.get(neighbour, math.inf):
                dist[neighbour] = new_cost
                previous[neighbour] = node
                heapq.heappush(heap, (new_cost, neighbour))

    elapsed_ms = (time.perf_counter() - t0) * 1000

    if target not in previous and target != source:
        route = evaluate_route(G, [], cost_model, algorithm="Dijkstra")
        route.valid = False
        route.violations = ["no route found within constraints"]
        route.runtime_ms = elapsed_ms
        return route

    # Walk the predecessor chain back to the source.
    nodes, cur = [target], target
    while cur != source:
        cur = previous[cur]
        nodes.append(cur)
    nodes.reverse()

    route = evaluate_route(G, nodes, cost_model, algorithm="Dijkstra")
    route.runtime_ms = elapsed_ms
    route.iterations = len(settled)                 # nodes settled, for reporting
    return route


def multigraph_weight(cost_model):
    """
    Weight callable for NetworkX on a MultiDiGraph.

    Careful: on a multigraph NetworkX passes the callable the dict of ALL
    parallel edges between u and v ({key: data, ...}), not one edge's data.
    Passing that straight to edge_cost() silently scores every edge 0 — the
    lookups all miss — and NetworkX then returns an arbitrary path. Take the
    cheapest parallel edge, matching what our own implementation does.
    """
    def weight(_u, _v, keydict):
        return min(cost_model.edge_cost(d) for d in keydict.values())
    return weight


def dijkstra_route_networkx(G, source, target, cost_model):
    """
    The same problem solved with NetworkX. Used only to verify our
    implementation — not for benchmarking, so the comparison stays apples to
    apples.
    """
    t0 = time.perf_counter()
    try:
        nodes = nx.shortest_path(
            G, source, target, weight=multigraph_weight(cost_model)
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        route = evaluate_route(G, [], cost_model, algorithm="Dijkstra (NetworkX)")
        route.valid = False
        route.violations = ["no route found"]
        return route

    route = evaluate_route(G, nodes, cost_model, algorithm="Dijkstra (NetworkX)")
    route.runtime_ms = (time.perf_counter() - t0) * 1000
    return route


def verify_against_networkx(G, source, target, cost_model, tol=1e-9):
    """
    Cross-check. Returns (ours, reference, agree?).

    Different routes of *identical* cost are fine — ties are common in road
    networks. What matters is that the objective values match, because that is
    what proves our implementation is optimal.
    """
    ours = dijkstra_route(G, source, target, cost_model)
    reference = dijkstra_route_networkx(G, source, target, cost_model)

    if not (ours.valid and reference.valid):
        return ours, reference, ours.valid == reference.valid

    agree = abs(ours.fitness - reference.fitness) <= tol * max(1.0, abs(reference.fitness))
    return ours, reference, agree
