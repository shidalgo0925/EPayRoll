"""Tests — tabla default editable de asistencia."""

from __future__ import annotations

from datetime import date

import pytest

from epayroll.db.attendance_facts_repository import AttendanceFactsRepository


@pytest.mark.skipif(
    not __import__("os").environ.get("DATABASE_URL"),
    reason="Requiere BD",
)
def test_ensure_period_grid_creates_rows():
    org = "00000000-0000-0000-0000-000000000010"
    repo = AttendanceFactsRepository()
    r = repo.ensure_period_grid(org, date(2026, 6, 1), date(2026, 6, 5))
    assert r["employees"] >= 1
    assert r["total"] >= 1
