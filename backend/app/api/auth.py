"""
Sign-in endpoints.

    GET   /auth/config    which sign-in methods are available (Google client ID)
    POST  /auth/register  create a USER account          -> {user, token}
    POST  /auth/login     email + password               -> {user, token}
    POST  /auth/google    a Google ID token              -> {user, token}
    GET   /auth/me        the signed-in account
    PATCH /auth/me        change name / preferences
    POST  /auth/password  change password

Every sign-in returns the same thing: the account, including its `role`, and
a signed session token the browser sends back as `Authorization: Bearer ...`.
There is no endpoint that creates an admin: see scripts/create_admin.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import SessionUser, current_user
from app.services import auth_service
from app.services.auth_service import (
    AccountNotFound,
    AccountsUnavailable,
    AuthError,
    EmailTaken,
    GoogleAuthNotConfigured,
    InvalidGoogleToken,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleSignIn(BaseModel):
    credential: str = Field(..., min_length=20, max_length=8192,
                            description="The ID token Google Identity Services returned")


class Registration(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class Credentials(BaseModel):
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    preferences: dict | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


def _answer(fn, *args, **kwargs):
    """The service's exceptions, as the HTTP answers they mean."""
    try:
        return fn(*args, **kwargs)
    except EmailTaken as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc
    except AccountNotFound as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AccountsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
    return {"google": {"enabled": bool(client_id), "clientId": client_id or None},
            "password": {"enabled": True, "minLength": auth_service.MIN_PASSWORD}}


@router.post("/register", summary="Create a user account",
             responses={409: {"description": "Email already registered"}})
def register(body: Registration) -> dict:
    return _answer(auth_service.register_user, body.name, body.email, body.password)


@router.post("/login", summary="Sign in with email and password",
             responses={401: {"description": "Email or password is incorrect"}})
def login(body: Credentials) -> dict:
    return _answer(auth_service.login_user, body.email, body.password)


@router.post(
    "/google",
    summary="Sign in with Google",
    description=(
        "Verifies a Google ID token — signature, expiry, audience, issuer, "
        "verified email — finds or creates the account, and returns a session."
    ),
    responses={401: {"description": "Token failed verification"},
               503: {"description": "Google sign-in not configured"}},
)
def google(body: GoogleSignIn) -> dict:
    try:
        return _answer(auth_service.sign_in_with_google, body.credential)
    except GoogleAuthNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidGoogleToken as exc:
        raise HTTPException(status_code=401, detail=f"Google sign-in failed: {exc}") from exc


@router.get("/me", summary="The signed-in account")
def me(user: SessionUser = Depends(current_user)) -> dict:
    return {"user": _answer(auth_service.get_profile, user.id)}


@router.patch("/me", summary="Change your name or preferences")
def update_me(body: ProfileUpdate, user: SessionUser = Depends(current_user)) -> dict:
    return {"user": _answer(auth_service.update_profile, user.id,
                            name=body.name, preferences=body.preferences)}


@router.post("/password", summary="Change your password")
def change_password(body: PasswordChange, user: SessionUser = Depends(current_user)) -> dict:
    _answer(auth_service.change_password, user.id, body.current_password, body.new_password)
    return {"ok": True}
