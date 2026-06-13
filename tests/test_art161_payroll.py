from __future__ import annotations

from decimal import Decimal

from epayroll.engine.context import PayrollInput
from epayroll.engine.deductions import validate_art161
from epayroll.engine.orchestrator import PayrollEngine


def test_descuento_voluntario_sobre_tope_art161():
    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=Decimal("1800"),
        dias_trabajados=Decimal("15"),
        es_quincena=True,
        descuento_voluntario=Decimal("500"),
    )
    r = engine.run(inp)
    deductions = {l.codigo_concepto: l.monto for l in r.lines if l.tipo == "DESCUENTO"}
    deductions["DESCUENTO_VOLUNTARIO"] = Decimal("500")
    v = validate_art161(r.bruto, deductions)
    assert v.valid is False
