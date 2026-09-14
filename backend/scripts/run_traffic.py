"""
Phase 4 entrypoint — generate synthetic traffic and show what it does to routes.

    python scripts/run_traffic.py --scenario peak_hour
    python scripts/run_traffic.py --all                 # all 8, with stats
    python scripts/run_traffic.py --all --save          # + write the dataset
    python scripts/run_traffic.py --effect              # effect on a real route
    python scripts/run_traffic.py --modes               # do the 4 modes diverge?
    python scripts/run_traffic.py --reproducible        # prove the seeding works
    python scripts/run_traffic.py --diurnal             # the time-of-day curve
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd                                              # noqa: E402

from graph.edge_weights import MODES, CostModel                  # noqa: E402
from graph.graph_loader import load_graph, reset_traffic, resolve_place  # noqa: E402
from optimization.dijkstra import dijkstra_route                 # noqa: E402
from traffic.congestion_model import CongestionModel             # noqa: E402
from traffic.simulator import SCENARIO_IDS, TrafficSimulator, diurnal_factor  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def show_diurnal():
    print("\nDiurnal traffic profile (network-wide intensity)")
    for h in range(24):
        f = diurnal_factor(h)
        print(f"  {h:02d}:00  {f:0.2f}  {'#' * int(f * 52)}")


def run_scenarios(sim, ids, save=False):
    print(f"\n{'scenario':<20}{'hour':>6}{'loaded':>10}{'mean':>8}{'p95':>8}"
          f"{'max':>8}{'moder.':>9}{'heavy':>9}{'severe':>9}{'clsd':>6}{'inc':>5}")
    print("-" * 100)

    frames, summaries = [], []
    for sid in ids:
        t0 = time.perf_counter()
        state = sim.generate(sid)
        s = state.summary()
        summaries.append(s)
        hour = state.timestamp.hour + state.timestamp.minute / 60
        print(f"{sid:<20}{hour:6.1f}{s['edges_loaded']:10,}{s['mean_congestion']:8.3f}"
              f"{s['p95_congestion']:8.3f}{s['max_congestion']:8.3f}"
              f"{s['moderate_edges']:9,}{s['heavy_edges']:9,}{s['severe_edges']:9,}"
              f"{s['closures']:6d}{s['incidents']:5d}"
              f"   {time.perf_counter() - t0:4.1f}s")
        if save:
            sim.apply(state)
            frames.append(sim.to_dataframe(state))

    print("-" * 100)

    if save and frames:
        OUT.mkdir(parents=True, exist_ok=True)
        df = pd.concat(frames, ignore_index=True)
        pq = OUT / "hyderabad_synthetic_traffic.parquet"
        df.to_parquet(pq, index=False)
        csv = OUT / "hyderabad_synthetic_traffic_sample.csv"
        df.sample(min(5000, len(df)), random_state=0).to_csv(csv, index=False)
        (OUT / "scenarios.json").write_text(json.dumps(summaries, indent=2))
        print(f"\nsaved {len(df):,} rows -> {pq.name}")
        print(f"      5k-row preview -> {csv.name}")
        print(f"      per-scenario stats -> scenarios.json")
        print(f"\ncolumns: {', '.join(df.columns)}")
        print()
        print(df["congestion_level"].value_counts().to_string())
    return summaries


def run_effect(G, sim, src_key="hitec", dst_key="charminar", mode="balanced"):
    """The point of the whole phase: traffic must change the chosen route."""
    source, src_name, _ = resolve_place(G, src_key)
    target, dst_name, _ = resolve_place(G, dst_key)

    reset_traffic(G)
    cost_model = CostModel.calibrate(G, source, target, mode=mode)
    free = dijkstra_route(G, source, target, cost_model)

    print(f"\nEffect of traffic on {src_name} -> {dst_name}  (mode={mode})")
    print("-" * 92)
    print(f"{'scenario':<20}{'dist km':>9}{'ETA min':>9}{'cong %':>8}"
          f"{'fitness':>10}{'vs free-flow':>14}{'route':>10}")
    print("-" * 92)
    print(f"{'(free flow)':<20}{free.distance_km:9.2f}{free.time_min:9.1f}"
          f"{free.mean_congestion * 100:8.1f}{free.fitness:10.5f}{'--':>14}{'--':>10}")

    base_nodes = tuple(free.nodes)
    for sid in SCENARIO_IDS:
        state = sim.generate(sid)
        sim.apply(state)
        r = dijkstra_route(G, source, target, cost_model)
        if not r.valid:
            print(f"{sid:<20}  no valid route: {r.violations[:1]}")
            continue
        delta = (r.time_min / free.time_min - 1) * 100 if free.time_min else 0
        changed = "changed" if tuple(r.nodes) != base_nodes else "same"
        print(f"{sid:<20}{r.distance_km:9.2f}{r.time_min:9.1f}"
              f"{r.mean_congestion * 100:8.1f}{r.fitness:10.5f}{delta:+13.1f}%{changed:>10}")

    print("-" * 92)
    reset_traffic(G)


def run_mode_divergence(G, sim, src_key="hitec", dst_key="charminar",
                        scenario="peak_hour"):
    """Phase 3 saw all four modes agree. Under congestion they should not."""
    source, _, _ = resolve_place(G, src_key)
    target, _, _ = resolve_place(G, dst_key)

    state = sim.generate(scenario)
    sim.apply(state)

    print(f"\nObjective modes under '{scenario}'")
    print("-" * 74)
    print(f"{'mode':<18}{'dist km':>9}{'ETA min':>9}{'cong %':>9}{'fitness':>11}{'hops':>8}")
    print("-" * 74)

    routes = {}
    for mode in MODES:
        cm = CostModel.calibrate(G, source, target, mode=mode)
        r = dijkstra_route(G, source, target, cm)
        routes[mode] = r
        print(f"{mode:<18}{r.distance_km:9.2f}{r.time_min:9.1f}"
              f"{r.mean_congestion * 100:9.1f}{r.fitness:11.5f}{r.hops:8d}")
    print("-" * 74)

    distinct = len({tuple(r.nodes) for r in routes.values()})
    print(f"{distinct} distinct route(s) across the 4 modes.")
    if distinct > 1:
        print("The objectives now disagree — which is the whole point of a")
        print("multi-objective cost model, and what QPSO will search over.")
    reset_traffic(G)


def run_reproducibility(sim):
    print("\nReproducibility check (same seed must give identical traffic)")
    print("-" * 64)
    for sid in ("peak_hour", "accident"):
        a = sim.generate(sid, seed=42)
        b = sim.generate(sid, seed=42)
        c = sim.generate(sid, seed=7)
        print(f"  {sid:<20} seed42==seed42: {a.congestion == b.congestion}"
              f"    seed7!=seed42: {c.congestion != a.congestion}")
    print("-" * 64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None, choices=SCENARIO_IDS)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--effect", action="store_true")
    ap.add_argument("--modes", action="store_true")
    ap.add_argument("--reproducible", action="store_true")
    ap.add_argument("--diurnal", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--from", dest="src", default="hitec")
    ap.add_argument("--to", dest="dst", default="charminar")
    args = ap.parse_args()

    if args.diurnal:
        show_diurnal()
        return

    G = load_graph()
    sim = TrafficSimulator(G, CongestionModel(), seed=args.seed)

    if args.reproducible:
        run_reproducibility(sim)
    elif args.effect:
        run_effect(G, sim, args.src, args.dst)
    elif args.modes:
        run_mode_divergence(G, sim, args.src, args.dst)
    elif args.all:
        run_scenarios(sim, SCENARIO_IDS, save=args.save)
    else:
        run_scenarios(sim, [args.scenario or "peak_hour"], save=args.save)


if __name__ == "__main__":
    main()
