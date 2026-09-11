"""AI Traffic Agent endpoints."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from graph.errors import UnknownGraphError

from app.core.security import current_user

from app.services.agent_service import (
    DEFAULT_HORIZON_MIN,
    AgentUnavailableError,
    TrafficAgent,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# Analyse, accept and decline all change the shared trip and its alert policy,
# so each needs someone signed in. Status only reads.
_signed_in = [Depends(current_user)]


@router.post(
    "/analyze",
    dependencies=_signed_in,
    summary="Should the driver reroute?",
    description=(
        "Runs the full decision loop on the active trip: forecast the road "
        "ahead, write the prediction onto the edges the driver has not reached, "
        "re-solve from the current position, and apply the alert policy.\n\n"
        "The decision is deterministic — measured ETAs against documented "
        "thresholds. No language model is involved.\n\n"
        "The forecast is reverted after the evaluation, and only edges near a "
        "sampled point on the route ahead are touched at all."
    ),
    responses={
        200: {"description": "The agent's decision, with the reasoning"},
        409: {"description": "No active trip to monitor"},
    },
)
def analyze(
    horizon_min: int = Query(default=DEFAULT_HORIZON_MIN, ge=15, le=60,
                             description="Forecast horizon; the model speaks at 15/30/45/60"),
    predictive: bool = Query(default=True,
                             description="False falls back to present conditions only"),
    force: bool = Query(default=False,
                        description="Bypass the alert policy gates and always compare"),
    graph: str | None = Query(default=None),
) -> dict:
    try:
        return TrafficAgent(graph=graph).analyse(
            horizon_min=horizon_min, apply_forecast=predictive, force=force)
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/accept",
    dependencies=_signed_in,
    summary="Driver switched to the recommended route",
    description=(
        "The recommended route becomes the active trip and monitoring "
        "continues. The response carries the new route, so the map can be "
        "redrawn from what was switched to.\n\n"
        "The assistant then checks the NEW road — forecast ahead, re-solve — "
        "and pushes what it found to /notifications/ws as a `route-check`. It "
        "runs after the response, so the switch itself is not held up by it."
    ),
)
def accept(background: BackgroundTasks, graph: str | None = Query(default=None)) -> dict:
    from app.integrations.engine_bridge import get_engine
    from app.services.helper_service import check_new_route

    from app.services import trip_service

    engine = get_engine(graph)
    if engine.trip is None:
        raise HTTPException(status_code=409, detail="No active trip.")
    # Which journey this switch belongs to, read before the engine replaces
    # its trip. The server knows; the browser is not asked.
    trip_id = trip_service.monitored_trip(engine)
    out = engine.accept_reroute()
    if out.get("ok") and out.get("newRoute"):
        if trip_id:
            trip_service.record_reroute(trip_id, engine, out)
            out["tripId"] = trip_id
        background.add_task(check_new_route, graph)
        out["routeCheck"] = "scheduled"
    return out


@router.post(
    "/decline",
    dependencies=_signed_in,
    summary="Driver kept the current route",
    description=(
        "The current route stands. Monitoring continues, and the policy's "
        "hysteresis gate means the next alert has to clear a higher bar rather "
        "than repeating the same suggestion immediately."
    ),
)
def decline(graph: str | None = Query(default=None)) -> dict:
    from app.integrations.engine_bridge import get_engine

    from app.services import trip_service

    engine = get_engine(graph)
    if engine.trip is None:
        raise HTTPException(status_code=409, detail="No active trip.")
    trip_id = trip_service.monitored_trip(engine)
    out = engine.decline_reroute()
    if out.get("ok") and trip_id:
        trip_service.record_decline(trip_id)
    return out


@router.get(
    "/status",
    summary="What the agent can see right now",
    description="Whether a trip is being monitored, and which components it depends on.",
)
def status(graph: str | None = Query(default=None)) -> dict:
    from app.integrations.engine_bridge import get_engine
    from app.services.forecast_service import ForecastService
    from app.services.vision_service import VisionService

    try:
        engine = get_engine(graph)
        trip = engine.trip
    except UnknownGraphError:
        # "Not monitoring" is true of a network that is loading; for one that
        # does not exist it is an answer to the wrong question.
        raise
    except Exception as exc:
        return {"active": False, "reason": str(exc)}

    return {
        "active": trip is not None,
        "progress": round(trip.progress, 3) if trip is not None else None,
        "alertsRaised": len(engine.alerts.history),
        "policy": {
            "minSavingMin": engine.alerts.policy.min_saving_min,
            "minSavingPct": engine.alerts.policy.min_saving_pct,
            "cooldownS": engine.alerts.policy.cooldown_s,
            "maxAlertsPerTrip": engine.alerts.policy.max_alerts_per_trip,
        },
        "depends": {
            "forecaster": ForecastService().available(),
            "detector": VisionService().available(),
            "graph": engine.G.number_of_nodes(),
        },
    }
