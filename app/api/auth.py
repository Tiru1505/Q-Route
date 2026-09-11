"""
Sign-in endpoints.

/auth/config tells the login page whether Google sign-in is available and with
which client ID. /auth/google turns a Google ID token into a verified user.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.services.auth_service import (
    GoogleAuthNotConfigured,
    InvalidGoogleToken,
    sign_in_with_google,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSignIn(BaseModel):
    credential: str = Field(..., min_length=20, max_length=8192,
                            description="The ID token Google Identity Services returned")


@router.get(
    "/config",
    summary="Which sign-in methods are available",
    description=(
        "The Google OAuth client ID, when one is configured. It is public by "
        "design — Google sends it to every browser that shows the button — and "
        "serving it from here keeps one copy, on the server, instead of a "
        "second in the frontend's environment that could disagree."
    ),
)
def config() -> dict:
    client_id = get_settings().google_client_id
    return {"google": {"enabled": bool(client_id), "clientId": client_id or None}}


@router.post(
    "/google",
    summary="Sign in with Google",
    description=(
        "Verifies a Google ID token — signature, expiry, audience, issuer, "
        "verified email — and returns the user. The user is recorded in "
        "MongoDB.\n\nIdentity is verified here, once. Other endpoints do not "
        "yet check a session, so this is sign-in, not API authorisation."
    ),
    responses={401: {"description": "Token failed verification"},
               503: {"description": "Google sign-in not configured"}},
)
def google(body: GoogleSignIn) -> dict:
    try:
        return {"user": sign_in_with_google(body.credential)}
    except GoogleAuthNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidGoogleToken as exc:
        raise HTTPException(status_code=401, detail=f"Google sign-in failed: {exc}") from exc
