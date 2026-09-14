"""Prediction module status endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/prediction", tags=["prediction"])


@router.get(
    "/status",
    summary="Prediction module status",
    description=(
        "Check whether the prediction module (LSTM/GRU) is loaded and ready. "
        "Traffic predictions are served at GET /api/traffic/predict."
    ),
)
def prediction_status() -> dict[str, str]:
    return {
        "status": "adapter_placeholder",
        "data_source": "mock",
        "info": "Prediction is available at GET /api/traffic/predict. "
                "This endpoint reports module readiness only.",
    }
