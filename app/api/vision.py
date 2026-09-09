"""Road-imagery analysis endpoints."""

from __future__ import annotations

import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.services.vision_service import (
    DEFAULT_SEGMENT_M,
    VisionService,
    VisionUnavailableError,
)

router = APIRouter(prefix="/vision", tags=["vision"])
_service = VisionService()

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
MAX_BYTES = 40 * 1024 * 1024          # 40 MB — a 30 s clip fits comfortably


@router.post(
    "/analyse",
    summary="Detect and count vehicles in a road image or clip",
    description=(
        "Runs the trained YOLO detector over an uploaded photo or video.\n\n"
        "A photo measures OCCUPANCY — the vehicles present — which converts to "
        "density and a congestion level for right now.\n\n"
        "A clip measures FLOW — the vehicles crossing a line — which is what the "
        "forecaster consumes. Pass a `session` and each clip is appended to a "
        "rolling window; once the window holds enough steps the response carries "
        "a forecast as well.\n\n"
        "Uploads are processed in memory and never stored."
    ),
    responses={
        200: {"description": "Detection, and a forecast once the window is full"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported file type"},
        503: {"description": "The detector has not been trained yet"},
    },
)
async def analyse(
    file: UploadFile = File(..., description="Road photo or short clip"),
    session: str | None = Form(default=None,
                               description="Groups clips into one rolling window"),
    segment_m: float = Form(default=DEFAULT_SEGMENT_M,
                            description="Assumed visible road length, metres (images)"),
    sample_fps: float = Form(default=12.5,
                             description="Frames sampled per second; below ~10 the "
                                         "tracker loses ids and crossings go uncounted"),
    max_frames: int = Form(default=150, description="Cap on frames processed (video)"),
) -> dict:
    content_type = (file.content_type or "").lower()
    if content_type in VIDEO_TYPES:
        is_video = True
    elif content_type in IMAGE_TYPES:
        is_video = False
    else:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported type {content_type!r}. Send a JPEG/PNG image or an MP4 clip.",
        )

    payload = await file.read()
    if len(payload) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is {len(payload)/1e6:.1f} MB; the limit is {MAX_BYTES/1e6:.0f} MB.",
        )
    if not payload:
        raise HTTPException(status_code=415, detail="Empty upload.")

    # OpenCV and Ultralytics both want a path. The file is written to the OS
    # temp directory, read once, and removed in the finally block — nothing the
    # user uploads is kept.
    suffix = os.path.splitext(file.filename or "")[1] or (".mp4" if is_video else ".jpg")
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(payload)
        tmp.close()
        return _service.analyse(
            tmp.name, is_video=is_video, segment_m=segment_m, session=session,
            sample_fps=sample_fps, max_frames=min(max_frames, 300),
        )
    except VisionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@router.post(
    "/reset",
    summary="Clear a session's rolling window",
    description="Drops the observations accumulated for one session id.",
)
def reset(session: str = Query(..., description="Session id to clear")) -> dict:
    return _service.reset_window(session)


@router.get(
    "/status",
    summary="Is the detector available?",
    description="Reports the trained weights, the classes, and the detector's known limits.",
)
def status() -> dict:
    return _service.detector_info()
