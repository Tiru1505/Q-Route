#!/usr/bin/env python
"""
Derive the simulator's daily traffic profile from real Indian counts.

WHY THIS EXISTS
---------------
`traffic.simulator.diurnal_factor` used to be two Gaussians with hand-chosen
parameters, asserted to match "the shape Indian metros show". Nothing had been
measured. With 31 days of real 15-minute counts from an Indian junction now in
the repository, the assertion can be replaced by a measurement — and the two
turn out to disagree badly:

    hour   real   formula
    06:00  0.94     0.11      the formula treats the morning build-up as empty
    17:00  1.00     0.83      the real peak is 17:00, the formula peaks 18:30
    01:00  0.36     0.06      overnight traffic is understated six-fold

Mean absolute error across the day was 0.302 on a 0-1 scale, which is not a
small correction. A simulator driven by the wrong daily shape produces jams at
the wrong hours, and every route optimised against it inherits that error.

WHAT THIS DOES AND DOES NOT CLAIM
---------------------------------
The profile is normalised, so it carries the SHAPE of the day and nothing else.
Absolute volumes are not transferable: this is one junction, and a six-lane
arterial and a residential lane obviously do not carry the same number of
vehicles. The simulator already scales per-edge volume by road class, and this
only replaces the time-of-day curve it is multiplied by.

The honest limit: one junction, 31 days, one city. The shape of Indian urban
traffic generalises far better than its magnitude, but this has not been
validated against a second junction because no second series exists here.

USAGE
-----
    python scripts/derive_diurnal_profile.py           # print the table
    python scripts/derive_diurnal_profile.py --emit    # emit Python to paste

The result is pasted into traffic/simulator.py as MEASURED_DIURNAL rather than
loaded at runtime: the simulator must never fail to import because a data file
moved, and 24 numbers do not need a file.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSV = ROOT / "data" / "raw" / "india" / "indian_junction_traffic.csv"

# The same conversion the congestion model uses, so the profile is weighted by
# road space occupied rather than by vehicle headcount. A bus-heavy hour and a
# bike-heavy hour with equal headcounts do not load the road equally.
PCU = {"CarCount": 1.0, "BikeCount": 0.5, "BusCount": 3.0, "TruckCount": 3.0}


def derive() -> np.ndarray:
    df = pd.read_csv(CSV)
    t = pd.to_datetime(df["Time"], format="%I:%M:%S %p")
    df["hour"] = t.dt.hour
    df["pcu"] = sum(df[c] * w for c, w in PCU.items())

    # Mean across all 31 days, so a single unusual day cannot set the shape.
    hourly = df.groupby("hour")["pcu"].mean().reindex(range(24))
    if hourly.isna().any():
        missing = hourly[hourly.isna()].index.tolist()
        raise ValueError(f"No observations for hour(s) {missing}; cannot build a profile.")
    return (hourly / hourly.max()).to_numpy("float64")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true",
                    help="print the Python literal for traffic/simulator.py")
    args = ap.parse_args()

    profile = derive()

    if args.emit:
        print("MEASURED_DIURNAL = (")
        for i in range(0, 24, 4):
            row = ", ".join(f"{v:.3f}" for v in profile[i:i + 4])
            print(f"    {row},"
                  f"{'':<4}# {i:02d}:00-{min(i + 3, 23):02d}:00")
        print(")")
        return 0

    from traffic.simulator import diurnal_factor
    print(f"{'hour':>5s} {'measured':>9s} {'current':>9s} {'diff':>7s}")
    print("-" * 34)
    diffs = []
    for h in range(24):
        cur = diurnal_factor(h)
        diffs.append(abs(profile[h] - cur))
        print(f"{h:02d}:00 {profile[h]:9.3f} {cur:9.3f} {profile[h] - cur:+7.3f}")
    print(f"\nmean |difference| : {np.mean(diffs):.3f}")
    print(f"measured peak     : {int(np.argmax(profile)):02d}:00")
    print(f"measured trough   : {int(np.argmin(profile)):02d}:00")
    print(f"trough / peak     : {profile.min():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
