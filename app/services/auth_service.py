"""
Accounts: registration, sign-in, roles, and profile.

WHAT CHANGES
------------
Sign-in used to happen entirely in the browser: any email with a password of
four characters was accepted, the password was never checked or stored, and
the "user" was an object the browser wrote into sessionStorage. Nothing on the
server knew who anyone was.

Now every account lives in the MongoDB `users` collection, and every way in
ends the same way — the server returns a signed session (see core.security)
naming the user and their role:

    register      name + email + password  ->  a new USER account
    password      email + password         ->  checked against the stored hash
    Google        a Google-signed ID token ->  verified here, then linked

THERE IS NO PUBLIC ADMIN REGISTRATION
-------------------------------------
Anyone who could register as an admin could make themselves one. An account
is an admin when either:

  * scripts/create_admin.py set role "admin" on it (run by whoever runs the
    server, with a password they type themselves), or
  * it is linked to a Google account whose email is listed in ADMIN_EMAILS.
    Google has verified that address; a password registration has not, which
    is why the list is never consulted for password-only accounts.

The env-list role is worked out at each sign-in rather than stored, so taking
an email off the list takes the access away.
"""

from __future__ import annotations

import re

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    ROLES,
    burn_password_check,
    hash_password,
    issue_session,
    verify_password,
)
from app.utils.time_helpers import utc_now_iso

_logger = get_logger("services.auth")

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8

# What a new account starts with. Only settings the app actually applies:
# the vehicle and objective go into every route request, and the robot's
# auto-open is honoured by the assistant panel.
DEFAULT_PREFERENCES = {"vehicle": "car", "mode": "balanced", "autoOpenAlerts": True}


class GoogleAuthNotConfigured(RuntimeError):
    """No client ID is set, so there is nothing to verify tokens against."""


class InvalidGoogleToken(ValueError):
    """The token failed verification — forged, expired, or for another app."""


class AuthError(ValueError):
    """
    A request the account rules refuse. `status` is the HTTP answer: 401 only
    for a failed sign-in. A wrong *current* password on the change form is a
    400 — to the browser a 401 means "your session is over", and it would sign
    the person out for a typo.
    """

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class EmailTaken(ValueError):
    """An account with this email already exists."""


class AccountNotFound(LookupError):
    """The session names an account that no longer exists."""


class AccountsUnavailable(RuntimeError):
    """The users database cannot be reached, so nobody can be signed in."""


# ------------------------------------------------------------------ helpers

def _users():
    try:
        from app.database.collections import get_users_col

        return get_users_col()
    except Exception as exc:  # pragma: no cover - depends on the database
        raise AccountsUnavailable(f"The accounts database is unavailable: {exc}") from exc


def normalise_email(email: str) -> str:
    return (email or "").strip().lower()


def _id_query(user_id: str) -> dict:
    """Accounts created by MongoDB carry ObjectIds; the session carries their string form."""
    from bson import ObjectId

    return {"_id": ObjectId(user_id)} if ObjectId.is_valid(user_id) else {"_id": user_id}


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return (name[:2] or "U").upper()


def effective_role(doc: dict) -> str:
    if doc.get("role") == "admin":
        return "admin"
    if doc.get("google_sub") and normalise_email(doc.get("email")) in get_settings().admin_email_set:
        return "admin"
    return "user"


def public_user(doc: dict) -> dict:
    """What the browser may know about an account. Never the password hash."""
    email = normalise_email(doc.get("email"))
    name = doc.get("name") or email.split("@")[0]
    providers = [p for p, present in (("password", doc.get("password_hash")),
                                      ("google", doc.get("google_sub"))) if present]
    return {
        "id": str(doc["_id"]),
        "email": email,
        "name": name,
        "initials": _initials(name),
        "picture": doc.get("picture"),
        "role": effective_role(doc),
        "provider": "google" if "google" in providers else "password",
        "providers": providers,
        "preferences": {**DEFAULT_PREFERENCES, **(doc.get("preferences") or {})},
        "createdAt": doc.get("created_at"),
    }


def _session(doc: dict) -> dict:
    user = public_user(doc)
    return {"user": user, "token": issue_session(user)}


def _check_password_rules(password: str) -> None:
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"Use a password of at least {MIN_PASSWORD} characters.")
    if len(password) > 128:
        raise AuthError("That password is too long (128 characters at most).")


# ----------------------------------------------------------- email + password

def register_user(name: str, email: str, password: str) -> dict:
    """Create a USER account. Role is never taken from the request."""
    name = (name or "").strip()
    email = normalise_email(email)
    if not name:
        raise AuthError("Enter your name.")
    if not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    _check_password_rules(password)

    users = _users()
    if users.find_one({"email": email}):
        raise EmailTaken("An account with this email already exists. Sign in instead.")

    now = utc_now_iso()
    doc = {
        "name": name[:80],
        "email": email,
        "password_hash": hash_password(password),
        "role": "user",
        "preferences": {},
        "created_at": now,
        "last_login_at": now,
    }
    try:
        doc["_id"] = users.insert_one(doc).inserted_id
    except Exception as exc:
        # The unique index on email catches two registrations racing each other.
        if "duplicate" in str(exc).lower():
            raise EmailTaken("An account with this email already exists. Sign in instead.") from exc
        raise
    _logger.info("Registered user %s", email)
    return _session(doc)


