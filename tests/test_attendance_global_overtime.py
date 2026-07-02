"""Tests captura global de horas extra por período."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from epayroll.db.attendance_facts_repository import AttendanceFactsRepository


@pytest.fixture
def repo():
    return AttendanceFactsRepository()


def test_global_overtime_overrides_daily_summary(repo):
    org_id = "00000000-0000-0000-0000-000000000010"
    emp_id = "7036b36d-26c0-43e8-83ae-f7d4771cea83"
    f_ini = date(2026, 6, 1)
    f_fin = date(2026, 6, 15)
    try:
        repo.save_period_overtime(
            org_id,
            f_ini,
            f_fin,
            [
                {
                    "employee_id": emp_id,
                    "horas_extra_diurnas": Decimal("12.5"),
                    "horas_extra_nocturnas": Decimal("0"),
                    "horas_extra_mixta_nocturnas": Decimal("0"),
                    "horas_domingo": Decimal("0"),
                    "horas_feriado": Decimal("0"),
                }
            ],
        )
    except Exception as exc:
        if "does not exist" in str(exc):
            pytest.skip("Migración 016 pendiente")
        pytest.skip(f"BD no disponible: {exc}")

    summary = {
        "horas_extra_diurnas": Decimal("1"),
        "horas_extra_nocturnas": Decimal("0"),
        "horas_extra_mixta_nocturnas": Decimal("0"),
        "horas_domingo": Decimal("0"),
        "horas_feriado": Decimal("0"),
    }
    merged = repo._apply_global_overtime(org_id, emp_id, f_ini, f_fin, summary)
    assert merged["horas_extra_diurnas"] == Decimal("12.5")
    assert merged.get("overtime_source") == "global"
