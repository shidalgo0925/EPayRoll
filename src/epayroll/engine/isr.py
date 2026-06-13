from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .rounding import round_amount, RoundingMode


@dataclass(frozen=True)
class IsrBracket:
    rango_desde: Decimal
    rango_hasta: Decimal | None
    porcentaje: Decimal
    excedente_desde: Decimal
    impuesto_fijo_acumulado: Decimal


@dataclass
class IsrConfig:
    factor_anualizacion: int = 13
    deduccion_previa: str = "css_empleado"
    brackets: list[IsrBracket] | None = None


def calc_impuesto_anual(ingreso_anual_gravable: Decimal, brackets: list[IsrBracket]) -> Decimal:
    """Aplica tabla progresiva anual (Art. 700 Código Fiscal)."""
    for bracket in sorted(brackets, key=lambda b: b.rango_desde):
        limite = bracket.rango_hasta
        if limite is None or ingreso_anual_gravable <= limite:
            excedente = max(Decimal("0"), ingreso_anual_gravable - bracket.excedente_desde)
            return bracket.impuesto_fijo_acumulado + excedente * bracket.porcentaje
    last = sorted(brackets, key=lambda b: b.rango_desde)[-1]
    excedente = max(Decimal("0"), ingreso_anual_gravable - last.excedente_desde)
    return last.impuesto_fijo_acumulado + excedente * last.porcentaje


def calc_isr_mensual(
    bruto_mensual: Decimal,
    css_mensual: Decimal,
    config: IsrConfig,
    mes: int = 1,
    acumulado_isr_ytd: Decimal = Decimal("0"),
) -> Decimal:
    """
    Retención ISR mensual por proyección anual.

    Método: anualizar ingreso (×13), restar CSS anual, aplicar tabla, dividir /13.
    Ajuste YTD simplificado en meses > 1 (Fase 2).
    """
    brackets = config.brackets or []
    factor = Decimal(str(config.factor_anualizacion))

    ingreso_anual = bruto_mensual * factor
    css_anual = css_mensual * factor
    gravable_anual = max(Decimal("0"), ingreso_anual - css_anual)

    impuesto_anual = calc_impuesto_anual(gravable_anual, brackets)
    retencion_mensual_teorica = impuesto_anual / factor

    if mes == 12 and acumulado_isr_ytd >= 0:
        retencion_mensual = max(Decimal("0"), impuesto_anual - acumulado_isr_ytd)
    elif mes > 1 and acumulado_isr_ytd > 0:
        objetivo_ytd = retencion_mensual_teorica * Decimal(str(mes))
        retencion_mensual = max(Decimal("0"), objetivo_ytd - acumulado_isr_ytd)
    else:
        retencion_mensual = retencion_mensual_teorica

    return round_amount(retencion_mensual, RoundingMode.CENTESIMO)
