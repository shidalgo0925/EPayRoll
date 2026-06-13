from __future__ import annotations

from datetime import date
from decimal import Decimal

from epayroll.engine.deductions import validate_art161
from epayroll.engine.liquidation import LiquidationInput, antiguedad_anios, run_liquidation


def test_gt05_renuncia_con_prestaciones():
    """GT-05 — vacaciones + décimo + prima antigüedad."""
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2022, 2, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        dias_vacaciones_pendientes=Decimal("12"),
        salario_diario_vacaciones=Decimal("58.33"),
        salarios_acumulados_anio=Decimal("5250"),
        cumplio_preaviso=True,
    )
    r = run_liquidation(inp)

    assert r.amount("VACACIONES_LIQUIDACION") == Decimal("699.96")
    assert r.amount("DECIMO_PROPORCIONAL") == Decimal("437.50")
    assert r.amount("PRIMA_ANTIGUEDAD") == Decimal("1456.88")
    assert r.amount("INDEMNIZACION") == Decimal("0")
    assert r.neto == Decimal("2594.34")


def test_gt05_preaviso_deduccion():
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2022, 2, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        dias_vacaciones_pendientes=Decimal("12"),
        salario_diario_vacaciones=Decimal("58.33"),
        salarios_acumulados_anio=Decimal("5250"),
        cumplio_preaviso=False,
    )
    r = run_liquidation(inp)
    assert r.amount("PREAVISO_DEDUCCION") == Decimal("437.50")
    assert r.neto == Decimal("2156.84")


def test_gt06_indemnizacion_despido():
    """GT-06 — 5 años, 15 semanas × salario semanal."""
    inp = LiquidationInput(
        causa="DESPIDO_INJUSTIFICADO",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        salario_promedio_indemnizacion=Decimal("2000"),
        dias_vacaciones_pendientes=Decimal("0"),
    )
    r = run_liquidation(inp)
    assert antiguedad_anios(inp.fecha_inicio, inp.fecha_terminacion) == Decimal("5.00")
    assert r.amount("INDEMNIZACION") == Decimal("7500.00")


def test_art161_tope_descuentos_voluntarios():
    ok = validate_art161(
        bruto=Decimal("900"),
        deductions_by_concept={
            "CSS_EMPLEADO": Decimal("87.75"),
            "SE_EMPLEADO": Decimal("11.25"),
            "ISR": Decimal("116.75"),
            "DESCUENTO_VOLUNTARIO": Decimal("400"),
        },
    )
    assert ok.valid is True
    assert ok.max_voluntario_permitido == Decimal("450.00")

    fail = validate_art161(
        bruto=Decimal("900"),
        deductions_by_concept={
            "CSS_EMPLEADO": Decimal("87.75"),
            "DESCUENTO_VOLUNTARIO": Decimal("500"),
        },
    )
    assert fail.valid is False
    assert "Art. 161" in fail.errors[0]
