from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import pytest

from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine
from epayroll.time.calculator import ShiftConfig, calculate_day, summarize_period
from epayroll.time.tz import TZ
DIURNO = ShiftConfig(codigo="DIURNO", tipo_jornada="DIURNA", horas_max_dia=Decimal("8"))


def _dt(y: int, m: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=TZ)


def test_extra_diurna_10h():
    """10 horas diurnas → 8 ord + 2 extra diurna."""
    daily = calculate_day(
        date(2026, 6, 2),
        _dt(2026, 6, 2, 7, 0),
        _dt(2026, 6, 2, 17, 0),
        DIURNO,
    )
    assert daily.horas_ordinarias == Decimal("8.00")
    assert daily.horas_extra_diurna == Decimal("2.00")
    assert daily.dias_trabajados == Decimal("1")


def test_gt02_week_extras_via_attendance_summary():
    """GT-02: 4h extra diurna + 2h extra nocturna en la semana."""
    days = [
        calculate_day(date(2026, 6, 2), _dt(2026, 6, 2, 7), _dt(2026, 6, 2, 17), DIURNO),  # 10h → 2 extra
        calculate_day(date(2026, 6, 3), _dt(2026, 6, 3, 7), _dt(2026, 6, 3, 17), DIURNO),  # 10h → 2 extra
        calculate_day(date(2026, 6, 4), _dt(2026, 6, 4, 18), _dt(2026, 6, 5, 4), DIURNO),  # 10h noct → 2 extra
    ]
    summary = summarize_period(days)
    assert summary.horas_extra_diurnas >= Decimal("4")
    assert summary.horas_extra_nocturnas >= Decimal("2")

    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=Decimal("1600"),
        dias_trabajados=Decimal("26"),
        horas_extra_diurnas=summary.horas_extra_diurnas,
        horas_extra_nocturnas=summary.horas_extra_nocturnas,
    )
    r = engine.run(inp)
    assert r.amount("HORA_EXTRA_DIURNA") + r.amount("HORA_EXTRA_NOCTURNA") >= Decimal("61")


def test_gt03_feriado_8h():
    """GT-03: 8 horas en feriado → horas_feriado = 8."""
    daily = calculate_day(
        date(2026, 11, 3),
        _dt(2026, 11, 3, 8),
        _dt(2026, 11, 3, 16),
        DIURNO,
        es_feriado=True,
    )
    assert daily.horas_feriado == Decimal("8.00")
    assert daily.es_feriado is True

    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=Decimal("1600"),
        dias_trabajados=Decimal("1"),
        horas_feriado=Decimal("8"),
    )
    r = engine.run(inp)
    # salario_hora ≈ 7.69; recargo 1.50 * 8 * 7.69 ≈ 92.28
    assert r.amount("RECARGO_FERIADO") >= Decimal("90")


def test_art36_max_extras_capped():
    """Art. 36: máximo 3h extras/día en configuración turno."""
    daily = calculate_day(
        date(2026, 6, 5),
        _dt(2026, 6, 5, 6),
        _dt(2026, 6, 5, 20),  # 14h → 6 extra raw, capped to 3
        DIURNO,
    )
    assert daily.horas_extra_diurna <= Decimal("3")
