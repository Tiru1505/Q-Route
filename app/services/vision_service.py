"""
Road-imagery analysis service.

Turns an uploaded photo or clip into the numbers the rest of the system already
speaks: vehicle counts by class, PCU, and — for a clip — a flow rate the
forecaster can consume.

THE TWO PATHS ARE DELIBERATELY DIFFERENT
----------------------------------------
An image yields occupancy, so it answers "how congested is this road NOW"
through Greenshields, and stops there. A clip yields flow, so it can be
appended to a rolling window and, once the window is full, drive a forecast.

Feeding an image into the forecaster would mean treating "vehicles standing in
frame" as "vehicles passing per 15 minutes". Those are different physical
quantities and the substitution would be silently wrong, so the service refuses
it rather than producing a confident bad number.

WINDOWS LIVE IN MEMORY
----------------------
Observations accumulate per session id and are lost on restart. That is
appropriate for a demo surface: nothing here is a system of record, and the
uploads themselves are never written to disk.
"""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from collections import deque
from pathlib import Path

from app.core.logging import get_logger

_logger = get_logger("services.vision")

_lock = threading.Lock()
_analyser = None

# Assumed geometry for the stretch of road visible in a still. There is no way
# to recover this from pixels without calibration, so it is a stated input with
# a default rather than a hidden constant.
DEFAULT_SEGMENT_M = 100.0
DEFAULT_FREE_FLOW_KPH = 40.0
DEFAULT_CAPACITY_PCU_H = 1800.0

# Per-session rolling windows of flow observations.
_windows: dict[str, deque] = {}
_windows_lock = threading.Lock()
MAX_SESSIONS = 32


def _engine_root() -> None:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _load():
    """Process-wide detector. Loading the weights costs a second or two."""
    global _analyser
    if _analyser is None:
        with _lock:
            if _analyser is None:
                _engine_root()
                from vision.detector import RoadVisionAnalyser

                _analyser = RoadVisionAnalyser()
                _logger.info("Vehicle detector ready: %s", _analyser.weights_path)
    return _analyser


class VisionUnavailableError(RuntimeError):
    """The detector weights are missing."""


def _congestion(pcu: float, segment_m: float) -> dict:
    """PCU on a stretch of road -> density -> Greenshields congestion."""
    _engine_root()
    from traffic.congestion_model import CongestionModel

    model = CongestionModel()
    edge = {
        "length_m": segment_m,
        "free_flow_speed_kph": DEFAULT_FREE_FLOW_KPH,
        "capacity_pcu_h": DEFAULT_CAPACITY_PCU_H,
    }
    density = pcu / max(segment_m / 1000.0, 1e-6)
    congestion = model.congestion_from_density(edge, density)
    speed = DEFAULT_FREE_FLOW_KPH * (1.0 - congestion)
    return {
        "densityPcuKm": round(density, 1),
        "congestion": round(congestion, 3),
        "level": ("low" if congestion < 0.3 else
                  "moderate" if congestion < 0.55 else
                  "heavy" if congestion < 0.8 else "severe"),
        "speedKph": round(max(speed, model.min_speed_kph), 1),
        "assumptions": {
            "segmentMetres": segment_m,
            "freeFlowKph": DEFAULT_FREE_FLOW_KPH,
            "capacityPcuH": DEFAULT_CAPACITY_PCU_H,
            "note": (
                "The visible length of road cannot be recovered from pixels. "
                f"{segment_m:.0f} m is assumed; change it to match the scene."
            ),
        },
    }


def _distribution(counts: dict) -> dict:
    """
    The vehicle mix, by count and by PCU.

    Imported inside the call for the same reason the analyser is: pulling in
    the detector module drags ultralytics and torch with it, and a process that
    never analyses anything should not pay that at import time.
    """
    from vision.detector import distribution

    return distribution(counts)


