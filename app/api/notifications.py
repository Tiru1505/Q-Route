"""
Driver notifications — pushed, not polled.

The browser cannot ask often enough to feel live without hammering the API, and
a jam that forms between two polls is a jam the driver hears about late. A
WebSocket lets the backend speak first, which is what "the system notifies you"
has to mean.

A REST view of the same queue exists alongside it, because a page that has just
opened needs the recent ones and a WebSocket only carries what happens next.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.services import notify_service

router = APIRouter(prefix="/notifications", tags=["notifications"])
_logger = get_logger("api.notifications")


@router.get(
    "",
    summary="Recent notifications",
    description=(
        "The most recent notifications for this process.\n\n"
        "Each carries both the phrased text and the deterministic `facts` it "
        "was built from, so a message written by a language model can always be "
        "checked against what was actually measured."
    ),
)
@router.get("/", include_in_schema=False)
def recent(limit: int = Query(default=20, ge=1, le=50)) -> dict:
    from app.core.config import get_settings

    return {
        "notifications": notify_service.recent(limit),
        "listeners": notify_service.listener_count(),
        "phrasing": "llm" if get_settings().ai_api_key else "template",
        "note": (
            "Numbers are measured by the routing engine and the forecaster "
            "before any model is called. A language model only rewords them, "
            "and `phrasedBy` records whether it did."
        ),
    }


@router.post("/clear", summary="Discard notifications")
def clear() -> dict:
    return notify_service.clear()


@router.post(
    "/test",
    summary="Send a test notification",
    description=(
        "Publishes a notification from the agent's current view, so delivery "
        "can be checked without waiting for traffic to deteriorate. It reports "
        "whatever the agent actually decides — it does not fabricate an alert."
    ),
)
async def test(graph: str | None = Query(default=None)) -> dict:
    from app.services.agent_service import AgentUnavailableError, TrafficAgent

    try:
        decision = TrafficAgent(graph=graph).analyse(apply_forecast=False)
    except AgentUnavailableError as exc:
        # No trip is a legitimate state, and saying so beats inventing a jam.
        decision = {
            "decision": "keep",
            "severity": "info",
            "reason": str(exc),
            "currentEta": None,
            "alternativeEta": None,
            "timeSaved": 0.0,
        }
    return await notify_service.publish(decision, source="manual")


@router.websocket("/ws")
async def stream(ws: WebSocket) -> None:
    """
    Live notifications.

    Sends the recent queue on connect so a page that has just opened is not
    blank, then stays open for whatever the monitor raises next.
    """
    await ws.accept()
    notify_service.add_listener(ws)
    _logger.info("Notification listener connected (%d total)",
                 notify_service.listener_count())

    try:
        await ws.send_json({
            "type": "backlog",
            "notifications": notify_service.recent(10),
        })
        while True:
            # Nothing is expected from the client; this waits for the socket to
            # close. Reading is also what surfaces a disconnect promptly.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        _logger.debug("Notification socket closed: %s", exc)
    finally:
        notify_service.remove_listener(ws)
        _logger.info("Notification listener gone (%d left)",
                     notify_service.listener_count())
