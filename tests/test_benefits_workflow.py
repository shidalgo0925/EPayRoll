"""Vacaciones, incapacidades y liquidaciones — flujo integrado."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def wf_client(monkeypatch):
    monkeypatch.setenv("EPAYROLL_AUTH_MODE", "disabled")
    from epayroll.auth.settings import get_auth_settings

    get_auth_settings.cache_clear()
    from epayroll.api.main import app

    return TestClient(app)


def _demo_run(wf_client):
    setup = wf_client.get("/api/v1/demo/setup")
    assert setup.status_code == 200
    data = setup.json()
    org = data["organization_id"]
    emp_id = data["employee_id"]
    period_id = data.get("payroll_period_id")
    if not period_id:
        periods = wf_client.get(f"/api/v1/organizations/{org}/payroll-periods")
        period_id = periods.json()[0]["id"]
    return org, emp_id, period_id


def test_vacation_reject_and_coverage_fields(wf_client):
    org, emp_id, _ = _demo_run(wf_client)
    req = wf_client.post(
        f"/api/v1/employees/{emp_id}/vacation/requests",
        json={"fecha_inicio": "2026-08-01", "fecha_fin": "2026-08-05", "dias_solicitados": "5"},
    )
    assert req.status_code == 200, req.text
    request_id = req.json()["request_id"]

    reject = wf_client.post(f"/api/v1/vacation/requests/{request_id}/reject")
    assert reject.status_code == 200
    assert reject.json()["estado"] == "RECHAZADO"

    coverage = wf_client.get(f"/api/v1/organizations/{org}/vacation/coverage")
    assert coverage.status_code == 200
    body = coverage.json()
    assert "programadas" in body
    assert "items" in body
    assert "sin_sustituto" in body


def _period_dates(wf_client, org, period_id):
    periods = wf_client.get(f"/api/v1/organizations/{org}/payroll-periods")
    assert periods.status_code == 200
    match = next((p for p in periods.json() if p["id"] == period_id), None)
    assert match, "periodo demo no encontrado"
    return match["fecha_inicio"], match["fecha_fin"]


def test_vacation_approve_syncs_attendance(wf_client):
    org, emp_id, period_id = _demo_run(wf_client)
    fecha_inicio, _ = _period_dates(wf_client, org, period_id)

    req = wf_client.post(
        f"/api/v1/employees/{emp_id}/vacation/requests",
        json={"fecha_inicio": fecha_inicio, "fecha_fin": fecha_inicio, "dias_solicitados": "1"},
    )
    assert req.status_code == 200
    request_id = req.json()["request_id"]

    approve = wf_client.post(f"/api/v1/vacation/requests/{request_id}/approve", json={})
    assert approve.status_code == 200

    grid = wf_client.get(
        f"/api/v1/organizations/{org}/attendance/facts",
        params={"fecha_inicio": fecha_inicio, "fecha_fin": fecha_inicio, "employee_id": emp_id},
    )
    assert grid.status_code == 200
    facts = grid.json().get("facts") or []
    vac_facts = [f for f in facts if f.get("employee_id") == emp_id and f.get("vacaciones")]
    assert vac_facts, "Aprobar vacaciones debe marcar attendance_facts.vacaciones"


def test_incapacity_sync_and_period_impact(wf_client):
    org, emp_id, period_id = _demo_run(wf_client)
    fecha_inicio, fecha_fin = _period_dates(wf_client, org, period_id)

    inc = wf_client.post(
        f"/api/v1/employees/{emp_id}/incapacities",
        json={
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_inicio,
            "tipo": "CSS",
            "certificado_ref": "CERT-TEST",
        },
    )
    assert inc.status_code == 200, inc.text

    impact = wf_client.post(
        f"/api/v1/employees/{emp_id}/incapacities/period-impact",
        json={"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin},
    )
    assert impact.status_code == 200
    assert "pago_empleador" in impact.json()


def test_termination_context_and_pdf(wf_client):
    org, emp_id, _ = _demo_run(wf_client)
    ctx = wf_client.get(f"/api/v1/employees/{emp_id}/termination/context")
    assert ctx.status_code == 200, ctx.text
    body = ctx.json()
    assert "salarios_acumulados_anio" in body
    assert "dias_vacaciones_pendientes" in body

    calc = wf_client.post(
        f"/api/v1/employees/{emp_id}/termination/calculate",
        json={
            "causa": "RENUNCIA",
            "fecha_terminacion": "2026-06-30",
            "dias_vacaciones_pendientes": body["dias_vacaciones_pendientes"],
            "salarios_acumulados_anio": body["salarios_acumulados_anio"],
            "persist": True,
        },
    )
    assert calc.status_code == 200, calc.text
    case_id = calc.json()["case_id"]

    pdf = wf_client.get(f"/api/v1/termination/{case_id}/export.pdf")
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
