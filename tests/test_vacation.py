from __future__ import annotations

from datetime import date
from decimal import Decimal

from epayroll.vacation.calculator import (
    calc_dias_ganados,
    calculate_balance,
    check_art59,
    check_art57_alert,
    months_of_service,
)


def test_11_meses_primer_periodo():
    periodos, dias = calc_dias_ganados(11)
    assert periodos == 1
    assert dias == Decimal("30")


def test_22_meses_dos_periodos():
    periodos, dias = calc_dias_ganados(22)
    assert periodos == 2
    assert dias == Decimal("60")


def test_10_meses_sin_derecho():
    periodos, dias = calc_dias_ganados(10)
    assert periodos == 0
    assert dias == Decimal("0")


def test_art59_tope_dos_periodos():
    excede, max_dias, sobre = check_art59(Decimal("65"))
    assert excede is True
    assert max_dias == Decimal("60")
    assert sobre == Decimal("5")


def test_art57_alerta_sin_programacion():
    alerta, msg = check_art57_alert(
        dias_pendientes=Decimal("35"),
        proxima_vacacion_inicio=None,
        fecha_referencia=date(2026, 6, 1),
    )
    assert alerta is True
    assert msg is not None


def test_balance_con_pasivo():
    result = calculate_balance(
        fecha_inicio=date(2024, 1, 1),
        fecha_corte=date(2026, 6, 1),
        dias_gozados=Decimal("0"),
        salario_mensual=Decimal("1800"),
    )
    assert result.meses_servicio == 29
    assert result.periodos_ganados == 2
    assert result.dias_pendientes == Decimal("60")
    assert result.pasivo_estimado == Decimal("3600.00")
    assert result.excede_art59 is False
