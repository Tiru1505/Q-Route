#!/usr/bin/env python
"""
Make sure the road graph exists before the API starts.

WHY THIS RUNS AT STARTUP, NOT AT BUILD TIME
-------------------------------------------
On Railway and Render alike, a persistent volume is attached to the *running*
container, not to the build step. A build command that writes the graph to the
volume path writes into an ordinary directory that is then thrown away, and the
first request finds nothing. So this runs from the start command instead, once,
before uvicorn binds.

It is idempotent: if the graph is already on the volume it returns immediately,
so only the very first boot after provisioning pays the cost.

TWO WAYS TO GET THE GRAPH
-------------------------
QRO_GRAPH_URL   download a prebuilt .pkl. Fast (a couple of minutes for
                ~214 MB) and predictable. Preferred for hosting: build the
                graph once on a laptop, put it in any object store, set the
                variable.

(unset)         rebuild from OpenStreetMap with preprocessing/osm_processor.py.
                Self-contained, but it downloads and reprojects the whole
                Hyderabad metro extract, which is slow and memory-hungry — it
                can exceed the peak footprint of the API itself. Fine on a
                large instance, risky on a small one.

The graph is not in the repository because the GraphML is 575 MB and the
pickle 214 MB, both past GitHub's limit.
"""
from __future__ import annotations

import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

CITY = os.environ.get("QRO_CITY", "Hyderabad, Telangana, India")
SLUG = os.environ.get("QRO_CITY_SLUG", "hyderabad")


def _target() -> Path:
    """Where the loader will look. Kept in one place: graph_loader owns it."""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from graph.graph_loader import DEFAULT_GRAPH

    return Path(DEFAULT_GRAPH)


def _download(url: str, dest: Path) -> None:
    print(f"[ensure_graph] downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary name and move into place, so an interrupted download
    # cannot leave a half-written file that looks valid on the next boot.
    tmp = dest.with_suffix(dest.suffix + ".part")
    started = time.time()
    with urllib.request.urlopen(url) as response, open(tmp, "wb") as fh:
        shutil.copyfileobj(response, fh, length=1024 * 1024)
    tmp.replace(dest)

    mb = dest.stat().st_size / (1024 * 1024)
    print(f"[ensure_graph] downloaded {mb:.0f} MB in {time.time() - started:.0f}s")


def _build(dest: Path) -> None:
    print("[ensure_graph] building from OpenStreetMap — this is slow")
    from preprocessing.osm_processor import METRO_BBOX, build

    box = METRO_BBOX.get(SLUG)
    if box is None:
        raise SystemExit(
            f"No METRO_BBOX preset for '{SLUG}'. Set QRO_GRAPH_URL to a "
            "prebuilt graph instead, or add a bounding box for that city."
        )

    # Same arguments as the documented --metro build. The city-boundary graph
    # is not an acceptable substitute: it stops at the municipal limit and
    # returns routes shorter than the straight-line distance to the airport.
    build(CITY, SLUG, dest.parent, "drive", bbox=box)


def main() -> int:
    dest = _target()

    if dest.exists() and dest.stat().st_size > 0:
        mb = dest.stat().st_size / (1024 * 1024)
        print(f"[ensure_graph] graph already present at {dest} ({mb:.0f} MB)")
        return 0

    print(f"[ensure_graph] no graph at {dest}")
    url = os.environ.get("QRO_GRAPH_URL", "").strip()

    try:
        if url:
            _download(url, dest)
        else:
            _build(dest)
    except Exception as exc:
        # Fail loudly and stop the boot. Starting the API without a graph would
        # give a service that answers /health and 500s on everything that
        # matters, which is harder to diagnose than not starting at all.
        print(f"[ensure_graph] FAILED: {exc}", file=sys.stderr)
        return 1

    if not dest.exists():
        print(f"[ensure_graph] FAILED: nothing at {dest} afterwards", file=sys.stderr)
        return 1

    print(f"[ensure_graph] ready at {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
