"""
AI Traffic Agent — the decision layer that ties detection, forecasting and
optimisation into one loop.

WHAT IT ADDS THAT DID NOT EXIST
-------------------------------
The reroute machinery was already complete: an active trip, a Dijkstra
re-solve from the driver's current position, a deterministic alert policy with
suppression gates, accept/decline. But it reacted to congestion that is
happening NOW. A jam only moved the route once the driver was already in it.

This service makes the loop PREDICTIVE. It asks the trained forecaster what the
road ahead will look like in fifteen to thirty minutes, writes that onto the
graph edges the driver has not reached yet, and only then asks whether a better
route exists. That is the difference between "you are stuck" and "you are about
to be stuck, turn here".

THE DECISION IS DETERMINISTIC
-----------------------------
No language model decides anything. The chain is:

    forecast -> predicted congestion on edges ahead
             -> Dijkstra re-solve from the current node
             -> measured ETA difference
             -> AlertPolicy gates (minimum saving, percentage, cooldown,
                escalation, hysteresis, per-trip cap)
             -> alert or documented silence

Every number in the alert is measured from a real route evaluation. An LLM may
later phrase the explanation, but it is handed these values; it never invents
them.

WHAT IT REFUSES TO DO
---------------------
Predicted congestion is applied ONLY to edges the forecaster was actually asked
about — the corridor ahead of the driver. There are 741,203 edges in the
Hyderabad graph and real observations for one junction; writing a forecast onto
all of them would be broadcasting a single reading across a city and calling it
prediction. Edges outside the sampled corridor keep whatever the traffic layer
already gave them, and the response says how many were touched.

The original congestion is restored after the evaluation. A forecast is a
question asked of the graph, not a permanent edit to it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.models.route_models import Coordinate

_logger = get_logger("services.agent")

# How far ahead the agent plans. 15 minutes is the forecaster's shortest
# horizon and the one where vehicle counts — rather than the clock — drive the
# prediction, which is measured in the ablation: counts-only scores 71.8% at
# +15 min and collapses to 64.5% at +60.
DEFAULT_HORIZON_MIN = 15

# Points sampled along the road ahead. Each costs one forecast, and the model
# is location-blind, so more points buy resolution in the anchoring congestion
# rather than in the model itself.
CORRIDOR_SAMPLES = 5

# An edge is "near" a sampled point if it is within this many metres.
SAMPLE_RADIUS_M = 1500.0


@dataclass
class AgentReading:
    """What the agent observed before deciding."""

    horizon_min: int
    samples: int = 0
    edges_updated: int = 0
    observed_mean: float = 0.0
    predicted_mean: float = 0.0
    worsening: bool = False
    source: str = "forecast"
    detail: list = field(default_factory=list)


class AgentUnavailableError(RuntimeError):
    """The agent cannot run — no trip, or no forecaster."""


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    import math

    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class TrafficAgent:
    """Monitors the active trip and decides whether rerouting is worth it."""

    def __init__(self, graph: str | None = None):
        self.graph = graph

    # ------------------------------------------------------------ sensing
    def _route_points(self, engine, n: int = CORRIDOR_SAMPLES):
        """Evenly spaced coordinates along the road the driver has left."""
        nodes = list(engine.trip.remaining_nodes)
        if len(nodes) < 2:
            return []
        step = max(len(nodes) // n, 1)
        picked = nodes[::step][:n]
        if nodes[-1] not in picked:
            picked.append(nodes[-1])
        return [(float(engine.G.nodes[x]["y"]), float(engine.G.nodes[x]["x"]))
                for x in picked]

    def forecast_ahead(self, engine, horizon_min: int = DEFAULT_HORIZON_MIN) -> AgentReading:
        """
        Predicted congestion for the corridor ahead, written onto its edges.

        Returns a reading describing what changed, so the caller can report it
        rather than assert it.
        """
        from app.integrations.prediction_adapter import get_prediction_adapter

        adapter = get_prediction_adapter()
        reading = AgentReading(horizon_min=horizon_min)
        reading.source = getattr(adapter, "__class__").__name__

        points = self._route_points(engine)
        if not points:
            return reading

        ahead = set(engine.trip.remaining_nodes)
        observed, predicted = [], []

        for lat, lon in points:
            try:
                out = adapter.predict(Coordinate(lat=lat, lon=lon), horizon_min)
            except Exception as exc:                     # a dead model must not
                _logger.warning("forecast failed at %.4f,%.4f: %s", lat, lon, exc)
                continue                                  # silently reroute

            obs = float(out.get("observed_congestion", 0.0) or 0.0)
            pred = float(out["predicted_congestion"])
            observed.append(obs)
            predicted.append(pred)
            reading.detail.append({
                "lat": round(lat, 5), "lon": round(lon, 5),
                "observed": round(obs, 3), "predicted": round(pred, 3),
                "situation": out.get("situation"),
                "confidence": out.get("confidence"),
            })

            # Apply to nearby edges that are still ahead of the driver. Edges
            # already passed are irrelevant, and edges elsewhere in the city
            # were never forecast.
            for node in ahead:
                nd = engine.G.nodes[node]
                if _haversine_m(lat, lon, float(nd["y"]), float(nd["x"])) > SAMPLE_RADIUS_M:
                    continue
                for _u, _v, data in engine.G.edges(node, data=True):
                    if data.get("road_status") == "closed":
                        continue                          # a closure outranks a forecast
                    engine.model.apply_edge(data, pred)
                    reading.edges_updated += 1

        reading.samples = len(predicted)
        if predicted:
            reading.observed_mean = round(sum(observed) / len(observed), 4)
            reading.predicted_mean = round(sum(predicted) / len(predicted), 4)
            reading.worsening = reading.predicted_mean > reading.observed_mean
        return reading

    # ----------------------------------------------------------- deciding
    def analyse(self, horizon_min: int = DEFAULT_HORIZON_MIN,
                apply_forecast: bool = True, force: bool = False) -> dict:
        """
        The full loop: forecast ahead, re-solve, decide, explain.

        `apply_forecast=False` reduces this to the reactive behaviour that
        existed before — useful for showing the difference, and for the case
        where no forecaster is available.
        """
        from app.integrations.engine_bridge import get_engine

        engine = get_engine(self.graph)
        if engine.trip is None:
            raise AgentUnavailableError(
                "No active trip. Optimise a route first — the agent monitors a "
                "journey, it does not invent one."
            )

        t0 = time.perf_counter()

        # Snapshot every edge we are about to touch, so a forecast is a
        # question rather than a permanent edit to the shared graph.
        snapshot = {}
        reading = AgentReading(horizon_min=horizon_min)
        if apply_forecast:
            ahead = set(engine.trip.remaining_nodes)
            for node in ahead:
                for u, v, k, data in engine.G.edges(node, keys=True, data=True):
                    snapshot.setdefault((u, v, k), float(data.get("congestion", 0.0)))
            try:
                reading = self.forecast_ahead(engine, horizon_min)
            except Exception as exc:
                _logger.warning("forecast unavailable: %s", exc)
                reading.source = "unavailable"

        try:
            decision = engine.check_reroute(force=force)
        finally:
            # Restore, whatever happened above.
            for (u, v, k), congestion in snapshot.items():
                data = engine.G[u][v][k]
                engine.model.apply_edge(data, congestion)

        elapsed = (time.perf_counter() - t0) * 1000
        return self._contract(decision, reading, elapsed, apply_forecast)

    # ---------------------------------------------------------- reporting
    def _contract(self, decision: dict, reading: AgentReading,
                  elapsed_ms: float, predictive: bool) -> dict:
        """The agent's output contract, with the reason spelled out."""
        saved = float(decision.get("timeSavedMin") or 0.0)
        alert = decision.get("alert")

        # "reroute" means the driver is actually being asked to switch, which
        # requires an alert to have survived the policy gates. The factual
        # comparison can favour an alternative that the policy then suppresses
        # for being too small — a 4.2 min saving against a 5 min floor — and
        # reporting that as "reroute" put a Switch button on screen that failed
        # when pressed, because there was no alert to accept. The comparison is
        # still reported in full; it is simply not presented as an instruction.
        should = bool(decision.get("shouldReroute")) and alert is not None
        recommended_but_suppressed = (
            bool(decision.get("shouldReroute")) and alert is None
        )

        if decision.get("blocked"):
            severity = "severe"
        elif should and saved >= 10:
            severity = "severe"
        elif should:
            severity = "moderate"
        else:
            severity = "info"

        return {
            "decision": "reroute" if should else "keep",
            # True when an alternative was genuinely better but the policy held
            # its tongue. The UI can show the numbers without offering a switch.
            "betterButBelowThreshold": recommended_but_suppressed,
            "reason": self._explain(decision, reading, predictive),
            "severity": severity,
            "alert": alert,
            "suppressedBecause": decision.get("suppressedBecause"),
            "currentEta": decision.get("currentEtaMin"),
            "alternativeEta": decision.get("newEtaMin"),
            "timeSaved": decision.get("timeSavedMin"),
            "savedPct": decision.get("savedPct"),
            "blocked": decision.get("blocked"),
            "algorithm": decision.get("algorithm"),
            "recommendedRoute": decision.get("newRoute"),
            "forecast": {
                "applied": predictive and reading.samples > 0,
                "horizonMin": reading.horizon_min,
                "samples": reading.samples,
                "edgesUpdated": reading.edges_updated,
                "observedMean": reading.observed_mean,
                "predictedMean": reading.predicted_mean,
                "worsening": reading.worsening,
                "points": reading.detail,
                "note": (
                    "Predicted congestion was written only onto edges within "
                    f"{SAMPLE_RADIUS_M / 1000:.1f} km of a sampled point on the "
                    "road ahead, and reverted after the evaluation. Edges the "
                    "forecaster was not asked about were left alone."
                ),
            },
            "analysisMs": round(elapsed_ms, 1),
        }

    def _explain(self, decision: dict, reading: AgentReading, predictive: bool) -> str:
        """
        Why the agent decided what it decided, from the numbers themselves.

        Assembled from measured values rather than written out as a template
        with blanks, so it cannot claim something the data does not show.
        """
        if decision.get("blocked"):
            return ("The road ahead on the current route is closed, so the "
                    "current plan is not driveable. A replacement was computed "
                    "from the driver's position.")

        saved = float(decision.get("timeSavedMin") or 0.0)
        pct = float(decision.get("savedPct") or 0.0)
        basis = ""
        if predictive and reading.samples:
            direction = "rising" if reading.worsening else "not rising"
            basis = (f"Forecast {reading.horizon_min} min ahead over "
                     f"{reading.samples} points on the current route: "
                     f"congestion {reading.observed_mean:.0%} now, "
                     f"{reading.predicted_mean:.0%} predicted — {direction}. ")
        elif predictive:
            basis = ("No forecast was available for the road ahead, so this "
                     "decision used present conditions only. ")

        if decision.get("shouldReroute") and decision.get("alert") is not None:
            return (f"{basis}Rerouting recommended: the alternative saves "
                    f"{saved:.1f} min ({pct:.0f}%), "
                    f"{decision.get('currentEtaMin')} min down to "
                    f"{decision.get('newEtaMin')} min, solved with "
                    f"{decision.get('algorithm') or 'Dijkstra'}.")

        suppressed = decision.get("suppressedBecause")
        if suppressed or (decision.get("shouldReroute") and not decision.get("alert")):
            why = (f": {suppressed}" if suppressed
                   else " because the saving is below the policy threshold")
            return (f"{basis}A better route exists — it would save "
                    f"{saved:.1f} min ({pct:.0f}%) — but no alert was raised{why}. "
                    "Staying on the current route.")
        return (f"{basis}Staying on the current route: "
                f"{decision.get('reason') or 'no better alternative found'}.")
