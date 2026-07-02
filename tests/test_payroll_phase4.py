from __future__ import annotations

from decimal import Decimal

from epayroll.engine.decimo import DecimoInput, run_decimo
from epayroll.engine.isr import IsrBracket, IsrConfig, calc_impuesto_anual, calc_isr_mensual


def test_gt04_decimo_abril():
    """GT-04: salarios dic–mar = 7350 → décimo 612.50, CSS 7.25%."""
    r = run_decimo(DecimoInput(salarios_cotizables=Decimal("7350")))

    assert r.amount("DECIMO_TERCER") == Decimal("612.50")
    assert r.amount("CSS_EMPLEADO") == Decimal("44.41")
    assert r.amount("CSS_EMPLEADOR") == Decimal("44.41")
    assert r.amount("SE_EMPLEADO") == Decimal("0")
    assert r.amount("ISR") == Decimal("0")
    assert r.neto == Decimal("568.09")


def test_gt09_isr_ajuste_diciembre():
    """GT-09: ajuste mes 12 — suma ene–dic = impuesto anual exacto."""
    brackets = [
        IsrBracket(
            rango_desde=Decimal("0"),
            rango_hasta=Decimal("11000"),
            porcentaje=Decimal("0"),
            excedente_desde=Decimal("0"),
            impuesto_fijo_acumulado=Decimal("0"),
        ),
        IsrBracket(
            rango_desde=Decimal("11000.01"),
            rango_hasta=Decimal("50000"),
            porcentaje=Decimal("0.15"),
            excedente_desde=Decimal("11000"),
            impuesto_fijo_acumulado=Decimal("0"),
        ),
    ]
    config = IsrConfig(factor_anualizacion=13, brackets=brackets)
    bruto = Decimal("3000")
    css = Decimal("0")

    impuesto_anual = calc_impuesto_anual(bruto * Decimal("13"), brackets)
    assert impuesto_anual == Decimal("4200")

    acumulado = Decimal("0")
    retenciones: list[Decimal] = []
    for mes in range(1, 13):
        isr = calc_isr_mensual(
            bruto_mensual=bruto,
            css_mensual=css,
            config=config,
            mes=mes,
            acumulado_isr_ytd=acumulado,
        )
        retenciones.append(isr)
        acumulado += isr

    assert sum(retenciones) == impuesto_anual
    assert abs(retenciones[0] - Decimal("323.08")) <= Decimal("0.01")
    assert retenciones[11] > retenciones[0]


def test_isr_juan_perez_quincenal_1700():
    """Juan Perez: (1700×13 − 11000) × 15% / 13 / 2 = 64.04"""
    brackets = [
        IsrBracket(
            rango_desde=Decimal("0"),
            rango_hasta=Decimal("11000"),
            porcentaje=Decimal("0"),
            excedente_desde=Decimal("0"),
            impuesto_fijo_acumulado=Decimal("0"),
        ),
        IsrBracket(
            rango_desde=Decimal("11000.01"),
            rango_hasta=Decimal("50000"),
            porcentaje=Decimal("0.15"),
            excedente_desde=Decimal("11000"),
            impuesto_fijo_acumulado=Decimal("0"),
        ),
    ]
    config = IsrConfig(factor_anualizacion=13, deduccion_previa="ninguna", brackets=brackets)
    isr = calc_isr_mensual(
        bruto_mensual=Decimal("1700"),
        css_mensual=Decimal("165.76"),
        config=config,
        mes=1,
        es_quincena=True,
    )
    assert isr == Decimal("64.04")
