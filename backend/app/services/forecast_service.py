"""
Traffic forecasting service.

Wraps the trained LSTM and the replay source. The model and weights are loaded
once per process — the network is small, so this costs a few megabytes rather
than the gigabytes the road graph needs.

Everything served here is labelled with where it came from. The forecast is a
real model output on data the model never saw during training, and the actuals
alongside it are the recorded outcome — but it is replay, not a live feed, and
the response says so in a field rather than only in documentation.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from app.core.logging import get_logger

_logger = get_logger("services.forecast")

_lock = threading.Lock()
_forecaster = None
_replay = None


def _engine_root() -> None:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _load():
    """Process-wide singletons. Cheap, but no reason to build them twice."""
    global _forecaster, _replay
    if _forecaster is None or _replay is None:
        with _lock:
            if _forecaster is None or _replay is None:
                _engine_root()
                from forecasting.model import IndiaTrafficForecaster
                from forecasting.replay import ReplaySource

                _forecaster = IndiaTrafficForecaster()
                # The replay window must match what the weights were trained
                # with, or predict() rejects the history it is handed.
                _replay = ReplaySource(lookback=_forecaster.lookback)
                _logger.info(
                    "Forecaster ready: %d held-out positions available",
                    len(_replay.cursors),
                )
    return _forecaster, _replay


class ForecastUnavailableError(RuntimeError):
    """The model has not been trained, or the series is missing."""


class ForecastService:
    def available(self) -> bool:
        try:
            _load()
            return True
        except Exception:
            return False

    def replay(self, offset: int | None = None) -> dict:
        try:
            model, source = _load()
        except FileNotFoundError as exc:
            raise ForecastUnavailableError(str(exc)) from exc

        from forecasting.model import COUNTS, SITUATIONS, pcu_of

        cursor = source.resolve(offset)
        counts, clock_raw, window = source.history(cursor)
        clock = model.clock_features(clock_raw[:, 0], clock_raw[:, 1])

        forecasts = model.predict(counts, clock)
        truth = source.truth(cursor)

        history = [
            {
                "time": str(row["Time"]),
                "pcu": round(pcu_of(row[COUNTS].to_numpy("float32")), 1),
                "situation": SITUATIONS[int(row["situation"])],
                "total": int(row["Total"]),
            }
            for _, row in window.iterrows()
        ]

        # Scored on the spot, because a forecast shown without its outcome is
        # just a claim. This is only possible because the future is recorded.
        hits = sum(f.situation == t["situation"] for f, t in zip(forecasts, truth))

        return {
            "source": "replay",
            "dataset": "Indian junction, 15-minute vehicle counts",
            "heldOut": "days 28-31, excluded from training and validation",
            "model": "LSTM, location-blind (no junction, city or coordinates)",
            "clock": source.clock_label(cursor),
            "position": {"cursor": int(cursor), "of": len(source.cursors)},
            "history": history,
            "forecast": [f.to_dict() for f in forecasts],
            "actual": truth,
            "correctThisWindow": f"{hits}/{len(forecasts)}",
        }
