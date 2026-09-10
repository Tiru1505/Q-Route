#!/usr/bin/env python
"""
Route between Indian cities on the national highway graph.

    python scripts/test_india_routing.py

WHAT THIS CHECKS
----------------
Not that the router returns something — Dijkstra almost always does. The
question is whether what it returns is a REAL ROAD JOURNEY. A graph stitched
together from a country extract can be subtly wrong in ways that still produce
a path: ways cut at the wrong nodes, lengths accumulated incorrectly, one-way
tags misread, or a "route" that is really a straight-line hop across a gap.

So each result is compared against the driving distance actually observed on
these corridors, and against the straight-line distance. A road route should be
15-40% longer than the crow flies. Much less than that means the graph is
skipping over terrain; much more means it is detouring absurdly, which is what
a badly connected network looks like.

The times are FREE-FLOW: no traffic, no tolls, no stops, no breaks. They will
come out optimistic against a real drive, and that is expected rather than a
fault — congestion is applied on top by the traffic layer.
"""

from __future__ import annotations

import math
import pathlib
import pickle
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GRAPH = ROOT / "data" / "processed" / "india-highways" / "india_highways.pkl"

CITIES = {
    "Hyderabad": (17.3850, 78.4867),
    "Mumbai":    (19.0760, 72.8777),
    "Bengaluru": (12.9716, 77.5946),
    "Delhi":     (28.6139, 77.2090),
    "Chennai":   (13.0827, 80.2707),
    "Pune":      (18.5204, 73.8567),
    "Kolkata":   (22.5726, 88.3639),
}

# Driving distances commonly observed on these corridors, in km. Used as a
# sanity band, not as ground truth — the exact figure depends on which route is
# taken and where in the city you start.
EXPECTED_KM = {
    ("Hyderabad", "Mumbai"): 710,
    ("Hyderabad", "Bengaluru"): 570,
    ("Hyderabad", "Chennai"): 630,
    ("Mumbai", "Pune"): 150,
    ("Delhi", "Mumbai"): 1420,
    ("Delhi", "Kolkata"): 1500,
}


def haversine_km(a, b) -> float:
    from preprocessing.osm_pbf import haversine
    return haversine(a[0], a[1], b[0], b[1]) / 1000.0


def nearest_node(G, lat, lon):
    """
    Closest graph node to a coordinate, by brute force.

    A KD-tree would be faster, but this runs a handful of times in a test and
    building the tree costs more than the scan saves.
    """
    best, best_d = None, float("inf")
    for n, d in G.nodes(data=True):
        dy = d["y"] - lat
        dx = (d["x"] - lon) * math.cos(math.radians(lat))
        dist = dy * dy + dx * dx
        if dist < best_d:
            best, best_d = n, dist
    return best, math.sqrt(best_d) * 111.32


def main() -> int:
    import networkx as nx

    if not GRAPH.exists():
        print(f"No graph at {GRAPH}\nBuild it: python scripts/build_india_highways.py")
        return 1

    t0 = time.time()
    with open(GRAPH, "rb") as fh:
        G = pickle.load(fh)
    print(f"[graph] {G.number_of_nodes():,} nodes  {G.number_of_edges():,} edges "
          f"(loaded in {time.time() - t0:.1f}s)\n")

    snapped = {}
    for name, (lat, lon) in CITIES.items():
        n, km = nearest_node(G, lat, lon)
        snapped[name] = n
        flag = "  <-- far from any highway" if km > 15 else ""
        print(f"  {name:<10s} snapped to a node {km:5.1f} km away{flag}")

    print(f"\n{'route':<24s} {'road km':>9s} {'crow km':>9s} {'ratio':>6s} "
          f"{'hours':>7s} {'km/h':>6s} {'expected':>9s} {'delta':>7s}")
    print("-" * 88)

    failures = 0
    for (a, b), expected in EXPECTED_KM.items():
        try:
            t = time.time()
            path = nx.shortest_path(G, snapped[a], snapped[b], weight="free_flow_time_s")
        except nx.NetworkXNoPath:
            print(f"{a + ' -> ' + b:<24s} NO PATH")
            failures += 1
            continue

        km = sum(min(d["length_m"] for d in G[u][v].values())
                 for u, v in zip(path, path[1:])) / 1000.0
        secs = sum(min(d["free_flow_time_s"] for d in G[u][v].values())
                   for u, v in zip(path, path[1:]))
        crow = haversine_km(CITIES[a], CITIES[b])
        ratio = km / crow if crow else 0.0
        hours = secs / 3600.0
        delta = 100.0 * (km - expected) / expected

        warn = ""
        if ratio < 1.05:
            warn = "  <-- suspiciously direct"
            failures += 1
        elif ratio > 1.6:
            warn = "  <-- large detour"
            failures += 1
        elif abs(delta) > 25:
            warn = "  <-- far from the usual road distance"
            failures += 1

        print(f"{a + ' -> ' + b:<24s} {km:9.0f} {crow:9.0f} {ratio:6.2f} "
              f"{hours:7.1f} {km / hours if hours else 0:6.0f} "
              f"{expected:9d} {delta:+6.0f}%{warn}")

    print(f"\n{'=' * 88}")
    if failures:
        print(f"{failures} route(s) outside the sanity band — inspect before trusting "
              f"this graph.")
        return 1
    print("All routes within the expected band for real road journeys.")
    print("Times are free-flow: no traffic, tolls, stops or breaks, so they are "
          "optimistic against a real drive by design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
