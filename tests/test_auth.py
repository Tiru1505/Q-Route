"""
Google sign-in: identity checked on the server, never taken from the browser.

Google's verifier is replaced here, so these run without a network or a real
Google account. What they hold is everything around it: that nothing signs in
without a configured client ID, that the token is checked against THIS app's
client ID, that a failed check is a 401 rather than a user, and that an email
Google has not verified is refused.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)
CLIENT_ID = "1234567890-test.apps.googleusercontent.com"
TOKEN = "header.payload.signature-" + "x" * 40


def claims(**overrides):
    base = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "109876543210",
        "email": "priya.sharma@example.com",
        "email_verified": True,
        "name": "Priya Sharma",
        "picture": "https://lh3.googleusercontent.com/a/example",
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def users(memory_db):
    # The first version of these tests signed "Priya Sharma" into the real
    # `users` collection, and she had to be deleted by hand. Every test here
    # gets an in-memory stand-in instead.
    return memory_db["users"]


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", CLIENT_ID)


@pytest.fixture
def google_says(monkeypatch):
    """Stand in for Google's verifier; record what it was asked."""
    seen = {}

    def install(result):
        def verify(credential, request, audience, clock_skew_in_seconds=0):
            seen["credential"], seen["audience"] = credential, audience
            if isinstance(result, Exception):
                raise result
            return result
        monkeypatch.setattr("google.oauth2.id_token.verify_oauth2_token", verify)
        return seen
    return install


def test_config_reports_google_off_until_a_client_id_is_set(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    assert client.get("/api/auth/config").json()["google"] == {"enabled": False, "clientId": None}
    monkeypatch.setattr(get_settings(), "google_client_id", CLIENT_ID)
    assert client.get("/api/auth/config").json()["google"] == {"enabled": True, "clientId": CLIENT_ID}


def test_nothing_signs_in_without_a_client_id(monkeypatch, google_says):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    google_says(claims())
    r = client.post("/api/auth/google", json={"credential": TOKEN})
    assert r.status_code == 503
    assert "GOOGLE_CLIENT_ID" in r.json()["error"]["message"]


def test_a_verified_google_account_signs_in(configured, google_says, users):
    seen = google_says(claims())
    r = client.post("/api/auth/google", json={"credential": TOKEN})
    assert r.status_code == 200, r.text
    body = r.json()
    user = body["user"]
    assert {k: user[k] for k in ("email", "name", "initials", "picture", "provider", "role")} == {
        "email": "priya.sharma@example.com", "name": "Priya Sharma", "initials": "PS",
        "picture": "https://lh3.googleusercontent.com/a/example", "provider": "google",
        "role": "user",
    }
    assert body["token"], "a verified sign-in starts a session"
    # The token was checked against THIS app's client ID, not any Google app's.
    assert seen["audience"] == CLIENT_ID
    assert seen["credential"] == TOKEN

    # Recorded once, keyed by Google's stable account id — and signing in
    # again finds the same account rather than making a second.
    [doc] = users.docs
    assert doc["google_sub"] == "109876543210" and doc["email"] == "priya.sharma@example.com"
    again = client.post("/api/auth/google", json={"credential": TOKEN}).json()
    assert again["user"]["id"] == user["id"] and len(users.docs) == 1


def test_a_refused_token_records_nobody(configured, google_says, users):
    google_says(claims(email_verified=False))
    assert client.post("/api/auth/google", json={"credential": TOKEN}).status_code == 401
    assert users.docs == []


@pytest.mark.parametrize("reason,outcome", [
    ("forged or expired", ValueError("Token expired")),
    ("issued by someone else", claims(iss="https://evil.example.com")),
    ("email not verified by Google", claims(email_verified=False)),
])
def test_a_token_that_fails_any_check_is_refused(configured, google_says, reason, outcome):
    google_says(outcome)
    r = client.post("/api/auth/google", json={"credential": TOKEN})
    assert r.status_code == 401, f"{reason}: {r.status_code}"
    assert "user" not in r.json() and "token" not in r.json()


def test_a_missing_or_trivial_credential_never_reaches_google(configured, google_says):
    seen = google_says(claims())
    for body in ({}, {"credential": ""}, {"credential": "short"}):
        assert client.post("/api/auth/google", json=body).status_code == 422
    assert not seen, "an invalid request was passed to the verifier"
