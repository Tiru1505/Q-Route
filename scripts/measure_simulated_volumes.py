"""
How much traffic does the simulator put on Hyderabad's roads over a day?

WHY THIS SCRIPT EXISTS
----------------------
traffic/simulator.py used to quote 12-hour volumes by road class — "primary
median 16,589 PCU/12h" and so on — with a note saying they were STALE and must
not be quoted. They had been measured under an older, hand-fitted daily curve,
and nothing in the repository could reproduce them: a docstring claimed
scripts/run_traffic.py did, and it did not. This is the script that should
have existed. The numbers it prints are the ones the docstring now quotes.

WHAT IT MEASURES
----------------
The "normal" scenario — background traffic only, no hotspots, incidents or
closures — regenerated at each hour from 07:00 to 18:00 through the measured
diurnal curve. Each hour's congestion becomes a flow by Greenshields,
q = k * v, using the congestion model's own method rather than a copy of it.
Twelve hourly flows summed give PCU per 12 hours (07:00-19:00).

The same seed is used for every hour, so a road that is busier than its class
average at 08:00 is also busier at 17:00. That is a choice: it models roads as
having persistent character rather than being redrawn hourly.

TWO WAYS TO COMPARE WITH HYDERABAD
----------------------------------
The comparison the old note made was against the HMDA Comprehensive
Transportation Study: 2,470-76,193 PCU/12h at three-arm junctions and
5,810-74,705 at four-arm junctions.

Those are JUNCTION totals — every vehicle passing through, from every arm. A
per-road figure is one direction of one segment, so setting it beside a
junction total and finding it "inside the range" says very little: almost any
per-road number fits under a junction ceiling.

So this also measures the like-for-like quantity: at every junction of the
monitored network, the flow arriving on all its approaches, summed, grouped by
how many arms the junction has. That is what a junction count counts.

WHAT IT DOES NOT SHOW
---------------------
That the simulator is realistic. A volume inside an observed range is a
plausibility check on magnitude, not validation of when and where traffic
forms. The HMDA ranges are also very wide, and they are from a survey, not a
city-wide census.

Usage:
    python scripts/measure_simulated_volumes.py
Writes:
    results/traffic/simulated_volumes.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np                                                  # noqa: E402

from graph.graph_loader import load_graph                           # noqa: E402
from traffic.congestion_model import CongestionModel                # noqa: E402
from traffic.simulator import (                                     # noqa: E402
    MEASURED_DIURNAL, MONITORED_CLASSES, TrafficSimulator,
)

OUT = ROOT / "results" / "traffic" / "simulated_volumes.json"
SCENARIO = "normal"
SEED = 42
HOURS = range(7, 19)            # 07:00 .. 18:00 starts = 07:00-19:00
REPORTED_CLASSES = ("motorway", "trunk", "primary", "secondary")

# HMDA Comprehensive Transportation Study, junction totals, PCU per 12 hours.
HMDA = {3: (2470, 76193), 4: (5810, 74705)}


def klass(data) -> str:
    h = data.get("highway")
    return str(h[0] if isinstance(h, list) else h)


def summarise(values) -> dict:
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "median": round(float(np.median(a))),
        "p5": round(float(np.percentile(a, 5))),
        "p95": round(float(np.percentile(a, 95))),
    }


def main() -> None:
    t0 = time.perf_counter()
    G = load_graph(verbose=False)
    model = CongestionModel()
    sim = TrafficSimulator(G, model, seed=SEED)
    print(f"Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges "
          f"({time.perf_counter() - t0:.0f}s)")

    states = []
    for h in HOURS:
        states.append(sim.generate(SCENARIO, seed=SEED, hour=float(h)).congestion)
    print(f"Generated {len(states)} hourly states "
          f"({time.perf_counter() - t0:.0f}s)")

    # Per-edge PCU over the 12 hours, for every edge that carries any traffic.
    # An edge absent from a state is free flow, which Greenshields gives zero
    # flow at — density zero — so it contributes nothing that hour.
    loaded = set()
    for s in states:
        loaded.update(s)

    per_edge: dict = {}
    for key in loaded:
        u, v, k = key
        data = G[u][v][k]
        per_edge[key] = sum(model.flow_pcu_h(data, s.get(key, 0.0)) for s in states)
    print(f"Flows for {len(per_edge):,} loaded edges "
          f"({time.perf_counter() - t0:.0f}s)")

    # --- per road class ------------------------------------------------------
    by_class = defaultdict(list)
    capacity = defaultdict(list)
    for (u, v, k), total in per_edge.items():
        data = G[u][v][k]
        c = klass(data)
        if c in MONITORED_CLASSES:
            by_class[c].append(total)
            capacity[c].append(float(data.get("capacity_pcu_h", 0.0) or 0.0))

    # How much of the day's volume is simply the road's capacity. Greenshields
    # flow, q = capacity * 4c(1-c), is flat near its top: anywhere between 25%
    # and 70% congestion a road carries 75-100% of capacity. If the simulator
    # holds arterials there all day, the 12-hour total mostly restates the
    # capacity assumption rather than anything the traffic model decided.
    per_class = {}
    for c in sorted(by_class):
        stats = summarise(by_class[c])
        cap = float(np.median(capacity[c]))
        stats["capacityPcuH"] = round(cap)
        stats["shareOfCapacityOver12h"] = round(stats["median"] / (cap * len(HOURS)), 3) if cap else None
        per_class[c] = stats

    # --- per junction, like-for-like with a junction count --------------------
    # A junction is a node where a monitored road meets at least two others.
    # Arms are distinct neighbouring nodes regardless of direction, so a
    # two-way road counts once.
    junctions = {3: [], 4: []}
    for node in G.nodes:
        incoming = list(G.in_edges(node, keys=True))
        if not any(klass(G[u][v][k]) in MONITORED_CLASSES for u, v, k in incoming):
            continue
        arms = len(set(G.predecessors(node)) | set(G.successors(node)))
        if arms not in junctions:
            continue
        junctions[arms].append(sum(per_edge.get(e, 0.0) for e in incoming))

    per_junction = {}
    for arms, totals in junctions.items():
        lo, hi = HMDA[arms]
        a = np.asarray(totals, dtype=float)
        stats = summarise(totals)
        stats.update({
            "hmdaRange": [lo, hi],
            "shareInsideHmdaRange": round(float(((a >= lo) & (a <= hi)).mean()), 3) if a.size else None,
            "shareBelowHmdaMin": round(float((a < lo).mean()), 3) if a.size else None,
            "shareAboveHmdaMax": round(float((a > hi).mean()), 3) if a.size else None,
        })
        per_junction[f"{arms}-arm"] = stats

    out = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
        "scenario": SCENARIO,
        "seed": SEED,
        "window": "07:00-19:00, twelve hourly states",
        "diurnalMeanOverWindow": round(float(np.mean([MEASURED_DIURNAL[h] for h in HOURS])), 3),
        "flowModel": "Greenshields q = k*v via CongestionModel.flow_pcu_h",
        "perRoadPcu12h": per_class,
        "perJunctionInflowPcu12h": per_junction,
        "note": (
            "Per-road figures are one direction of one segment. HMDA figures "
            "are junction totals across all arms, so only the per-junction "
            "inflow is comparable with them. Background traffic only: no "
            "hotspots, incidents or closures."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))

    print(f"\nWrote {OUT.relative_to(ROOT)} in {time.perf_counter() - t0:.0f}s\n")
    print("Per road, one direction (PCU per 12 h):")
    print(f"  {'class':15s} {'n':>7s} {'median':>8s} {'p5':>8s} {'p95':>8s} {'of capacity':>12s}")
    for c, s in per_class.items():
        mark = "  *" if c in REPORTED_CLASSES else ""
        print(f"  {c:15s} {s['n']:7,d} {s['median']:8,d} {s['p5']:8,d} {s['p95']:8,d} "
              f"{s['shareOfCapacityOver12h']:12.0%}{mark}")
    print("\nPer junction, all approaches summed — comparable with HMDA:")
    for name, s in per_junction.items():
        if not s.get("n"):
            continue
        lo, hi = s["hmdaRange"]
        print(f"  {name}: n={s['n']:,}  median {s['median']:,}  "
              f"p5 {s['p5']:,}  p95 {s['p95']:,}   HMDA {lo:,}-{hi:,}  "
              f"inside {s['shareInsideHmdaRange']:.0%}, below {s['shareBelowHmdaMin']:.0%}, "
              f"above {s['shareAboveHmdaMax']:.0%}")


if __name__ == "__main__":
    main()
