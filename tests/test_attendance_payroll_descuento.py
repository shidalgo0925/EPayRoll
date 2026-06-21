"""Tests — descuento por tardanza en planilla."""

from __future__ import annotations

from decimal import Decimal

from epayroll.attendance.payroll_descuento import descuento_horas_decimal, monto_descuento_tiempo


def test_monto_descuento_tiempo_quincena():
    # 1800/mes → 7.50/h → 135 min = 2.25 h → 16.88
    monto = monto_descuento_tiempo(Decimal("1800"), 135)
    assert monto == Decimal("16.88")


def test_descuento_horas_decimal():
    assert descuento_horas_decimal(135) == Decimal("2.25")
    assert descuento_horas_decimal(10) == Decimal("0.17")
