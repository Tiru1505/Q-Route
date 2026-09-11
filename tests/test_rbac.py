"""
Accounts, sessions, and who may do what.

These run with the REAL session checks (marker `real_auth`) against in-memory
collections (`memory_db`), so nothing is written to the real database.

What they hold:
  * registering always makes a USER — the role cannot be sent in
  * passwords are stored hashed, and sign-in checks them
  * a user's session is refused by every control-room endpoint (403), and no
    session at all is refused too (401)
  * a session edited to say "admin" no longer matches its signature
  * admins come only from the script or, for Google accounts, ADMIN_EMAILS
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

pytestmark = pytest.mark.real_auth
client = TestClient(app)

PASSWORD = "correct horse battery"


def register(name="Asha Rao", email="asha@example.com", password=PASSWORD, **extra):
    return client.post("/api/auth/register",
                       json={"name": name, "email": email, "password": password, **extra})


def login(email="asha@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------ registration

def test_registering_makes_a_user_and_stores_no_password(memory_db):
    r = register()
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "user" and body["token"]
    assert "password_hash" not in body["user"], "the hash must never leave the server"

    [stored] = memory_db["users"].docs
    assert stored["password_hash"].startswith("pbkdf2_sha256$")
    assert PASSWORD not in stored["password_hash"]


def test_the_role_cannot_be_sent_in(memory_db):
    r = register(email="sneaky@example.com", role="admin")
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "user"


def test_an_email_registers_once_whatever_its_case(memory_db):
    assert register().status_code == 200
    again = register(email="  ASHA@Example.com ")
    assert again.status_code == 409
    assert "already exists" in again.json()["error"]["message"]


def test_a_short_password_is_refused(memory_db):
    r = register(password="short")
    assert r.status_code == 400
    assert memory_db["users"].docs == []


# ------------------------------------------------------------------ sign-in

def test_sign_in_checks_the_password(memory_db):
    register()
    ok = login(email="ASHA@example.com")
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "user"

    wrong = login(password="not the password")
    unknown = login(email="nobody@example.com")
    # The same answer either way, so the form cannot be used to find accounts.
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


# --------------------------------------------------------------- sessions

def test_a_user_session_is_refused_by_every_control(memory_db):
    token = register().json()["token"]
    controls = [
        "/api/simulation/event?scenario=normal",
        "/api/simulation/congest-route",
        "/api/simulation/advance",
        "/api/simulation/reset",
        "/api/monitor/start",
        "/api/monitor/stop",
        "/api/alerts/trigger",
        "/api/alerts/clear",
        "/api/notifications/clear",
        "/api/routes/reroute",
    ]
    for path in controls:
        assert client.post(path, headers=auth(token)).status_code == 403, path
        assert client.post(path).status_code == 401, f"{path} without a session"


def test_an_edited_session_no_longer_matches_its_signature(memory_db):
    token = register().json()["token"]
    body, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload["role"] = "admin"
    forged_body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    assert client.get("/api/auth/me", headers=auth(f"{forged_body}.{signature}")).status_code == 401
    assert client.post("/api/monitor/stop",
                       headers=auth(f"{forged_body}.{signature}")).status_code == 401
    assert client.get("/api/auth/me", headers=auth("not-a-token")).status_code == 401


def test_an_expired_session_is_refused(memory_db):
    from app.core.security import issue_session

    user = register().json()["user"]
    expired = issue_session(user, hours=-1)
    assert client.get("/api/auth/me", headers=auth(expired)).status_code == 401


# ------------------------------------------------------------------ admins

def test_the_script_makes_an_admin(memory_db):
    from app.services.auth_service import create_or_promote_admin

    create_or_promote_admin("ops@example.com", name="Control Room", password=PASSWORD)
    r = login(email="ops@example.com")
    assert r.json()["user"]["role"] == "admin"
    assert client.post("/api/notifications/clear",
                       headers=auth(r.json()["token"])).status_code == 200


def test_the_admin_list_needs_google_to_have_verified_the_email(memory_db, monkeypatch):
    """
    Someone registers the admin's email with a password first. The list must
    not make them an admin — and when the real owner signs in with Google, the
    account becomes theirs and the planted password stops working.
    """
    monkeypatch.setattr(get_settings(), "admin_emails", "boss@example.com")
    monkeypatch.setattr(get_settings(), "google_client_id", "123-test.apps.googleusercontent.com")

    planted = register(name="Mallory", email="boss@example.com")
    assert planted.json()["user"]["role"] == "user", "an unverified email must not be admin"

    monkeypatch.setattr("google.oauth2.id_token.verify_oauth2_token",
                        lambda credential, request, audience, clock_skew_in_seconds=0: {
                            "iss": "https://accounts.google.com", "sub": "g-boss",
                            "email": "boss@example.com", "email_verified": True,
                            "name": "The Boss"})
    google = client.post("/api/auth/google", json={"credential": "x" * 40})
    assert google.status_code == 200, google.text
    assert google.json()["user"]["role"] == "admin"
    assert login(email="boss@example.com").status_code == 401, "the planted password still works"
    assert len(memory_db["users"].docs) == 1


# ----------------------------------------------------------------- profile

def test_profile_preferences_and_password(memory_db):
    token = register().json()["token"]

    me = client.get("/api/auth/me", headers=auth(token)).json()["user"]
    assert me["name"] == "Asha Rao" and me["preferences"]["vehicle"] == "car"

    r = client.patch("/api/auth/me", headers=auth(token), json={
        "name": "Asha R.", "preferences": {"vehicle": "bus", "mode": "fastest",
                                           "autoOpenAlerts": False}})
    assert r.status_code == 200
    assert r.json()["user"]["preferences"] == {"vehicle": "bus", "mode": "fastest",
                                               "autoOpenAlerts": False}
    assert client.patch("/api/auth/me", headers=auth(token),
                        json={"preferences": {"vehicle": "spaceship"}}).status_code == 400

    # A wrong current password is a 400: a 401 would sign the person out.
    wrong = client.post("/api/auth/password", headers=auth(token),
                        json={"current_password": "nope", "new_password": "a new password"})
    assert wrong.status_code == 400
    ok = client.post("/api/auth/password", headers=auth(token),
                     json={"current_password": PASSWORD, "new_password": "a new password"})
    assert ok.status_code == 200
    assert login(password="a new password").status_code == 200
    assert login().status_code == 401


def test_every_direct_fetch_in_the_frontend_sends_the_session():
    """
    Calls that bypass `request()` — uploads, whose Content-Type the browser
    must set — have to add the session header themselves. The Traffic
    Analysis Lab's upload did not, and every admin's analysis was refused as
    coming from nobody.
    """
    import pathlib
    import re

    js = (pathlib.Path(__file__).resolve().parent.parent
          / "frontend" / "src" / "services" / "api.js").read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(r"\bfetch\(", js)]
    assert calls, "no fetch calls found — the check would pass vacuously"
    for at in calls:
        call = js[at:js.index(")\n", at) + 1]
        if "`${BASE}${path}`" in call:      # request() itself, which adds it
            continue
        assert "headers" in call, f"a direct fetch sends no session header:\n{call}"


def test_route_history_is_always_your_own(memory_db):
    token = register().json()["token"]
    assert client.get("/api/routes/history").status_code == 401
    r = client.get("/api/routes/history?user_id=someone-else", headers=auth(token))
    assert r.status_code == 200
    assert all(row.get("user_id") != "someone-else" for row in r.json()["results"])
