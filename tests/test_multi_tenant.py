"""Tests multi-tenant — aislamiento de datos por tenant."""

from __future__ import annotations

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


def _headers(tenant: str = DEMO_TENANT, roles: str = "payroll_admin,tenant_admin") -> dict[str, str]:
    return {"X-Tenant-Id": tenant, "X-Roles": roles, "X-User-Id": "test-user"}


def test_login_returns_tenant_organizations(auth_client):
    r = auth_client.post(
        "/api/v1/auth/login",
        json={
            "tenant_id": DEMO_TENANT,
            "user_id": "ui-user",
            "api_key": "dev-login-key",
        },
    )
    if r.status_code == 404:
        pytest.skip("Tenant demo no disponible en BD")
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_id"] == DEMO_TENANT
    assert isinstance(data["organizations"], list)
    if data["organizations"]:
        assert all(o["tenant_id"] == DEMO_TENANT for o in data["organizations"])


def test_list_my_organizations_scoped_to_tenant(auth_client):
    r = auth_client.get("/api/v1/me/organizations", headers=_headers())
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 200
    orgs = r.json()
    assert all(o["tenant_id"] == DEMO_TENANT for o in orgs)


def test_login_rejects_unknown_tenant(auth_client):
    r = auth_client.post(
        "/api/v1/auth/login",
        json={
            "tenant_id": OTHER_TENANT,
            "user_id": "ui-user",
            "api_key": "dev-login-key",
        },
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 404


def test_wrong_tenant_cannot_read_demo_employees(auth_client):
    r = auth_client.get(
        f"/api/v1/organizations/{DEMO_ORG}/employees",
        headers=_headers(tenant=OTHER_TENANT),
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 403


def test_create_organization_requires_admin_role(auth_client):
    r = auth_client.post(
        "/api/v1/me/organizations",
        headers=_headers(roles="empleado"),
        json={"razon_social": "Empresa Test Aislada", "ruc": "123"},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 403


def test_create_organization_in_tenant(auth_client):
    r = auth_client.post(
        "/api/v1/me/organizations",
        headers=_headers(),
        json={"razon_social": "Empresa Multi-Tenant QA", "ruc": "999999999"},
    )
    if r.status_code == 503:
        pytest.skip("BD no disponible")
    assert r.status_code == 201
    created = r.json()
    assert created["tenant_id"] == DEMO_TENANT
    assert created["razon_social"] == "Empresa Multi-Tenant QA"

    listed = auth_client.get("/api/v1/me/organizations", headers=_headers()).json()
    assert any(o["id"] == created["id"] for o in listed)

    blocked = auth_client.get(
        f"/api/v1/organizations/{created['id']}/employees",
        headers=_headers(tenant=OTHER_TENANT),
    )
    assert blocked.status_code == 403
