"""
The demo's pipeline, with nobody pressing anything.

    spike the road ahead  ->  the monitor alerts on its own
    ->  the driver switches  ->  the assistant checks the new road

The dashboard used to raise its own alert: two mock segments painted red and a
hard-coded "Mehdipatnam – Masab Tank, 62% -> 94% in 15 min" that nothing had
computed. These tests hold the replacement to what the system actually does.

THE RACE THEY ALSO GUARD
------------------------
The monitor's forecast writes predicted congestion onto the road ahead,
re-solves, and restores a snapshot. A spike applied in the middle of that was
overwritten by the restore and lost — the monitor then said "keep" forever. It
was measured, not hypothesised: a spike right after `advance` produced no
alert; the same spike eight seconds later alerted in six. The engine now holds
a lock across the overlay, and the test below reproduces the collision on
purpose.
"""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

START = {"lat": 17.4435, "lon": 78.3772}
END = {"lat": 17.3616, "lon": 78.4747}


def _wait_for(c, pred, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        notes = c.get("/api/notifications?limit=30").json()["notifications"]
        hit = next((n for n in notes if pred(n)), None)
        if hit:
            return hit
        time.sleep(0.5)
    return None


def _new_trip(c):
    r = c.post("/api/routes/optimize",
               json={"source": START, "destination": END, "algorithm": "dijkstra"})
    assert r.status_code == 200, r.text


def test_the_monitor_alerts_on_its_own_and_the_robot_checks_the_new_route():
    with TestClient(app) as c:
        c.post("/api/notifications/clear")
        c.post("/api/simulation/event?scenario=normal")
        try:
            for run in (1, 2):
                _new_trip(c)
                c.post("/api/monitor/start?tick_seconds=1")
                c.post("/api/simulation/advance?progress=0.3")
                t = time.time()
                # No pause: the spike lands while the monitor is likely still
                # forecasting the new trip, which is the case that used to fail.
                c.post("/api/simulation/congest-route?level=0.92")

                alert = _wait_for(c, lambda n: n.get("kind") == "alert"
                                  and n.get("actionable") and n["at"] >= t)
                assert alert, (
                    f"run {run}: the monitor raised no alert — "
                    f"{c.get('/api/monitor/status').json()['history'][:3]}")
                # Run 2 proves the policy's memory belongs to the trip: a new
                # journey within five minutes must not inherit the cooldown.

                acc = c.post("/api/agent/accept").json()
                assert acc["ok"], acc
                assert acc["newRoute"]["path"], "switching returned nothing to draw"
                assert acc["timeSavedMin"] > 0
                assert acc["newEtaMin"] < acc["previousEtaMin"]

                ta = time.time()
                check = _wait_for(c, lambda n: n.get("kind") == "route-check" and n["at"] >= ta - 1)
                assert check, f"run {run}: the assistant never checked the new route"
                assert check["actionable"] is False, "a route check reports; it never asks to act"
                assert "new route" in check["text"] and "min" in check["text"]
        finally:
            c.post("/api/monitor/stop")


def test_a_suggestion_can_be_answered_once():
    """Two tabs in Demo Mode both auto-switching must not count one switch twice."""
    with TestClient(app) as c:
        c.post("/api/simulation/event?scenario=normal")
        _new_trip(c)
        c.post("/api/simulation/advance?progress=0.3")
        c.post("/api/simulation/congest-route?level=0.92")
        d = c.post("/api/agent/analyze?predictive=false").json()
        assert d["decision"] == "reroute", d.get("reason")

        first = c.post("/api/agent/accept").json()
        second = c.post("/api/agent/accept").json()
        assert first["ok"] is True
        assert second["ok"] is False and "already accepted" in second["reason"]
        assert c.post("/api/agent/decline").json()["ok"] is False


def test_a_spike_during_a_forecast_is_not_lost(monkeypatch):
    """
    Reproduce the collision deliberately: make the forecast slow, spike the
    route while it runs, and check the spike is still on the graph afterwards.
    """
    from app.integrations.engine_bridge import get_engine
    from app.services import agent_service
    from app.services.agent_service import TrafficAgent

    with TestClient(app) as c:
        c.post("/api/simulation/event?scenario=normal")
        _new_trip(c)
        c.post("/api/simulation/advance?progress=0.3")
    engine = get_engine()
    ahead = engine.trip.remaining_nodes

    real_forecast = TrafficAgent.forecast_ahead
    inside = threading.Event()

    def slow_forecast(self, eng, horizon_min):
        reading = real_forecast(self, eng, horizon_min)
        inside.set()
        time.sleep(1.5)            # the window a spike used to fall into
        return reading

    monkeypatch.setattr(TrafficAgent, "forecast_ahead", slow_forecast)
    analysis = threading.Thread(
        target=lambda: agent_service.TrafficAgent().analyse(apply_forecast=True))
    analysis.start()
    assert inside.wait(30), "the forecast never ran"

    engine.spike_route(level=0.92)        # blocks until the overlay is restored
    analysis.join(30)

    spiked = [float(engine.G[u][v][k].get("congestion", 0.0))
              for u, v in zip(ahead, ahead[1:]) if engine.G.has_edge(u, v)
              for k in engine.G[u][v]]
    assert max(spiked) >= 0.9, (
        "the spike was overwritten by the forecast's restore — the lock is not held")


# --------------------------------------------- the assistant only ever asks

def test_previewing_the_policy_changes_nothing():
    """preview() answers what consider() would do, and remembers none of it."""
    from alerts.alert_engine import AlertEngine
    from routing.rerouting import RerouteDecision

    worth_it = RerouteDecision(should_reroute=True, time_saved_min=20.0, saved_pct=40.0)
    engine = AlertEngine()

    for _ in range(3):
        alert, reason = engine.preview(worth_it)
        assert alert is not None and reason is None
    assert engine.history == [] and engine.last_alert_at is None and engine.suppressed == []

    # The recording path still records — and then previews see its cooldown.
    assert engine.consider(worth_it) is not None
    assert len(engine.history) == 1 and engine.last_alert_at is not None
    alert, reason = engine.preview(worth_it)
    assert alert is None and "cooldown" in reason
    assert len(engine.history) == 1, "a preview added to the history"


def test_asking_the_robot_does_not_silence_the_real_alert(monkeypatch):
    """
    The bug: the robot's "should I switch?" went through the committing path.
    It counted as the trip's alert and started the five-minute cooldown with
    nothing shown — so the monitor's real alert moments later was suppressed.

    The robot looks 15 minutes ahead, and a forecast of the jam easing makes it
    answer "keep" — which never spent an alert, even before the fix, so the
    test would prove nothing. The forecast is neutralised here so the robot's
    honest answer is "I would switch": the case that used to consume the alert.
    """
    from app.services.agent_service import AgentReading, TrafficAgent

    monkeypatch.setattr(TrafficAgent, "forecast_ahead",
                        lambda self, eng, horizon_min: AgentReading(horizon_min=horizon_min))
    with TestClient(app) as c:
        c.post("/api/simulation/event?scenario=normal")
        _new_trip(c)
        c.post("/api/simulation/advance?progress=0.3")
        c.post("/api/simulation/congest-route?level=0.92")

        # The driver opens the robot, and asks, after the jam.
        brief = c.get("/api/assistant/briefing").json()
        ask = c.post("/api/assistant/ask", json={"question": "should I reroute?"}).json()
        assert "switch" in brief["text"].lower() or "saves" in brief["text"].lower(), brief["text"]
        assert ask["decision"]["decision"] == "reroute", ask["text"]

        status = c.get("/api/agent/status").json()
        assert status["alertsRaised"] == 0, "the robot's answer was counted as an alert"

        # What the monitor does next must still raise the alert.
        real = c.post("/api/agent/analyze?predictive=false").json()
        assert real["decision"] == "reroute", real.get("suppressedBecause")
        assert real["alertCommitted"] is True and real["alert"] is not None
        assert c.get("/api/agent/status").json()["alertsRaised"] == 1

        # And the robot's check of the new road, after switching, adds nothing.
        assert c.post("/api/agent/accept").json()["ok"] is True
        time.sleep(1)
        assert c.get("/api/agent/status").json()["alertsRaised"] == 1
