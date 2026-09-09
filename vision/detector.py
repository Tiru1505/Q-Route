"""
Vehicle detection and counting from road imagery.

AN IMAGE AND A VIDEO MEASURE DIFFERENT QUANTITIES
-------------------------------------------------
This is the whole design, and getting it wrong would quietly invalidate every
number downstream.

A photograph shows the vehicles PRESENT on a stretch of road at one instant.
That is OCCUPANCY, and it converts to density (PCU per km) and from there to
congestion through the Greenshields model this project already uses.

A video shows vehicles PASSING a point over a period. That is FLOW, and it is
what the forecasting LSTM was trained on — the dataset counts vehicles crossing
a junction in each 15-minute window.

They are not interchangeable. Twenty cars standing still in a jam is high
occupancy and near-zero flow. Twenty cars sweeping past in ten seconds is the
reverse. So:

    image  -> occupancy -> density -> congestion NOW      (no forecast)
    video  -> flow      -> counts per 15 min -> forecast  (feeds the LSTM)

A single photograph therefore cannot drive the forecaster, no matter how long
we wait. That is a property of what a photograph contains, not a limitation of
the model.

WHAT THE DETECTOR ACTUALLY SEES
-------------------------------
The weights were trained on DATS_2022 at 416px on CPU, and reach mAP50 ~0.41
with recall ~0.36 — it MISSES roughly two vehicles in three. Counts from this
detector are therefore undercounts, and `calibration` exists so a measured
correction factor can be applied per camera rather than pretending the raw
number is the truth.
"""

from __future__ import annotations

import base64
import pathlib
from dataclasses import dataclass, field

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "results" / "yolo" / "dats_v8n" / "weights" / "best.pt"

# The 12 trained classes. Only the vehicles matter for traffic; person, signal,
# crossing and sign board are detected but must never enter a vehicle count.
VEHICLE_PCU = {
    "Bike": 0.5,        # two_wheeler
    "Cycle": 0.4,       # bicycle
    "Car": 1.0,
    "Rikshaw": 0.8,     # auto_rickshaw
    "Tempo": 3.0,       # light commercial, counted as a truck
    "Bus": 3.0,
    "Truck": 3.0,
    "Cart": 3.0,        # slow and wide; occupies road space like a truck
}
NON_VEHICLE = {"person", "Traffic Signal", "Zebra Crossing", "Traffic Sign Board"}

# The forecaster knows four classes. Everything the detector sees has to land in
# one of them, so the mapping is stated once, here, rather than being improvised
# at each call site.
LSTM_CLASS = {
    "Bike": "BikeCount",
    "Cycle": "BikeCount",
    "Car": "CarCount",
    "Rikshaw": "CarCount",
    "Bus": "BusCount",
    "Truck": "TruckCount",
    "Tempo": "TruckCount",
    "Cart": "TruckCount",
}
LSTM_COUNTS = ["CarCount", "BikeCount", "BusCount", "TruckCount"]


@dataclass
class Detection:
    """What was found, before any traffic interpretation."""

    counts: dict[str, int]                      # by detector class name
    pcu: float                                  # passenger car units
    lstm_counts: dict[str, int]                 # folded into the model's 4 classes
    non_vehicles: dict[str, int] = field(default_factory=dict)
    frames: int = 1
    annotated_jpeg_b64: str | None = None

    def total_vehicles(self) -> int:
        return sum(self.counts.values())


@dataclass
class VideoFlow(Detection):
    """A video additionally measures flow, which an image cannot."""

    duration_s: float = 0.0
    crossings: int = 0
    per_15_min: dict[str, int] = field(default_factory=dict)
    sampled_fps: float = 0.0


def _encode_jpeg(bgr: np.ndarray, max_width: int = 900) -> str:
    import cv2

    h, w = bgr.shape[:2]
    if w > max_width:                                   # keep the payload sane
        bgr = cv2.resize(bgr, (max_width, int(h * max_width / w)))
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _tally(class_names, calibration: float) -> tuple[dict, dict, float, dict]:
    """Split a list of detected class names into vehicles and non-vehicles."""
    counts: dict[str, int] = {}
    others: dict[str, int] = {}
    for name in class_names:
        if name in NON_VEHICLE:
            others[name] = others.get(name, 0) + 1
        elif name in VEHICLE_PCU:
            counts[name] = counts.get(name, 0) + 1

    if calibration != 1.0:
        counts = {k: int(round(v * calibration)) for k, v in counts.items()}

    pcu = sum(n * VEHICLE_PCU[k] for k, n in counts.items())
    lstm = {c: 0 for c in LSTM_COUNTS}
    for k, n in counts.items():
        lstm[LSTM_CLASS[k]] += n
    return counts, others, pcu, lstm


