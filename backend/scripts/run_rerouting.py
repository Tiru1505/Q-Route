"""
Phases 9-10 — dynamic rerouting and the alert engine, end to end.

    python scripts/run_rerouting.py                 # single-destination trip
    python scripts/run_rerouting.py --multistop     # QPSO resequences the stops
    python scripts/run_rerouting.py --gates         # show WHY alerts are suppressed
    python scripts/run_rerouting.py --closure       # road ahead closes mid-trip

The scenario mirrors the frontend's Demo Mode: plan a route, drive part of it,
traffic worsens, the system notices, recomputes from the driver's CURRENT
position, and decides whether the improvement is worth interrupting them for.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alerts.alert_engine import AlertEngine, AlertPolicy                  # noqa: E402
from graph.edge_weights import MODES, CostModel                          # noqa: E402
from graph.graph_loader import load_graph, reset_traffic, resolve_place   # noqa: E402
from optimization.dijkstra import dijkstra_route                         # noqa: E402
from routing.rerouting import ActiveTrip, RerouteEngine                  # noqa: E402
from traffic.congestion_model import CongestionModel                     # noqa: E402
from traffic.simulator import SCENARIO_IDS, TrafficSimulator             # noqa: E402

RULE = "-" * 78


def banner(text):
    print(f"\n{text}")
    print(RULE)


def run_single(G, sim, args):
    source, src_name, _ = resolve_place(G, args.src)
    target, dst_name, _ = resolve_place(G, args.dst)

    # --- 1. plan under light traffic ----------------------------------
    reset_traffic(G)
    sim.apply(sim.generate("normal"))
    cost_model = CostModel.calibrate(G, source, target, mode=args.mode)
    planned = dijkstra_route(G, source, target, cost_model)

    banner(f"1. TRIP PLANNED   {src_name} -> {dst_name}")
    print(f"   {planned.distance_km:.2f} km, ETA {planned.time_min:.1f} min, "
          f"{planned.mean_congestion * 100:.0f}% congestion")

    trip = ActiveTrip(route=planned)
    engine = RerouteEngine(G, cost_model)
    alerts = AlertEngine(AlertPolicy(min_saving_min=args.min_saving,
                                     cooldown_s=args.cooldown))

    # --- 2. drive part of it -------------------------------------------
    trip.advance_to_fraction(args.progress)
    remaining = trip.remaining_on_current_route(G, cost_model)
    banner(f"2. DRIVING   {trip.progress:.0%} complete")
    print(f"   {remaining.time_min:.1f} min remaining, on plan")

    decision = engine.evaluate(trip)
    print(f"   check: {decision.summary()}")

    # --- 3. traffic worsens on the road ahead ---------------------------
    state = sim.generate("normal")
    state = sim.congest_route(state, trip.remaining_nodes, level=args.spike)
    if args.closure:
        ahead = trip.remaining_nodes[3:9]
        for u, v in zip(ahead, ahead[1:]):
            if G.has_edge(u, v):
                for d in G[u][v].values():
                    d["road_status"] = "closed"
        sim.apply(state)
        for u, v in zip(ahead, ahead[1:]):
            if G.has_edge(u, v):
                for d in G[u][v].values():
                    d["road_status"] = "closed"
        banner("3. ROAD CLOSED AHEAD")
    else:
        sim.apply(state)
        banner(f"3. CONGESTION SPIKE on the road ahead ({args.spike:.0%})")

    now = trip.remaining_on_current_route(G, cost_model)
    if now is None:
        print("   the road ahead is impassable")
    else:
        print(f"   remaining journey is now {now.time_min:.1f} min "
              f"(was {remaining.time_min:.1f})")

    # --- 4. the system reacts -------------------------------------------
    decision = engine.evaluate(trip)
    banner("4. REROUTE DECISION")
    print(f"   recomputed from the driver's CURRENT position in "
          f"{decision.computed_ms:.0f} ms")
    print(f"   {decision.summary()}")
    if decision.new_route is not None:
        print(f"   staying put: {decision.current_eta_min:.1f} min   "
              f"switching: {decision.new_eta_min:.1f} min")

    # --- 5. should we interrupt the driver? ------------------------------
    alert = alerts.consider(decision)
    banner("5. ALERT ENGINE")
    if alert:
        print(alert.render())
    else:
        print(f"   stayed silent: {alerts.suppressed[-1][0]}")

    return trip, engine, alerts, decision


def run_gates(G, sim, args):
    """
    Show the suppression logic working — the part that makes alerts trustworthy.

    Same trip, escalating congestion. Early spikes are correctly ignored; only
    once the saving is material does the system speak, and after that the
    cooldown holds it quiet again.
    """
    source, src_name, _ = resolve_place(G, args.src)
    target, dst_name, _ = resolve_place(G, args.dst)

    reset_traffic(G)
    sim.apply(sim.generate("normal"))
    cost_model = CostModel.calibrate(G, source, target, mode=args.mode)
    planned = dijkstra_route(G, source, target, cost_model)

    trip = ActiveTrip(route=planned).advance_to_fraction(0.25)
    engine = RerouteEngine(G, cost_model)
    alerts = AlertEngine(AlertPolicy(min_saving_min=5.0, min_saving_pct=10.0,
                                     cooldown_s=300.0))

    banner(f"ALERT GATES   {src_name} -> {dst_name}, escalating congestion")
    print(f"{'spike':>7}{'current':>10}{'best':>9}{'saving':>9}{'':>4}"
          f"  outcome")
    print(RULE)

    for spike in (0.20, 0.35, 0.50, 0.65, 0.80, 0.92, 0.95):
        state = sim.congest_route(sim.generate("normal"),
                                  trip.remaining_nodes, level=spike)
        sim.apply(state)
        decision = engine.evaluate(trip, force=True)
        alert = alerts.consider(decision)
        outcome = "ALERT RAISED" if alert else f"silent — {alerts.suppressed[-1][0]}"
        print(f"{spike:7.0%}{decision.current_eta_min:9.1f}m"
              f"{decision.new_eta_min:8.1f}m{decision.time_saved_min:8.1f}m"
              f"{'':>4}  {outcome}")

    print(RULE)
    r = alerts.report()
    print(f"{r['alerts_raised']} alert(s) raised, {r['suppressed']} suppressed — "
          f"the driver was interrupted only when it mattered.")


def run_multistop(G, sim, args):
    """Traffic changes mid-round; QPSO resequences the stops still outstanding."""
    from optimization.multistop import MultiStopProblem
    from benchmarking.benchmark import Budget, qpso_runner

    keys = ["hitec", "gachibowli", "kondapur", "jubilee", "panjagutta",
            "ameerpet", "begumpet", "mehdipatnam", "charminar"]
    nodes, names = [], []
    for k in keys:
        n, nm, _ = resolve_place(G, k)
        nodes.append(n)
        names.append(nm)

    reset_traffic(G)
    sim.apply(sim.generate("normal"))
    cost_model = CostModel.calibrate(G, nodes[0], nodes[-1], mode=args.mode)

    banner("1. DELIVERY ROUND PLANNED (light traffic)")
    problem = MultiStopProblem(G, cost_model, nodes[0], nodes[1:])
    planned = qpso_runner(problem, Budget(), 42).best_solution
    print(f"   depot {names[0]}, {len(nodes) - 1} stops")
    print(f"   {planned.distance_km:.2f} km, ETA {planned.time_min:.1f} min")

    trip = ActiveTrip(route=planned).advance_to_fraction(args.progress)
    engine = RerouteEngine(G, cost_model)
    alerts = AlertEngine(AlertPolicy(min_saving_min=args.min_saving))

    before = trip.remaining_on_current_route(G, cost_model)
    banner(f"2. DRIVING   {trip.progress:.0%} complete")
    print(f"   {before.time_min:.1f} min remaining")

    banner("3. PEAK HOUR ARRIVES")
    sim.apply(sim.generate("peak_hour"))
    now = trip.remaining_on_current_route(G, cost_model)
    print(f"   remaining journey is now {now.time_min:.1f} min "
          f"(was {before.time_min:.1f})")

    banner("4. QPSO RESEQUENCES THE REMAINING STOPS")
    remaining_stops = trip.stops_ahead(nodes[1:])
    done = len(nodes) - 1 - len(remaining_stops)
    print(f"   {done} stop(s) already delivered; {len(remaining_stops)} still ahead")
    decision = engine.evaluate_multistop(trip, remaining_stops)
    print(f"   {decision.algorithm} searched the orderings in "
          f"{decision.computed_ms:.0f} ms")
    print(f"   {decision.summary()}")
    print("   Dijkstra could not do this: it has no notion of stop order.")

    alert = alerts.consider(decision)
    banner("5. ALERT ENGINE")
    print(alert.render() if alert else
          f"   stayed silent: {alerts.suppressed[-1][0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="hitec")
    ap.add_argument("--to", dest="dst", default="charminar")
    ap.add_argument("--mode", default="balanced", choices=list(MODES))
    ap.add_argument("--scenario", default="normal", choices=SCENARIO_IDS)
    ap.add_argument("--progress", type=float, default=0.35)
    ap.add_argument("--spike", type=float, default=0.92)
    ap.add_argument("--min-saving", type=float, default=5.0)
    ap.add_argument("--cooldown", type=float, default=300.0)
    ap.add_argument("--closure", action="store_true")
    ap.add_argument("--gates", action="store_true")
    ap.add_argument("--multistop", action="store_true")
    args = ap.parse_args()

    G = load_graph()
    sim = TrafficSimulator(G, CongestionModel(), seed=42)

    if args.gates:
        run_gates(G, sim, args)
    elif args.multistop:
        run_multistop(G, sim, args)
    else:
        run_single(G, sim, args)

    reset_traffic(G)


if __name__ == "__main__":
    main()
