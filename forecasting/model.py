"""
The trained Indian-traffic forecaster, loaded for serving.

WHAT IT TAKES AND WHAT IT GIVES
-------------------------------
In:  the last 3 hours of vehicle counts at one point (Car, Bike, Bus, Truck,
     every 15 minutes) plus the clock.
Out: those four counts at +15, +30, +45 and +60 minutes, and a congestion class
     for each.

The counts are the useful part. Everything else the app needs follows from
them through machinery that already exists:

    counts -> PCU -> density -> Greenshields -> congestion -> speed -> ETA

so a forecast enters the routing cost model the same way an observation does,
with no separate set of invented thresholds.

DELIBERATELY LOCATION-BLIND
---------------------------
The model is never told which junction, city or road it is looking at. That is
what allows it to be pointed at a road it has never seen. The limit of that
freedom is stated plainly in the training script: it was fitted on ONE junction
over 31 days, so it has learned the rhythm of Indian traffic rather than any
one place — but it has not been validated in a second city, and applying it
elsewhere is an extrapolation.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEIGHTS = ROOT / "results" / "lstm_india" / "india_traffic_lstm.pt"

COUNTS = ["CarCount", "BikeCount", "BusCount", "TruckCount"]
SITUATIONS = ["low", "normal", "high", "heavy"]

# Passenger Car Units — the same conversion the congestion model uses, so a
# forecast and an observation are expressed in identical units.
PCU_FACTORS = {"CarCount": 1.0, "BikeCount": 0.5, "BusCount": 3.0, "TruckCount": 3.0}

LOOKBACK = 12          # default only; the checkpoint's own value wins
# How much history the model reads is a property of the TRAINED WEIGHTS, not of
# this file. A checkpoint trained with a one-hour window cannot be served with a
# three-hour constant, so the value is read back from the checkpoint and this
# constant is only the fallback for weights saved before it was recorded.
STEPS = 4              # forecast horizon, +15 .. +60 minutes
HORIZON_MINUTES = [15, 30, 45, 60]


@dataclass
class Forecast:
    """One step of the forecast, in every unit the app needs."""

    minutes_ahead: int
    counts: dict[str, float]
    pcu: float
    situation: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "minutesAhead": self.minutes_ahead,
            "counts": {k: round(v, 1) for k, v in self.counts.items()},
            "pcu": round(self.pcu, 1),
            "situation": self.situation,
            "confidence": round(self.confidence, 3),
        }


def _build_net(hidden: int, layers: int, n_features: int):
    import torch.nn as nn

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden, layers, batch_first=True)
            self.drop = nn.Dropout(0.3)
            self.count = nn.Linear(hidden, STEPS * len(COUNTS))
            self.sit = nn.Linear(hidden, STEPS * len(SITUATIONS))

        def forward(self, x):
            h, _ = self.lstm(x)
            h = self.drop(h[:, -1, :])
            return (self.count(h).view(-1, STEPS, len(COUNTS)),
                    self.sit(h).view(-1, STEPS, len(SITUATIONS)))

    return Net()


class IndiaTrafficForecaster:
    """Loads the trained weights once and answers forecast requests."""

    def __init__(self, weights: pathlib.Path | None = None):
        import torch

        path = pathlib.Path(weights or WEIGHTS)
        if not path.exists():
            raise FileNotFoundError(
                f"No trained forecaster at {path}.\n"
                "Train it with: python scripts/train_lstm_india.py"
            )

        ck = torch.load(path, weights_only=False, map_location="cpu")
        self.lookback = int(ck.get("lookback", LOOKBACK))
        self.features = ck.get("features", "all")
        self._mu, self._sd = ck["mu"], ck["sd"]
        self._cmu, self._csd = ck["cmu"], ck["csd"]
        self.net = _build_net(ck["hidden"], ck["layers"], len(self._mu))
        self.net.load_state_dict(ck["state_dict"])
        self.net.eval()
        self._torch = torch

    @staticmethod
    def clock_features(minute_of_day: np.ndarray, dow: np.ndarray) -> np.ndarray:
        """
        The clock, encoded so that 23:45 sits next to 00:00.

        A raw 0-1439 minute counter tells the model those two are maximally far
        apart, which is the opposite of the truth and costs accuracy across
        midnight. sin/cos of the angle keeps the adjacency.
        """
        ang = 2 * np.pi * minute_of_day / 1440.0
        dang = 2 * np.pi * dow / 7.0
        return np.stack([np.sin(ang), np.cos(ang), np.sin(dang), np.cos(dang)], axis=-1)

    def predict(self, counts_history: np.ndarray, clock_history: np.ndarray) -> list[Forecast]:
        """
        counts_history : (lookback, 4) vehicle counts, oldest first
        clock_history  : (lookback, 4) clock features for those same steps
        """
        if counts_history.shape[0] != self.lookback:
            raise ValueError(
                f"need exactly {self.lookback} steps of history "
                f"({self.lookback * 15} min), got {counts_history.shape[0]}")

        x = np.concatenate([counts_history, clock_history], axis=1).astype("float32")
        xn = ((x - self._mu) / self._sd)[None, ...]

        with self._torch.no_grad():
            pc, ps = self.net(self._torch.from_numpy(xn))

        counts = pc.numpy()[0] * self._csd + self._cmu
        logits = ps.numpy()[0]
        probs = np.exp(logits - logits.max(-1, keepdims=True))
        probs /= probs.sum(-1, keepdims=True)

        out = []
        for i, mins in enumerate(HORIZON_MINUTES):
            # Counts cannot be negative; the regression head is unconstrained.
            step = np.maximum(counts[i], 0.0)
            named = {c: float(step[j]) for j, c in enumerate(COUNTS)}
            out.append(Forecast(
                minutes_ahead=mins,
                counts=named,
                pcu=sum(named[c] * PCU_FACTORS[c] for c in COUNTS),
                situation=SITUATIONS[int(probs[i].argmax())],
                confidence=float(probs[i].max()),
            ))
        return out


def pcu_of(counts: dict[str, float] | np.ndarray) -> float:
    """Passenger Car Units for a set of counts, in either shape."""
    if isinstance(counts, dict):
        return sum(counts[c] * PCU_FACTORS[c] for c in COUNTS)
    return float(sum(counts[j] * PCU_FACTORS[c] for j, c in enumerate(COUNTS)))
