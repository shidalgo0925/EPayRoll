"""Conversión de minutos de descuento de asistencia a monto de planilla."""

from __future__ import annotations

from decimal import Decimal

from epayroll.engine.rounding import RoundingMode, round_amount


def monto_descuento_tiempo(salario_mensual: Decimal, descuento_minutos: int) -> Decimal:
    """Valor a descontar: salario_hora × horas no trabajadas por tardanza/salida anticipada."""
    if descuento_minutos <= 0:
        return Decimal("0")
    sal_hora = salario_mensual / Decimal("30") / Decimal("8")
    return round_amount(
        sal_hora * Decimal(descuento_minutos) / Decimal("60"),
        RoundingMode.CENTESIMO,
    )


def descuento_horas_decimal(descuento_minutos: int) -> Decimal:
    if descuento_minutos <= 0:
        return Decimal("0")
    return (Decimal(descuento_minutos) / Decimal("60")).quantize(Decimal("0.01"))
