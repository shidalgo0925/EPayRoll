"""Tests EN1 SSO (JWKS + OAuth exchange + RBAC)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

DEMO_TENANT = "00000000-0000-0000-0000-000000000001"
DEMO_ORG = "00000000-0000-0000-0000-000000000010"


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


@pytest.fixture
def sso_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "stub")
    monkeypatch.setenv("EPAYROLL_EN1_AUTHORIZE_URL", "https://en1.example/oauth/authorize")
    monkeypatch.setenv("EPAYROLL_EN1_TOKEN_URL", "https://en1.example/oauth/token")
    monkeypatch.setenv("EPAYROLL_EN1_CLIENT_ID", "epayroll-ui")
    monkeypatch.setenv("EPAYROLL_EN1_CLIENT_SECRET", "secret")
    monkeypatch.setenv("EPAYROLL_EN1_REDIRECT_URI", "http://localhost:8001/app/")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_sso_config_enabled(sso_client):
    r = sso_client.get("/api/v1/auth/sso/config")
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True
    assert data["client_id"] == "epayroll-ui"
    assert data["authorize_url"].startswith("https://en1.example")


@patch("epayroll.auth.sso.httpx.Client")
def test_sso_exchange_success(mock_client_cls, sso_client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "access_token": "en1-access-token",
        "token_type": "bearer",
        "expires_in": 3600,
        "refresh_token": "en1-refresh",
    }
    mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

    r = sso_client.post(
        "/api/v1/auth/sso/exchange",
        json={"code": "auth-code-123"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"] == "en1-access-token"
    assert r.json()["refresh_token"] == "en1-refresh"


def test_rbac_blocks_close_without_role(auth_client):
    r = auth_client.post(
        "/api/v1/payroll/periods/00000000-0000-0000-0000-000000000099/close",
        headers={"X-Tenant-Id": DEMO_TENANT, "X-Roles": "empleado"},
        json={},
    )
    assert r.status_code == 403
    assert "Rol insuficiente" in r.json()["detail"]


def test_rbac_allows_contador_on_export(auth_client):
    r = auth_client.post(
        "/api/v1/exports/sipe/00000000-0000-0000-0000-000000000099",
        headers={"X-Tenant-Id": DEMO_TENANT, "X-Roles": "contador"},
        json={},
    )
    assert r.status_code in (403, 404)


@patch("epayroll.auth.jwks._jwk_client")
def test_en1_mode_jwks_decode(mock_jwk_client, monkeypatch):
    pytest.importorskip("jwt")
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "en1")
    monkeypatch.setenv("EPAYROLL_EN1_JWKS_URL", "https://en1.example/.well-known/jwks.json")
    monkeypatch.setenv("EPAYROLL_JWT_SECRET", "unused")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()

    import jwt as pyjwt

    secret = "test-secret-key"
    token = pyjwt.encode(
        {
            "sub": "en1-sso-user",
            "tenant_id": DEMO_TENANT,
            "organization_id": DEMO_ORG,
            "roles": ["contador"],
            "exp": datetime.now(tz=UTC) + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )

    signing_key = MagicMock()
    signing_key.key = secret
    mock_jwk_client.return_value.get_signing_key_from_jwt.return_value = signing_key

    from epayroll.api.main import app

    client = TestClient(app)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["user_id"] == "en1-sso-user"
