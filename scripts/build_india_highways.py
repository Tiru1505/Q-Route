#!/usr/bin/env python
"""
Build the national highway graph from a Geofabrik extract.

    # once, ~1.7 GB
    curl -L --retry 3 -C - -o data/raw/osm/geofabrik/india-latest.osm.pbf \\
        https://download.geofabrik.de/asia/india-latest.osm.pbf

    python scripts/build_india_highways.py
    python scripts/build_india_highways.py --classes motorway trunk   # smaller
    python scripts/build_india_highways.py --pbf some/other.osm.pbf

Output: data/processed/india-highways/india_highways.pkl (+ _stats.json)

The extract is read twice — once for the highway ways, once for the coordinates
those ways reference — so memory stays proportional to the highway network
rather than to the 100+ million nodes in the file.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from preprocessing.india_highways import build, finalise, save      # noqa: E402
from preprocessing.osm_pbf import HIGHWAY_KEEP                      # noqa: E402

PBF = ROOT / "data" / "raw" / "osm" / "geofabrik" / "india-latest.osm.pbf"
OUT = ROOT / "data" / "processed" / "india-highways"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", type=pathlib.Path, default=PBF,
                    help="Geofabrik .osm.pbf extract")
    ap.add_argument("--classes", nargs="+", default=None,
                    help=f"highway classes to keep (default: {sorted(HIGHWAY_KEEP)})")
    ap.add_argument("--slug", default="india_highways")
    args = ap.parse_args()

    if args.classes:
        # Keeping a class without its _link roads disconnects every interchange
        # on it, so the slip roads are added back rather than silently missing.
        wanted = set(args.classes)
        wanted |= {f"{c}_link" for c in args.classes if not c.endswith("_link")}
        import preprocessing.osm_pbf as pbf_mod
        pbf_mod.HIGHWAY_KEEP = wanted
        print(f"[filter] keeping {sorted(wanted)}")

    t0 = time.time()
    G = build(args.pbf)
    if not G.number_of_nodes():
        print("Extracted graph is empty.")
        return 1

    G = finalise(G)
    stats = save(G, OUT, slug=args.slug)

    print(f"\n{'=' * 62}")
    print(f"  nodes          {stats['nodes']:>14,}")
    print(f"  edges          {stats['edges']:>14,}")
    print(f"  directed road  {stats['directed_km']:>14,.0f} km")
    print(f"  pickle         {stats['pickle_mb']:>14.1f} MB")
    print(f"  built in       {(time.time() - t0) / 60:>14.1f} min")
    print(f"  bbox           {stats['actual_bbox']}")
    print(f"{'=' * 62}")
    for hwy, n in stats["edges_by_class"].items():
        print(f"  {hwy:<18s} {n:>10,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
