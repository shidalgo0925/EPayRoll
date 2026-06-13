"""Tests login JWT EN1."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def login_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    monkeypatch.setenv("EPAYROLL_LOGIN_API_KEY", "test-login-key")
    monkeypatch.setenv("EPAYROLL_JWT_SECRET", "test-jwt-secret-key-32bytes!!")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_login_rejects_bad_key(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "user_id": "u1",
            "api_key": "wrong",
        },
    )
    assert r.status_code == 401


def test_login_returns_jwt(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "organization_id": "00000000-0000-0000-0000-000000000010",
            "user_id": "admin",
            "api_key": "test-login-key",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["token_type"] == "bearer"

    me = login_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["tenant_id"] == "00000000-0000-0000-0000-000000000001"
