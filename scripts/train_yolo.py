#!/usr/bin/env python
"""
Fine-tune YOLOv8 on DATS_2022 for Indian vehicle detection.

WHY THIS DATASET AND NOT COCO
-----------------------------
A COCO-pretrained model knows car, bus, truck and motorcycle. It has never seen
an auto-rickshaw or a tempo, which together are a large share of Hyderabad
traffic and carry their own PCU weights. DATS_2022 is annotated for Indian
roads, so the classes line up with the congestion model instead of needing a
lossy mapping.

WHY THESE SETTINGS
------------------
There is no CUDA device on this machine — the GPU is an AMD integrated part
with 0.5 GB of VRAM, which neither CUDA nor ROCm-on-Windows can use. So this
trains on 8 CPU threads, and every setting below follows from that:

  imgsz=416    640 is the usual default and roughly 2.4x slower per image. At
               416 the vehicles in these frames are still comfortably larger
               than the 8-pixel floor where small-object recall collapses.
  yolov8n      the smallest model. Anything larger is not trainable here in a
               sensible number of hours.
  pretrained   starting from COCO weights rather than scratch is what makes
               this feasible at all: the backbone already knows edges, wheels
               and vehicle-shaped blobs, so only the head has to learn the new
               classes.
  batch=8      fits comfortably in 15 GB of system RAM with workers=2.

TWO CLASSES CANNOT BE LEARNED
-----------------------------
Cart has 4 instances in the whole dataset and Cycle has 43. Those will score
near zero mAP and that is a property of the data, not a bug in the run. They
are kept so the class list matches the source, but no claim should rest on them.
"""

from __future__ import annotations

import argparse
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data/vision/dats_yolo/data.yaml"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--imgsz", type=int, default=416)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--model", default="yolov8n.pt")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--name", default="dats_v8n")
    args = ap.parse_args()

    if not DATA.exists():
        raise SystemExit(
            f"No dataset at {DATA}.\nBuild it first with scripts/prepare_yolo_data.py"
        )

    from ultralytics import YOLO

    print(f"training {args.model} on {DATA}")
    print(f"  {args.epochs} epochs @ {args.imgsz}px, batch {args.batch}, CPU")

    t0 = time.time()
    model = YOLO(args.model)
    model.train(
        data=str(DATA),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        workers=args.workers,
        device="cpu",
        project=str(ROOT / "results" / "yolo"),
        name=args.name,
        exist_ok=True,
        # Stop early if validation mAP stops improving — on CPU every wasted
        # epoch is expensive, and 25 is an upper bound rather than a target.
        patience=8,
        # Mosaic augmentation costs time and mainly helps long schedules; it is
        # turned off for the last epochs anyway, so it earns little here.
        mosaic=0.3,
        plots=True,
        verbose=True,
    )
    print(f"\ntotal {(time.time() - t0) / 60:.1f} min")
    print(f"weights: {ROOT / 'results' / 'yolo' / args.name / 'weights' / 'best.pt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
