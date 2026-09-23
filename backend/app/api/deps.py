"""Shared FastAPI dependencies.

``get_current_user`` is the single auth gate: when ``AUTH_ENABLED`` is true it
requires a valid ``Authorization: Bearer <token>`` on every request except the
public allowlist; when disabled it transparently passes (offline/test mode).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import InvalidTokenError, verify_token

_bearer = HTTPBearer(auto_error=False)

# Paths that stay reachable without a token even when auth is enforced.
_PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/health/ready",
    "/api/v1/auth/login",
    "/api/v1/auth/config",
}


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Resolve the authenticated username, or the sentinel ``"offline"``.

    When ``settings.AUTH_ENABLED`` is False the gate is open (the hermetic
    test suite runs this way). When True, public paths pass through and
    everything else demands a valid bearer token.
    """
    if request.url.path in _PUBLIC_PATHS:
        return "public"
    if not settings.AUTH_ENABLED:
        return "offline"
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return verify_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=401, detail=f"Invalid or expired token ({exc})"
        ) from exc