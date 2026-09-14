"""
Route validity checks.

Dijkstra cannot produce an invalid route — it walks the graph edge by edge. The
metaheuristics can and will, especially early in a run, which is exactly why
this module exists now rather than in Phase 5: QPSO will need it to repair or
reject its candidates, and the benchmark reports "route validity %" per
algorithm.
"""
from graph.edge_weights import is_closed


def validate(G, nodes, source=None, target=None, max_cost=None,
             cost_model=None, allow_revisits=False):
    """
    Check a node sequence. Returns (is_valid, violations).

    Checks, in order:
      1. non-empty and at least two nodes
      2. every node exists in the graph
      3. correct endpoints
      4. consecutive nodes are actually connected (respects one-way direction,
         because the graph is directed)
      5. no repeated nodes — a cycle wastes distance and can never be optimal
      6. no closed roads
      7. optional budget: total cost <= max_cost
    """
    violations = []

    if not nodes:
        return False, ["empty route"]
    if len(nodes) < 2:
        return False, ["route has fewer than two nodes"]

    missing = [n for n in nodes if n not in G]
    if missing:
        violations.append(f"{len(missing)} node(s) not in graph: {missing[:3]}")
        return False, violations

    if source is not None and nodes[0] != source:
        violations.append(f"starts at {nodes[0]}, expected {source}")
    if target is not None and nodes[-1] != target:
        violations.append(f"ends at {nodes[-1]}, expected {target}")

    if not allow_revisits and len(set(nodes)) != len(nodes):
        seen, repeats = set(), []
        for n in nodes:
            if n in seen:
                repeats.append(n)
            seen.add(n)
        violations.append(f"revisits {len(repeats)} node(s): {repeats[:3]}")

    for u, v in zip(nodes, nodes[1:]):
        if not G.has_edge(u, v):
            violations.append(f"disconnected: no edge {u} -> {v}")
            continue
        if all(is_closed(d) for d in G[u][v].values()):
            violations.append(f"closed road: {u} -> {v}")

    if max_cost is not None and cost_model is not None and not violations:
        total = sum(cost_model.best_edge(G, u, v)[1] for u, v in zip(nodes, nodes[1:]))
        if total > max_cost:
            violations.append(f"cost {total:.4f} exceeds budget {max_cost:.4f}")

    return not violations, violations


def repair(G, nodes, cost_model=None):
    """
    Best-effort cleanup of a broken candidate. Used by the metaheuristics in
    Phase 5; harmless for Dijkstra output.

    Two fixes only, both cheap and always safe:
      * loop removal   — if a node repeats, delete everything between the
                         occurrences. This can only shorten the route.
      * gap bridging   — if consecutive nodes are not adjacent, splice in the
                         cheapest connecting path.

    Returns (nodes, repaired?) — nodes unchanged if nothing could be fixed.
    """
    import networkx as nx

    if not nodes or len(nodes) < 2:
        return nodes, False

    changed = False

    # 1. loop removal
    seen = {}
    cleaned = []
    for n in nodes:
        if n in seen:
            cleaned = cleaned[: seen[n] + 1]
            changed = True
        else:
            seen[n] = len(cleaned)
            cleaned.append(n)
        seen = {node: i for i, node in enumerate(cleaned)}
    nodes = cleaned

    # 2. gap bridging
    bridged = [nodes[0]]
    # On a MultiDiGraph the callable receives every parallel edge at once, so
    # reduce over them — see optimization.dijkstra.multigraph_weight.
    if cost_model is not None:
        def weight(_u, _v, keydict):
            return min(cost_model.edge_cost(d) for d in keydict.values())
    else:
        weight = "length_m"
    for u, v in zip(nodes, nodes[1:]):
        if G.has_edge(u, v):
            bridged.append(v)
            continue
        try:
            segment = nx.shortest_path(G, u, v, weight=weight)
            bridged.extend(segment[1:])
            changed = True
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return nodes, False        # unrepairable — caller should reject it

    return bridged, changed
