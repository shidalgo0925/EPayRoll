from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from .orchestrator import LineResult, PayrollResult
from .rounding import RoundingMode, round_amount

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES = ROOT / "docs" / "seed" / "liquidation_rules.json"


@dataclass(frozen=True)
class IndemnizationBand:
    desde_anios: Decimal
    hasta_anios: Decimal | None
    semanas_por_anio: Decimal


@dataclass(frozen=True)
class LiquidationRulesConfig:
    preaviso_renuncia_dias: int
    prima_semanas_por_anio: Decimal
    indemnizacion_bands: list[IndemnizationBand]


@dataclass
class LiquidationInput:
    causa: str  # RENUNCIA, DESPIDO_JUSTIFICADO, DESPIDO_INJUSTIFICADO
    fecha_inicio: date
    fecha_terminacion: date
    salario_promedio_prima: Decimal
    dias_vacaciones_pendientes: Decimal = Decimal("0")
    salario_diario_vacaciones: Decimal | None = None
    salarios_acumulados_anio: Decimal = Decimal("0")
    salario_promedio_indemnizacion: Decimal | None = None
    cumplio_preaviso: bool = True
    preaviso_dias: int | None = None
    calcular_indemnizacion: bool | None = None


def load_liquidation_rules(path: Path | None = None) -> LiquidationRulesConfig:
    rules_path = path or DEFAULT_RULES
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    bands = [
        IndemnizationBand(
            desde_anios=Decimal(str(b["desde_anios"])),
            hasta_anios=Decimal(str(b["hasta_anios"])) if b.get("hasta_anios") else None,
            semanas_por_anio=Decimal(str(b["semanas_por_anio"])),
        )
        for b in data["indemnizacion_escala_b"]
    ]
    return LiquidationRulesConfig(
        preaviso_renuncia_dias=data.get("preaviso_renuncia_dias", 15),
        prima_semanas_por_anio=Decimal(str(data.get("prima_semanas_por_anio", 1))),
        indemnizacion_bands=bands,
    )


def antiguedad_anios(fecha_inicio: date, fecha_terminacion: date) -> Decimal:
    """Años de servicio con fracción mensual — Art. 224 CT."""
    if fecha_terminacion < fecha_inicio:
        return Decimal("0")
    meses = (fecha_terminacion.year - fecha_inicio.year) * 12 + (
        fecha_terminacion.month - fecha_inicio.month
    )
    if fecha_terminacion.day < fecha_inicio.day:
        meses -= 1
    meses = max(0, meses)
    return round_amount(Decimal(str(meses)) / Decimal("12"), RoundingMode.CENTESIMO)


def calc_vacaciones(dias: Decimal, salario_diario: Decimal) -> Decimal:
    return round_amount(dias * salario_diario, RoundingMode.CENTESIMO)


def calc_decimo_proporcional(salarios_acumulados_anio: Decimal) -> Decimal:
    """Décimo proporcional en liquidación — salarios devengados del año / 12."""
    return round_amount(salarios_acumulados_anio / Decimal("12"), RoundingMode.CENTESIMO)


def calc_prima_antiguedad(
    anios: Decimal,
    salario_mensual: Decimal,
    semanas_por_anio: Decimal = Decimal("1"),
) -> Decimal:
    """Prima antigüedad — Art. 224: N semanas de salario por año."""
    salario_semanal = salario_mensual / Decimal("4")
    return round_amount(anios * semanas_por_anio * salario_semanal, RoundingMode.CENTESIMO)


def calc_preaviso(salario_mensual: Decimal, dias: int) -> Decimal:
    salario_diario = salario_mensual / Decimal("30")
    return round_amount(salario_diario * Decimal(str(dias)), RoundingMode.CENTESIMO)


def calc_indemnizacion(
    anios: Decimal,
    salario_mensual: Decimal,
    config: LiquidationRulesConfig | None = None,
) -> Decimal:
    """Indemnización despido injustificado — Art. 225 escala B."""
    if anios < Decimal("2"):
        return Decimal("0")

    config = config or load_liquidation_rules()
    band_2_10 = next(
        (b for b in config.indemnizacion_bands if b.desde_anios == Decimal("2") and b.semanas_por_anio > 0),
        None,
    )
    band_10_plus = next(
        (b for b in config.indemnizacion_bands if b.desde_anios == Decimal("10")),
        None,
    )
    rate_mid = band_2_10.semanas_por_anio if band_2_10 else Decimal("3")
    rate_high = band_10_plus.semanas_por_anio if band_10_plus else Decimal("4")

    if anios <= Decimal("10"):
        semanas_total = anios * rate_mid
    else:
        semanas_total = Decimal("10") * rate_mid + (anios - Decimal("10")) * rate_high

    salario_semanal = salario_mensual / Decimal("4")
    return round_amount(semanas_total * salario_semanal, RoundingMode.CENTESIMO)


def run_liquidation(
    inp: LiquidationInput,
    rules: LiquidationRulesConfig | None = None,
) -> PayrollResult:
    rules = rules or load_liquidation_rules()
    anios = antiguedad_anios(inp.fecha_inicio, inp.fecha_terminacion)
    salario_prima = inp.salario_promedio_prima
    salario_diario = inp.salario_diario_vacaciones or round_amount(
        salario_prima / Decimal("30"), RoundingMode.CENTESIMO
    )

    lines: list[LineResult] = []

    vacaciones = calc_vacaciones(inp.dias_vacaciones_pendientes, salario_diario)
    if vacaciones > 0:
        lines.append(
            LineResult("VACACIONES_LIQUIDACION", "INGRESO", vacaciones, 1, "Art. 47 CT")
        )

    decimo = calc_decimo_proporcional(inp.salarios_acumulados_anio)
    if decimo > 0:
        lines.append(
            LineResult("DECIMO_PROPORCIONAL", "INGRESO", decimo, 2, "Decreto 19/1973")
        )

    prima = calc_prima_antiguedad(anios, salario_prima, rules.prima_semanas_por_anio)
    if prima > 0 and inp.causa != "DESPIDO_JUSTIFICADO":
        lines.append(
            LineResult("PRIMA_ANTIGUEDAD", "INGRESO", prima, 3, "Art. 224 CT")
        )

    calc_indem = inp.calcular_indemnizacion
    if calc_indem is None:
        calc_indem = inp.causa == "DESPIDO_INJUSTIFICADO"

    if calc_indem:
        sal_indem = inp.salario_promedio_indemnizacion or salario_prima
        indemn = calc_indemnizacion(anios, sal_indem, rules)
        if indemn > 0:
            lines.append(
                LineResult("INDEMNIZACION", "INGRESO", indemn, 4, "Art. 225 CT")
            )

    if not inp.cumplio_preaviso and inp.causa == "RENUNCIA":
        preaviso = round_amount(salario_prima / Decimal("4"), RoundingMode.CENTESIMO)
        if preaviso > 0:
            lines.append(
                LineResult(
                    "PREAVISO_DEDUCCION",
                    "DESCUENTO",
                    preaviso,
                    5,
                    "Art. 222 CT — renuncia sin preaviso (1 semana)",
                )
            )

    return PayrollResult(
        lines=lines,
        config_snapshot={
            "tipo_corrida": "LIQUIDACION",
            "causa": inp.causa,
            "antiguedad_anios": str(anios),
        },
    )
