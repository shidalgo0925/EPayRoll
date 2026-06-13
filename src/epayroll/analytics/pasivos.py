from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from epayroll.engine.liquidation import calc_prima_antiguedad, load_liquidation_rules
from epayroll.engine.liquidation import antiguedad_anios as liq_antiguedad
from epayroll.engine.rounding import RoundingMode, round_amount


@dataclass
class PasivoItem:
    concepto: str
    monto: Decimal
    detalle: str | None = None


@dataclass
class PasivosConsolidados:
    vacaciones: Decimal
    decimo_pendiente: Decimal
    prima_antiguedad: Decimal
    indemnizacion_contingente: Decimal
    total: Decimal
    items: list[PasivoItem]


def estimate_prima_total(
    employees: list[dict],
    fecha_corte,
) -> Decimal:
    rules = load_liquidation_rules()
    total = Decimal("0")
    for emp in employees:
        anios = liq_antiguedad(emp["fecha_inicio"], fecha_corte)
        total += calc_prima_antiguedad(
            anios,
            emp["salario_mensual"],
            rules.prima_semanas_por_anio,
        )
    return round_amount(total, RoundingMode.CENTESIMO)


def consolidate_pasivos(
    vacaciones: Decimal,
    decimo_pendiente: Decimal,
    prima_antiguedad: Decimal,
    indemnizacion_contingente: Decimal = Decimal("0"),
) -> PasivosConsolidados:
    items = [
        PasivoItem("VACACIONES", vacaciones, "Pasivo estimado dias pendientes"),
        PasivoItem("DECIMO", decimo_pendiente, "Acumulaciones no pagadas"),
        PasivoItem("PRIMA_ANTIGUEDAD", prima_antiguedad, "Provision prima Art. 224"),
    ]
    if indemnizacion_contingente > 0:
        items.append(
            PasivoItem(
                "INDEMNIZACION_CONTINGENTE",
                indemnizacion_contingente,
                "Escenario despido injustificado",
            )
        )
    total = vacaciones + decimo_pendiente + prima_antiguedad + indemnizacion_contingente
    return PasivosConsolidados(
        vacaciones=vacaciones,
        decimo_pendiente=decimo_pendiente,
        prima_antiguedad=prima_antiguedad,
        indemnizacion_contingente=indemnizacion_contingente,
        total=round_amount(total, RoundingMode.CENTESIMO),
        items=items,
    )
