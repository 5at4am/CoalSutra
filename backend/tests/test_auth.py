"""Prototype authentication: token issue/verify + the API gate.

The suite-wide conftest disables auth (``AUTH_ENABLED=false``) so the rest of the
tests exercise services directly. Here we flip it on per-test to prove the gate
works: anonymous requests are rejected, login issues a token, and the token
opens protected routes.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import (
    InvalidTokenError,
    check_password,
    create_token,
    verify_token,
)
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


# --- token primitives -------------------------------------------------------


def test_token_roundtrip():
    token = create_token("analyst")
    assert verify_token(token) == "analyst"


def test_tampered_token_is_rejected():
    body, signature = create_token("admin").rsplit(".", 1)
    assert verify_token(f"{body}.{signature[:-1]}0") != "admin"
    with pytest.raises(InvalidTokenError):
        verify_token(f"{body}.deadbeef")


def test_expired_token_is_rejected():
    with pytest.raises(InvalidTokenError):
        verify_token(create_token("admin", ttl=-5))


def test_check_password():
    assert check_password("admin", "admin123")
    assert not check_password("admin", "wrong")
    assert not check_password("nobody", "admin123")


# --- API gate ---------------------------------------------------------------


def test_login_and_me(client):
    settings.AUTH_ENABLED = True
    try:
        resp = client.post(
            "/api/v1/auth/login", json={"username": "reviewer", "password": "reviewer123"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["username"] == "reviewer"
        assert body["role"] == "reviewer"

        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json() == {"username": "reviewer", "role": "reviewer"}
    finally:
        settings.AUTH_ENABLED = False


def test_bad_credentials_rejected(client):
    settings.AUTH_ENABLED = True
    try:
        resp = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "nope"}
        )
        assert resp.status_code == 401
    finally:
        settings.AUTH_ENABLED = False


def test_protected_route_requires_token(client):
    settings.AUTH_ENABLED = True
    try:
        assert client.get("/api/v1/reports").status_code == 401
        assert (
            client.get(
                "/api/v1/reports", headers={"Authorization": "Bearer garbage"}
            ).status_code
            == 401
        )

        token = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
        ).json()["access_token"]
        authed = client.get(
            "/api/v1/reports", headers={"Authorization": f"Bearer {token}"}
        )
        assert authed.status_code == 200
    finally:
        settings.AUTH_ENABLED = False


def test_health_stays_public_while_authed(client):
    settings.AUTH_ENABLED = True
    try:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/auth/config").status_code == 200
    finally:
        settings.AUTH_ENABLED = False


def test_auth_disabled_allows_anonymous(client):
    assert settings.AUTH_ENABLED is False
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "offline"