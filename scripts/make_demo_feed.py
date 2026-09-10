#!/usr/bin/env python
"""
Build a clip for the camera feed to watch.

    python scripts/make_demo_feed.py                       # from the dataset
    python scripts/make_demo_feed.py --from my_traffic.mp4 # use real footage

WHY THIS EXISTS
---------------
The camera feed needs something to watch, and a real municipal CCTV stream is
not obtainable before a demonstration. If you have footage of an Indian road,
use it with --from and this only copies it into place; that is the better
demonstration and the counting is entirely genuine.

Without footage, this pans across real photographs from the DATS_2022 set so
their vehicles sweep past the counting line. The detections and the tracking
are real — the vehicles are real vehicles in real Indian traffic — and only the
camera motion is manufactured. Say that plainly when showing it; a synthetic
pan described as CCTV is the kind of claim one question destroys.

WHY PANNING AT ALL
------------------
Counting is done by line crossing, not by counting boxes per frame, because a
parked car in view would otherwise be counted once per frame. Crossing needs
motion, and a still photograph has none.
"""

from __future__ import annotations

import argparse
import pathlib
import random
import shutil
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VAL = ROOT / "data" / "vision" / "dats_yolo" / "images" / "val"
OUT = ROOT / "data" / "vision" / "demo_feed.mp4"


def build(images: list[pathlib.Path], out: pathlib.Path,
          per_image: int = 90, fps: float = 25.0, width: int = 1280) -> pathlib.Path:
    import cv2

    first = cv2.imread(str(images[0]))
    if first is None:
        raise SystemExit(f"Could not read {images[0]}")
    h, w = first.shape[:2]
    if w > width:
        h, w = int(h * width / w), width

    out.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

    frames = 0
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            print(f"  skipped unreadable {path.name}")
            continue
        img = cv2.resize(img, (w, h))
        for i in range(per_image):
            # Pan downward so vehicles cross the line at 60% height.
            dy = int((i / per_image) * h * 1.3) - int(h * 0.4)
            m = np.float32([[1, 0, 0], [0, 1, dy]])
            writer.write(cv2.warpAffine(img, m, (w, h), borderValue=(120, 120, 120)))
            frames += 1
        print(f"  {path.name[:38]:40s} {per_image} frames")

    writer.release()
    return out, frames, fps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=None,
                    help="use real footage instead of building one")
    ap.add_argument("--images", type=int, default=8, help="how many stills to pan")
    ap.add_argument("--per-image", type=int, default=90, help="frames per still")
    ap.add_argument("--out", type=pathlib.Path, default=OUT)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    if args.src:
        src = pathlib.Path(args.src)
        if not src.exists():
            print(f"No such file: {src}")
            return 1
        args.out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, args.out)
        print(f"Copied real footage to {args.out}")
        print("Counting from this is genuine end to end — nothing is synthetic.")
        return 0

    if not VAL.exists():
        print(f"No imagery at {VAL}. Build the YOLO dataset first.")
        return 1

    pool = sorted(VAL.glob("*"))
    if not pool:
        print("No validation images found.")
        return 1

    random.seed(args.seed)
    picked = random.sample(pool, min(args.images, len(pool)))
    print(f"Panning {len(picked)} real road photographs:")
    out, frames, fps = build(picked, args.out, per_image=args.per_image)

    print(f"\nwrote {out}  ({frames} frames, {frames / fps:.0f}s at {fps:.0f}fps)")
    print("\nThe vehicles are real and the detector's counts will be real.")
    print("The CAMERA MOTION is synthetic — say so when demonstrating it.")
    print("\nStart the feed with:")
    print(f'  POST /api/camera/start?source={out}'
          "&city=hyderabad&road_id=hyderabad:inner-ring-road&bucket_seconds=30")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
