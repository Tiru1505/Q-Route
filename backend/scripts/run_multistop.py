"""
Phases 6-9 — the main experiment.

Multi-stop routing: visit N stops in any order, minimising cost under traffic.
This is the Vehicle Routing Problem named in the SIH brief, and it is the one
problem in this project that Dijkstra CANNOT express — it has no notion of
ordering stops.

    python scripts/run_multistop.py                       # 5 stops, 30 trials
    python scripts/run_multistop.py --stops 6 --trials 30
    python scripts/run_multistop.py --scalability          # 3..10 stops
    python scripts/run_multistop.py --scenario normal
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarking.benchmark import Budget, print_table, run_benchmark   # noqa: E402
from benchmarking.convergence import (                                  # noqa: E402
    plot_boxplot, plot_convergence, plot_scalability,
)
from graph.edge_weights import MODES, CostModel                          # noqa: E402
from graph.graph_loader import load_graph, reset_traffic, resolve_place  # noqa: E402
from optimization.multistop import MultiStopProblem, StopMatrix          # noqa: E402
from traffic.congestion_model import CongestionModel                     # noqa: E402
from traffic.simulator import SCENARIO_IDS, TrafficSimulator             # noqa: E402

RESULTS = Path(__file__).resolve().parents[2] / "results" / "metrics"

# A plausible Hyderabad delivery round. Depot first.
DEFAULT_ROUND = ["hitec", "gachibowli", "jubilee", "panjagutta", "ameerpet",
                 "begumpet", "secunderabad", "charminar", "mehdipatnam",
                 "dilsukhnagar", "uppal"]


def build_problem(G, cost_model, keys, verbose=False):
    nodes = []
    for k in keys:
        node, name, _ = resolve_place(G, k)
        nodes.append((node, name))
    depot = nodes[0][0]
    stops = [n for n, _ in nodes[1:]]
    problem = MultiStopProblem(G, cost_model, depot, stops, verbose=verbose)
    return problem, [nm for _, nm in nodes]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stops", type=int, default=5, help="stops after the depot")
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--population", type=int, default=40)
    ap.add_argument("--iterations", type=int, default=120)
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--scenario", default="peak_hour", choices=SCENARIO_IDS)
    ap.add_argument("--scalability", action="store_true")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()

    G = load_graph()
    reset_traffic(G)
    sim = TrafficSimulator(G, CongestionModel(), seed=42)
    sim.apply(sim.generate(args.scenario))

    budget = Budget(population=args.population, iterations=args.iterations)

    if args.scalability:
        run_scalability(G, sim, args, budget)
        return

    keys = DEFAULT_ROUND[: args.stops + 1]
    depot_node, _, _ = resolve_place(G, keys[0])
    last_node, _, _ = resolve_place(G, keys[-1])
    cost_model = CostModel.calibrate(G, depot_node, last_node, mode=args.mode)

    print(f"\nMULTI-STOP ROUTING   traffic={args.scenario}   mode={args.mode}")
    t0 = time.perf_counter()
    problem, names = build_problem(G, cost_model, keys, verbose=True)
    print(f"depot: {names[0]}")
    print(f"stops: {', '.join(names[1:])}")
    print(f"{problem.describe()}")
    print(f"[setup] {time.perf_counter() - t0:.1f}s")

    if not problem.matrix.complete():
        print(f"WARNING: {len(problem.matrix.unreachable)} stop pairs unreachable")

    print("\nCLASSICAL METHODS")
    print("-" * 104)
    print("Dijkstra              cannot solve — it finds a path between TWO points and")
    print("                      has no concept of ordering stops.")
    print("Dijkstra + Lagrangian cannot solve — it also handles only two endpoints; it")
    print("                      merely reweights the edges between them.")

    optimum, best_order = problem.brute_force()
    if optimum is not None:
        print(f"Brute force           {optimum:.6f}  (searched "
              f"{math.factorial(problem.dimensions):,} orderings)")
    else:
        print(f"Brute force           intractable at {problem.dimensions} stops "
              f"({math.factorial(problem.dimensions):,} orderings)")
    print("-" * 104)

    print(f"\nMETAHEURISTICS — {args.trials} independent trials each")
    summaries = run_benchmark(problem, trials=args.trials, budget=budget,
                              optimum=optimum)
    ranked = print_table(summaries, optimum=optimum, budget=budget,
                         title="RESULTS")

    best = summaries[ranked[0].name].best_solution
    if best is not None:
        print(f"\nBest tour found: {best.distance_km:.2f} km, "
              f"{best.time_min:.1f} min, "
              f"{best.mean_congestion * 100:.1f}% mean congestion")

    if not args.no_plots:
        p1 = plot_convergence(summaries, optimum=optimum,
                              title=f"Convergence — {args.stops} stops, {args.scenario}",
                              filename=f"convergence_{args.stops}stops.png")
        p2 = plot_boxplot(summaries, optimum=optimum,
                          filename=f"distribution_{args.stops}stops.png")
        print(f"\nplots: {p1.name}, {p2.name}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "problem": problem.describe(),
        "scenario": args.scenario,
        "mode": args.mode,
        "depot": names[0],
        "stops": names[1:],
        "trials": args.trials,
        "budget": budget.describe(),
        "brute_force_optimum": optimum,
        "results": {
            n: {
                "best": s.best, "mean": s.mean, "worst": s.worst, "std": s.std,
                "gap_pct": s.gap_vs(optimum), "optimal_hits": s.optimal_hits,
                "mean_runtime_ms": s.mean_runtime_ms,
                "mean_iterations": s.mean_iterations,
                "mean_iteration_of_best": s.mean_iteration_of_best,
            } for n, s in summaries.items()
        },
    }
    out = RESULTS / f"multistop_{args.stops}stops_{args.scenario}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    print(f"saved {out.name}")


def run_scalability(G, sim, args, budget):
    """How each method behaves as the problem grows — the headline chart."""
    print(f"\nSCALABILITY — traffic={args.scenario}, {args.trials} trials per size")
    rows = []

    for n_stops in (3, 4, 5, 6, 7, 8, 9, 10):
        keys = DEFAULT_ROUND[: n_stops + 1]
        depot_node, _, _ = resolve_place(G, keys[0])
        last_node, _, _ = resolve_place(G, keys[-1])
        cost_model = CostModel.calibrate(G, depot_node, last_node, mode=args.mode)
        problem, _ = build_problem(G, cost_model, keys)

        t0 = time.perf_counter()
        optimum, _ = problem.brute_force(limit=9)
        brute_ms = (time.perf_counter() - t0) * 1000 if optimum is not None else None

        summaries = run_benchmark(problem, trials=args.trials, budget=budget,
                                  optimum=optimum, verbose=False)
        row = {
            "stops": n_stops,
            "orderings": math.factorial(n_stops),
            "brute_ms": brute_ms,
            "optimum": optimum,
        }
        for name, s in summaries.items():
            row[name] = {
                "mean": s.mean, "best": s.best, "std": s.std,
                "gap_pct": s.gap_vs(optimum),
                "runtime_ms": s.mean_runtime_ms,
                "optimal_hits": s.optimal_hits,
            }
        rows.append(row)

        gaps = "  ".join(
            f"{n} {row[n]['gap_pct']:+.2f}%" if row[n]["gap_pct"] is not None
            else f"{n} --" for n in ("QPSO", "PSO", "GA")
        )
        bf = f"{brute_ms:8.0f} ms" if brute_ms else "intractable"
        print(f"  {n_stops:2d} stops  {math.factorial(n_stops):>10,} orderings  "
              f"brute {bf:>13}   {gaps}")

    if not args.no_plots:
        p = plot_scalability(rows)
        print(f"\nplot: {p.name}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"scalability_{args.scenario}.json"
    out.write_text(json.dumps(rows, indent=2, default=str))
    print(f"saved {out.name}")


if __name__ == "__main__":
    main()
