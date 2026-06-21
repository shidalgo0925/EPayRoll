"""Tests — tabla estándar de asistencia (hechos)."""

from __future__ import annotations

from datetime import date

from epayroll.attendance.importer import parse_attendance_csv
from epayroll.attendance.validator import compute_descuento_minutos, normalize_fact_row, validate_fact_row


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


def test_validate_empty_template_ok():
    _, errors = validate_fact_row(
        {"cedula": "8-888-8888", "fecha": "2026-06-16"},
        employee_id="00000000-0000-0000-0000-000000000001",
    )
    assert errors == []


def test_validate_partial_hours_error():
    _, errors = validate_fact_row(
        {
            "cedula": "8-888-8888",
            "fecha": "2026-06-16",
            "hora_entrada": "08:00",
        },
        employee_id="00000000-0000-0000-0000-000000000001",
    )
    assert any("hora_salida" in e for e in errors)


def test_compute_descuento_tardanza():
    mins = compute_descuento_minutos("08:10", "17:00", 'EPAYROLL_ATT_SPLIT:{"amOut":"12:00","pmIn":"13:00"}')
    assert mins == 10


def test_compute_descuento_salida_anticipada():
    mins = compute_descuento_minutos("08:00", "15:00", 'EPAYROLL_ATT_SPLIT:{"amOut":"12:00","pmIn":"13:00"}')
    assert mins == 120


def test_compute_descuento_combinado():
    mins = compute_descuento_minutos(
        "08:15",
        "15:30",
        'EPAYROLL_ATT_SPLIT:{"amOut":"11:45","pmIn":"13:20"}',
    )
    assert mins == 15 + 15 + 20 + 90  # tarde am + salida am temprana + tarde pm + salida pm temprana


def test_normalize_descanso_from_split_obs():
    row = normalize_fact_row(
        {
            "cedula": "8-888-8888",
            "fecha": "2026-06-02",
            "hora_entrada": "08:00",
            "hora_salida": "17:00",
            "descanso_minutos": 60,
            "observacion": 'EPAYROLL_ATT_SPLIT:{"amOut":"12:30","pmIn":"13:45"}',
        }
    )
    assert row["descanso_minutos"] == 75


def test_normalize_bool_variants():
    row = normalize_fact_row({"ausencia": "sí", "incapacidad": "1", "vacaciones": "no"})
    assert row["ausencia"] is True
    assert row["incapacidad"] is True
    assert row["vacaciones"] is False
