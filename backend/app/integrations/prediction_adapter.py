"""Prediction adapter — the boundary between the API and the trained forecaster.

WHAT CHANGED AND WHY
--------------------
This module used to contain only ``MockPredictionAdapter``, which returned
``random.uniform(0.1, 0.9)``. Every call to /api/traffic/predict was a random
number wearing a confidence score. Meanwhile a trained LSTM sat in
results/lstm_india/ with measured accuracy, connected to nothing.

``LstmPredictionAdapter`` connects them.

THE PROBLEM IT HAS TO SOLVE
---------------------------
The model reads a run of recent 15-minute vehicle counts for a road. The
endpoint is handed a coordinate and nothing else. No road in this system keeps
a count history, so that run has to come from somewhere.

It is built by anchoring: take the congestion observed on the graph at that
point right now, convert it to a vehicle flow through Greenshields, then walk
backwards in 15-minute steps scaling by the measured daily profile. In words —
"traffic over the last hour followed the average shape of an Indian traffic
day, ending at what we observe here now".

The conversion is flow, not occupancy, and the distinction is the whole game.
Congestion says how FULL a road is; the model is trained on how many vehicles
PASS in 15 minutes. Dividing a vehicle count by segment length would confuse
the two and is the same category error the vision module refuses to make.
Greenshields relates them properly: q = k * v.

That is an assumption, and it is reported in every response rather than buried:
``data_source`` says ``lstm+anchored-history`` and ``assumption`` spells it out.
It is a far weaker claim than a genuine measured history would support, and a
far stronger one than a random number.

The quality of the answer depends on the quality of the congestion it is
anchored to. Fed the simulator, it forecasts the simulator. Fed real
observations through /api/traffic/update, the same code forecasts real traffic —
which is why the anchoring lives here rather than in the model.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.models.route_models import Coordinate

_logger = get_logger("integrations.prediction")


class BasePredictionAdapter(ABC):
    """Abstract interface that the prediction module must follow."""

    @abstractmethod
    def predict(self, location: Coordinate, horizon_minutes: int) -> dict:
        """Return a dict with 'predicted_congestion' and optional 'confidence'."""
        ...


class MockPredictionAdapter(BasePredictionAdapter):
    """Development-only placeholder — returns random predictions.

    This is NOT a real traffic prediction model. It survives only as the
    fallback for when the trained weights are missing, and it labels itself
    "mock" so nothing downstream can mistake it for a forecast.
    """

    def predict(self, location: Coordinate, horizon_minutes: int) -> dict:
        congestion = round(random.uniform(0.1, 0.9), 2)
        confidence = round(random.uniform(0.4, 0.85), 2)
        _logger.debug(
            "MockPredictionAdapter: predicted %.2f congestion (confidence %.2f) "
            "for (%.4f, %.4f) at +%d min",
            congestion, confidence, location.lat, location.lon, horizon_minutes,
        )
        return {
            "predicted_congestion": congestion,
            "confidence": confidence,
            "data_source": "mock",
            "assumption": "No model — this is a random number, not a prediction.",
        }


class LstmPredictionAdapter(BasePredictionAdapter):
    """The trained Indian-traffic LSTM, anchored to congestion observed now."""

    # A notional road used to move between congestion and a vehicle flow. The
    # same figures are used in both directions, so they cancel out of the round
    # trip and only set the scale the model is shown.
    #
    # capacity_pcu_h is NOT a free choice. For Greenshields, peak flow equals
    # capacity exactly (q_max = kj*vf/4 and kj = 4*capacity/vf), so this number
    # sets the busiest flow the notional road can carry — and therefore the
    # busiest input the model can ever be handed. Set too high, every location
    # is described to the model in vehicle counts far beyond anything in its
    # training data, the model falls back on its prior, and every prediction
    # comes back the same regardless of the road. At 1800 that is exactly what
    # happened: Hitec City and Charminar both returned 0.92.
    #
    # 1140 PCU/h is the p95 flow measured at the junction the model was trained
    # on, so a fully loaded road here looks like the busiest road it has seen
    # rather than one three times busier than anything it knows.
    SEGMENT_M = 500.0
    EDGE = {
        "length_m": SEGMENT_M,
        "free_flow_speed_kph": 40.0,
        "capacity_pcu_h": 1140.0,
    }

    # Vehicle-class shares measured at that same junction: Car 60.1%,
    # Bike 13.1%, Bus 13.4%, Truck 13.4%, giving 1.47 PCU per vehicle.
    #
    # This is deliberately NOT the congestion model's DEFAULT_FLEET_MIX, which
    # folds to 0.76 PCU per vehicle on a two-wheeler-dominated Indian street.
    # The two disagree by nearly a factor of two, and that is not a bug in
    # either: they describe different things. DEFAULT_FLEET_MIX is what the
    # congestion model assumes rolls down a Hyderabad road; this is what the
    # forecaster actually saw during training. When translating INTO the
    # model's input space, its own distribution is the one that matters.
    #
    # Worth stating plainly to anyone reading: a 60% car share is unusual for
    # an Indian junction and this one is probably not typical. It is used here
    # because it is what the weights encode, not because it describes India.
    TRAINING_MIX = {
        "CarCount": 0.601,
        "BikeCount": 0.131,
        "BusCount": 0.134,
        "TruckCount": 0.134,
    }
    TRAINING_PCU_PER_VEHICLE = 1.471

    def __init__(self) -> None:
        from app.services.forecast_service import _load

        self._forecaster, _ = _load()          # raises if untrained
        from traffic.congestion_model import CongestionModel

        self._cm = CongestionModel()

    # -- units -----------------------------------------------------------
    #
    # The model is trained on FLOW: vehicles passing a junction in 15 minutes.
    # A congestion value describes OCCUPANCY: how full the road is. Converting
    # one to the other by dividing by segment length would be the same category
    # error the vision module exists to avoid — twenty cars stopped in a jam is
    # high occupancy and near-zero flow.
    #
    # Greenshields already relates them: q = k * v. Density times speed IS flow,
    # and congestion_model.flow_pcu_h computes it. So congestion converts to a
    # real flow, and flow is what the model is handed.

    def _congestion_to_vehicles_per_15min(self, congestion: float) -> float:
        """Occupancy -> flow -> vehicles crossing in 15 minutes."""
        pcu_per_hour = self._cm.flow_pcu_h(self.EDGE, congestion)
        pcu_per_15min = pcu_per_hour / 4.0
        return pcu_per_15min / self.TRAINING_PCU_PER_VEHICLE

    def _vehicles_per_15min_to_congestion(self, vehicles: float,
                                          observed: float) -> float:
        """
        Flow -> occupancy, choosing the branch that matches what we observe.

        Greenshields flow is a parabola in density: q = kj*vf*x*(1-x) where
        x is congestion. Every flow below capacity therefore has TWO answers —
        a quiet road and a jammed one carry the same number of vehicles past a
        point. Flow alone cannot tell them apart.

        The observed state breaks the tie: if the road is currently free
        flowing, take the free-flowing root; if it is already congested, take
        the congested one. Above capacity there is no real root at all, and the
        answer is the density at capacity.
        """
        import math

        kj = self._cm.jam_density(self.EDGE)
        vf = float(self.EDGE["free_flow_speed_kph"])
        q = (vehicles * self.TRAINING_PCU_PER_VEHICLE) * 4.0   # back to PCU/h

        disc = 1.0 - 4.0 * q / (kj * vf)
        if disc <= 0.0:
            return 0.5                                          # at capacity
        root = math.sqrt(disc)
        x = (1.0 + root) / 2.0 if observed >= 0.5 else (1.0 - root) / 2.0
        return min(max(x, 0.0), self._cm.max_congestion)

    # -- history ---------------------------------------------------------
    def _history(self, congestion: float):
        """
        Vehicle counts for the last `lookback` steps, ending at now.

        Shape comes from the measured daily profile; the level is pinned to the
        congestion observed at this location.
        """
        import numpy as np
        from datetime import datetime, timedelta

        from traffic.simulator import diurnal_factor

        steps = self._forecaster.lookback
        now = datetime.now()

        vehicles_now = self._congestion_to_vehicles_per_15min(congestion)
        here = diurnal_factor(now.hour + now.minute / 60.0) or 1e-6
        split = self.TRAINING_MIX

        counts, clock = [], []
        for i in range(steps - 1, -1, -1):
            t = now - timedelta(minutes=15 * i)
            hour = t.hour + t.minute / 60.0
            scaled = vehicles_now * (diurnal_factor(hour) / here)
            counts.append([scaled * split["CarCount"], scaled * split["BikeCount"],
                           scaled * split["BusCount"], scaled * split["TruckCount"]])
            clock.append([t.hour * 60 + t.minute, t.weekday()])

        counts = np.asarray(counts, dtype="float32")
        clock = np.asarray(clock, dtype="float32")
        return counts, self._forecaster.clock_features(clock[:, 0], clock[:, 1])

    # -- real observations -----------------------------------------------
    def _observed_series(self, location: Coordinate):
        """
        A full window of REAL counts near this point, if any road has one.

        This is the difference between forecasting measured traffic and
        forecasting an assumption. Uploaded footage on a nearby road gives the
        model exactly what it was trained on — vehicles per 15 minutes — so
        when that exists it is used, and the anchoring below is not.

        Returns None when no road within range has a full window. A partial
        series is refused rather than padded: padding is how a confident number
        gets manufactured out of two data points.
        """
        import numpy as np

        from app.services.observation_store import nearest_with_series
        from forecasting.model import COUNTS

        need = self._forecaster.lookback
        found = nearest_with_series(location.lat, location.lon, need)
        if not found:
            return None

        obs = found["observations"]
        counts = np.array(
            [[float(o["counts"].get(c, 0.0)) for c in COUNTS] for o in obs],
            dtype="float32")

        # The observations carry their own wall-clock times, so the clock the
        # model sees is the clock they were taken at rather than a reconstruction.
        from datetime import datetime

        clock = np.array(
            [[(t := datetime.fromtimestamp(o["at"])).hour * 60 + t.minute,
              t.weekday()] for o in obs], dtype="float32")
        return counts, self._forecaster.clock_features(clock[:, 0], clock[:, 1]), found

    # -- prediction ------------------------------------------------------
    def predict(self, location: Coordinate, horizon_minutes: int) -> dict:
        from app.integrations.engine_bridge import RealTrafficAdapter
        from forecasting.model import COUNTS, HORIZON_MINUTES

        observed = RealTrafficAdapter().get_congestion(location)

        # Real counts win. Anchoring exists because no road here keeps a
        # history; the moment one does, using the assumption instead would be
        # perverse.
        real = self._observed_series(location)
        if real is not None:
            counts, clock, found = real
            # Named after what actually produced the counts.
            srcs = found.get("sources") or ["upload"]
            basis = f"{'+'.join(srcs)}-observations"
            near = found
        else:
            counts, clock = self._history(observed)
            basis, near = "anchored-history", None

        steps = self._forecaster.predict(counts, clock)

        # The model speaks at fixed horizons; answer with the nearest one and
        # say which, rather than silently interpolating to whatever was asked.
        idx = min(range(len(steps)),
                  key=lambda i: abs(HORIZON_MINUTES[i] - horizon_minutes))
        step = steps[idx]

        vehicles = sum(step.counts[c] for c in COUNTS)
        predicted = self._vehicles_per_15min_to_congestion(vehicles, observed)

        _logger.info(
            "LSTM prediction for (%.4f, %.4f) +%d min (model step +%d): "
            "observed %.2f -> predicted %.2f",
            location.lat, location.lon, horizon_minutes,
            HORIZON_MINUTES[idx], observed, predicted,
        )
        return {
            "predicted_congestion": round(float(predicted), 4),
            "confidence": round(float(step.confidence), 3),
            "data_source": f"lstm+{basis}",
            "observed_road": (
                {"roadId": near["road_id"], "name": near["name"],
                 "distanceM": near["distance_m"], "observations": near["depth"]}
                if near else None
            ),
            "model_horizon_minutes": HORIZON_MINUTES[idx],
            "observed_congestion": observed,
            "predicted_vehicles_15min": round(float(vehicles), 1),
            "situation": step.situation,
            "assumption": (
                f"Driven by {near['depth']} real counts from "
                f"{' and '.join(near.get('sources') or ['upload'])} on "
                f"{near['name']}, {near['distance_m']:.0f} m away. This is "
                "measured traffic, not a reconstruction."
                if near else
                "The model needs a run of recent counts and no road here keeps "
                "one. History is reconstructed by scaling the congestion "
                "observed now along the measured daily profile — an assumption, "
                "not a measurement."
            ),
        }


def get_prediction_adapter() -> BasePredictionAdapter:
    """The trained model when it is available, the random placeholder when not."""
    try:
        return LstmPredictionAdapter()
    except Exception as exc:
        _logger.warning(
            "Trained forecaster unavailable (%s) — falling back to the random "
            "placeholder. Train it with scripts/train_lstm_india.py", exc,
        )
        return MockPredictionAdapter()


# Default adapter instance
PredictionAdapter = LstmPredictionAdapter
