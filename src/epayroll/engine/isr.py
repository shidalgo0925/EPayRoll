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
    deduccion_previa: str = "ninguna"
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
    es_quincena: bool = False,
) -> Decimal:
    """
    Retención ISR por proyección anual (Art. 699-700).

    Método operativo Panamá (planilla):
      (bruto_mensual × 13 − exención tramo) × tasa / 13
      En quincena: resultado / 2 por corrida.

    No resta CSS del gravable salvo que isr_config.deduccion_previa = css_empleado.
    """
    brackets = config.brackets or []
    factor = Decimal(str(config.factor_anualizacion))

    ingreso_anual = bruto_mensual * factor
    gravable_anual = ingreso_anual
    if config.deduccion_previa == "css_empleado" and css_mensual > 0:
        gravable_anual = max(Decimal("0"), ingreso_anual - css_mensual * factor)

    impuesto_anual = calc_impuesto_anual(gravable_anual, brackets)
    retencion_mensual_teorica = impuesto_anual / factor

    if mes == 12 and acumulado_isr_ytd >= 0:
        retencion_mensual = max(Decimal("0"), impuesto_anual - acumulado_isr_ytd)
    elif mes > 1 and acumulado_isr_ytd > 0:
        objetivo_ytd = retencion_mensual_teorica * Decimal(str(mes))
        retencion_mensual = max(Decimal("0"), objetivo_ytd - acumulado_isr_ytd)
    else:
        retencion_mensual = retencion_mensual_teorica

    if es_quincena:
        retencion_mensual = retencion_mensual / Decimal("2")

    return round_amount(retencion_mensual, RoundingMode.CENTESIMO)
