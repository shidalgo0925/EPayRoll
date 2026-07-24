"""Tests login JWT EN1."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

DEMO_ORG = "00000000-0000-0000-0000-000000000010"
DEMO_PASSWORD = os.environ.get("EPAYROLL_DEMO_PASSWORD", "EasyTech2026!")


@pytest.fixture
def login_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    monkeypatch.setenv("EPAYROLL_JWT_SECRET", "test-jwt-secret-key-32bytes!!")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_login_rejects_bad_password(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@easytech.services", "password": "wrong"},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 401


def test_login_returns_jwt(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@easytech.services",
            "password": DEMO_PASSWORD,
            "organization_id": DEMO_ORG,
        },
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    me = login_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "admin@easytech.services"
    assert "expires_in_hours" in data


def test_auth_refresh_slides_session(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@easytech.services",
            "password": DEMO_PASSWORD,
            "organization_id": DEMO_ORG,
        },
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    token = r.json()["access_token"]

    refreshed = login_client.post(
        "/api/v1/auth/refresh",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["access_token"]
    assert "expires_in_hours" in body

    me = login_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
