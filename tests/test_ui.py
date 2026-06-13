"""Smoke test: UI estática montada en FastAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def ui_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "disabled")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_ui_redirect(ui_client):
    r = ui_client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/app/"


def test_ui_index_served(ui_client):
    r = ui_client.get("/app/")
    assert r.status_code == 200
    assert "EPayRoll" in r.text
    assert "/app/js/bundle.js" in r.text


def test_ui_dashboard_bundle(ui_client):
    r = ui_client.get("/app/js/bundle.js")
    assert r.status_code == 200
    assert "X-Tenant-Id" in r.text
    assert "proyeccion_liquidaciones" in r.text
    assert "btn-sso-en1" in r.text
    assert "handleSsoCallback" in r.text