def _count_accuracy(analyser) -> dict:
    """
    How far the served detector's counts are from the truth, as measured.

    Read from results/yolo/calibration.json rather than restated, so the
    figure shown to a visitor is the one the measurement produced. The note
    that used to live here said "recall is about 0.36, so raw counts
    undercount" — the recall is real, but it is averaged over all twelve
    classes at a different threshold, and measured on vehicles at the served
    settings the detector finds 91% of the count.

    A measurement taken under different settings describes a different
    detector, so a mismatch is reported rather than the stale figures.
    """
    import json

    path = Path(__file__).resolve().parents[2] / "results" / "yolo" / "calibration.json"
    if not path.exists():
        return {
            "measured": False,
            "summary": ("Count accuracy has not been measured. Run "
                        "scripts/calibrate_yolo.py to compare this detector's "
                        "counts against labelled images."),
        }

    m = json.loads(path.read_text())
    det = m.get("detector", {})
    served = {"weights": analyser.weights_path.name,
              "conf": analyser.conf, "imgsz": analyser.imgsz}
    if any(det.get(k) != v for k, v in served.items()):
        return {
            "measured": True,
            "stale": True,
            "measuredWith": det,
            "servedWith": served,
            "summary": ("Count accuracy was measured with different detector "
                        "settings than are being served, so it does not apply. "
                        "Re-run scripts/calibrate_yolo.py."),
        }

    per = m["perClass"]
    truth = sum(c["groundTruth"] for c in per.values())
    found = sum(c["detected"] for c in per.values())
    raw = m["heldOutError"]["raw"]
    blind = sorted(n for n, c in per.items() if c["groundTruth"] and not c["detected"])
    share = found / truth if truth else 0.0

    summary = (
        f"Measured on {m['images']} labelled images at these settings, the "
        f"detector finds {share:.0%} of vehicles by count, and is about "
        f"{raw['vehicles_mae']:.2f} vehicles off on a typical image. A "
        "correction factor did not improve held-out accuracy, so none is "
        "applied. These are occupancy figures from still images; video flow "
        "has no ground truth to be measured against."
    )
    if blind:
        summary += f" Never detected in validation: {', '.join(blind)}."

    return {
        "measured": True,
        "stale": False,
        "images": m["images"],
        "countShare": round(share, 3),
        "vehiclesMae": raw["vehicles_mae"],
        "vehiclesBias": raw["vehicles_bias"],
        "blindClasses": blind,
        "bestOnHeldOut": m.get("bestOnHeldOut"),
        "appliesTo": m.get("appliesTo", "occupancy"),
        "summary": summary,
    }


