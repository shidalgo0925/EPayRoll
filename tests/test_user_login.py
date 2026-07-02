"""Tests login por usuario (email + contraseña)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

DEMO_ORG = "00000000-0000-0000-0000-000000000010"
DEMO_PASSWORD = os.environ.get("EPAYROLL_DEMO_PASSWORD", "EasyTech2026!")
SHIDALGO_EMAIL = "shidalgo@eastech.services"
SHIDALGO_PASSWORD = os.environ.get("EPAYROLL_SHIDALGO_PASSWORD", DEMO_PASSWORD)


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
        json={"email": SHIDALGO_EMAIL, "password": "wrong"},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 401


def test_login_accepts_legacy_easytech_email(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={
            "email": "shidalgo@easytech.services",
            "password": SHIDALGO_PASSWORD,
        },
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    assert r.json()["email"] == SHIDALGO_EMAIL


def test_login_returns_only_user_companies(login_client):
    r = login_client.post(
        "/api/v1/auth/login",
        json={
            "email": SHIDALGO_EMAIL,
            "password": SHIDALGO_PASSWORD,
        },
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    data = r.json()
    assert data["access_token"]
    assert data["email"] == SHIDALGO_EMAIL
    orgs = data["organizations"]
    assert len(orgs) >= 1
    assert all("Multi-Tenant QA" not in o["razon_social"] for o in orgs)
    assert any(o["id"] == DEMO_ORG for o in orgs)


def test_login_with_org_issues_scoped_jwt(login_client):
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
    me = login_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["organization_id"] == DEMO_ORG

    orgs = login_client.get(
        "/api/v1/me/organizations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert orgs.status_code == 200
    assert all(o["tenant_id"] == r.json()["tenant_id"] for o in orgs.json())
