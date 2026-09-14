"""Traffic forecasting endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.services.forecast_service import ForecastService, ForecastUnavailableError

router = APIRouter(prefix="/forecast", tags=["forecast"])
_service = ForecastService()


@router.get(
    "/replay",
    summary="Forecast held-out traffic",
    description=(
        "Runs the trained LSTM over recorded traffic it never saw during "
        "training, and returns the forecast together with what actually "
        "happened. Replay rather than a live feed: the model needs three hours "
        "of recent vehicle counts for a road, which no live road in this system "
        "yet provides. Advances on the wall clock unless `offset` is given."
    ),
    responses={
        200: {
            "description": "Forecast and the recorded outcome beside it",
            "content": {
                "application/json": {
                    "example": {
                        "source": "replay",
                        "heldOut": "days 28-31, excluded from training and validation",
                        "clock": {"time": "8:00:00 AM", "day": "Monday", "dayOfMonth": 29},
                        "forecast": [{"minutesAhead": 60, "pcu": 141.0,
                                      "situation": "normal", "confidence": 0.72}],
                        "actual": [{"minutesAhead": 60, "pcu": 158.0, "situation": "normal"}],
                        "correctThisWindow": "3/4",
                    }
                }
            },
        },
        503: {"description": "The forecaster has not been trained yet"},
    },
)
def replay(
    offset: int | None = Query(
        default=None,
        description="Pin a specific held-out position. Omit to advance with the clock.",
    ),
) -> dict:
    try:
        return _service.replay(offset)
    except ForecastUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/status",
    summary="Is the forecaster available?",
    description="Whether trained weights and the held-out series are both present.",
)
def status() -> dict:
    ok = _service.available()
    return {
        "available": ok,
        "kind": "lstm",
        "trainedOn": "Indian junction, 15-minute vehicle counts, 31 days",
        "predicts": "vehicle counts by class -> PCU -> congestion, at +15/30/45/60 min",
        # Said plainly so nobody has to infer it from the endpoint name.
        "livePredictions": False,
        "note": (
            "Forecasts run over recorded held-out data. A live forecast needs "
            "three hours of recent vehicle counts for the road in question, "
            "which requires the camera pipeline or a traffic feed."
        ) if ok else "Model not trained — run scripts/train_lstm_india.py",
    }
