from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class PayrollInput:
    """Entrada operativa para una corrida de planilla (un empleado)."""

    salario_mensual: Decimal
    dias_trabajados: Decimal = Decimal("0")
    dias_mes: Decimal = Decimal("30")
    horas_jornada: Decimal = Decimal("8")
    dias_laborables_mes: Decimal = Decimal("26")

    horas_extra_diurnas: Decimal = Decimal("0")
    horas_extra_nocturnas: Decimal = Decimal("0")
    horas_extra_mixta_nocturnas: Decimal = Decimal("0")
    horas_domingo: Decimal = Decimal("0")
    horas_feriado: Decimal = Decimal("0")

    tipo_contrato: str = "INDEFINIDO"
    mes: int = 1
    acumulado_isr_ytd: Decimal = Decimal("0")
    acumulado_gravable_ytd: Decimal = Decimal("0")

    tasa_css_patronal: Decimal = Decimal("0.1325")
    tasa_riesgo_empresa: Decimal = Decimal("0.0105")
    tasa_prima_antiguedad_patronal: Decimal = Decimal("0.0192")
    tope_css: Decimal | None = None

    es_quincena: bool = False
    descuento_voluntario: Decimal = Decimal("0")


@dataclass
class PayrollContext:
    """Variables disponibles para fórmulas configurables."""

    input: PayrollInput
    concept_amounts: dict[str, Decimal] = field(default_factory=dict)
    extra: dict[str, Decimal] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        inp = self.input
        salario_diario = inp.salario_mensual / inp.dias_mes
        salario_hora = inp.salario_mensual / (inp.dias_laborables_mes * inp.horas_jornada)

        bruto_ingresos = sum(
            v for k, v in self.concept_amounts.items()
            if k in _INGRESO_CODES
        )
        bruto_cotizable = bruto_ingresos
        bruto_cotizable_se = bruto_ingresos
        bruto_gravable = bruto_ingresos

        css_empleado = self.concept_amounts.get("CSS_EMPLEADO", Decimal("0"))

        tope = inp.tope_css if inp.tope_css is not None else Decimal("999999999")

        base: dict[str, Any] = {
            "salario_base": inp.salario_mensual,
            "salario_mensual": inp.salario_mensual,
            "salario_diario": salario_diario,
            "salario_hora": salario_hora,
            "dias_trabajados": inp.dias_trabajados,
            "horas_extra_diurnas": inp.horas_extra_diurnas,
            "horas_extra_nocturnas": inp.horas_extra_nocturnas,
            "horas_extra_mixta_nocturnas": inp.horas_extra_mixta_nocturnas,
            "horas_domingo": inp.horas_domingo,
            "horas_feriado": inp.horas_feriado,
            "bruto_parcial": bruto_ingresos,
            "bruto_cotizable": bruto_cotizable,
            "bruto_cotizable_se": bruto_cotizable_se,
            "bruto_gravable": bruto_gravable,
            "css_empleado": css_empleado,
            "acumulado_ytd": inp.acumulado_gravable_ytd,
            "mes": inp.mes,
            "tasa_css_patronal": inp.tasa_css_patronal,
            "tasa_riesgo_empresa": inp.tasa_riesgo_empresa,
            "tasa_prima_antiguedad_patronal": inp.tasa_prima_antiguedad_patronal,
            "tope_css": tope,
            "true": True,
            "false": False,
        }
        for k, v in self.extra.items():
            base[k] = v
        return base


_INGRESO_CODES = frozenset({
    "SALARIO_BASE",
    "HORA_EXTRA_DIURNA",
    "HORA_EXTRA_NOCTURNA",
    "HORA_EXTRA_MIXTA_NOCTURNA",
    "RECARGO_DOMINGO",
    "RECARGO_FERIADO",
    "DECIMO_TERCER",
})
