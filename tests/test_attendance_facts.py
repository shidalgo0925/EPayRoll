"""Tests — tabla estándar de asistencia (hechos)."""

from __future__ import annotations

from datetime import date

from epayroll.attendance.importer import parse_attendance_csv
from epayroll.attendance.validator import normalize_fact_row, validate_fact_row


def test_parse_csv_template():
    with open("docs/seed/attendance_import_template.csv", encoding="utf-8") as f:
        rows = parse_attendance_csv(f.read())
    assert len(rows) == 2
    assert rows[0]["cedula"] == "8-888-8888"


def test_validate_fact_ok():
    row, errors = validate_fact_row(
        {
            "cedula": "8-888-8888",
            "fecha": "2026-06-16",
            "hora_entrada": "07:58",
            "hora_salida": "17:12",
            "descanso_minutos": "60",
        },
        employee_id="00000000-0000-0000-0000-000000000001",
    )
    assert errors == []
    assert row["fecha"] == date(2026, 6, 16)
    assert row["descanso_minutos"] == 60


def test_validate_ausencia_sin_horas():
    row, errors = validate_fact_row(
        {
            "cedula": "8-888-8888",
            "fecha": "2026-06-16",
            "ausencia": "si",
        },
        employee_id="00000000-0000-0000-0000-000000000001",
    )
    assert errors == []
    assert row["ausencia"] is True


def test_validate_missing_hours():
    _, errors = validate_fact_row(
        {"cedula": "8-888-8888", "fecha": "2026-06-16"},
        employee_id="00000000-0000-0000-0000-000000000001",
    )
    assert "hora_entrada requerida" in errors[0]


def test_normalize_bool_variants():
    row = normalize_fact_row({"ausencia": "sí", "incapacidad": "1", "vacaciones": "no"})
    assert row["ausencia"] is True
    assert row["incapacidad"] is True
    assert row["vacaciones"] is False
