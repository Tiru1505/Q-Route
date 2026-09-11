"""Continuous traffic monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.services import monitor_service

from app.core.security import require_admin

router = APIRouter(prefix="/monitor", tags=["monitor"])

# Control-room actions: they change traffic, the monitor or shared state for
# everyone, so they need an admin session (see app/core/security.py).
_admin = [Depends(require_admin)]


@router.post(
    "/start",
    dependencies=_admin,
    summary="Start watching the active trip",
    description=(
        "Runs the decision loop on a timer instead of waiting to be asked.\n\n"
        "Each tick re-evaluates the current route against the graph as it "
        "stands, which catches a closure or a congestion spike as soon as the "
        "traffic layer applies it. The forecast is re-run only when its inputs "
        "have actually changed — new observations, a different scenario, or the "
        "driver having moved.\n\n"
        "That distinction is deliberate. The model reads 15-minute vehicle "
        "counts, so running it repeatedly inside one window returns the answer "
        "it already gave; a loop that did so would burn CPU to look busy."
    ),
)
async def start(
    tick_seconds: float = Query(default=monitor_service.DEFAULT_TICK_S, ge=1, le=600),
    graph: str | None = Query(default=None),
) -> dict:
    from app.integrations.engine_bridge import require_known_graph

    # Checked before the loop starts. Unchecked, the loop started, reported
    # running, and then failed every tick in the background.
    require_known_graph(graph)
    return await monitor_service.start(tick_s=tick_seconds, graph=graph)


@router.post(
    "/stop",
    dependencies=_admin,
    summary="Stop watching",
    description="Ends the loop and waits for the in-flight tick to finish.",
)
async def stop() -> dict:
    return await monitor_service.stop()


@router.get(
    "/status",
    summary="What the monitor has been doing",
    description=(
        "Counts, timings and the recent tick history. Each tick says whether it "
        "refreshed the forecast or reused it, so the loop can be seen working "
        "rather than taken on trust."
    ),
)
def status() -> dict:
    return monitor_service.status()
