"""Planilla operador — vista completa y config legal por org."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def planilla_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "disabled")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def test_planilla_view_after_run(planilla_client):
    setup = planilla_client.get("/api/v1/demo/setup")
    assert setup.status_code == 200
    data = setup.json()
    org = data["organization_id"]
    emp_id = data["employee_id"]
    if not planilla_client.get(f"/api/v1/employees/{emp_id}").json().get("activo", True):
        pytest.skip("empleado demo inactivo")
    contract = planilla_client.post(
        f"/api/v1/employees/{emp_id}/contracts",
        json={
            "salario_base": "1800",
            "fecha_inicio": "2026-01-01",
            "forma_pago": "QUINCENAL",
        },
    )
    if contract.status_code not in (200, 400):
        assert contract.status_code == 200, contract.text

    period_id = data.get("payroll_period_id")
    if not period_id:
        periods = planilla_client.get(f"/api/v1/organizations/{org}/payroll-periods")
        assert periods.status_code == 200
        items = periods.json()
        period_id = items[0]["id"] if items else None
    assert period_id
    run = planilla_client.post(
        f"/api/v1/payroll/periods/{period_id}/run",
        json={
            "use_attendance": False,
            "dias_trabajados": 15,
            "employee_ids": [emp_id],
        },
    )
    assert run.status_code == 200, run.text
    run_id = run.json()["run_id"]

    view = planilla_client.get(f"/api/v1/payroll/runs/{run_id}/planilla")
    assert view.status_code == 200, view.text
    body = view.json()
    assert "columnas" in body
    assert len(body["columnas"]) >= 20
    assert body["rows"]
    keys = {c["key"] for c in body["columnas"]}
    assert "css_empleado" in keys
    assert "cancelacion" in keys
    assert "total_cpp_prest" in keys


def test_legal_config_seed(planilla_client):
    org = "00000000-0000-0000-0000-000000000010"
    r = planilla_client.post(f"/api/v1/organizations/{org}/legal/seed-defaults")
    assert r.status_code == 200
    rates = planilla_client.get(f"/api/v1/organizations/{org}/legal/rates")
    assert rates.status_code == 200
    assert len(rates.json()) >= 5
    accounts = planilla_client.get(f"/api/v1/organizations/{org}/legal/account-codes")
    assert accounts.status_code == 200
    assert len(accounts.json()) >= 5


def test_employee_ficha_telefono(planilla_client):
    import uuid

    org = "00000000-0000-0000-0000-000000000010"
    cedula = f"FICHA-{uuid.uuid4().hex[:8]}"
    r = planilla_client.post(
        f"/api/v1/organizations/{org}/employees",
        json={
            "cedula": cedula,
            "nombres": "Ana",
            "apellidos": "Test",
            "ficha": "99",
            "telefono": "6000-0000",
        },
    )
    assert r.status_code == 200, r.text
    emp = r.json()
    assert emp["ficha"] == "99"
    assert emp["telefono"] == "6000-0000"
    planilla_client.delete(f"/api/v1/employees/{emp['id']}")
