"""CRUD API endpoints for employees, vacations, incapacities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def crud_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "disabled")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_employee_crud(crud_client):
    org = "00000000-0000-0000-0000-000000000010"
    r = crud_client.post(
        f"/api/v1/organizations/{org}/employees",
        json={"cedula": "CRUD-001", "nombres": "Test", "apellidos": "CRUD", "email": "t@x.com"},
    )
    assert r.status_code == 200, r.text
    emp_id = r.json()["id"]

    r2 = crud_client.get(f"/api/v1/employees/{emp_id}")
    assert r2.status_code == 200
    assert r2.json()["email"] == "t@x.com"

    r3 = crud_client.patch(
        f"/api/v1/employees/{emp_id}",
        json={"nombres": "Updated"},
    )
    assert r3.status_code == 200
    assert r3.json()["nombres"] == "Updated"

    r4 = crud_client.delete(f"/api/v1/employees/{emp_id}")
    assert r4.status_code == 204

    r5 = crud_client.get(f"/api/v1/employees/{emp_id}")
    assert r5.status_code == 404


def test_vacation_request_update_cancel(crud_client):
    setup = crud_client.get("/api/v1/demo/setup")
    assert setup.status_code == 200
    emp_id = setup.json()["employee_id"]

    r = crud_client.post(
        f"/api/v1/employees/{emp_id}/vacation/requests",
        json={
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-07-05",
            "dias_solicitados": "5",
        },
    )
    assert r.status_code == 200
    req_id = r.json()["request_id"]

    r2 = crud_client.patch(
        f"/api/v1/vacation/requests/{req_id}",
        json={
            "fecha_inicio": "2026-07-02",
            "fecha_fin": "2026-07-06",
            "dias_solicitados": "4",
        },
    )
    assert r2.status_code == 200

    r3 = crud_client.delete(f"/api/v1/vacation/requests/{req_id}")
    assert r3.status_code == 204


def test_incapacity_crud(crud_client):
    setup = crud_client.get("/api/v1/demo/setup")
    emp_id = setup.json()["employee_id"]

    r = crud_client.post(
        f"/api/v1/employees/{emp_id}/incapacities",
        json={"fecha_inicio": "2026-06-01", "fecha_fin": "2026-06-03", "tipo": "CSS"},
    )
    assert r.status_code == 200
    inc_id = r.json()["incapacity_id"]

    r2 = crud_client.get(f"/api/v1/incapacities/{inc_id}")
    assert r2.status_code == 200

    r3 = crud_client.patch(
        f"/api/v1/incapacities/{inc_id}",
        json={"fecha_inicio": "2026-06-01", "fecha_fin": "2026-06-04", "tipo": "CSS"},
    )
    assert r3.status_code == 200

    r4 = crud_client.delete(f"/api/v1/incapacities/{inc_id}")
    assert r4.status_code == 204


def test_payroll_periods_list(crud_client):
    org = "00000000-0000-0000-0000-000000000010"
    r = crud_client.get(f"/api/v1/organizations/{org}/payroll-periods")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_payroll_period_crud(crud_client):
    org = "00000000-0000-0000-0000-000000000010"
    r = crud_client.post(
        f"/api/v1/organizations/{org}/payroll-periods",
        json={
            "fecha_inicio": "2026-08-01",
            "fecha_fin": "2026-08-15",
            "fecha_pago": "2026-08-16",
            "tipo": "QUINCENAL",
        },
    )
    assert r.status_code == 200, r.text
    period_id = r.json()["payroll_period_id"]

    r2 = crud_client.get(f"/api/v1/payroll/periods/{period_id}")
    assert r2.status_code == 200
    assert r2.json()["fecha_inicio"] == "2026-08-01"

    r3 = crud_client.patch(
        f"/api/v1/payroll/periods/{period_id}",
        json={"fecha_pago": "2026-08-17"},
    )
    assert r3.status_code == 200
    assert r3.json()["fecha_pago"] == "2026-08-17"

    r4 = crud_client.delete(f"/api/v1/payroll/periods/{period_id}")
    assert r4.status_code == 204

    r5 = crud_client.get(f"/api/v1/payroll/periods/{period_id}")
    assert r5.status_code == 404
