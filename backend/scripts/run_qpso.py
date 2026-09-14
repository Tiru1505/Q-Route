"""
Phase 5 entrypoint — run QPSO and measure it against Dijkstra's known optimum.

    python scripts/run_qpso.py                          # one run, free flow
    python scripts/run_qpso.py --scenario peak_hour     # under traffic
    python scripts/run_qpso.py --trials 20              # stochastic spread
    python scripts/run_qpso.py --waypoints 7 --particles 40
    python scripts/run_qpso.py --verbose                # per-iteration trace

The number that matters is the OPTIMALITY GAP: how far QPSO's fitness sits above
Dijkstra's proven optimum. Small gap = the implementation works.
"""
import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.edge_weights import MODES, CostModel                     # noqa: E402
from graph.graph_loader import load_graph, reset_traffic, resolve_place  # noqa: E402
from optimization.dijkstra import dijkstra_route                    # noqa: E402
from optimization.encoding import WaypointDecoder                   # noqa: E402
from optimization.qpso import QPSO, QPSOConfig                      # noqa: E402
from routing.route_validator import validate                        # noqa: E402
from traffic.congestion_model import CongestionModel                # noqa: E402
from traffic.simulator import SCENARIO_IDS, TrafficSimulator        # noqa: E402


def setup(G, src_key, dst_key, mode, scenario):
    source, src_name, _ = resolve_place(G, src_key)
    target, dst_name, _ = resolve_place(G, dst_key)

    reset_traffic(G)
    if scenario:
        sim = TrafficSimulator(G, CongestionModel(), seed=42)
        sim.apply(sim.generate(scenario))

    cost_model = CostModel.calibrate(G, source, target, mode=mode)
    return source, target, src_name, dst_name, cost_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="hitec")
    ap.add_argument("--to", dest="dst", default="charminar")
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--scenario", default=None, choices=SCENARIO_IDS)
    ap.add_argument("--waypoints", type=int, default=5)
    ap.add_argument("--particles", type=int, default=30)
    ap.add_argument("--iterations", type=int, default=80)
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    G = load_graph()
    source, target, src_name, dst_name, cost_model = setup(
        G, args.src, args.dst, args.mode, args.scenario
    )

    print(f"\n{src_name} -> {dst_name}   mode={args.mode}   "
          f"traffic={args.scenario or 'free flow'}")
    print(f"{cost_model.describe()}")

    # ---- the known optimum -------------------------------------------
    optimal = dijkstra_route(G, source, target, cost_model)
    print(f"\nDIJKSTRA (proven optimum)")
    print(f"  {optimal.distance_km:6.2f} km  {optimal.time_min:6.1f} min  "
          f"cong {optimal.mean_congestion * 100:5.1f}%  "
          f"fitness {optimal.fitness:.6f}  {optimal.runtime_ms:7.1f} ms")

    # ---- build the shared search space -------------------------------
    t0 = time.perf_counter()
    decoder = WaypointDecoder(G, source, target, cost_model,
                              n_waypoints=args.waypoints, verbose=True)
    setup_ms = (time.perf_counter() - t0) * 1000
    print(f"[encoding] built in {setup_ms:.0f} ms  "
          f"(shared by every metaheuristic, so the comparison stays fair)")

    cfg = QPSOConfig(n_particles=args.particles, max_iterations=args.iterations,
                     seed=args.seed)

    print(f"\nQPSO  particles={cfg.n_particles} iterations={cfg.max_iterations} "
          f"dimensions={decoder.dimensions} beta={cfg.beta_start}->{cfg.beta_end}")

    results = []
    for trial in range(args.trials):
        solver = QPSO(G, decoder, cost_model, cfg)
        res = solver.run(seed=args.seed + trial, verbose=args.verbose and trial == 0)
        results.append(res)

        if args.trials == 1 or trial == 0:
            r = res.route
            gap = (res.best_fitness / optimal.fitness - 1) * 100
            ok, violations = validate(G, r.nodes, source, target)
            print(f"\n  {r.distance_km:6.2f} km  {r.time_min:6.1f} min  "
                  f"cong {r.mean_congestion * 100:5.1f}%  "
                  f"fitness {res.best_fitness:.6f}  {res.runtime_ms:7.1f} ms")
            print(f"  iterations {res.iterations_run} "
                  f"(best found at {res.iteration_of_best})  "
                  f"evaluations {res.evaluations}  "
                  f"decodes {decoder.decode_calls}")
            print(f"  valid route: {ok}" + ("" if ok else f"  {violations[:2]}"))
            print(f"\n  OPTIMALITY GAP: {gap:+.3f}%  "
                  f"({'matches the optimum' if gap < 0.01 else 'above optimum'})")
            wp = decoder.waypoints_for(res.best_vector)
            print(f"  best vector: {[round(v, 3) for v in res.best_vector]}")
            print(f"  waypoints:   {wp}")

    # ---- multi-trial statistics --------------------------------------
    if args.trials > 1:
        fits = [r.best_fitness for r in results]
        gaps = [(f / optimal.fitness - 1) * 100 for f in fits]
        times = [r.runtime_ms for r in results]
        iters = [r.iterations_run for r in results]
        hits = sum(1 for g in gaps if g < 0.01)

        print(f"\n{args.trials} TRIALS")
        print("-" * 68)
        print(f"  fitness   best {min(fits):.6f}   mean {statistics.mean(fits):.6f}"
              f"   worst {max(fits):.6f}")
        print(f"            std  {statistics.pstdev(fits):.6f}")
        print(f"  gap %     best {min(gaps):+.3f}   mean {statistics.mean(gaps):+.3f}"
              f"   worst {max(gaps):+.3f}")
        print(f"  runtime   mean {statistics.mean(times):.0f} ms"
              f"   (Dijkstra {optimal.runtime_ms:.0f} ms)")
        print(f"  iterations mean {statistics.mean(iters):.1f}")
        print(f"  reached the proven optimum in {hits}/{args.trials} trials "
              f"({hits / args.trials * 100:.0f}%)")
        print("-" * 68)
        print("  Dijkstra is provably optimal on this objective, so QPSO cannot")
        print("  beat it. A small, consistent gap is the correct result and is")
        print("  what validates the implementation.")

    reset_traffic(G)


if __name__ == "__main__":
    main()
