"""
A continuous vehicle-counting feed.

WHAT THIS IS FOR
----------------
The system was built to consume a camera watching a road. Getting a real
municipal CCTV feed before a demonstration is not realistic, so this reads a
recorded clip on a loop and treats it exactly as it would treat a camera.

The substitution is one line — cv2.VideoCapture takes a webcam index, an RTSP
URL or a file path through the same call — and everything downstream is
identical. Point it at rtsp://… on the day a real feed exists and nothing else
changes.

WHAT IS REAL HERE AND WHAT IS NOT
---------------------------------
REAL: the detection, the tracking, the line crossings, the PCU conversion, the
forecast that consumes them and the routing decision that follows. Every frame
is genuinely run through the trained detector; no counts are scripted.

NOT REAL: the footage repeats, and time may be compressed. Both are reported on
every observation — `feed` says "recorded-loop", and a compressed run stamps
its factor — because a looping clip presented as a live feed, or thirty seconds
presented as fifteen minutes, is the kind of claim one question destroys.

WHY TIME COMPRESSION EXISTS AT ALL
----------------------------------
The forecaster reads vehicles-per-15-minutes and needs four of those buckets,
so a genuinely real-time feed produces its first forecast one hour after being
switched on. That is correct and useless in a ten-minute demonstration.

Compressing the bucket keeps every real part real — the same frames, the same
detector, the same model — and speeds up only the clock. The scaling to a
15-minute rate is stated, so the number can be read for what it is.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from app.core.logging import get_logger

_logger = get_logger("vision.camera")

# Frames sampled per second. Measured: below about 10 the tracker loses ids
# between samples and crossings go uncounted entirely.
DEFAULT_SAMPLE_FPS = 12.5

# Seconds of footage per observation. 900 is a true 15-minute bucket; the
# default is compressed so a demonstration reaches a forecast in minutes.
REAL_BUCKET_S = 900.0
DEFAULT_BUCKET_S = 30.0

RECENT = 24


@dataclass
class FeedState:
    running: bool = False
    source: str = ""
    kind: str = "recorded-loop"
    city: str | None = None
    road_id: str | None = None
    road_name: str | None = None
    bucket_s: float = DEFAULT_BUCKET_S
    started_at: float = 0.0
    frames: int = 0
    loops: int = 0
    crossings_total: int = 0
    bucket_started_at: float = 0.0
    bucket_counts: dict = field(default_factory=dict)
    observations: int = 0
    last_error: str | None = None
    recent: deque = field(default_factory=lambda: deque(maxlen=RECENT))


class CameraFeed:
    """Reads a source frame by frame and emits one observation per bucket."""

    def __init__(self, analyser, on_observation=None):
        self.analyser = analyser
        self.on_observation = on_observation
        self.state = FeedState()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------ control
    def start(self, source, city, road_id, road_name, lat, lon,
              bucket_s: float = DEFAULT_BUCKET_S,
              sample_fps: float = DEFAULT_SAMPLE_FPS,
              line_y: float = 0.6, loop: bool = True) -> dict:
        if self.state.running:
            self.stop()

        s = self.state = FeedState()
        s.running = True
        s.source = str(source)
        s.kind = "recorded-loop" if loop else "stream"
        s.city, s.road_id, s.road_name = city, road_id, road_name
        s.bucket_s = max(float(bucket_s), 5.0)
        s.started_at = s.bucket_started_at = time.time()
        s.bucket_counts = {}

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(source, lat, lon, sample_fps, line_y, loop),
            daemon=True,
            name="camera-feed",
        )
        self._thread.start()
        _logger.info("Camera feed started on %s -> %s", source, road_name)
        return self.status()

    def stop(self) -> dict:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=10)
        self.state.running = False
        _logger.info("Camera feed stopped after %d frames, %d observations",
                     self.state.frames, self.state.observations)
        return self.status()

    # --------------------------------------------------------------- loop
    def _run(self, source, lat, lon, sample_fps, line_y, loop) -> None:
        import cv2

        from vision.detector import LSTM_COUNTS, VEHICLE_PCU, LSTM_CLASS

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            self.state.last_error = f"could not open {source!r}"
            self.state.running = False
            _logger.warning("Camera feed could not open %s", source)
            return

        src_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        stride = max(int(round(src_fps / max(sample_fps, 0.1))), 1)
        frame_gap = 1.0 / max(sample_fps, 0.1)

        seen_side: dict[int, bool] = {}
        counted: set[int] = set()
        idx = 0

        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    if not loop:
                        break
                    # Rewind. Track ids restart, which is correct — the same
                    # vehicle coming round again is a new passage past the line,
                    # exactly as a different car would be on a live road.
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    seen_side.clear()
                    counted.clear()
                    with self._lock:
                        self.state.loops += 1
                    continue

                idx += 1
                if idx % stride:
                    continue

                t0 = time.perf_counter()
                try:
                    res = self.analyser.model.track(
                        frame, imgsz=self.analyser.imgsz, conf=self.analyser.conf,
                        device="cpu", persist=True, verbose=False,
                        tracker="bytetrack.yaml")[0]
                except Exception as exc:
                    self.state.last_error = str(exc)[:160]
                    _logger.warning("detector failed on a frame: %s", exc)
                    continue

                with self._lock:
                    self.state.frames += 1

                if res.boxes is not None and res.boxes.id is not None:
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
                            counted.add(tid)
                            with self._lock:
                                cls = LSTM_CLASS[name]
                                self.state.bucket_counts[cls] = (
                                    self.state.bucket_counts.get(cls, 0) + 1)
                                self.state.crossings_total += 1
                        seen_side[tid] = above

                if (time.time() - self.state.bucket_started_at) >= self.state.bucket_s:
                    self._close_bucket(lat, lon)

                # Pace to the sampling rate so a fast file is not devoured at
                # disk speed — a feed should behave like a feed.
                spent = time.perf_counter() - t0
                if frame_gap > spent:
                    self._stop.wait(frame_gap - spent)
        finally:
            cap.release()
            with self._lock:
                self.state.running = False

    def _close_bucket(self, lat, lon) -> None:
        """Turn the bucket's crossings into one observation and hand it on."""
        from vision.detector import LSTM_COUNTS

        with self._lock:
            elapsed = max(time.time() - self.state.bucket_started_at, 1e-6)
            raw = dict(self.state.bucket_counts)
            self.state.bucket_counts = {}
            self.state.bucket_started_at = time.time()

        # Scale the observed passage rate to the 15 minutes the model reads.
        factor = REAL_BUCKET_S / elapsed
        per_15 = {c: int(round(raw.get(c, 0) * factor)) for c in LSTM_COUNTS}

        record = {
            "at": time.time(),
            "elapsedS": round(elapsed, 1),
            "crossings": sum(raw.values()),
            "per15Min": per_15,
            "scaleFactor": round(factor, 1),
            "timeCompressed": self.state.bucket_s < REAL_BUCKET_S,
        }
        with self._lock:
            self.state.observations += 1
            self.state.recent.appendleft(record)

        if self.on_observation:
            try:
                self.on_observation(self.state, per_15, lat, lon)
            except Exception as exc:
                _logger.warning("observation handler failed: %s", exc)

    # ------------------------------------------------------------- status
    def status(self) -> dict:
        s = self.state
        with self._lock:
            live = dict(s.bucket_counts)
            uptime = time.time() - s.started_at if s.started_at else 0.0
            bucket_age = time.time() - s.bucket_started_at if s.bucket_started_at else 0.0
            recent = list(s.recent)

        return {
            "running": s.running,
            "source": s.source,
            "feed": s.kind,
            "city": s.city,
            "roadId": s.road_id,
            "roadName": s.road_name,
            "uptimeS": round(uptime, 1),
            "framesProcessed": s.frames,
            "fps": round(s.frames / uptime, 1) if uptime > 1 else None,
            "loops": s.loops,
            "crossingsTotal": s.crossings_total,
            "liveCounts": live,
            "liveTotal": sum(live.values()),
            "bucketSeconds": s.bucket_s,
            "bucketAgeS": round(bucket_age, 1),
            "nextObservationInS": round(max(s.bucket_s - bucket_age, 0), 1),
            "observations": s.observations,
            "timeCompressed": s.bucket_s < REAL_BUCKET_S,
            "compressionFactor": (round(REAL_BUCKET_S / s.bucket_s, 1)
                                  if s.bucket_s < REAL_BUCKET_S else 1.0),
            "recent": recent,
            "lastError": s.last_error,
            "note": (
                "Detection, tracking and counting are real — every frame goes "
                "through the trained detector. The footage repeats, and each "
                "bucket is scaled to a 15-minute rate; both are reported rather "
                "than presented as a live camera."
            ),
        }
