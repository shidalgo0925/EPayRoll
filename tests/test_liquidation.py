from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from epayroll.engine.deductions import validate_art161
from epayroll.engine.liquidation import (
    LiquidationInput,
    antiguedad_anios,
    calc_indemnizacion,
    get_causa_config,
    list_termination_causes,
    run_liquidation,
    salario_semanal_desde_mensual,
)


def test_catalogo_art210_tiene_diez_causas():
    causas = list_termination_causes()
    codigos = {c["codigo"] for c in causas}
    assert len(causas) == 10
    assert "MUTUO_ACUERDO" in codigos
    assert get_causa_config("DESPIDO_JUSTIFICADO").genera_prima is True
    assert get_causa_config("SUSPENSION_PROLONGADA").genera_indemnizacion is False
    assert get_causa_config("SUSPENSION_PROLONGADA").indemnizacion_condicional is True


def test_causa_invalida_raise():
    with pytest.raises(ValueError, match="no válida"):
        get_causa_config("CAUSA_INEXISTENTE")


def test_salario_semanal_12_sobre_52():
    assert salario_semanal_desde_mensual(Decimal("1750")) == Decimal("403.85")
    assert salario_semanal_desde_mensual(Decimal("2000")) == Decimal("461.54")


def test_gt05_renuncia_con_prestaciones_indefinido():
    """GT-05 — vacaciones + décimo + prima (contrato indefinido, semanal×12/52)."""
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2022, 2, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        dias_vacaciones_pendientes=Decimal("12"),
        salario_diario_vacaciones=Decimal("58.33"),
        salarios_acumulados_anio=Decimal("5250"),
        cumplio_preaviso=True,
        tipo_contrato="INDEFINIDO",
        es_indefinido=True,
    )
    r = run_liquidation(inp)

    assert r.amount("VACACIONES_LIQUIDACION") == Decimal("699.96")
    assert r.amount("DECIMO_PROPORCIONAL") == Decimal("437.50")
    assert r.amount("PRIMA_ANTIGUEDAD") == Decimal("1344.82")
    assert r.amount("INDEMNIZACION") == Decimal("0")
    assert r.neto == Decimal("2482.28")


def test_gt05_renuncia_sin_prima_si_no_indefinido():
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2022, 2, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        dias_vacaciones_pendientes=Decimal("12"),
        salario_diario_vacaciones=Decimal("58.33"),
        salarios_acumulados_anio=Decimal("5250"),
        tipo_contrato="DEFINIDO",
        es_indefinido=False,
    )
    r = run_liquidation(inp)
    assert r.amount("PRIMA_ANTIGUEDAD") == Decimal("0")
    assert r.neto == Decimal("1137.46")


def test_gt05_preaviso_deduccion_una_semana():
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2022, 2, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        dias_vacaciones_pendientes=Decimal("12"),
        salario_diario_vacaciones=Decimal("58.33"),
        salarios_acumulados_anio=Decimal("5250"),
        cumplio_preaviso=False,
        es_indefinido=True,
    )
    r = run_liquidation(inp)
    assert r.amount("PREAVISO_DEDUCCION") == Decimal("403.85")
    assert r.neto == Decimal("2078.43")


def test_preaviso_por_fechas_tecnico():
    """Técnico: 60 días requeridos; 30 días de aviso → incumplimiento."""
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2020, 1, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        es_indefinido=True,
        es_tecnico=True,
        fecha_notificacion_preaviso=date(2025, 5, 1),
        preaviso_formalizado=True,
    )
    r = run_liquidation(inp)
    assert r.amount("PREAVISO_DEDUCCION") == Decimal("403.85")


def test_gt06_indemnizacion_escala_c():
    """GT-06 moderno — escala C: 5 × 3.4 semanas × (2000×12/52)."""
    inp = LiquidationInput(
        causa="DESPIDO_INJUSTIFICADO",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        salario_promedio_indemnizacion=Decimal("2000"),
        dias_vacaciones_pendientes=Decimal("0"),
        es_indefinido=True,
        regimen_indemnizacion="C",
    )
    r = run_liquidation(inp)
    assert antiguedad_anios(inp.fecha_inicio, inp.fecha_terminacion) == Decimal("5.00")
    assert r.amount("INDEMNIZACION") == Decimal("7846.18")


def test_indemnizacion_escala_b_legacy():
    """Escala B histórica: <2 años = 0; 5 años = 3 sem/año × semanal 12/52."""
    assert calc_indemnizacion(Decimal("1.5"), Decimal("2000"), regimen="B") == Decimal("0")
    # 5 × 3 × 461.54 = 6923.10
    assert calc_indemnizacion(Decimal("5"), Decimal("2000"), regimen="B") == Decimal("6923.10")