class RoadVisionAnalyser:
    """Loads the trained detector once and answers analysis requests."""

    def __init__(self, weights: pathlib.Path | None = None, conf: float = 0.25,
                 imgsz: int = 416, calibration: float = 1.0):
        path = pathlib.Path(weights or WEIGHTS)
        if not path.exists():
            raise FileNotFoundError(
                f"No trained detector at {path}.\n"
                "Train it with: python scripts/train_yolo.py"
            )
        from ultralytics import YOLO

        self.model = YOLO(str(path))
        self.conf = conf
        self.imgsz = imgsz
        # Recall is ~0.36, so raw counts are undercounts. A per-camera factor
        # measured by hand against a real count belongs here — not a guess.
        self.calibration = calibration
        self.weights_path = path

    # ------------------------------------------------------------- image
    def analyse_image(self, path: str, annotate: bool = True) -> Detection:
        """Occupancy: what is on the road in this frame."""
        res = self.model.predict(path, imgsz=self.imgsz, conf=self.conf,
                                 device="cpu", verbose=False)[0]
        ids = res.boxes.cls.tolist() if res.boxes is not None else []
        counts, others, pcu, lstm = _tally(
            [res.names[int(c)] for c in ids], self.calibration)
        return Detection(
            counts=counts, pcu=pcu, lstm_counts=lstm, non_vehicles=others,
            frames=1,
            annotated_jpeg_b64=_encode_jpeg(res.plot()) if annotate else None,
        )

    # ------------------------------------------------------------- video
    def analyse_video(self, path: str, sample_fps: float = 12.5,
                      max_frames: int = 150, line_y: float = 0.6,
                      annotate: bool = True) -> VideoFlow:
        """
        Flow: how many vehicles CROSS a line during the clip.

        Counting detections per frame would count one parked car once per frame.
        Tracking gives each vehicle a stable id, and the id is counted once, on
        the frame where its centre crosses the line — which is what "flow" means
        and what the forecaster was trained on.

        WHY sample_fps IS NOT LOWER
        ---------------------------
        Sampling is what makes CPU inference affordable, but a tracker needs the
        same vehicle in consecutive samples to keep its id. Sampled too sparsely,
        a vehicle appears in one frame and is gone the next, no id survives, and
        no crossing is ever recorded — the count comes back 0 with nothing to
        indicate anything went wrong. Measured on synthetic pans of a still that
        the detector reads as 7 vehicles: 12 sampled frames found 0 crossings,
        30 found 0, 60 found 3, and 120 found 4. 5 fps was the original default
        and it was silently losing almost everything.
        """
        import cv2

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {path}")

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        stride = max(int(round(src_fps / max(sample_fps, 0.1))), 1)

        seen_side: dict[int, bool] = {}      # track id -> was above the line
        counted: dict[int, str] = {}         # track id -> class, counted once
        first_annotated, processed, idx = None, 0, 0

        while processed < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride:
                idx += 1
                continue
            idx += 1
            processed += 1

            res = self.model.track(frame, imgsz=self.imgsz, conf=self.conf,
                                   device="cpu", persist=True, verbose=False,
                                   tracker="bytetrack.yaml")[0]
            if annotate and first_annotated is None:
                h, w = frame.shape[:2]
                plotted = res.plot()
                y = int(h * line_y)
                cv2.line(plotted, (0, y), (w, y), (0, 255, 255), 2)
                first_annotated = _encode_jpeg(plotted)

            if res.boxes is None or res.boxes.id is None:
                continue

            h = frame.shape[0]
            line = h * line_y
            for box, tid, cid in zip(res.boxes.xyxy.tolist(),
                                     res.boxes.id.tolist(),
                                     res.boxes.cls.tolist()):
                name = res.names[int(cid)]
                if name not in VEHICLE_PCU:
                    continue
                tid = int(tid)
                above = ((box[1] + box[3]) / 2.0) < line
                if tid in seen_side and seen_side[tid] != above and tid not in counted:
                    counted[tid] = name              # crossed, in either direction
                seen_side[tid] = above

        cap.release()
        duration = processed * stride / src_fps if src_fps else 0.0

        # counted holds one entry per vehicle that crossed the line, so its
        # values are already the list of class names to tally.
        counts, others, pcu, lstm = _tally(counted.values(), self.calibration)

        # Scale the observed flow to the 15-minute window the model expects.
        # This assumes the rate during the clip holds for the window, which is a
        # real assumption and is reported alongside the number.
        scale = (15 * 60) / duration if duration > 0 else 0.0
        per_15 = {k: int(round(v * scale)) for k, v in lstm.items()}

        return VideoFlow(
            counts=counts, pcu=pcu, lstm_counts=lstm, non_vehicles=others,
            frames=processed, annotated_jpeg_b64=first_annotated,
            duration_s=round(duration, 1), crossings=len(counted),
            per_15_min=per_15, sampled_fps=round(src_fps / stride, 1),
        )
