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
    assert "/app/img/logo-epayroll.png" in r.text
    assert "/app/js/bundle.js" in r.text
    assert 'id="org-switcher"' in r.text
    assert 'id="login-org-select"' in r.text


def test_ui_logo_asset(ui_client):
    r = ui_client.get("/app/img/logo-epayroll.png")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_ui_dashboard_bundle(ui_client):
    r = ui_client.get("/app/js/bundle.js")
    assert r.status_code == 200
    assert "X-Tenant-Id" in r.text
    assert "/api/v1/me/organizations" in r.text
    assert "requireOrgId" in r.text
    assert "proyeccion_liquidaciones" in r.text


def test_ui_vacations_incapacities_pages(ui_client):
    r = ui_client.get("/app/js/bundle.js")
    assert r.status_code == 200
    assert "renderVacations" in r.text
    assert "renderIncapacities" in r.text


def test_ui_liquidations_page(ui_client):
    r = ui_client.get("/app/")
    assert r.status_code == 200
    assert 'data-page="liquidations"' in r.text
    r2 = ui_client.get("/app/js/bundle.js")
    assert "renderLiquidations" in r2.text
    assert "termination/calculate" in r2.text


def test_ui_nav_icons(ui_client):
    r = ui_client.get("/app/")
    assert r.status_code == 200
    assert "nav-icon" in r.text
    assert "nav-label" in r.text


def test_ui_crud_helpers(ui_client):
    r = ui_client.get("/app/js/bundle.js")
    assert r.status_code == 200
    assert "crudActions" in r.text
    assert "apiPatch" in r.text
    assert "apiDelete" in r.text


def test_ui_multi_employee_payroll(ui_client):
    r = ui_client.get("/app/js/bundle.js")
    assert r.status_code == 200
    assert "renderBatchResultsHtml" in r.text
    assert "createEmployeeContract" in r.text
    assert "Multi-empleado" in r.text


def test_ui_settings_page(ui_client):
    r = ui_client.get("/app/")
    assert r.status_code == 200
    assert 'data-page="settings"' in r.text
    r2 = ui_client.get("/app/js/bundle.js")
    assert "renderSettings" in r2.text
