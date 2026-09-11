"""
A journey, end to end, on the real Hyderabad graph — as a user and an admin.

    user plans a route -> starts navigation (the route becomes the monitored trip)
    -> the car moves (progress) -> the ADMIN congests the road ahead
    -> the agent recommends a switch -> the user switches
    -> the switch is recorded on the trip by the server -> the user arrives
    -> the trip is in their history, and in nobody else's

Real session checks (`real_auth`), in-memory users and trips (`memory_db`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.real_auth

HITEC = {"lat": 17.4435, "lon": 78.3772}
CHARMINAR = {"lat": 17.3616, "lon": 78.4747}
PASSWORD = "correct horse battery"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def sign_up(c, email, name="Driver"):
    r = c.post("/api/auth/register", json={"name": name, "email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def admin_token(c):
    from app.services.auth_service import create_or_promote_admin

    create_or_promote_admin("ops@example.com", name="Control Room", password=PASSWORD)
    return c.post("/api/auth/login",
                  json={"email": "ops@example.com", "password": PASSWORD}).json()["token"]


def plan(c, token):
    r = c.post("/api/routes/optimize", headers=auth(token),
               json={"source": HITEC, "destination": CHARMINAR, "algorithm": "dijkstra"})
    assert r.status_code == 200, r.text
    return r.json()


def start(c, token, planned):
    route = planned["route"]
    return c.post("/api/trips", headers=auth(token), json={
        "source": {**HITEC, "name": "Hitec City"},
        "destination": {**CHARMINAR, "name": "Charminar"},
        "request_id": planned["request_id"],
        "route": {"label": "Route 1", "distance_km": route["distance_km"],
                  "eta_min": route["travel_time_minutes"], "congestion": 0.2,
                  "nodes": route["nodes"]},
    })


def test_a_journey_with_a_switch_ends_up_in_history(memory_db):
    from app.integrations.engine_bridge import get_engine

    with TestClient(app) as c:
        admin = admin_token(c)
        user = sign_up(c, "asha@example.com")
        assert c.post("/api/simulation/event?scenario=normal", headers=auth(admin)).status_code == 200
        try:
            planned = plan(c, user)
            r = start(c, user, planned)
            assert r.status_code == 200, r.text
            trip = r.json()["trip"]
            assert trip["status"] == "active" and trip["plannedEtaMin"] > 0

            # The route the user chose is the one the monitor now watches.
            assert [str(n) for n in get_engine().trip.route.nodes] == planned["route"]["nodes"]

            moved = c.post(f"/api/trips/{trip['id']}/progress", headers=auth(user),
                           json={"fraction": 0.3})
            assert moved.status_code == 200, moved.text
            assert 0.25 <= moved.json()["progress"] <= 0.35

            # A user may not touch the traffic; the admin may.
            assert c.post("/api/simulation/congest-route?level=0.92",
                          headers=auth(user)).status_code == 403
            assert c.post("/api/simulation/congest-route?level=0.92",
                          headers=auth(admin)).status_code == 200

            d = c.post("/api/agent/analyze?predictive=false", headers=auth(user)).json()
            # The monitor, started with the trip, may have raised the alert first;
            # either way one must exist for the user to act on.
            assert d["decision"] == "reroute", d.get("reason")
            assert c.get("/api/agent/status").json()["alertsRaised"] >= 1

            acc = c.post("/api/agent/accept", headers=auth(user)).json()
            assert acc["ok"] and acc["tripId"] == trip["id"], acc

            [mine] = c.get("/api/trips", headers=auth(user)).json()["trips"]
            assert mine["rerouted"] is True and len(mine["reroutes"]) == 1
            assert mine["originalEtaMin"] == acc["previousEtaMin"]
            assert mine["optimizedEtaMin"] == acc["newEtaMin"]
            assert mine["timeSavedMin"] == acc["timeSavedMin"] > 0
            assert mine["currentRoute"]["distanceKm"] == acc["newRoute"]["distanceKm"]

            # The car carries on along the new route, which is still this trip.
            assert c.post(f"/api/trips/{trip['id']}/progress", headers=auth(user),
                          json={"fraction": 0.5}).status_code == 200

            done = c.post(f"/api/trips/{trip['id']}/finish", headers=auth(user),
                          json={"status": "completed"}).json()["trip"]
            assert done["status"] == "completed" and done["endedAt"]
            assert c.post(f"/api/trips/{trip['id']}/progress", headers=auth(user),
                          json={"fraction": 0.6}).status_code == 409, "an ended trip moved"
        finally:
            c.post("/api/monitor/stop", headers=auth(admin))


def test_a_trip_belongs_to_its_user(memory_db):
    with TestClient(app) as c:
        admin = admin_token(c)
        asha, ravi = sign_up(c, "asha@example.com"), sign_up(c, "ravi@example.com")
        try:
            trip = start(c, asha, plan(c, asha)).json()["trip"]
            for method, path, body in (
                ("POST", f"/api/trips/{trip['id']}/progress", {"fraction": 0.4}),
                ("POST", f"/api/trips/{trip['id']}/finish", {"status": "cancelled"}),
                ("GET", f"/api/trips/{trip['id']}/outlook", None),
            ):
                r = c.request(method, path, headers=auth(ravi), json=body)
                assert r.status_code == 404, f"{path}: another user's trip answered {r.status_code}"
            assert c.get("/api/trips", headers=auth(ravi)).json()["trips"] == []
            assert c.get("/api/trips").status_code == 401
        finally:
            c.post("/api/monitor/stop", headers=auth(admin))


def test_a_displaced_trip_is_told_so_rather_than_moving_someone_else(memory_db):
    with TestClient(app) as c:
        admin = admin_token(c)
        user = sign_up(c, "asha@example.com")
        try:
            trip = start(c, user, plan(c, user)).json()["trip"]
            plan(c, user)       # a new route replaces the engine's active trip
            r = c.post(f"/api/trips/{trip['id']}/progress", headers=auth(user),
                       json={"fraction": 0.4})
            assert r.status_code == 409 and "no longer" in r.json()["error"]["message"]
        finally:
            c.post("/api/monitor/stop", headers=auth(admin))


def test_a_route_that_is_not_a_road_path_is_refused(memory_db):
    with TestClient(app) as c:
        user = sign_up(c, "asha@example.com")
        planned = plan(c, user)
        planned["route"]["nodes"] = planned["route"]["nodes"][::7]   # skips most roads
        r = start(c, user, planned)
        assert r.status_code == 422, r.text
