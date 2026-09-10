"""Pydantic models for alert and notification endpoints."""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.route_models import Coordinate


class AlertType(str, Enum):
    congestion = "congestion"
    incident = "incident"
    weather = "weather"
    route_deviation = "route_deviation"
    general = "general"


class AlertSeverity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class TriggerAlertRequest(BaseModel):
    """
    Raise an alert on demand.

    The alerting path normally fires only when traffic actually deteriorates
    past the policy gates, which is the right behaviour and impossible to
    schedule for a live demonstration. This lets one be raised deliberately.
    It produces a genuine alert through the same service and storage as an
    automatic one — `trigger: "manual"` in its metadata is the only difference,
    so nothing here can be mistaken later for something the system detected.
    """

    scenario: str = Field(
        default="congestion",
        description="Which preset situation to raise: congestion, incident, "
                    "closure, reroute, or weather",
    )
    message: str | None = Field(
        default=None, max_length=400,
        description="Overrides the preset wording when supplied",
    )
    severity: AlertSeverity | None = Field(
        default=None, description="Overrides the preset severity",
    )
    location_name: str | None = Field(
        default=None, max_length=120,
        description="Where it is happening; defaults to the preset's location",
    )
    user_id: str | None = None


class Alert(BaseModel):
    alert_id: str
    alert_type: AlertType = AlertType.general
    message: str
    severity: AlertSeverity = AlertSeverity.info
    user_id: str | None = None
    location: Coordinate | None = None
    # A readable place for the UI. Without it the interface has only a
    # coordinate pair to show, which means nothing to a driver.
    location_name: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
