"""Alert and notification API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.models.alert_models import Alert, TriggerAlertRequest
from app.services.alert_service import AlertService

from app.core.security import require_admin

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Control-room actions: they change traffic, the monitor or shared state for
# everyone, so they need an admin session (see app/core/security.py).
_admin = [Depends(require_admin)]
_service = AlertService()


@router.get(
    "/",
    response_model=list[Alert],
    summary="Get alerts",
    description="Retrieve active alerts. Optionally filter by user_id.",
)
def alerts(
    user_id: str | None = Query(default=None, description="Filter by user ID"),
    limit: int = Query(default=50, ge=1, le=200, description="Max alerts to return"),
) -> list[Alert]:
    return _service.get_alerts(user_id=user_id, limit=limit)


@router.post(
    "/trigger",
    dependencies=_admin,
    summary="Raise an alert on demand",
    description=(
        "Create a real alert immediately, for demonstrating the alerting path "
        "without waiting for traffic to deteriorate on its own. The alert is "
        "persisted and returned by GET /alerts/ exactly like an automatic one — "
        "the only difference is what caused it, which is recorded in the "
        "alert's own metadata."
    ),
)
def trigger_alert(request: TriggerAlertRequest) -> dict:
    return _service.trigger(request)


@router.post(
    "/clear",
    dependencies=_admin,
    summary="Clear alerts",
    description="Remove alerts so a demo can be run again from a clean slate.",
)
def clear_alerts(user_id: str | None = Query(default=None)) -> dict:
    return {"cleared": _service.clear(user_id=user_id)}


