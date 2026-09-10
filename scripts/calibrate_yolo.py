"""
Measure how far the served detector's vehicle counts are from the truth.

WHY NOT JUST DIVIDE BY RECALL
-----------------------------
The detector's reported recall is 0.36, so the obvious correction is to
multiply every count by 1 / 0.36 = 2.78. That number is wrong for this job in
three separate ways:

  1. It is averaged over all twelve classes, including zebra crossings and
     sign boards. Only eight of them are vehicles.
  2. Ultralytics reports it at the confidence threshold that maximises F1,
     not at the 0.25 the server actually runs at.
  3. Recall ignores false positives. A count is wrong by (misses - false
     detections), and scaling up also scales up the false detections.

What a count needs is the ratio of true vehicles to detected vehicles, per
class, measured with the detector exactly as it is served. That is what this
script measures, on the labelled validation images.

HOW IT AVOIDS FOOLING ITSELF
----------------------------
Factors are fitted on one half of the images and scored on the other, then
the halves swap. A factor scored on the images it was fitted to would look
better than it is.

The halves are contiguous blocks of the sorted filenames, not a random
shuffle. Most images are phone photos (IMG_1234, IMG_1235) or millisecond
timestamps, so burst shots of the same scene sort next to each other. A
random split would put near-identical frames on both sides and flatter the
result.

A class with too few detections to fit a stable ratio falls back to the pooled
ratio across all vehicles, and says so. A factor of 7.5 fitted from two
detections is noise with a decimal point.

WHAT THIS DOES NOT MEASURE
--------------------------
Flow. These are still images, so this calibrates OCCUPANCY — the vehicles
present in a frame. Video flow is counted by tracking vehicles across a line,
and a vehicle visible for thirty frames only needs to be detected in enough of
them for the tracker to hold its identity. Per-frame miss rates do not carry
over to crossings, and there are no ground-truth crossing counts here to
measure them against. The forecaster is fed by flow, so its input remains
uncalibrated, and the output file says so.

The validation set also chose which checkpoint became best.pt, so it is not a
perfectly untouched test set. There is no separate test split. The
cross-fitting guards the factors; it cannot undo that.

Usage:
    python scripts/calibrate_yolo.py
Writes:
    results/yolo/calibration.json
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vision.detector import VEHICLE_PCU, RoadVisionAnalyser  # noqa: E402

DATA = ROOT / "data" / "vision" / "dats_yolo"
OUT = ROOT / "results" / "yolo" / "calibration.json"

# The detector's class order, from its data.yaml. Read rather than restated so
# a retrained model with a different order cannot be silently mislabelled.
def _class_names() -> list[str]:
    import yaml

    return list(yaml.safe_load((DATA / "data.yaml").read_text())["names"])


BLOCK = 20              # images per contiguous block when splitting
MIN_DETECTIONS = 30     # below this a per-class ratio is too noisy to trust
REPORTED_RECALL = 0.360  # results.csv, best-mAP epoch — for comparison only


def ground_truth(label_path: pathlib.Path, names: list[str]) -> Counter:
    counts: Counter = Counter()
    if not label_path.exists():
        return counts
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        name = names[int(parts[0])]
        if name in VEHICLE_PCU:
            counts[name] += 1
    return counts


def pcu(counts: dict) -> float:
    return sum(n * VEHICLE_PCU[k] for k, n in counts.items())


def fit(rows: list[dict]) -> dict:
    """Per-class true/detected ratios, pooled where a class is too sparse."""
    gt, det = Counter(), Counter()
    for r in rows:
        gt.update(r["gt"])
        det.update(r["det"])

    pooled = sum(gt.values()) / max(sum(det.values()), 1)
    factors = {}
    for name in VEHICLE_PCU:
        if det[name] >= MIN_DETECTIONS:
            factors[name] = {"factor": gt[name] / det[name], "source": "class"}
        else:
            factors[name] = {"factor": pooled, "source": "pooled"}
    return {"factors": factors, "pooled": pooled}


def apply(det: dict, factors: dict) -> dict:
    """What the server will report: scaled, then rounded per class."""
    return {k: int(round(v * factors[k]["factor"])) for k, v in det.items()}


def score(rows: list[dict], estimate) -> dict:
    """Error in total vehicles and total PCU per image. Negative = undercount."""
    ev, ep = [], []
    for r in rows:
        est = estimate(r["det"])
        ev.append(sum(est.values()) - sum(r["gt"].values()))
        ep.append(pcu(est) - pcu(r["gt"]))
    n = max(len(rows), 1)
    return {
        "vehicles_mae": round(sum(abs(e) for e in ev) / n, 2),
        "vehicles_bias": round(sum(ev) / n, 2),
        "pcu_mae": round(sum(abs(e) for e in ep) / n, 2),
        "pcu_bias": round(sum(ep) / n, 2),
    }


def main() -> None:
    names = _class_names()
    analyser = RoadVisionAnalyser()          # the SERVED config, calibration 1.0
    images = sorted((DATA / "images" / "val").glob("*.*"))
    print(f"Detector: {analyser.weights_path.name}  conf={analyser.conf}  "
          f"imgsz={analyser.imgsz}  images={len(images)}")

    rows = []
    t0 = time.perf_counter()
    for i, img in enumerate(images):
        label = DATA / "labels" / "val" / (img.stem + ".txt")
        det = analyser.analyse_image(str(img), annotate=False).counts
        rows.append({"image": img.name, "gt": ground_truth(label, names),
                     "det": Counter(det), "block": i // BLOCK})
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(images)}  {time.perf_counter() - t0:.0f}s")

    # Two folds of alternating contiguous blocks.
    folds = [[r for r in rows if r["block"] % 2 == k] for k in (0, 1)]

    naive = 1.0 / REPORTED_RECALL
    estimators = {
        "raw": lambda d: dict(d),
        "divide_by_recall": lambda d: {k: int(round(v * naive)) for k, v in d.items()},
    }

    held_out = {name: [] for name in (*estimators, "pooled_fitted", "per_class_fitted")}
    for k in (0, 1):
        train, test = folds[1 - k], folds[k]
        fitted = fit(train)
        pooled_only = {c: {"factor": fitted["pooled"]} for c in VEHICLE_PCU}
        for name, est in estimators.items():
            held_out[name].append(score(test, est))
        held_out["pooled_fitted"].append(score(test, lambda d: apply(d, pooled_only)))
        held_out["per_class_fitted"].append(score(test, lambda d: apply(d, fitted["factors"])))

    def mean(parts: list[dict]) -> dict:
        return {m: round(sum(p[m] for p in parts) / len(parts), 2) for m in parts[0]}

    comparison = {name: mean(parts) for name, parts in held_out.items()}

    # Final factors are fitted on everything; the held-out scores above are
    # the honest estimate of how well factors fitted this way generalise.
    final = fit(rows)
    gt_all, det_all = Counter(), Counter()
    for r in rows:
        gt_all.update(r["gt"])
        det_all.update(r["det"])

    per_class = {
        name: {
            "groundTruth": gt_all[name],
            "detected": det_all[name],
            "factor": round(final["factors"][name]["factor"], 3),
            "source": final["factors"][name]["source"],
        }
        for name in VEHICLE_PCU
    }

    best = min(comparison, key=lambda n: comparison[n]["pcu_mae"])
    out = {
        "measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "detector": {"weights": analyser.weights_path.name,
                     "conf": analyser.conf, "imgsz": analyser.imgsz},
        "images": len(rows),
        "split": f"2-fold, alternating contiguous blocks of {BLOCK} sorted filenames",
        "minDetectionsPerClass": MIN_DETECTIONS,
        "pooledFactor": round(final["pooled"], 3),
        "perClass": per_class,
        "heldOutError": comparison,
        "bestOnHeldOut": best,
        "appliesTo": "occupancy",
        "caveats": [
            "Measured on still images: this calibrates occupancy counts only. "
            "Video flow is counted by line-crossing with a tracker; per-frame "
            "misses do not translate to missed crossings, and no ground-truth "
            "crossing counts exist to measure it. The forecaster's input is "
            "flow and remains uncalibrated.",
            "The validation set selected best.pt, so it is not an untouched "
            "test set. Cross-fitting protects the factors from being scored on "
            "their own fitting data; it cannot remove that selection effect.",
            "Factors hold for this dataset's cameras and scenes. A new camera "
            "angle, height or resolution changes the miss rate.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))

    print(f"\nDone in {time.perf_counter() - t0:.0f}s. Wrote {OUT.relative_to(ROOT)}\n")
    print(f"{'class':9s} {'truth':>6s} {'found':>6s} {'factor':>7s}  source")
    for name, c in per_class.items():
        print(f"{name:9s} {c['groundTruth']:6d} {c['detected']:6d} {c['factor']:7.3f}  {c['source']}")
    print(f"\nHeld-out error per image (negative bias = undercount):")
    print(f"{'estimator':18s} {'veh MAE':>8s} {'veh bias':>9s} {'PCU MAE':>8s} {'PCU bias':>9s}")
    for name, s in comparison.items():
        mark = "  <- best" if name == best else ""
        print(f"{name:18s} {s['vehicles_mae']:8.2f} {s['vehicles_bias']:9.2f} "
              f"{s['pcu_mae']:8.2f} {s['pcu_bias']:9.2f}{mark}")


if __name__ == "__main__":
    main()
