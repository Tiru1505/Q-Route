"""
Google sign-in, verified on the server.

WHAT CHANGES
------------
Until now sign-in happened entirely in the browser: any email with a password
of four characters or more was accepted, the password was never checked or
stored, and the "user" was an object the browser wrote into sessionStorage.
Nothing on the server knew who anyone was.

Google sign-in is different because the identity is checked HERE. The browser
receives a signed ID token from Google and sends it to /api/auth/google; this
module verifies Google's signature, that the token was issued for THIS app's
client ID, that it has not expired, and that Google has verified the email.
Only then is the user accepted — and recorded in MongoDB.

WHAT IT DOES NOT DO (YET)
-------------------------
It does not issue a session token, and the other API endpoints do not check
one. A signed-in user's identity is verified once, at sign-in; requests after
that still carry the user id the browser sends. Closing that is the next step
— a signed session cookie or bearer token checked per request — and until it
is done this should not be described as securing the API.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger("services.auth")

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleAuthNotConfigured(RuntimeError):
    """No client ID is set, so there is nothing to verify tokens against."""


class InvalidGoogleToken(ValueError):
    """The token failed verification — forged, expired, or for another app."""


def verify_google_credential(credential: str, client_id: str) -> dict:
    """
    Check a Google ID token and return its claims.

    google-auth fetches Google's public certificates (cached) and checks the
    signature, the expiry, and that the audience is `client_id`. The issuer
    and verified-email checks are added here: a token for an unverified
    address proves only that someone typed it.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_oauth2_token(
            credential, google_requests.Request(), client_id,
            clock_skew_in_seconds=10,
        )
    except ValueError as exc:
        raise InvalidGoogleToken(str(exc)) from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleToken(f"unexpected issuer {claims.get('iss')!r}")
    if not claims.get("email_verified"):
        raise InvalidGoogleToken("Google has not verified this email address")
    return claims


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (name[:2] or "U").upper()


def sign_in_with_google(credential: str) -> dict:
    """Verify the credential, record the user, and return who they are."""
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleAuthNotConfigured(
            "Google sign-in is not configured on the server: set GOOGLE_CLIENT_ID."
        )

    claims = verify_google_credential(credential, settings.google_client_id)
    email = claims["email"]
    name = claims.get("name") or email.split("@")[0]
    user = {
        "email": email,
        "name": name,
        "initials": _initials(name),
        "picture": claims.get("picture"),
        "provider": "google",
    }

    # Recorded best-effort: a database outage should not stop someone Google
    # has just vouched for from signing in.
    try:
        from app.database.collections import get_users_col

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        get_users_col().update_one(
            {"google_sub": claims["sub"]},
            {"$set": {**user, "google_sub": claims["sub"], "last_login_at": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except Exception as exc:
        _logger.warning("Could not record Google user %s: %s", email, exc)

    _logger.info("Google sign-in: %s", email)
    return user
