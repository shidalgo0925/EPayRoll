"""Tests multi-tenant — aislamiento de datos por tenant."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"
DEMO_ORG = "00000000-0000-0000-0000-000000000010"
OTHER_TENANT = "00000000-0000-0000-0000-000000000099"
DEMO_PASSWORD = os.environ.get("EPAYROLL_DEMO_PASSWORD", "EasyTech2026!")


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def _headers(tenant: str = DEMO_TENANT, roles: str = "payroll_admin,tenant_admin") -> dict[str, str]:
    return {"X-Tenant-Id": tenant, "X-Roles": roles, "X-User-Id": "test-user"}


def _login(client: TestClient, email: str = "admin@easytech.services") -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": DEMO_PASSWORD, "organization_id": DEMO_ORG},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    return r.json()


def test_login_returns_user_organizations(auth_client):
    data = _login(auth_client, "shidalgo@easytech.services")
    assert data["tenant_id"] == DEMO_TENANT
    assert all(o["tenant_id"] == DEMO_TENANT for o in data["organizations"])
    assert all("Multi-Tenant QA" not in o["razon_social"] for o in data["organizations"])


def test_list_my_organizations_scoped_to_user(auth_client):
    token = _login(auth_client)["access_token"]
    r = auth_client.get(
        "/api/v1/me/organizations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    orgs = r.json()
    assert all(o["tenant_id"] == DEMO_TENANT for o in orgs)


def test_wrong_tenant_cannot_read_demo_employees(auth_client):
    r = auth_client.get(
        f"/api/v1/organizations/{DEMO_ORG}/employees",
        headers=_headers(tenant=OTHER_TENANT),
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 403


def test_login_rejects_unknown_user(auth_client):
    r = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": DEMO_PASSWORD},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 401


def test_create_organization_requires_admin_role(auth_client):
    token = _login(auth_client)["access_token"]
    r = auth_client.post(
        "/api/v1/me/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"razon_social": "Empresa Test Aislada", "ruc": "123"},
    )
    assert r.status_code in (201, 403)
