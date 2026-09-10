"""
Continuous traffic feed — a stand-in camera watching one road.

Reads a recorded clip on a loop and treats it exactly as a camera would be
treated. cv2.VideoCapture takes a webcam index, an RTSP URL or a file path
through the same call, so pointing this at a real feed on the day one exists
changes nothing else.

Observations it produces go to the same road store uploads use, which means the
forecaster and the routing agent consume them without knowing the difference.
"""

from __future__ import annotations

import pathlib

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger

router = APIRouter(prefix="/camera", tags=["camera"])
_logger = get_logger("api.camera")

_feed = None


def _record(state, per_15_min, lat, lon) -> None:
    """A closed bucket becomes an observation on the road being watched."""
    from app.services.observation_store import record

    record(
        road_id=state.road_id, city=state.city, name=state.road_name,
        lat=lat, lon=lon, counts=per_15_min,
        # Distinguishable from an upload for anything that cares where a
        # measurement came from.
        source="camera",
    )


def _get_feed():
    global _feed

    if _feed is None:
        from app.services.vision_service import _load
        from vision.camera import CameraFeed

        _feed = CameraFeed(_load(), on_observation=_record)
    return _feed


@router.post(
    "/start",
    summary="Start watching a road",
    description=(
        "Opens the source and counts vehicles across a line, continuously.\n\n"
        "Every frame really goes through the trained detector — the counting is "
        "not scripted. What is not real is that the footage loops, and that "
        "each bucket is scaled up to a 15-minute rate so a forecast arrives in "
        "minutes rather than an hour. Both are reported in the status.\n\n"
        "Leave `bucket_seconds` at 900 for true real time: four buckets, so the "
        "first forecast lands an hour after starting."
    ),
    responses={
        404: {"description": "Source file not found"},
        422: {"description": "Unknown city or road"},
        503: {"description": "The detector has not been trained yet"},
    },
)
def start(
    source: str = Query(..., description="Video file path, webcam index, or RTSP URL"),
    city: str = Query(..., description="City id from /vision/cities"),
    road_id: str = Query(..., description="Road id from /vision/roads"),
    bucket_seconds: float = Query(default=30.0, ge=5, le=900,
                                  description="Footage per observation; 900 is real time"),
    sample_fps: float = Query(default=12.5, ge=1, le=30),
    loop: bool = Query(default=True, description="Restart the clip when it ends"),
) -> dict:
    from app.services.location_service import resolve
    from app.services.vision_service import VisionService

    if not VisionService().available():
        raise HTTPException(status_code=503,
                            detail="Detector not trained — run scripts/train_yolo.py")

    road = resolve(city, road_id)
    if road is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown road {road_id!r} in {city!r}. See /api/vision/roads.")

    # A digit is a webcam index; anything with a scheme is a stream; otherwise
    # it must be a file that exists, and saying so beats failing silently in a
    # background thread.
    target: object = source
    if source.isdigit():
        target = int(source)
    elif "://" not in source:
        path = pathlib.Path(source)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"No such file: {source}")
        target = str(path)

    return _get_feed().start(
        source=target, city=city, road_id=road_id, road_name=road["name"],
        lat=road["lat"], lon=road["lon"],
        bucket_s=bucket_seconds, sample_fps=sample_fps, loop=loop,
    )


@router.post("/stop", summary="Stop watching")
def stop() -> dict:
    return _get_feed().stop()


@router.get(
    "/status",
    summary="What the feed is seeing",
    description=(
        "Live vehicle count for the bucket in progress, frames processed, "
        "measured fps, and the observations already handed to the forecaster."
    ),
)
def status() -> dict:
    global _feed

    if _feed is None:
        return {"running": False, "note": "No feed has been started."}
    return _feed.status()