class VisionService:
    def available(self) -> bool:
        try:
            _load()
            return True
        except Exception:
            return False

    def detector_info(self) -> dict:
        try:
            a = _load()
        except Exception as exc:
            return {"available": False, "reason": str(exc)}
        accuracy = _count_accuracy(a)
        return {
            "available": True,
            "weights": a.weights_path.name,
            "classes": list(a.model.names.values()),
            "confidence": a.conf,
            "imageSize": a.imgsz,
            "calibration": a.calibration,
            "countAccuracy": accuracy,
            "note": accuracy["summary"],
        }

    # ------------------------------------------------------------- analyse
    def analyse(self, path: str, is_video: bool, segment_m: float = DEFAULT_SEGMENT_M,
                session: str | None = None, sample_fps: float = 12.5,
                max_frames: int = 150, city: str | None = None,
                road_id: str | None = None) -> dict:
        try:
            analyser = _load()
        except FileNotFoundError as exc:
            raise VisionUnavailableError(str(exc)) from exc

        t0 = time.perf_counter()
        if is_video:
            det = analyser.analyse_video(path, sample_fps=sample_fps,
                                         max_frames=max_frames)
        else:
            det = analyser.analyse_image(path)
        elapsed = (time.perf_counter() - t0) * 1000

        # A count with no place attached is a detection, not an observation.
        # Resolved from the graph, so the coordinates are a real point on a real
        # road rather than whatever the caller asserted.
        from app.services.location_service import resolve as resolve_road

        road = resolve_road(city, road_id)

        out = {
            "kind": "video" if is_video else "image",
            "measures": "flow" if is_video else "occupancy",
            "observedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "city": city,
            "roadId": road_id,
            "roadName": road["name"] if road else None,
            "lat": road["lat"] if road else None,
            "lon": road["lon"] if road else None,
            "located": road is not None,
            "counts": det.counts,
            # The same counts split by number and by road space. Computed in
            # the detector module beside the PCU factors themselves, so the
            # chart cannot drift from the table the cost model uses.
            "distribution": _distribution(det.counts),
            "lstmCounts": det.lstm_counts,
            "nonVehicles": det.non_vehicles,
            "totalVehicles": det.total_vehicles(),
            "pcu": round(det.pcu, 1),
            "framesProcessed": det.frames,
            "elapsedMs": round(elapsed),
            "annotated": det.annotated_jpeg_b64,
        }

        if is_video:
            factor = (15 * 60) / det.duration_s if det.duration_s > 0 else 0.0
            out.update({
                "durationS": det.duration_s,
                "crossings": det.crossings,
                "sampledFps": det.sampled_fps,
                "per15Min": det.per_15_min,
                "extrapolationFactor": round(factor, 1),
                "flowNote": (
                    f"{det.crossings} vehicles crossed the line in "
                    f"{det.duration_s:.0f}s. The 15-minute figure multiplies that "
                    f"by {factor:.0f}x, assuming the rate holds; it is an "
                    "extrapolation, not a measurement."
                ),
                # A very short clip is multiplied by a very large number, so one
                # missed or spurious crossing moves the 15-minute figure by a lot.
                # Said out loud rather than left for the reader to work out.
                "flowWarning": (
                    f"This clip is only {det.duration_s:.0f}s long. Each crossing "
                    f"is worth {factor:.0f} vehicles per 15 min, so the estimate "
                    "is very sensitive to a single detection. Use 60s or more."
                ) if det.duration_s < 30 else None,
            })
            # Recorded against the ROAD, not just the session. The session
            # window drives this visitor's progress bar; the road store is what
            # the forecaster and the routing agent read, and without it a real
            # count on a real road never reaches the thing that routes on it.
            if road:
                from app.services.observation_store import record

                out["recorded"] = record(
                    road_id=road["road_id"], city=road["city"], name=road["name"],
                    lat=road["lat"], lon=road["lon"],
                    counts=det.per_15_min, source="upload",
                )

            if session:
                out["window"] = self._observe(session, det.per_15_min,
                                              city=city, road_id=road_id)
        else:
            out["congestion"] = _congestion(det.pcu, segment_m)
            out["forecastNote"] = (
                "A still frame measures what is present, not what passes. The "
                "forecaster is trained on vehicles per 15 minutes, so a photo "
                "cannot drive it — upload a clip for that."
            )

        return out

    # -------------------------------------------------------------- window
    def _observe(self, session: str, per_15_min: dict,
                 city: str | None = None, road_id: str | None = None) -> dict:
        """Append a flow observation and forecast once the window is full."""
        try:
            model, _ = self._forecaster()
        except Exception as exc:
            return {"error": f"forecaster unavailable: {exc}"}

        need = model.lookback
        with _windows_lock:
            if session not in _windows and len(_windows) >= MAX_SESSIONS:
                _windows.pop(next(iter(_windows)))          # oldest out
            win = _windows.setdefault(session, deque(maxlen=need))
            win.append({"counts": dict(per_15_min), "at": time.time(),
                        "roadId": road_id, "city": city})
            have = len(win)
            snapshot = list(win)

        state = {
            "have": have,
            "need": need,
            "minutesOfHistory": need * 15,
            "note": (
                f"The model reads {need} steps of 15-minute counts. Each clip "
                "supplies one step, so it is treated as one 15-minute window."
            ),
        }
        if have < need:
            state["forecast"] = None
            return state

        state["forecast"] = self._forecast_from(snapshot)
        return state

    def _forecaster(self):
        _engine_root()
        from app.services.forecast_service import _load as load_forecast
        return load_forecast()

    def _forecast_from(self, observations: list) -> dict:
        """Run the trained model over uploaded observations."""
        import numpy as np

        model, _ = self._forecaster()
        _engine_root()
        from forecasting.model import COUNTS, pcu_of

        counts = np.array(
            [[float(o["counts"][c]) for c in COUNTS] for o in observations],
            dtype="float32")

        # Uploads carry no timestamps of their own, so the clock is taken from
        # now, stepping backwards 15 minutes per observation. Stated, because
        # the model does use time of day and this choice affects the answer.
        now = time.localtime()
        minute_now = now.tm_hour * 60 + now.tm_min
        dow = (now.tm_wday) % 7
        mins = np.array([(minute_now - 15 * (len(observations) - 1 - i)) % 1440
                         for i in range(len(observations))], dtype="float32")
        clock = model.clock_features(mins, np.full(len(observations), dow, "float32"))

        forecasts = model.predict(counts, clock)
        return {
            "observedPcu": round(pcu_of(counts[-1]), 1),
            "clockUsed": {
                "minuteOfDay": int(minute_now),
                "dayOfWeek": int(dow),
                "note": ("Uploads have no timestamps, so the current wall clock "
                         "is used and earlier steps are placed 15 minutes apart."),
            },
            "steps": [f.to_dict() for f in forecasts],
        }

    def reset_window(self, session: str) -> dict:
        with _windows_lock:
            existed = _windows.pop(session, None) is not None
        return {"cleared": existed}
