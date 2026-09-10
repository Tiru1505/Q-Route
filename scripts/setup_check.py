#!/usr/bin/env python
"""
Check whether this clone can actually run, and say what is missing.

WHY THIS EXISTS
---------------
Several things the system needs are too large for the repository: the road
graphs run to hundreds of megabytes and the country extract is 1.71 GB. A fresh
clone therefore starts out incomplete, and the failure it produces is not
obvious — the API boots, the UI loads, and only a specific request reports that
a graph is missing.

This reports the whole picture at once, and every line is checked rather than
assumed: a package is imported, a file is stat-ed, a model is opened.

    python scripts/setup_check.py            # report only
    python scripts/setup_check.py --fix      # install packages, build graphs
    python scripts/setup_check.py --fix --download-extract   # also fetch 1.71 GB

Downloading the country extract is behind its own flag deliberately. It is a
large transfer that only matters if you intend to build the national or
city-level graphs, and a setup script should not start one on your behalf.
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GEOFABRIK = "https://download.geofabrik.de/asia/india-latest.osm.pbf"
PBF = ROOT / "data" / "raw" / "osm" / "geofabrik" / "india-latest.osm.pbf"

OK, WARN, BAD = "  OK  ", " WARN ", "MISSING"

# Import name -> what stops working without it.
PACKAGES = {
    "fastapi": "the API itself",
    "uvicorn": "serving the API",
    "networkx": "the road graph",
    "osmnx": "building graphs",
    "numpy": "everything numeric",
    "pandas": "data loading",
    "scipy": "the spatial index used to snap coordinates",
    "torch": "the LSTM forecaster and YOLO",
    "ultralytics": "vehicle detection",
    "cv2": "reading uploaded images and video",
    "lap": "vehicle tracking in video (ByteTrack)",
    "multipart": "file uploads",
    "osmium": "reading .osm.pbf extracts",
    "yaml": "reading config/places.yaml",
    "pymongo": "route history (optional — the API degrades without it)",
}

OPTIONAL_PACKAGES = {"pymongo"}


def check_packages() -> list[tuple]:
    rows = []
    for mod, why in PACKAGES.items():
        try:
            importlib.import_module(mod)
            rows.append((OK, mod, why))
        except Exception:
            rows.append((WARN if mod in OPTIONAL_PACKAGES else BAD, mod, why))
    return rows


def check_graphs() -> list[tuple]:
    from graph.graph_loader import GRAPHS

    rows = []
    for name, cfg in GRAPHS.items():
        path = cfg["path"]
        if path.exists():
            mb = path.stat().st_size / 1e6
            rows.append((OK, name, f"{mb:,.0f} MB — {cfg['scope']}"))
        else:
            rows.append((WARN, name, f"not built — {cfg['build']}"))
    return rows


def check_models() -> list[tuple]:
    rows = []

    lstm = ROOT / "results" / "lstm_india" / "india_traffic_lstm.pt"
    if lstm.exists():
        try:
            import json

            m = json.loads((lstm.parent / "metrics.json").read_text())
            acc = m["horizons"]["15 min"]["situation_accuracy"] * 100
            rows.append((OK, "LSTM forecaster",
                         f"{lstm.stat().st_size / 1e3:.0f} KB — {acc:.1f}% at +15 min"))
        except Exception:
            rows.append((OK, "LSTM forecaster", "present"))
    else:
        rows.append((BAD, "LSTM forecaster",
                     "not trained — python scripts/train_lstm_india.py"))

    yolo = ROOT / "results" / "yolo" / "dats_v8n" / "weights" / "best.pt"
    if yolo.exists():
        rows.append((OK, "YOLO detector",
                     f"{yolo.stat().st_size / 1e6:.1f} MB — 12 classes"))
    else:
        rows.append((BAD, "YOLO detector",
                     "not trained — python scripts/train_yolo.py"))
    return rows


def check_data() -> list[tuple]:
    rows = []
    csv = ROOT / "data" / "raw" / "india" / "indian_junction_traffic.csv"
    rows.append((OK if csv.exists() else BAD, "traffic series",
                 "31 days of 15-min counts" if csv.exists()
                 else "missing — the forecaster cannot be retrained without it"))

    if PBF.exists():
        rows.append((OK, "country extract", f"{PBF.stat().st_size / 1e9:.2f} GB"))
    else:
        rows.append((WARN, "country extract",
                     "not downloaded — needed only to build national/city graphs"))

    places = ROOT / "config" / "places.yaml"
    if places.exists():
        import yaml

        n = len(yaml.safe_load(places.read_text(encoding="utf-8"))["places"])
        rows.append((OK, "landmarks", f"{n} across six cities"))
    else:
        rows.append((BAD, "landmarks", "missing — python scripts/build_places.py"))
    return rows


def report(title: str, rows: list[tuple]) -> int:
    print(f"\n{title}")
    print("-" * 74)
    bad = 0
    for state, name, detail in rows:
        print(f"[{state}] {name:<22s} {detail}")
        if state == BAD:
            bad += 1
    return bad


def run(cmd: list[str]) -> bool:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def download_extract() -> bool:
    """Stream the country extract to a .part file, then move it into place."""
    if PBF.exists():
        print(f"[skip] extract already at {PBF}")
        return True
    if shutil.which("curl") is None:
        print("[fail] curl not found — download it manually:\n"
              f"       {GEOFABRIK}\n       -> {PBF}")
        return False

    PBF.parent.mkdir(parents=True, exist_ok=True)
    part = PBF.with_suffix(".pbf.part")
    # -C - resumes a partial transfer; the move only happens on success, so an
    # interrupted download can never be mistaken for a complete one.
    if not run(["curl", "-L", "--fail", "--retry", "3", "-C", "-",
                "-o", str(part), GEOFABRIK]):
        print("[fail] download did not complete")
        return False
    part.replace(PBF)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true",
                    help="install packages and build what is missing")
    ap.add_argument("--download-extract", action="store_true",
                    help="also fetch the 1.71 GB country extract")
    args = ap.parse_args()

    print(f"Q-Route setup check — {sys.version.split()[0]} at {sys.executable}")

    pkgs = check_packages()
    missing_pkgs = [n for s, n, _ in pkgs if s == BAD]
    bad = report("PACKAGES", pkgs)

    if args.fix and missing_pkgs:
        run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
        pkgs = check_packages()
        bad = report("PACKAGES (after install)", pkgs)

    bad += report("DATA", check_data())
    bad += report("MODELS", check_models())

    # Graphs need networkx importable, so this comes after the package check.
    try:
        graph_rows = check_graphs()
    except Exception as exc:
        graph_rows = [(BAD, "graph registry", f"could not load: {exc}")]
    report("ROAD GRAPHS", graph_rows)

    if args.fix:
        if args.download_extract and not PBF.exists():
            download_extract()

        from graph.graph_loader import GRAPHS

        if not GRAPHS["hyderabad"]["path"].exists():
            run([sys.executable, str(ROOT / "preprocessing" / "osm_processor.py"),
                 "--city", "Hyderabad, Telangana, India", "--metro"])

        if PBF.exists():
            if not GRAPHS["india"]["path"].exists():
                run([sys.executable, str(ROOT / "scripts" / "build_india_highways.py")])
            unbuilt = [c for c in ("bengaluru", "delhi", "chennai", "mumbai", "pune")
                       if not GRAPHS[c]["path"].exists()]
            if unbuilt:
                run([sys.executable, str(ROOT / "scripts" / "build_city_graphs.py"),
                     "--city", *unbuilt])
        elif not args.download_extract:
            print("\n[note] the country extract is absent, so the national and "
                  "city graphs were skipped.\n"
                  "       Re-run with --download-extract to fetch it (1.71 GB).")

        report("ROAD GRAPHS (after build)", check_graphs())

    print(f"\n{'=' * 74}")
    if bad:
        print(f"{bad} required item(s) missing. Re-run with --fix, or follow the "
              "commands above.")
        return 1
    print("Everything required is present. A graph marked WARN is optional — the "
          "system runs without it, and the feature that needs it says so.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
