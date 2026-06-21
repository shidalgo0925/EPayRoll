"""Tests — tasas legales por organización en motor."""

from __future__ import annotations

from decimal import Decimal

from epayroll.db.legal_config_repository import LegalConfigRepository
from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine
from epayroll.db.config_loader import load_config_from_seed


def test_payroll_input_exposes_org_rate_variables():
    inp = PayrollInput(
        salario_mensual=Decimal("1600"),
        dias_trabajados=Decimal("15"),
        tasa_css_empleado=Decimal("0.10"),
        tasa_se_empleado=Decimal("0.02"),
        tasa_se_patronal=Decimal("0.02"),
    )
    ctx = inp  # PayrollContext uses input
    from epayroll.engine.context import PayrollContext

    d = PayrollContext(input=inp).as_dict()
    assert d["tasa_css_empleado"] == Decimal("0.10")
    assert d["tasa_se_empleado"] == Decimal("0.02")


def test_engine_uses_variable_css_rate():
    config = load_config_from_seed()
    engine = PayrollEngine(config=config)
    inp = PayrollInput(
        salario_mensual=Decimal("1000"),
        dias_trabajados=Decimal("15"),
        tasa_css_empleado=Decimal("0.10"),
        tasa_se_empleado=Decimal("0.0125"),
        tasa_se_patronal=Decimal("0.015"),
    )
    r = engine.run(inp)
    bruto = r.amount("SALARIO_BASE")
    expected_css = (bruto * Decimal("0.10")).quantize(Decimal("0.01"))
    assert r.amount("CSS_EMPLEADO") == expected_css


def test_resolve_rates_defaults():
    repo = LegalConfigRepository()
    rates = repo.resolve_rates_for_payroll("00000000-0000-0000-0000-000000000010")
    assert rates["tasa_css_empleado"] == Decimal("0.0975")
    assert rates["tasa_css_patronal"] == Decimal("0.1325")
