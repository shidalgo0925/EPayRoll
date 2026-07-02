"""Tests administración de usuarios."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

DEMO_ORG = "00000000-0000-0000-0000-000000000010"
DEMO_PASSWORD = os.environ.get("EPAYROLL_DEMO_PASSWORD", "EasyTech2026!")
SHIDALGO_PASSWORD = os.environ.get("EPAYROLL_SHIDALGO_PASSWORD", DEMO_PASSWORD)


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    monkeypatch.setenv("EPAYROLL_JWT_SECRET", "test-jwt-secret-key-32bytes!!")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def _login(client: TestClient, email: str = "shidalgo@eastech.services") -> str:
    password = SHIDALGO_PASSWORD if "shidalgo" in email else DEMO_PASSWORD
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "organization_id": DEMO_ORG},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    return r.json()["access_token"]


def test_superuser_is_protected(auth_client):
    token = _login(auth_client)
    users = auth_client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    if users.status_code == 503:
        pytest.skip("BD no disponible")
    assert users.status_code == 200
    shidalgo = next(u for u in users.json() if u["email"] == "shidalgo@eastech.services")
    assert shidalgo["is_superuser"] is True
    assert shidalgo["protected"] is True

    r = auth_client.delete(
        f"/api/v1/users/{shidalgo['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_create_admin_user(auth_client):
    token = _login(auth_client)
    email = f"admin.test.{uuid4().hex[:8]}@easytech.services"
    r = auth_client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": email,
            "password": "TestAdmin123!",
            "nombres": "Admin Prueba",
            "memberships": [
                {"organization_id": DEMO_ORG, "roles": ["tenant_admin", "payroll_admin"]},
            ],
        },
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == email
    assert data["is_superuser"] is False
    assert data["memberships"][0]["roles"]

    delete = auth_client.delete(
        f"/api/v1/users/{data['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete.status_code == 204
