"""
Inventory and sanity-check everything under data/. Run after any fetch.

    python scripts/inspect_data.py
"""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024
    return "%.1f TB" % n


def rule(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def inspect_benchmarks():
    rule("BENCHMARKS  (open traffic time-series, for training the predictor)")
    for name, h5 in (("METR-LA", "metr-la/metr-la.h5"),
                     ("PEMS-BAY", "pems-bay/pems-bay.h5")):
        path = DATA / "raw/benchmarks" / h5
        if not path.exists():
            print("  %-10s MISSING  (%s)" % (name, path))
            continue
        try:
            df = pd.read_hdf(path)
        except Exception as exc:
            print("  %-10s unreadable: %s" % (name, exc))
            continue
        vals = df.to_numpy(dtype="float64")
        zeros = float((vals == 0).mean())
        print("  %-10s %s  shape=%s (timesteps x sensors)" % (name, human(path.stat().st_size), df.shape))
        print("             span   %s -> %s" % (df.index[0], df.index[-1]))
        print("             step   %s" % (df.index[1] - df.index[0]))
        print("             speed  min=%.1f mean=%.1f max=%.1f  (mph)"
              % (np.nanmin(vals), np.nanmean(vals), np.nanmax(vals)))
        print("             zeros  %.1f%%  <- missing-data sentinel, mask these in training"
              % (zeros * 100))

        loc = path.parent / "sensor_graph/sensor_locations.csv"
        if loc.exists():
            s = pd.read_csv(loc)
            print("             geo    %d sensors, lat %.3f..%.3f  lon %.3f..%.3f"
                  % (len(s), s.iloc[:, 1].min(), s.iloc[:, 1].max(),
                     s.iloc[:, 2].min(), s.iloc[:, 2].max()))

    for pkl in sorted((DATA / "raw/benchmarks").rglob("adj_mx*.pkl")):
        try:
            with open(pkl, "rb") as fh:
                obj = pickle.load(fh, encoding="latin1")
            adj = obj[-1] if isinstance(obj, (list, tuple)) else obj
            adj = np.asarray(adj)
            print("  adjacency  %-38s shape=%s density=%.3f"
                  % (pkl.relative_to(DATA), adj.shape, float((adj > 0).mean())))
        except Exception as exc:
            print("  adjacency  %s unreadable: %s" % (pkl.name, exc))


def inspect_india():
    rule("INDIA  (open Indian traffic data)")
    ind = DATA / "raw/india/indore-congestion/event_log.xlsx"
    if ind.exists():
        df = pd.read_excel(ind, sheet_name="event_log")
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        span = df.timestamp.max() - df.timestamp.min()
        print("  Indore congestion (Mendeley, CC BY 4.0)")
        print("    rows=%d  segments=%d  span=%s" % (len(df), df.road_id.nunique(), span))
        print("    per-segment observations/day = %.1f"
              % (len(df) / max(df.road_id.nunique(), 1) / max(span.days, 1)))
        print("    VERDICT: too small to train a sequence model. Sanity check only.")

    seg = DATA / "raw/india/hyderabad_segments.csv"
    if seg.exists():
        s = pd.read_csv(seg)
        print("\n  Hyderabad collection points (seed list for TomTom)")
        print("    %d points across %d corridors: %s"
              % (len(s), s.corridor.nunique(), ", ".join(sorted(s.corridor.unique()))))
        print("    bbox lat %.4f..%.4f  lon %.4f..%.4f"
              % (s.lat.min(), s.lat.max(), s.lon.min(), s.lon.max()))

    tom = sorted((DATA / "raw/india").glob("tomtom_*/date=*.parquet"))
    if tom:
        df = pd.concat([pd.read_parquet(p) for p in tom], ignore_index=True)
        good = df[df.error.isna()] if "error" in df else df
        print("\n  TomTom collected observations")
        print("    files=%d  rows=%d  ok=%d" % (len(tom), len(df), len(good)))
        if len(good):
            print("    span  %s -> %s" % (good.ts_local.min(), good.ts_local.max()))
            print("    congestion_ratio  mean=%.3f  p90=%.3f"
                  % (good.congestion_ratio.mean(), good.congestion_ratio.quantile(0.9)))
    else:
        print("\n  TomTom collected observations: NONE YET")
        print("    -> set TOMTOM_API_KEY and run scripts/collect_tomtom.py to start.")
        print("    -> this is the only source of real Hyderabad traffic; it accrues")
        print("       in wall-clock time, so starting it early matters.")


def inspect_graphs():
    rule("ROAD GRAPHS  (OpenStreetMap)")
    found = False
    for stats in sorted((DATA / "processed").glob("*/*_stats.json")):
        found = True
        import json
        s = json.loads(stats.read_text())
        print("  %s" % s["city"])
        print("    nodes=%s  edges=%s  road length=%s km  strongly_connected=%s"
              % (format(s["nodes"], ","), format(s["edges"], ","),
                 format(s["total_length_km"], ","), s["strongly_connected"]))
        mix = s.get("highway_mix", {})
        top = sorted(mix.items(), key=lambda kv: -kv[1])[:6]
        print("    road mix: %s" % ", ".join("%s=%s" % (k, v) for k, v in top))
    if not found:
        print("  none built yet -> python scripts/build_city_graph.py --city \"Hyderabad, Telangana, India\"")


def disk():
    rule("DISK")
    total = 0
    # Direct-file size per directory, so parents with subdirectories are not skipped.
    for sub in sorted(p for p in DATA.rglob("*") if p.is_dir()):
        size = sum(f.stat().st_size for f in sub.iterdir() if f.is_file())
        if size:
            total += size
            print("  %-52s %s" % (str(sub.relative_to(ROOT)), human(size)))
    print("  %-52s %s" % ("TOTAL", human(total)))


if __name__ == "__main__":
    inspect_benchmarks()
    inspect_india()
    inspect_graphs()
    disk()
