from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .orchestrator import LineResult, PayrollResult
from .rounding import RoundingMode, round_amount


@dataclass(frozen=True)
class DecimoInput:
    """Entrada para pago de décimo tercer mes — Decreto 19/1973."""

    salarios_cotizables: Decimal
    tasa_css_decimo: Decimal = Decimal("0.0725")


def calc_monto_decimo(salarios_cotizables: Decimal) -> Decimal:
    return round_amount(salarios_cotizables / Decimal("12"), RoundingMode.CENTESIMO)


def run_decimo(inp: DecimoInput) -> PayrollResult:
    """Calcula décimo con CSS reducido (7.25%); sin SE ni ISR."""
    monto = calc_monto_decimo(inp.salarios_cotizables)
    css_empleado = round_amount(monto * inp.tasa_css_decimo, RoundingMode.CENTESIMO)
    css_empleador = round_amount(monto * inp.tasa_css_decimo, RoundingMode.CENTESIMO)

    lines = [
        LineResult(
            codigo_concepto="DECIMO_TERCER",
            tipo="INGRESO",
            monto=monto,
            prioridad=1,
            referencia_legal="Decreto 19/1973",
        ),
        LineResult(
            codigo_concepto="CSS_EMPLEADO",
            tipo="DESCUENTO",
            monto=css_empleado,
            prioridad=2,
            referencia_legal="Decreto 19/1973 + reglamento CSS",
        ),
        LineResult(
            codigo_concepto="CSS_EMPLEADOR",
            tipo="APORTE_EMPLEADOR",
            monto=css_empleador,
            prioridad=3,
            referencia_legal="Decreto 19/1973 + reglamento CSS",
        ),
    ]
    return PayrollResult(
        lines=lines,
        config_snapshot={
            "tipo_corrida": "DECIMO",
            "salarios_cotizables": str(inp.salarios_cotizables),
            "tasa_css_decimo": str(inp.tasa_css_decimo),
        },
    )
