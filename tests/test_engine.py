from __future__ import annotations

from decimal import Decimal

import pytest

from epayroll.engine.context import PayrollInput
from epayroll.engine.evaluator import SafeEvaluator
from epayroll.engine.orchestrator import PayrollEngine


def test_evaluator_salario_diario():
    ev = SafeEvaluator({"salario_diario": Decimal("60"), "dias_trabajados": Decimal("15")})
    assert ev.eval_amount("salario_diario * dias_trabajados") == Decimal("900")


def test_evaluator_min_tope():
    ev = SafeEvaluator(
        {"bruto_cotizable": Decimal("900"), "tope_css": Decimal("999999999")},
        functions={"min": min},
    )
    assert ev.eval_amount("min(bruto_cotizable, tope_css) * 0.0975") == Decimal("87.75")


def test_gt01_quincenal_administrativo():
    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=Decimal("1800"),
        dias_trabajados=Decimal("15"),
        es_quincena=True,
        mes=6,
        tasa_css_patronal=Decimal("0.1325"),
        tasa_riesgo_empresa=Decimal("0.0105"),
        tasa_prima_antiguedad_patronal=Decimal("0.0192"),
    )
    r = engine.run(inp)

    assert r.amount("SALARIO_BASE") == Decimal("900.00")
    assert r.amount("CSS_EMPLEADO") == Decimal("87.75")
    assert r.amount("SE_EMPLEADO") == Decimal("11.25")
    assert r.amount("CSS_EMPLEADOR") == Decimal("119.25")
    assert r.amount("SE_EMPLEADOR") == Decimal("13.50")
    assert r.amount("RIESGO_PROFESIONAL") == Decimal("9.45")
    assert r.amount("PRIMA_ANTIGUEDAD_PATRONAL") == Decimal("17.28")
    assert r.bruto == Decimal("900.00")

    # ISR: (bruto×13 − 11,000) × 15% / 13 / 2 quincenal
    isr = r.amount("ISR")
    assert isr == Decimal("71.54")

    neto = r.neto
    assert neto == Decimal("729.46")


def test_gt02_horas_extras():
    engine = PayrollEngine()
    salario = Decimal("1600")
    inp = PayrollInput(
        salario_mensual=salario,
        dias_trabajados=Decimal("26"),
        horas_extra_diurnas=Decimal("4"),
        horas_extra_nocturnas=Decimal("2"),
    )
    r = engine.run(inp)

    extra_d = r.amount("HORA_EXTRA_DIURNA")
    extra_n = r.amount("HORA_EXTRA_NOCTURNA")

    assert extra_d == Decimal("38.46")  # 7.6923... * 1.25 * 4
    assert extra_n == Decimal("23.08")  # 7.6923... * 1.5 * 2
    assert extra_d + extra_n == Decimal("61.54")