def login_user(email: str, password: str) -> dict:
    email = normalise_email(email)
    doc = _users().find_one({"email": email}) if email else None
    # One message for every failure, so the form does not reveal which emails
    # have accounts — and the unknown-email path costs the same time.
    if not doc or not doc.get("password_hash"):
        burn_password_check(password or "")
        raise AuthError("Email or password is incorrect.", status=401)
    if not verify_password(password or "", doc["password_hash"]):
        raise AuthError("Email or password is incorrect.", status=401)
    _users().update_one({"_id": doc["_id"]}, {"$set": {"last_login_at": utc_now_iso()}})
    return _session(doc)


# ------------------------------------------------------------------- Google

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


def sign_in_with_google(credential: str) -> dict:
    """Verify the credential, find or create the account, and start a session."""
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleAuthNotConfigured(
            "Google sign-in is not configured on the server: set GOOGLE_CLIENT_ID."
        )

    claims = verify_google_credential(credential, settings.google_client_id)
    email = normalise_email(claims["email"])
    sub = claims["sub"]
    users = _users()

    doc = users.find_one({"google_sub": sub}) or users.find_one({"email": email})
    now = utc_now_iso()
    fields = {
        "email": email,
        "google_sub": sub,
        "picture": claims.get("picture"),
        "last_login_at": now,
    }
    if doc is None:
        doc = {**fields, "name": claims.get("name") or email.split("@")[0],
               "role": "user", "preferences": {}, "created_at": now}
        doc["_id"] = users.insert_one(doc).inserted_id
    else:
        update = {"$set": fields}
        if not doc.get("name"):
            fields["name"] = claims.get("name") or email.split("@")[0]
        if doc.get("password_hash") and not doc.get("google_sub"):
            # A password account with this email was registered by someone who
            # never proved they own the address. Google just proved this person
            # does, so the account is theirs — and the password someone else may
            # have chosen stops working. (Without this, registering a victim's
            # email in advance would give a way back into their account.)
            update["$unset"] = {"password_hash": ""}
            doc.pop("password_hash", None)
            _logger.warning("Google sign-in claimed password account %s; password removed", email)
        users.update_one({"_id": doc["_id"]}, update)
        doc.update(fields)

    _logger.info("Google sign-in: %s", email)
    return _session(doc)


# ------------------------------------------------------------------ profile

def get_profile(user_id: str) -> dict:
    doc = _users().find_one(_id_query(user_id))
    if not doc:
        raise AccountNotFound("This account no longer exists.")
    return public_user(doc)


def update_profile(user_id: str, name: str | None = None,
                   preferences: dict | None = None) -> dict:
    from graph.edge_weights import MODES
    from graph.vehicles import VEHICLES

    doc = _users().find_one(_id_query(user_id))
    if not doc:
        raise AccountNotFound("This account no longer exists.")

    changes: dict = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise AuthError("Your name cannot be empty.")
        changes["name"] = name[:80]
    if preferences is not None:
        prefs = {**DEFAULT_PREFERENCES, **(doc.get("preferences") or {})}
        for key, value in preferences.items():
            if key == "vehicle" and value in VEHICLES:
                prefs[key] = value
            elif key == "mode" and value in MODES:
                prefs[key] = value
            elif key == "autoOpenAlerts" and isinstance(value, bool):
                prefs[key] = value
            else:
                raise AuthError(f"Unsupported preference {key}={value!r}.")
        changes["preferences"] = prefs

    if changes:
        _users().update_one({"_id": doc["_id"]}, {"$set": changes})
        doc.update(changes)
    return public_user(doc)


def change_password(user_id: str, current: str, new: str) -> None:
    doc = _users().find_one(_id_query(user_id))
    if not doc:
        raise AccountNotFound("This account no longer exists.")
    if not doc.get("password_hash"):
        raise AuthError("This account signs in with Google, so it has no password to change.")
    if not verify_password(current or "", doc["password_hash"]):
        raise AuthError("Your current password is incorrect.")
    _check_password_rules(new)
    _users().update_one({"_id": doc["_id"]}, {"$set": {"password_hash": hash_password(new)}})


# -------------------------------------------------------------------- admin

def create_or_promote_admin(email: str, name: str | None = None,
                            password: str | None = None) -> dict:
    """
    Used by scripts/create_admin.py only — never reachable over HTTP.

    An existing account is promoted (and gets the password, if one is given);
    otherwise a new admin account is created, which needs a password.
    """
    email = normalise_email(email)
    if not EMAIL_RE.match(email):
        raise AuthError("Enter a valid email address.")
    users = _users()
    doc = users.find_one({"email": email})
    changes: dict = {"role": "admin"}
    if password:
        _check_password_rules(password)
        changes["password_hash"] = hash_password(password)

    if doc:
        users.update_one({"_id": doc["_id"]}, {"$set": changes})
        doc.update(changes)
    else:
        if not password:
            raise AuthError("A new admin account needs a password.")
        now = utc_now_iso()
        doc = {"name": (name or email.split("@")[0]).strip()[:80], "email": email,
               "preferences": {}, "created_at": now, "last_login_at": None, **changes}
        doc["_id"] = users.insert_one(doc).inserted_id
    assert effective_role(doc) in ROLES
    return public_user(doc)
