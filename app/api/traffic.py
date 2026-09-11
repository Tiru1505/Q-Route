"""Traffic data API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.models.route_models import Coordinate
from app.models.traffic_models import TrafficPrediction, TrafficUpdate
from app.services.prediction_service import PredictionService
from app.services.traffic_service import TrafficService

from app.core.security import require_admin

router = APIRouter(prefix="/traffic", tags=["traffic"])

# Control-room actions: they change traffic, the monitor or shared state for
# everyone, so they need an admin session (see app/core/security.py).
_admin = [Depends(require_admin)]
_traffic_service = TrafficService()
_prediction_service = PredictionService()


@router.get(
    "/current",
    summary="Get current traffic data",
    description="Retrieve the latest traffic records across monitored road segments.",
    responses={
        200: {"description": "Current traffic snapshot"},
        503: {"description": "Traffic data unavailable"},
    },
)
def current_traffic() -> dict:
    snapshot = _traffic_service.get_current()
    return snapshot.model_dump()


@router.post(
    "/update",
    dependencies=_admin,
    summary="Push traffic data update",
    description="Ingest new traffic records from sensors, APIs, or manual input.",
    responses={
        200: {"description": "Records accepted"},
        422: {"description": "Validation error"},
    },
)
def update_traffic(payload: TrafficUpdate) -> dict:
    count = _traffic_service.update(payload.records)
    return {
        "updated": count,
        "metadata": {
            "data_source": getattr(_traffic_service.adapter, "data_source", "unknown"),
        },
    }


@router.get(
    "/predict",
    response_model=TrafficPrediction,
    summary="Predict future traffic congestion",
    description=(
        "Generate a traffic congestion prediction for a specific location "
        "and time horizon. Uses the prediction adapter (LSTM/GRU when available)."
    ),
    responses={
        200: {
            "description": "Traffic prediction",
            "content": {
                "application/json": {
                    "example": {
                        "location": {"lat": 17.385, "lon": 78.4867},
                        "horizon_minutes": 30,
                        "predicted_congestion": 0.65,
                        "confidence": 0.72,
                        "metadata": {"data_source": "mock"},
                    }
                }
            },
        },
        500: {"description": "Prediction failed"},
    },
)
def predict_traffic(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    horizon_minutes: int = Query(default=30, gt=0, le=1440, description="Prediction horizon in minutes"),
) -> TrafficPrediction:
    location = Coordinate(lat=lat, lon=lon)
    return _prediction_service.predict(location, horizon_minutes)
