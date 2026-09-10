#!/usr/bin/env python
"""
Build street-level road graphs for Indian cities from the country extract.

    python scripts/build_city_graphs.py                      # all five
    python scripts/build_city_graphs.py --city mumbai pune   # some
    python scripts/build_city_graphs.py --dry-run            # plan only

Hyderabad is excluded by default: it already has a street graph built by
preprocessing/osm_processor.py, and rebuilding it here would replace a known
network — and the benchmark figures measured on it — with a differently derived
one for no benefit. Pass it explicitly if you really want it rebuilt.

Both passes read the whole 1.71 GB extract, so this takes roughly half an hour
in total. It does NOT take half an hour per city: every city is filled during
the same sweep, which is the entire reason this script exists rather than a
loop around a single-city builder.

Output: data/processed/<city>/<city>_drive.pkl (+ _stats.json)
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.city_streets import (            # noqa: E402
    STREET_KEEP, build_city, finalise_and_save, scan_nodes, scan_ways,
)
from preprocessing.osm_processor import METRO_BBOX  # noqa: E402

PBF = ROOT / "data" / "raw" / "osm" / "geofabrik" / "india-latest.osm.pbf"
OUT = ROOT / "data" / "processed"

DEFAULT_CITIES = ["bengaluru", "delhi", "chennai", "mumbai", "pune"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", nargs="+", default=None,
                    choices=list(METRO_BBOX), help="cities to build")
    ap.add_argument("--pbf", type=pathlib.Path, default=PBF)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cities = args.city or DEFAULT_CITIES

    if not args.pbf.exists():
        print(f"No extract at {args.pbf}\nDownload it with:\n"
              "  curl -L -o data/raw/osm/geofabrik/india-latest.osm.pbf \\\n"
              "    https://download.geofabrik.de/asia/india-latest.osm.pbf")
        return 1

    print(f"[plan]  {len(cities)} cities from {args.pbf.name} "
          f"({args.pbf.stat().st_size / 1e9:.2f} GB)")
    for c in cities:
        w, s, e, n = METRO_BBOX[c]
        print(f"        {c:<10s} {(e - w) * 106:.0f} x {(n - s) * 111:.0f} km")
    print(f"[plan]  keeping {len(STREET_KEEP)} road classes, service ways excluded")
    if args.dry_run:
        print("dry run — nothing read")
        return 0

    t0 = time.time()
    coords = scan_nodes(args.pbf, cities)
    ways, refs = scan_ways(args.pbf, coords)

    results = []
    for city in cities:
        if not ways[city]:
            print(f"[skip]  {city}: no drivable ways found in the box")
            continue
        print(f"\n--- {city} ---")
        G = build_city(city, ways[city], refs[city], coords[city])
        if not G.number_of_nodes():
            print(f"[skip]  {city}: graph is empty after trimming")
            continue
        results.append(finalise_and_save(G, city, OUT))

    print(f"\n{'=' * 72}")
    print(f"{'city':<12s} {'nodes':>10s} {'edges':>11s} {'km':>10s} {'MB':>8s}")
    print("-" * 72)
    for s in results:
        print(f"{s['city']:<12s} {s['nodes']:>10,} {s['edges']:>11,} "
              f"{s['directed_km']:>10,.0f} {s['pickle_mb']:>8.1f}")
    print(f"{'=' * 72}")
    print(f"built {len(results)}/{len(cities)} in {(time.time() - t0) / 60:.1f} min")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
