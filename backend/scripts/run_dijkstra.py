"""
Phase 3 entrypoint — run and verify the Dijkstra baseline.

    python scripts/run_dijkstra.py                       # default demo route
    python scripts/run_dijkstra.py --from hitec --to charminar --mode fastest
    python scripts/run_dijkstra.py --all-modes           # compare the four objectives
    python scripts/run_dijkstra.py --verify              # cross-check vs NetworkX
    python scripts/run_dijkstra.py --places              # list valid place keys
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.edge_weights import MODES, CostModel                    # noqa: E402
from graph.graph_loader import (                                    # noqa: E402
    load_graph, place_names, resolve_place,
)
from optimization.dijkstra import dijkstra_route, verify_against_networkx  # noqa: E402
from routing.route_validator import validate                        # noqa: E402

RESULTS = Path(__file__).resolve().parents[2] / "results" / "routes"

VERIFY_PAIRS = [
    ("hitec", "charminar"),
    ("miyapur", "lbnagar"),
    ("secunderabad", "airport"),
    ("gachibowli", "uppal"),
    ("kukatpally", "dilsukhnagar"),
    ("banjara", "airport"),
]


def straight_line_km(G, a, b):
    import osmnx as ox
    return ox.distance.great_circle(
        float(G.nodes[a]["y"]), float(G.nodes[a]["x"]),
        float(G.nodes[b]["y"]), float(G.nodes[b]["x"]),
    ) / 1000.0


def run_one(G, src_key, dst_key, mode, save=False):
    source, src_name, src_snap = resolve_place(G, src_key)
    target, dst_name, dst_snap = resolve_place(G, dst_key)

    cost_model = CostModel.calibrate(G, source, target, mode=mode)
    print(f"\n{src_name}  ->  {dst_name}")
    print(f"  snapped {src_snap:.0f} m / {dst_snap:.0f} m from the named point")
    print(f"  {cost_model.describe()}")

    route = dijkstra_route(G, source, target, cost_model)

    if not route.valid:
        print(f"  FAILED: {route.violations}")
        return route

    ok, violations = validate(G, route.nodes, source, target)
    sl_km = straight_line_km(G, source, target)
    detour = route.distance_km / sl_km if sl_km > 0 else float("nan")

    print(f"  distance    {route.distance_km:7.2f} km")
    print(f"  travel time {route.time_min:7.1f} min   ({route.avg_speed_kph:.0f} km/h avg)")
    print(f"  congestion  {route.mean_congestion * 100:7.1f} %")
    print(f"  fitness     {route.fitness:7.5f}   (free-flow reference = "
          f"{cost_model.reference_fitness:.5f})")
    print(f"  hops        {route.hops:7d}   settled {route.iterations:,} nodes")
    print(f"  runtime     {route.runtime_ms:7.1f} ms")
    print(f"  valid       {ok}" + ("" if ok else f"  {violations}"))

    # The cheapest correctness check there is: a road route can never be
    # shorter than the straight line between its endpoints.
    flag = "OK" if detour >= 1.0 else "IMPOSSIBLE — graph is truncated"
    print(f"  detour      {detour:7.2f} x straight line ({sl_km:.2f} km)  [{flag}]")

    if save:
        RESULTS.mkdir(parents=True, exist_ok=True)
        out = RESULTS / f"dijkstra_{src_key}_{dst_key}_{mode}.json"
        payload = route.to_dict(G)
        payload.update({"from": src_name, "to": dst_name, "mode": mode,
                        "weights": cost_model.weights.as_dict()})
        out.write_text(json.dumps(payload, indent=2))
        print(f"  saved       {out.relative_to(RESULTS.parent.parent)}")

    return route


def run_all_modes(G, src_key, dst_key):
    source, src_name, _ = resolve_place(G, src_key)
    target, dst_name, _ = resolve_place(G, dst_key)

    print(f"\n{src_name} -> {dst_name}: the same graph under four objectives")
    print("-" * 78)
    print(f"{'mode':<16}{'distance':>11}{'time':>10}{'congestion':>13}{'fitness':>12}{'hops':>8}")
    print("-" * 78)

    routes = {}
    for mode in MODES:
        cm = CostModel.calibrate(G, source, target, mode=mode)
        r = dijkstra_route(G, source, target, cm)
        routes[mode] = r
        print(f"{mode:<16}{r.distance_km:8.2f} km{r.time_min:7.1f} m"
              f"{r.mean_congestion * 100:11.1f} %{r.fitness:12.5f}{r.hops:8d}")
    print("-" * 78)

    distinct = len({tuple(r.nodes) for r in routes.values()})
    print(f"{distinct} distinct route(s) across the 4 modes.")
    if distinct == 1:
        print("All modes agree — expected with congestion at zero, since time and\n"
              "distance are near-collinear on a free-flow network. Phase 4 adds\n"
              "congestion, which is what will pull the modes apart.")
    return routes


def run_verification(G):
    print("\nVerifying our Dijkstra against NetworkX on the same objective")
    print("-" * 78)
    print(f"{'pair':<32}{'ours':>12}{'networkx':>12}{'match':>8}{'speed':>12}")
    print("-" * 78)

    all_ok = True
    for a, b in VERIFY_PAIRS:
        try:
            source, _, _ = resolve_place(G, a)
            target, _, _ = resolve_place(G, b)
        except (KeyError, ValueError) as exc:
            print(f"{a} -> {b}: skipped ({exc})")
            continue

        cm = CostModel.calibrate(G, source, target, mode="balanced")
        ours, ref, agree = verify_against_networkx(G, source, target, cm)
        all_ok &= agree
        ratio = ref.runtime_ms / ours.runtime_ms if ours.runtime_ms > 0 else float("nan")
        print(f"{a + ' -> ' + b:<32}{ours.fitness:12.6f}{ref.fitness:12.6f}"
              f"{('yes' if agree else 'NO'):>8}{ratio:11.2f}x")

    print("-" * 78)
    print("All objective values match — our implementation is optimal."
          if all_ok else "MISMATCH — investigate before trusting the baseline.")
    return all_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="hitec")
    ap.add_argument("--to", dest="dst", default="charminar")
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--graph", default=None)
    ap.add_argument("--all-modes", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--places", action="store_true")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    if args.places:
        for k, v in sorted(place_names().items()):
            print(f"  {k:<15} {v}")
        return

    t0 = time.perf_counter()
    G = load_graph(args.graph)
    print(f"[graph] loaded in {time.perf_counter() - t0:.1f}s")

    if args.verify:
        run_verification(G)
    elif args.all_modes:
        run_all_modes(G, args.src, args.dst)
    else:
        run_one(G, args.src, args.dst, args.mode, save=args.save)


if __name__ == "__main__":
    main()
