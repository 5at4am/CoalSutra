"""Prototype login: issue & inspect HMAC bearer tokens.

Endpoint contract:
- ``POST /api/v1/auth/login``  — username/password → bearer token (public).
- ``GET /api/v1/auth/config``   — publicly readable hint of the demo users.
- ``GET /api/v1/auth/me``       — who the current token belongs to (authed).

Demo credentials live in ``settings.DEMO_USERS`` (see ``.env.example``):
``admin/admin123``, ``analyst/analyst123``, ``reviewer/reviewer123``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import check_password, create_token
from app.schemas.auth import AuthConfigResponse, LoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

ROLE_BY_USER: dict[str, str] = {
    "admin": "admin",
    "analyst": "analyst",
    "reviewer": "reviewer",
}


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    username = req.username.strip()
    if not check_password(username, req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(
        access_token=create_token(username),
        username=username,
        role=ROLE_BY_USER.get(username, "analyst"),
    )


@router.get("/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(
        auth_enabled=settings.AUTH_ENABLED,
        demo_users=settings.DEMO_USERS,
    )


@router.get("/me", response_model=UserRead)
def me(username: str = Depends(get_current_user)) -> UserRead:
    return UserRead(username=username, role=ROLE_BY_USER.get(username, "analyst"))