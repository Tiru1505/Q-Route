#!/usr/bin/env python
"""
End-to-end test of the vision -> forecasting chain.

WHAT THIS IS ACTUALLY CHECKING
------------------------------
Not "does it run without crashing" — that is easy and proves nothing. The
question is whether SIGNAL SURVIVES THE CHAIN:

    road imagery -> YOLO -> counts -> flow -> LSTM -> forecast

If a quiet road and a busy road produce the same forecast, then the detector's
output is not reaching the model in any meaningful way and the whole feature is
decorative, however impressive the screenshots look. So the test drives the real
pipeline twice, at two genuinely different traffic levels, and compares.

HOW THE CLIPS ARE MADE
----------------------
There is no video in this dataset, so clips are synthesised by panning a real
road photograph so its vehicles sweep across the counting line. The detections
are real and the tracking is real; only the camera motion is manufactured. That
is enough to exercise line-crossing, which is the part of the video path that
plain image inference does not cover.

A caveat this test cannot remove: the detector's vehicle counts are close to
unbiased in aggregate but about 1.15 vehicles off on a typical image
(results/yolo/calibration.json), and the flow figures are extrapolated from a
few seconds of footage. The test asks whether the chain RESPONDS, not whether the numbers
are correct in absolute terms.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VAL = ROOT / "data" / "vision" / "dats_yolo" / "images" / "val"

# Chosen by running the detector across the validation split: these sit at
# opposite ends of what it actually sees, rather than at ends we assumed.
QUIET = ["1634020997384.jpg", "1634020997470.jpg",
         "1634020997639.jpg", "1634020997656.jpg"]
BUSY = ["1635137342522.jpg", "1634016299562.jpg",
        "1635137342458.jpg", "1634016299451.jpg"]


def make_clip(image_path: pathlib.Path, out: pathlib.Path,
              frames: int = 180, fps: float = 25.0) -> pathlib.Path:
    """Pan a still downward so its vehicles cross the counting line."""
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)
    # Full-size frames are slow on CPU and add nothing here.
    h, w = img.shape[:2]
    if w > 1280:
        img = cv2.resize(img, (1280, int(h * 1280 / w)))
        h, w = img.shape[:2]

    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(frames):
        dy = int((i / frames) * h * 1.2) - int(h * 0.35)
        M = np.float32([[1, 0, 0], [0, 1, dy]])
        vw.write(cv2.warpAffine(img, M, (w, h), borderValue=(128, 128, 128)))
    vw.release()
    return out


def run_scenario(name: str, files: list[str], tmp: pathlib.Path) -> dict:
    """Drive the real service exactly as an upload would."""
    from app.services.vision_service import VisionService

    svc = VisionService()
    session = f"pipeline-test-{name}"
    svc.reset_window(session)

    print(f"\n{'=' * 68}\n{name.upper()} ROAD\n{'=' * 68}")
    window, total_ms = None, 0.0
    for i, fname in enumerate(files, 1):
        clip = make_clip(VAL / fname, tmp / f"{name}_{i}.mp4")
        t0 = time.perf_counter()
        # Enough sampled frames for the tracker to hold ids across the line;
        # see the measurement in RoadVisionAnalyser.analyse_video.
        r = svc.analyse(str(clip), is_video=True, session=session,
                        sample_fps=12.5, max_frames=90)
        total_ms += (time.perf_counter() - t0) * 1000

        per15 = r["per15Min"]
        window = r.get("window", {})
        print(f"  clip {i}  {fname[:26]:28s} crossings={r['crossings']:2d}  "
              f"per-15min={sum(per15.values()):5d}  window={window.get('have')}/{window.get('need')}")

    fc = (window or {}).get("forecast")
    if not fc:
        print("  NO FORECAST — window never filled")
        return {"name": name, "forecast": None}

    print(f"\n  observed PCU entering the model : {fc['observedPcu']}")
    print(f"  {'horizon':>8s} {'PCU':>9s} {'class':>9s} {'confidence':>11s}")
    print("  " + "-" * 40)
    for s in fc["steps"]:
        print(f"  {'+' + str(s['minutesAhead']) + 'm':>8s} {s['pcu']:9.1f} "
              f"{s['situation']:>9s} {s['confidence'] * 100:10.0f}%")
    print(f"\n  total detection time: {total_ms / 1000:.1f}s")
    return {"name": name, "forecast": fc, "observed": fc["observedPcu"]}


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="qro_pipeline_"))
    try:
        from app.services.vision_service import VisionService
        if not VisionService().available():
            print("Detector unavailable — run scripts/train_yolo.py first.")
            return 1

        quiet = run_scenario("quiet", QUIET, tmp)
        busy = run_scenario("busy", BUSY, tmp)

        print(f"\n{'=' * 68}\nDOES THE SIGNAL SURVIVE THE CHAIN?\n{'=' * 68}")
        if not (quiet["forecast"] and busy["forecast"]):
            print("Inconclusive: at least one scenario produced no forecast.")
            return 1

        print(f"{'horizon':>8s} {'quiet PCU':>11s} {'busy PCU':>10s} "
              f"{'difference':>12s}   classes")
        print("-" * 68)
        moved = 0
        for q, b in zip(quiet["forecast"]["steps"], busy["forecast"]["steps"]):
            diff = b["pcu"] - q["pcu"]
            if abs(diff) > 1.0:
                moved += 1
            cls = f"{q['situation']} -> {b['situation']}"
            print(f"{'+' + str(q['minutesAhead']) + 'm':>8s} {q['pcu']:11.1f} "
                  f"{b['pcu']:10.1f} {diff:+12.1f}   {cls}")

        print(f"\nobserved PCU into the model: quiet {quiet['observed']}  "
              f"busy {busy['observed']}")
        print(f"horizons where the forecast moved: {moved}/4")
        if moved == 0:
            print("\nFAIL — identical forecasts from different roads. The "
                  "detector's output is not reaching the model.")
            return 1
        print("\nPASS — the forecast tracks what the detector saw.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
