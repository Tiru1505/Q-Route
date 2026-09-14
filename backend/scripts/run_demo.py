"""
The complete SIH demonstration, end to end, in one command.

    python scripts/run_demo.py              # the 8-step story
    python scripts/run_demo.py --full       # + benchmark, convergence, scalability
    python scripts/run_demo.py --json out/  # dump every payload for the frontend

Runs the whole system through one QROEngine — the same object the FastAPI
backend will call — so this doubles as an integration test: if this script
works, the API layer will too.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import QROEngine                                    # noqa: E402

RULE = "=" * 78


def step(n, title):
    print(f"\n{RULE}\n {n}. {title}\n{RULE}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="hitec")
    ap.add_argument("--to", dest="dst", default="charminar")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--json", default=None, help="directory to dump JSON payloads")
    args = ap.parse_args()

    payloads = {}
    t_start = time.perf_counter()

    step(1, "SYSTEM START")
    engine = QROEngine(scenario="normal")
    h = engine.health()
    payloads["health"] = h
    print(f"   graph: {h['graph']['nodes']:,} nodes, {h['graph']['edges']:,} edges")
    print(f"   traffic scenario: {h['scenario']}")
    print(f"   {len(engine.places())} selectable locations")

    step(2, "PLAN A ROUTE")
    plan = engine.plan(args.src, args.dst, algorithm="qpso", mode="balanced")
    payloads["plan"] = plan
    rec = plan["recommended"]
    print(f"   {plan['meta']['from']} -> {plan['meta']['to']}")
    print(f"   {len(plan['routes'])} routes found in {plan['meta']['computeMs']:.0f} ms")
    for r in plan["routes"]:
        tag = "  <- recommended" if r["recommended"] else ""
        print(f"     {r['label']:<8} {r['distanceKm']:6.2f} km  {r['etaMin']:6.1f} min  "
              f"cong {r['congestion'] * 100:4.1f}%  score {r['score']}{tag}")
    print(f"   solver: {plan['meta']['solverUsed']}")

    step(3, "CURRENT TRAFFIC")
    traffic = engine.traffic()
    payloads["traffic"] = traffic
    levels = {}
    for s in traffic["segments"]:
        levels[s["level"]] = levels.get(s["level"], 0) + 1
    print(f"   {len(traffic['segments'])} congested arterial segments on the map")
    print(f"   {levels}")
    print(f"   {len(traffic['incidents'])} incident(s)")

    step(4, "DRIVER SETS OFF")
    prog = engine.advance(0.35)
    print(f"   {prog['progress']:.0%} complete, {prog['remainingEtaMin']:.1f} min remaining")
    quiet = engine.check_reroute()
    print(f"   reroute check: {quiet['reason']}")
    print(f"   alert: {'raised' if quiet['alert'] else 'none — ' + str(quiet['suppressedBecause'])}")

    step(5, "CONGESTION HITS THE ROAD AHEAD")
    spike = engine.spike_route(level=0.92)
    print(f"   {spike['affected']} road segments on the active route congested to "
          f"{spike['level']:.0%}")
    after = engine.advance(0.35)
    print(f"   remaining journey is now {after['remainingEtaMin']:.1f} min")

    step(6, "DYNAMIC REROUTING")
    decision = engine.check_reroute()
    payloads["reroute"] = decision
    print(f"   recomputed from the driver's current position in "
          f"{decision['computeMs']:.0f} ms")
    print(f"   staying put: {decision['currentEtaMin']:.1f} min")
    print(f"   switching:   {decision['newEtaMin']:.1f} min")
    print(f"   time saved:  {decision['timeSavedMin']:.1f} min "
          f"({decision['savedPct']:.0f}%)")

    step(7, "ALERT ENGINE")
    if decision["alert"]:
        a = decision["alert"]
        print(f"   [{a['severity'].upper()}] {a['title']}")
        print(f"   {a['message']}")
        print(f"   -> {a['action']}")
        engine.accept_reroute()
        print("   driver accepted; the new route is now active")
    else:
        print(f"   stayed silent: {decision['suppressedBecause']}")

    step(8, "MULTI-STOP — THE PROBLEM DIJKSTRA CANNOT SOLVE")
    engine.set_scenario("peak_hour")
    ms = engine.plan_multistop(
        "hitec", ["gachibowli", "jubilee", "panjagutta", "ameerpet", "charminar"])
    payloads["multistop"] = ms
    print(f"   depot {ms['depot']}, {ms['meta']['stops']} stops, "
          f"{ms['meta']['possibleOrderings']:,} possible orderings")
    print(f"   QPSO found the best order in {ms['meta']['computeMs']:.0f} ms")
    print(f"   visit order: {' -> '.join(ms['visitOrder'])}")
    print(f"   {ms['route']['distanceKm']:.2f} km, {ms['route']['etaMin']:.1f} min")
    print(f"   {ms['meta']['solverNote']}")

    if args.full:
        step(9, "BENCHMARK — QPSO vs PSO vs GA")
        bench = engine.benchmark(stops=6, trials=30)
        payloads["benchmark"] = bench
        print(f"   {bench['budget']}")
        print(f"   exact optimum (brute force): {bench['exactOptimum']}")
        for c in bench["classical"]:
            print(f"     {c['algorithm']:<24} {c['note']}")
        print()
        print(f"     {'algo':<6}{'best':>11}{'mean':>11}{'std':>10}{'gap%':>9}"
              f"{'optimal':>10}{'ms':>9}")
        for r in bench["rows"]:
            hits = "%d/%d" % (r["optimalHits"], r["trials"])
            print(f"     {r['algorithm']:<6}{r['best']:11.6f}{r['mean']:11.6f}"
                  f"{r['std']:10.6f}{r['gapPct']:+9.3f}{hits:>10}"
                  f"{r['runtimeMs']:9.1f}")

        step(10, "SCALABILITY")
        scale = engine.scalability(sizes=(3, 5, 7, 8), trials=10)
        payloads["scalability"] = scale
        print(f"     {'stops':>6}{'orderings':>12}{'brute ms':>12}"
              f"{'QPSO ms':>10}{'QPSO gap%':>11}")
        for r in scale["rows"]:
            brute = f"{r['bruteMs']:.0f}" if r["bruteMs"] else "intractable"
            gap = f"{r['QPSOGap']:+.2f}" if r.get("QPSOGap") is not None else "--"
            print(f"     {r['stops']:6d}{r['orderings']:12,}{brute:>12}"
                  f"{r['QPSO']:10.1f}{gap:>11}")

    print(f"\n{RULE}")
    print(f" DEMO COMPLETE in {time.perf_counter() - t_start:.1f}s")
    print(RULE)

    if args.json:
        out = Path(args.json)
        out.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            (out / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nwrote {len(payloads)} JSON payloads to {out}/")
        print("These are exactly what the FastAPI endpoints should return.")


if __name__ == "__main__":
    main()