def test_renuncia_justificada_incluye_indemnizacion_c():
    inp = LiquidationInput(
        causa="RENUNCIA_JUSTIFICADA",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        salario_promedio_indemnizacion=Decimal("2000"),
        es_indefinido=True,
        regimen_indemnizacion="C",
    )
    r = run_liquidation(inp)
    assert r.amount("PRIMA_ANTIGUEDAD") > 0
    assert r.amount("INDEMNIZACION") == Decimal("7846.18")


def test_despido_justificado_con_prima_si_indefinido():
    inp = LiquidationInput(
        causa="DESPIDO_JUSTIFICADO",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        dias_vacaciones_pendientes=Decimal("10"),
        salario_diario_vacaciones=Decimal("66.67"),
        salarios_acumulados_anio=Decimal("12000"),
        es_indefinido=True,
    )
    r = run_liquidation(inp)
    assert r.amount("VACACIONES_LIQUIDACION") == Decimal("666.70")
    assert r.amount("DECIMO_PROPORCIONAL") == Decimal("1000.00")
    assert r.amount("PRIMA_ANTIGUEDAD") > 0
    assert r.amount("INDEMNIZACION") == Decimal("0")


def test_mutuo_acuerdo_indemnizacion_negociada():
    inp = LiquidationInput(
        causa="MUTUO_ACUERDO",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        es_indefinido=True,
        monto_indemnizacion_acordado=Decimal("3500"),
        documento_ref="Acta 12-2025",
    )
    r = run_liquidation(inp)
    assert r.amount("PRIMA_ANTIGUEDAD") > 0
    assert r.amount("INDEMNIZACION") == Decimal("3500.00")


def test_vencimiento_sin_prima():
    inp = LiquidationInput(
        causa="VENCIMIENTO_CONTRATO",
        fecha_inicio=date(2023, 1, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1500"),
        dias_vacaciones_pendientes=Decimal("5"),
        salario_diario_vacaciones=Decimal("50"),
        salarios_acumulados_anio=Decimal("6000"),
        tipo_contrato="DEFINIDO",
        es_indefinido=False,
    )
    r = run_liquidation(inp)
    assert r.amount("PRIMA_ANTIGUEDAD") == Decimal("0")
    assert r.amount("INDEMNIZACION") == Decimal("0")


def test_suspension_sin_indemnizacion_automatica():
    inp = LiquidationInput(
        causa="SUSPENSION_PROLONGADA",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        es_indefinido=True,
    )
    r = run_liquidation(inp)
    assert r.amount("INDEMNIZACION") == Decimal("0")
    assert r.amount("PRIMA_ANTIGUEDAD") > 0


def test_suspension_indemnizacion_con_override_y_fundamento():
    inp = LiquidationInput(
        causa="SUSPENSION_PROLONGADA",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        es_indefinido=True,
        calcular_indemnizacion=True,
        fundamento_indemnizacion="Dictamen legal — Art. 213 C",
        regimen_indemnizacion="C",
    )
    r = run_liquidation(inp)
    assert r.amount("INDEMNIZACION") == Decimal("7846.18")


def test_salario_pendiente_suma_al_total():
    inp = LiquidationInput(
        causa="RENUNCIA",
        fecha_inicio=date(2022, 2, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("1750"),
        dias_vacaciones_pendientes=Decimal("0"),
        salarios_acumulados_anio=Decimal("0"),
        cumplio_preaviso=True,
        salario_pendiente=Decimal("875.50"),
        es_indefinido=True,
    )
    r = run_liquidation(inp)
    assert r.amount("SALARIO_PENDIENTE") == Decimal("875.50")
    assert r.neto == r.amount("PRIMA_ANTIGUEDAD") + Decimal("875.50")


def test_muerte_trabajador_prima_si_indefinido():
    inp = LiquidationInput(
        causa="MUERTE_TRABAJADOR",
        fecha_inicio=date(2020, 6, 1),
        fecha_terminacion=date(2025, 6, 1),
        salario_promedio_prima=Decimal("2000"),
        dias_vacaciones_pendientes=Decimal("8"),
        salario_diario_vacaciones=Decimal("66.67"),
        salarios_acumulados_anio=Decimal("10000"),
        es_indefinido=True,
        notas="Beneficiario: María Pérez",
    )
    r = run_liquidation(inp)
    assert r.amount("PRIMA_ANTIGUEDAD") > 0
    assert r.amount("INDEMNIZACION") == Decimal("0")
    assert r.config_snapshot.get("notas") == "Beneficiario: María Pérez"


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
