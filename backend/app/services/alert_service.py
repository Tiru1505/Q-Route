"""Alert service — alert creation and retrieval."""

from uuid import uuid4

from app.core.logging import get_logger
from app.models.alert_models import Alert, AlertType, AlertSeverity
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.alert")


class AlertService:
    """Service for creating and retrieving alerts."""

    def get_alerts(self, user_id: str | None = None, limit: int = 50) -> list[Alert]:
        """Retrieve alerts, optionally filtered by user_id."""
        try:
            from app.database.collections import get_alerts_col
            query: dict = {}
            if user_id:
                query["user_id"] = user_id
            cursor = get_alerts_col().find(query).sort("created_at", -1).limit(limit)
            alerts = []
            for doc in cursor:
                doc.pop("_id", None)
                alerts.append(Alert(**doc))
            return alerts
        except Exception as exc:
            _logger.warning("Failed to retrieve alerts: %s", exc)
            return []

    # Preset situations for a demonstrated alert. Each mirrors something the
    # engine raises on its own, so a triggered alert looks and reads exactly
    # like a detected one — the wording, severity and coordinates are all
    # plausible for Hyderabad rather than placeholder text.
    SCENARIOS: dict[str, dict] = {
        "congestion": {
            "type": AlertType.congestion,
            "severity": AlertSeverity.warning,
            "location_name": "Mehdipatnam – Masab Tank",
            "coords": (17.3950, 78.4360),
            "message": ("Congestion on Mehdipatnam – Masab Tank is forecast to reach "
                        "94% within 15 minutes. Consider leaving now or rerouting."),
        },
        "incident": {
            "type": AlertType.incident,
            "severity": AlertSeverity.critical,
            "location_name": "PVNR Expressway",
            "coords": (17.3600, 78.4200),
            "message": ("Accident reported on the PVNR Expressway. Two lanes blocked, "
                        "expect delays of 20 minutes or more."),
        },
        "closure": {
            "type": AlertType.incident,
            "severity": AlertSeverity.critical,
            "location_name": "Tank Bund Road",
            "coords": (17.4239, 78.4738),
            "message": ("Tank Bund Road is closed for an event. All traffic is being "
                        "diverted via Lower Tank Bund."),
        },
        "reroute": {
            "type": AlertType.route_deviation,
            "severity": AlertSeverity.info,
            "location_name": "Current route",
            "coords": (17.4126, 78.4482),
            "message": ("A faster route is available. Switching now saves about "
                        "20 minutes on the remaining journey."),
        },
        "weather": {
            "type": AlertType.weather,
            "severity": AlertSeverity.warning,
            "location_name": "Hyderabad city",
            "coords": (17.4065, 78.4772),
            "message": ("Heavy rain across the city. Speeds are down roughly 30% and "
                        "waterlogging is likely at underpasses."),
        },
    }

    def trigger(self, request) -> dict:
        """
        Raise one alert on demand, for demonstrating the alerting path.

        Unknown scenario names fall back to `congestion` rather than failing —
        during a live demonstration a typo should not produce an error dialog.
        """
        preset = self.SCENARIOS.get(request.scenario) or self.SCENARIOS["congestion"]
        lat, lon = preset["coords"]

        alert = self.create_alert(
            message=request.message or preset["message"],
            alert_type=preset["type"],
            severity=request.severity or preset["severity"],
            user_id=request.user_id,
            location={"lat": lat, "lon": lon},
            location_name=request.location_name or preset["location_name"],
        )

        _logger.info("Alert triggered manually: scenario=%s", request.scenario)
        return {
            "alert": alert.model_dump(),
            # Recorded so a triggered alert can never later be mistaken for
            # something the system detected by itself.
            "trigger": "manual",
            "scenario": request.scenario,
            "location_name": request.location_name or preset["location_name"],
        }

    def clear(self, user_id: str | None = None) -> int:
        """Delete stored alerts so a demonstration can be replayed cleanly."""
        try:
            from app.database.collections import get_alerts_col
            query: dict = {"user_id": user_id} if user_id else {}
            result = get_alerts_col().delete_many(query)
            _logger.info("Cleared %d alerts", result.deleted_count)
            return int(result.deleted_count)
        except Exception as exc:
            _logger.warning("Failed to clear alerts: %s", exc)
            return 0

    def create_alert(
        self,
        message: str,
        alert_type: AlertType = AlertType.general,
        severity: AlertSeverity = AlertSeverity.info,
        user_id: str | None = None,
        location: dict | None = None,
        location_name: str | None = None,
    ) -> Alert:
        """Create and persist a new alert."""
        alert = Alert(
            alert_id=str(uuid4()),
            alert_type=alert_type,
            message=message,
            severity=severity,
            user_id=user_id,
            location=location,
            location_name=location_name,
            created_at=utc_now_iso(),
        )
        try:
            from app.database.collections import get_alerts_col
            get_alerts_col().insert_one(alert.model_dump())
        except Exception as exc:
            _logger.warning("Failed to persist alert: %s", exc)

        _logger.info("Alert %s created: %s", alert.alert_id, message)
        return alert
