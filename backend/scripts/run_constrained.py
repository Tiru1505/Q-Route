"""
Phase 5b — the headline experiment.

    minimise travel time   subject to   congestion exposure <= B

This is the Resource-Constrained Shortest Path problem: NP-hard, and outside
what Dijkstra can solve exactly. It is where a metaheuristic earns its place.

    python scripts/run_constrained.py                        # default demo
    python scripts/run_constrained.py --ratio 0.5            # tighter budget
    python scripts/run_constrained.py --trials 15
    python scripts/run_constrained.py --show-sweep           # the lambda sweep

We do not strawman the baseline: Dijkstra is given Lagrangian relaxation, the
standard classical attack on this problem.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.edge_weights import MODES, CostModel                      # noqa: E402
from graph.graph_loader import load_graph, reset_traffic, resolve_place  # noqa: E402
from optimization.constraints import (                                # noqa: E402
    RouteConstraints, lagrangian_dijkstra, min_exposure_route, suggest_budget,
    time_optimal_route,
)
from optimization.encoding import WaypointDecoder                     # noqa: E402
from optimization.qpso import QPSO, QPSOConfig                        # noqa: E402
from routing.route_validator import validate                          # noqa: E402
from traffic.congestion_model import CongestionModel                  # noqa: E402
from traffic.simulator import SCENARIO_IDS, TrafficSimulator          # noqa: E402

RESULTS = Path(__file__).resolve().parents[2] / "results" / "metrics"


def line(route, constraints, cost_model, label=None):
    if route is None:
        return f"{label or '?':<26}  no feasible route found"
    tag = "feasible" if constraints.is_feasible(route) else "OVER BUDGET"
    return (f"{label or route.algorithm:<26}{route.time_min:8.1f} min"
            f"{route.distance_km:8.2f} km"
            f"{route.congested_m / 1000:9.2f} km"
            f"{constraints.objective(route, cost_model):10.4f}   {tag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="hitec")
    ap.add_argument("--to", dest="dst", default="charminar")
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--scenario", default="peak_hour", choices=SCENARIO_IDS)
    ap.add_argument("--ratio", type=float, default=0.6,
                    help="budget as a fraction of the fastest route's exposure")
    ap.add_argument("--trials", type=int, default=10)
    ap.add_argument("--waypoints", type=int, default=5)
    ap.add_argument("--show-sweep", action="store_true")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    G = load_graph()
    source, src_name, _ = resolve_place(G, args.src)
    target, dst_name, _ = resolve_place(G, args.dst)

    reset_traffic(G)
    sim = TrafficSimulator(G, CongestionModel(), seed=42)
    sim.apply(sim.generate(args.scenario))
    cost_model = CostModel.calibrate(G, source, target, mode=args.mode)

    print(f"\nCONSTRAINED ROUTING   {src_name} -> {dst_name}")
    print(f"traffic={args.scenario}   minimise travel time subject to a "
          f"congestion-exposure budget")

    # ---- set a budget that actually binds ----------------------------
    budget_m, fastest, cleanest = suggest_budget(
        G, source, target, cost_model, args.ratio)
    constraints = RouteConstraints(max_congested_m=budget_m, penalty_weight=10.0)

    floor = cleanest.congested_m if cleanest else 0.0
    print("\nExposure range for this instance:")
    print(f"  least-exposure route  {cleanest.time_min:6.1f} min   "
          f"exposure {floor / 1000:5.2f} km   <- floor, nothing can beat it")
    print(f"  fastest route         {fastest.time_min:6.1f} min   "
          f"exposure {fastest.congested_m / 1000:5.2f} km")
    print(f"BUDGET = floor + {args.ratio:.0%} of the span = {budget_m / 1000:.2f} km")
    print("(feasible, because it sits above the floor; binding, because the "
          "fastest route breaks it)")

    print(f"\n{'algorithm':<26}{'time':>12}{'distance':>12}{'exposure':>12}"
          f"{'objective':>10}")
    print("-" * 84)
    print(line(fastest, constraints, cost_model, "Dijkstra (time only)"))
    print(line(cleanest, constraints, cost_model, "Dijkstra (min exposure)"))

    # ---- baseline 1: plain Dijkstra on the mixed objective -----------
    from optimization.dijkstra import dijkstra_route
    plain = dijkstra_route(G, source, target, cost_model)
    print(line(plain, constraints, cost_model, "Dijkstra (balanced)"))

    # ---- baseline 2: Lagrangian relaxation --------------------------
    t0 = time.perf_counter()
    lagr, trace = lagrangian_dijkstra(G, source, target, cost_model, constraints,
                                      verbose=args.show_sweep)
    lagr_ms = (time.perf_counter() - t0) * 1000
    print(line(lagr, constraints, cost_model, "Dijkstra + Lagrangian"))

    # ---- QPSO -------------------------------------------------------
    print(f"\n[encoding] building shared search space...")
    t0 = time.perf_counter()
    decoder = WaypointDecoder(G, source, target, cost_model,
                              n_waypoints=args.waypoints, verbose=True)
    setup_ms = (time.perf_counter() - t0) * 1000
    print(f"[encoding] {setup_ms / 1000:.1f}s")

    objectives, feas_count, times = [], 0, []
    best_overall = None
    for trial in range(args.trials):
        solver = QPSO(G, decoder, cost_model,
                      QPSOConfig(seed=42 + trial), constraints=constraints)
        res = solver.run(seed=42 + trial)
        route = solver.best_feasible()
        times.append(res.runtime_ms)
        if route is not None:
            feas_count += 1
            obj = constraints.objective(route, cost_model)
            objectives.append(obj)
            if best_overall is None or obj < constraints.objective(best_overall, cost_model):
                best_overall = route

    print()
    print(line(best_overall, constraints, cost_model, "QPSO (best of trials)"))
    print("-" * 84)

    # ---- verdict ----------------------------------------------------
    print(f"\nQPSO over {args.trials} trials")
    print(f"  found a feasible route in {feas_count}/{args.trials} trials")
    if objectives:
        print(f"  objective  best {min(objectives):.4f}  "
              f"mean {statistics.mean(objectives):.4f}  worst {max(objectives):.4f}")
        if len(objectives) > 1:
            print(f"             std  {statistics.pstdev(objectives):.4f}")
    print(f"  runtime    mean {statistics.mean(times):.0f} ms   "
          f"(Lagrangian sweep {lagr_ms:.0f} ms over {len(trace)} lambdas)")

    n_feasible_lambdas = sum(1 for t in trace if t["feasible"])
    print(f"\n  the lambda sweep tried {len(trace)} values; "
          f"{n_feasible_lambdas} produced a feasible route")

    print("\nVERDICT")
    print("-" * 84)
    if constraints.is_feasible(fastest):
        print("  The budget did not bind — rerun with a smaller --ratio.")
    else:
        print("  Plain Dijkstra CANNOT solve this problem. Its route is fastest")
        print("  but breaks the budget, and it has no mechanism to trade a little")
        print("  time for less exposure: the budget destroys the optimal-substructure")
        print("  property Dijkstra relies on.")
    if lagr is not None and best_overall is not None:
        lo = constraints.objective(lagr, cost_model)
        qo = constraints.objective(best_overall, cost_model)
        delta = (qo / lo - 1) * 100
        if delta < -0.01:
            print(f"  QPSO beat the Lagrangian baseline by {-delta:.2f}% "
                  f"({best_overall.time_min:.1f} vs {lagr.time_min:.1f} min).")
        elif delta < 0.01:
            print(f"  QPSO matched the Lagrangian baseline "
                  f"({best_overall.time_min:.1f} min).")
        else:
            print(f"  The Lagrangian baseline beat QPSO by {delta:.2f}% "
                  f"({lagr.time_min:.1f} vs {best_overall.time_min:.1f} min).")
            print("  Report this honestly: Lagrangian relaxation is a strong")
            print("  classical method, and on this instance its duality gap is small.")
    elif best_overall is not None:
        print("  The Lagrangian sweep found NO feasible route; QPSO did. That is")
        print("  the clearest possible demonstration of the point.")
    print("-" * 84)

    if args.save:
        RESULTS.mkdir(parents=True, exist_ok=True)
        payload = {
            "instance": f"{src_name} -> {dst_name}",
            "scenario": args.scenario,
            "budget_m": budget_m,
            "budget_ratio": args.ratio,
            "fastest": fastest.to_dict(),
            "min_exposure": cleanest.to_dict() if cleanest else None,
            "dijkstra_balanced": plain.to_dict(),
            "lagrangian": lagr.to_dict() if lagr else None,
            "qpso_best": best_overall.to_dict() if best_overall else None,
            "qpso_feasible_trials": f"{feas_count}/{args.trials}",
            "qpso_objectives": objectives,
            "lambda_trace": trace,
        }
        out = RESULTS / f"constrained_{args.src}_{args.dst}_{args.scenario}.json"
        out.write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nsaved {out.name}")

    reset_traffic(G)


if __name__ == "__main__":
    main()
