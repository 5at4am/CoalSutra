"""Prototype-grade bearer tokens (HMAC-signed, stdlib only).

A token is ``<base64url(payload)>.<sha256_hmac(payload)>`` where the payload
carries ``sub`` (username), ``iat`` and ``exp``. No database, no JWT dependency:
good enough to gate a hackathon prototype behind a login screen. A real
deployment should swap this for proper OAuth2/JWT with a user store.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_DEV_SECRET = "coalsutra-dev-secret-change-me"


class InvalidTokenError(Exception):
    """Raised when a token is malformed, tampered with, or expired."""


def _signing_key() -> bytes:
    secret = (settings.AUTH_SECRET or _DEV_SECRET).encode("utf-8")
    if not settings.AUTH_SECRET:
        logger.warning(
            "security: AUTH_SECRET is empty — using the bundled dev secret. "
            "Set AUTH_SECRET for anything beyond the prototype."
        )
    return secret


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_token(username: str, ttl: int | None = None) -> str:
    """Issue a signed bearer token for ``username``."""
    now = int(time.time())
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + (ttl or settings.AUTH_TOKEN_TTL_SECONDS),
    }
    body = _b64encode(json.dumps(payload).encode("utf-8"))
    signature = hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def verify_token(token: str) -> str:
    """Return the username if ``token`` is valid, else raise ``InvalidTokenError``."""
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(
            _signing_key(), body.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise InvalidTokenError("signature mismatch")
        payload = json.loads(_b64decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise InvalidTokenError("token expired")
        username = payload.get("sub")
        if not username:
            raise InvalidTokenError("missing subject")
        return str(username)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidTokenError("malformed token") from exc


def check_password(username: str, password: str) -> bool:
    """Constant-time comparison against the configured demo users."""
    expected = settings.DEMO_USERS.get(username)
    if expected is None:
        return False
    return secrets.compare_digest(password, str(expected))