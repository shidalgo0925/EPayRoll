"""Tests auth EN1 + tenant isolation."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"
DEMO_ORG = "00000000-0000-0000-0000-000000000010"
OTHER_TENANT = "00000000-0000-0000-0000-000000000099"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


@pytest.fixture
def open_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "disabled")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_health_no_auth_required(auth_client):
    r = auth_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_api_requires_tenant_header(auth_client):
    r = auth_client.get(f"/api/v1/organizations/{DEMO_ORG}/employees")
    assert r.status_code == 401
    assert "X-Tenant-Id" in r.json()["detail"]


def test_stub_auth_me(auth_client):
    r = auth_client.get(
        "/api/v1/auth/me",
        headers={"X-Tenant-Id": DEMO_TENANT, "X-User-Id": "user-1", "X-Roles": "payroll_admin"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_id"] == DEMO_TENANT
    assert data["user_id"] == "user-1"
    assert "payroll_admin" in data["roles"]


def test_tenant_isolation_blocks_wrong_tenant(auth_client):
    r = auth_client.get(
        f"/api/v1/organizations/{DEMO_ORG}/employees",
        headers={"X-Tenant-Id": OTHER_TENANT},
    )
    assert r.status_code == 403


def test_demo_org_access_with_demo_tenant(auth_client):
    r = auth_client.get(
        f"/api/v1/organizations/{DEMO_ORG}/employees",
        headers={"X-Tenant-Id": DEMO_TENANT},
    )
    assert r.status_code in (200, 503)


def test_disabled_mode_allows_without_headers(open_client):
    r = open_client.get(f"/api/v1/organizations/{DEMO_ORG}/employees")
    assert r.status_code in (200, 503)


def test_jwt_mode_valid_token(monkeypatch):
    pytest.importorskip("jwt")
    secret = "test-secret-key"
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "jwt")
    monkeypatch.setenv("EPAYROLL_JWT_SECRET", secret)
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()

    import jwt as pyjwt

    from epayroll.api.main import app

    token = pyjwt.encode(
        {
            "sub": "en1-user-42",
            "tenant_id": DEMO_TENANT,
            "organization_id": DEMO_ORG,
            "roles": ["payroll_admin"],
            "exp": datetime.now(tz=UTC) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )
    client = TestClient(app)
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["tenant_id"] == DEMO_TENANT
    assert r.json()["user_id"] == "en1-user-42"


def test_jwt_wrong_tenant_blocked(monkeypatch):
    pytest.importorskip("jwt")
    secret = "test-secret-key"
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "jwt")
    monkeypatch.setenv("EPAYROLL_JWT_SECRET", secret)
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()

    import jwt as pyjwt

    from epayroll.api.main import app

    token = pyjwt.encode(
        {
            "sub": "user-x",
            "tenant_id": OTHER_TENANT,
            "exp": datetime.now(tz=UTC) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )
    client = TestClient(app)
    r = client.get(
        f"/api/v1/organizations/{DEMO_ORG}/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
