"""GT-10 — incapacidades Art. 200 y fondo licencia."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from epayroll.time.incapacity import (
    accrue_license_fund_hours,
    calculate_incapacity_payment,
    count_calendar_days,
    dias_incapacidad_en_periodo,
    license_fund_balance,
)


def test_fondo_licencia_12h_por_26_jornadas():
    assert accrue_license_fund_hours(Decimal("26")) == Decimal("12")
    assert accrue_license_fund_hours(Decimal("52")) == Decimal("24")
    assert accrue_license_fund_hours(Decimal("312")) == Decimal("144")


def test_license_fund_balance_disponible():
    bal = license_fund_balance(Decimal("52"), Decimal("8"))
    assert bal.horas_acumuladas == Decimal("24")
    assert bal.horas_disponibles == Decimal("16")


def test_gt10_payment_split_15_days():
    split = calculate_incapacity_payment(15, Decimal("60"), fondo_agotado=True)
    assert split.dias_empleador == 2
    assert split.dias_css == 13
    assert split.monto_empleador == Decimal("120.00")
    assert split.monto_css_subsidio == Decimal("546.00")


def test_gt10_fondo_usa_horas_cuando_disponible():
    split = calculate_incapacity_payment(2, Decimal("60"), fondo_agotado=False)
    assert split.fondo_licencia_usado_horas == Decimal("16")


def test_dias_incapacidad_en_periodo_sin_doble_conteo():
    inc = [(date(2026, 6, 5), date(2026, 6, 10))]
    assert dias_incapacidad_en_periodo(date(2026, 6, 1), date(2026, 6, 15), inc) == 6


def test_count_calendar_days():
    assert count_calendar_days(date(2026, 6, 1), date(2026, 6, 15)) == 15
