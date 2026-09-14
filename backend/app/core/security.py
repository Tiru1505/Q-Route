"""
Passwords, sessions, and who may call what.

THREE PIECES, EACH SMALL ENOUGH TO READ
---------------------------------------
1. Passwords are never stored. What is stored is PBKDF2-SHA256 of the password
   with a random salt, run 600,000 times — the figure OWASP recommends — so a
   stolen database does not hand over anyone's password. It is in Python's
   standard library; nothing new is installed for it.

2. A session is a signed note: "this is user X, role R, valid until T". The
   server signs it with a secret key (HMAC-SHA256) when someone signs in, the
   browser sends it back on every request, and the server checks the
   signature. A note someone edited — to change "user" into "admin" — no
   longer matches its signature and is refused.

3. FastAPI dependencies read the note: `current_user` for anything that needs
   a signed-in person, `require_admin` for the control-room endpoints
   (simulation, monitor, benchmark runs). The frontend hides admin pages from
   users as well, but hiding is not protection: these checks are.

The token is deliberately JWT-like rather than a JWT library, so it can be
explained line by line: base64(JSON) + "." + base64(HMAC of that JSON).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.logging import get_logger

_logger = get_logger("core.security")

ROLES = ("user", "admin")

# ------------------------------------------------------------------ passwords

PBKDF2_ITERATIONS = 600_000
_SCHEME = "pbkdf2_sha256"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, iterations: int | None = None) -> str:
    """`pbkdf2_sha256$<iterations>$<salt>$<hash>` — everything needed to check it later."""
    n = iterations or PBKDF2_ITERATIONS
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, n)
    return f"{_SCHEME}${n}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time comparison, so response timing does not leak how close a guess was."""
    try:
        scheme, n, salt, digest = (stored or "").split("$")
        if scheme != _SCHEME:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                        _unb64(salt), int(n))
        return hmac.compare_digest(candidate, _unb64(digest))
    except (ValueError, TypeError):
        return False


# A real hash to check against when the email is unknown. Answering "no such
# user" instantly and "wrong password" after 0.4 s would tell an attacker which
# emails are registered, just from the timing.
_dummy_hash: str | None = None


def burn_password_check(password: str) -> None:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(secrets.token_urlsafe(16))
    verify_password(password, _dummy_hash)


# ------------------------------------------------------------------- sessions

class InvalidSession(ValueError):
    """The token is missing a part, was altered, or has expired."""


_process_secret: bytes | None = None


def _secret() -> bytes:
    global _process_secret
    configured = get_settings().session_secret
    if configured:
        return configured.encode("utf-8")
    if _process_secret is None:
        _process_secret = secrets.token_bytes(32)
        _logger.warning(
            "SESSION_SECRET is not set: using a random key for this run. "
            "Everyone will be signed out when the server restarts.")
    return _process_secret


def _sign(payload_b64: str) -> str:
    return _b64(hmac.new(_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest())


def issue_session(user: dict, hours: int | None = None) -> str:
    """A signed token naming the user and their role, valid for `session_hours`."""
    now = int(time.time())
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "name": user.get("name") or "",
        "role": user.get("role") if user.get("role") in ROLES else "user",
        "iat": now,
        "exp": now + 3600 * (hours or get_settings().session_hours),
    }
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def read_session(token: str) -> dict:
    try:
        body, signature = token.split(".")
    except (ValueError, AttributeError) as exc:
        raise InvalidSession("malformed session token") from exc
    if not hmac.compare_digest(signature, _sign(body)):
        raise InvalidSession("session signature does not match")
    try:
        payload = json.loads(_unb64(body))
    except ValueError as exc:
        raise InvalidSession("unreadable session token") from exc
    if int(payload.get("exp", 0)) < time.time():
        raise InvalidSession("session has expired")
    if payload.get("role") not in ROLES or not payload.get("sub"):
        raise InvalidSession("session names no valid user")
    return payload


# --------------------------------------------------------------- dependencies

@dataclass(frozen=True)
class SessionUser:
    id: str
    email: str
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


_bearer = HTTPBearer(auto_error=False)


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> SessionUser | None:
    """The signed-in user, or None. A token that is present but invalid is a 401, not None."""
    if credentials is None:
        return None
    try:
        p = read_session(credentials.credentials)
    except InvalidSession as exc:
        raise HTTPException(status_code=401, detail=f"Please sign in again: {exc}.") from exc
    return SessionUser(id=p["sub"], email=p["email"], name=p.get("name", ""), role=p["role"])


def current_user(user: SessionUser | None = Depends(optional_user)) -> SessionUser:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in to use this.")
    return user


def require_admin(user: SessionUser = Depends(current_user)) -> SessionUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="This needs an admin account.")
    return user
