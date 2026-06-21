"""Planilla con asistencia — ausencias reducen días de pago."""

from __future__ import annotations

from decimal import Decimal

from epayroll.db.attendance_facts_repository import AttendanceFactsRepository
from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine


def test_monto_descuento_ausencia():
    salario_mensual = Decimal("850")
    sal_diario = salario_mensual / Decimal("30")
    monto = (sal_diario * Decimal("1")).quantize(Decimal("0.01"))
    assert monto == Decimal("28.33")


def test_dias_pago_nominal_quincena():
    repo = AttendanceFactsRepository()
    assert repo.payroll_dias_pago_nominal(True) == Decimal("15")
    assert repo.compute_payroll_dias_trabajados(0, 0, es_quincena=True) == Decimal("15")
    assert repo.compute_payroll_dias_trabajados(1, 0, es_quincena=True) == Decimal("14")
    assert repo.compute_payroll_dias_trabajados(1, 1, es_quincena=True) == Decimal("13")


def test_salario_baja_con_una_ausencia_quincena():
    engine = PayrollEngine()
    salario_mensual = Decimal("850")
    full = engine.run(
        PayrollInput(salario_mensual=salario_mensual, dias_trabajados=Decimal("15"), es_quincena=True)
    )
    con_ausencia = engine.run(
        PayrollInput(salario_mensual=salario_mensual, dias_trabajados=Decimal("14"), es_quincena=True)
    )
    assert con_ausencia.amount("SALARIO_BASE") < full.amount("SALARIO_BASE")
    diff = full.amount("SALARIO_BASE") - con_ausencia.amount("SALARIO_BASE")
    assert diff.quantize(Decimal("0.01")) == (salario_mensual / Decimal("30")).quantize(Decimal("0.01"))
