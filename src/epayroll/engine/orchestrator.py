from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .config import EngineConfig, load_config_from_seed
from .context import PayrollContext, PayrollInput
from .evaluator import SafeEvaluator
from .isr import calc_isr_mensual
from .rounding import RoundingMode, round_amount


@dataclass
class LineResult:
    codigo_concepto: str
    tipo: str
    monto: Decimal
    prioridad: int
    referencia_legal: str | None = None


@dataclass
class PayrollResult:
    lines: list[LineResult] = field(default_factory=list)
    config_snapshot: dict[str, Any] = field(default_factory=dict)

    def amount(self, codigo: str) -> Decimal:
        for line in self.lines:
            if line.codigo_concepto == codigo:
                return line.monto
        return Decimal("0")

    @property
    def bruto(self) -> Decimal:
        return sum(
            (l.monto for l in self.lines if l.tipo == "INGRESO"),
            Decimal("0"),
        )

    @property
    def deducciones(self) -> Decimal:
        return sum(
            (l.monto for l in self.lines if l.tipo == "DESCUENTO"),
            Decimal("0"),
        )

    @property
    def neto(self) -> Decimal:
        return self.bruto - self.deducciones

    @property
    def aportes_patronales(self) -> Decimal:
        return sum(
            (l.monto for l in self.lines if l.tipo == "APORTE_EMPLEADOR"),
            Decimal("0"),
        )


class PayrollEngine:
    """Motor genérico: interpreta reglas de tablas maestras."""

    VERSION = "1.0.0"

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or load_config_from_seed()

    def run(self, payroll_input: PayrollInput) -> PayrollResult:
        ctx = PayrollContext(input=payroll_input)
        lines: list[LineResult] = []

        for rule in self.config.rules:
            if rule.aplica_contratos and payroll_input.tipo_contrato not in rule.aplica_contratos:
                continue

            variables = ctx.as_dict()
            evaluator = SafeEvaluator(
                variables=variables,
                functions={"min": min, "max": max},
            )

            if not evaluator.eval_condition(rule.condicion_aplicacion):
                continue

            concept = self.config.concepts.get(rule.codigo_concepto)
            if not concept:
                continue

            rounding = RoundingMode(rule.redondeo)

            if rule.unidad == "MOTOR_ISR":
                bruto_mes = self._bruto_mensual_equivalente(payroll_input, ctx)
                css_mes = ctx.concept_amounts.get("CSS_EMPLEADO", Decimal("0"))
                if payroll_input.es_quincena:
                    css_mes = css_mes * Decimal("2")
                monto = calc_isr_mensual(
                    bruto_mensual=bruto_mes,
                    css_mensual=css_mes,
                    config=self.config.isr,
                    mes=payroll_input.mes,
                    acumulado_isr_ytd=payroll_input.acumulado_isr_ytd,
                )
            else:
                raw = evaluator.eval_amount(rule.base_calculo)
                monto = round_amount(raw, rounding)
                if concept.tipo == "DESCUENTO" and monto > 0:
                    monto = abs(monto)

            ctx.concept_amounts[rule.codigo_concepto] = monto
            lines.append(
                LineResult(
                    codigo_concepto=rule.codigo_concepto,
                    tipo=concept.tipo,
                    monto=monto,
                    prioridad=rule.prioridad_calculo,
                    referencia_legal=rule.referencia_legal,
                )
            )

        self._add_prima_antiguedad_patronal(payroll_input, ctx, lines)

        from .config import config_snapshot

        return PayrollResult(
            lines=lines,
            config_snapshot=config_snapshot(self.config),
        )

    def _bruto_mensual_equivalente(
        self, payroll_input: PayrollInput, ctx: PayrollContext
    ) -> Decimal:
        bruto_periodo = sum(
            v for k, v in ctx.concept_amounts.items()
            if k in {
                "SALARIO_BASE", "HORA_EXTRA_DIURNA", "HORA_EXTRA_NOCTURNA",
                "HORA_EXTRA_MIXTA_NOCTURNA", "RECARGO_DOMINGO", "RECARGO_FERIADO",
            }
        )
        if payroll_input.es_quincena:
            return bruto_periodo * Decimal("2")
        return bruto_periodo

    def _add_prima_antiguedad_patronal(
        self,
        payroll_input: PayrollInput,
        ctx: PayrollContext,
        lines: list[LineResult],
    ) -> None:
        bruto = ctx.as_dict()["bruto_cotizable"]
        tope = payroll_input.tope_css or Decimal("999999999")
        base = min(_dec(bruto), _dec(tope))
        tasa = payroll_input.tasa_prima_antiguedad_patronal
        monto = round_amount(base * tasa, RoundingMode.CENTESIMO)
        if monto <= 0:
            return
        ctx.concept_amounts["PRIMA_ANTIGUEDAD_PATRONAL"] = monto
        lines.append(
            LineResult(
                codigo_concepto="PRIMA_ANTIGUEDAD_PATRONAL",
                tipo="APORTE_EMPLEADOR",
                monto=monto,
                prioridad=10,
            )
        )


def _dec(v: Any) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))
