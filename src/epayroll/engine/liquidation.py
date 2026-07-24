from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .orchestrator import LineResult, PayrollResult
from .rounding import RoundingMode, round_amount

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RULES = ROOT / "docs" / "seed" / "liquidation_rules.json"

RegimenIndemnizacion = Literal["B", "C"]


@dataclass(frozen=True)
class IndemnizationBand:
    desde_anios: Decimal
    hasta_anios: Decimal | None
    semanas_por_anio: Decimal


@dataclass(frozen=True)
class RegimenCConfig:
    semanas_primeros_10: Decimal
    semanas_despues_10: Decimal
    min_anios_indemnizacion: Decimal


@dataclass(frozen=True)
class RegimenBConfig:
    min_anios_indemnizacion: Decimal
    bands: list[IndemnizationBand]


@dataclass(frozen=True)
class CausaConfig:
    codigo: str
    label: str
    iniciativa: str
    genera_prima: bool
    genera_indemnizacion: bool
    indemnizacion_negociable: bool
    indemnizacion_condicional: bool
    genera_preaviso: bool
    requiere_documento: bool


@dataclass(frozen=True)
class LiquidationRulesConfig:
    preaviso_renuncia_dias: int
    preaviso_tecnico_dias: int
    preaviso_incumplimiento_semanas: Decimal
    prima_semanas_por_anio: Decimal
    prima_requiere_indefinido: bool
    regimen_indemnizacion_default: RegimenIndemnizacion
    regimen_b: RegimenBConfig
    regimen_c: RegimenCConfig
    causas: dict[str, CausaConfig]


@dataclass
class LiquidationInput:
    causa: str
    fecha_inicio: date
    fecha_terminacion: date
    salario_promedio_prima: Decimal
    dias_vacaciones_pendientes: Decimal = Decimal("0")
    salario_diario_vacaciones: Decimal | None = None
    salarios_acumulados_anio: Decimal = Decimal("0")
    salario_promedio_indemnizacion: Decimal | None = None
    cumplio_preaviso: bool | None = None
    preaviso_dias: int | None = None
    calcular_indemnizacion: bool | None = None
    salario_pendiente: Decimal = Decimal("0")
    monto_indemnizacion_acordado: Decimal | None = None
    monto_prima_acordado: Decimal | None = None
    tipo_contrato: str | None = None
    es_indefinido: bool | None = None
    regimen_indemnizacion: RegimenIndemnizacion | None = None
    fecha_notificacion_preaviso: date | None = None
    es_tecnico: bool = False
    preaviso_formalizado: bool = True
    fundamento_indemnizacion: str | None = None
    notas: str | None = None
    documento_ref: str | None = None


def salario_semanal_desde_mensual(salario_mensual: Decimal) -> Decimal:
    """Política producto: mensual × 12 ÷ 52 (52 semanas/año)."""
    return round_amount(
        salario_mensual * Decimal("12") / Decimal("52"),
        RoundingMode.CENTESIMO,
    )


def _parse_causas(raw: list[dict]) -> dict[str, CausaConfig]:
    out: dict[str, CausaConfig] = {}
    for item in raw:
        # Compatibilidad seed v2 → v3
        genera_prima = item.get("genera_prima")
        if genera_prima is None:
            genera_prima = bool(item.get("prima", False))
        genera_indemnizacion = item.get("genera_indemnizacion")
        if genera_indemnizacion is None:
            genera_indemnizacion = bool(item.get("indemnizacion", False))
        genera_preaviso = item.get("genera_preaviso")
        if genera_preaviso is None:
            genera_preaviso = bool(item.get("preaviso_deduccion", False))
        cfg = CausaConfig(
            codigo=item["codigo"],
            label=item.get("label", item["codigo"]),
            iniciativa=item.get("iniciativa", ""),
            genera_prima=bool(genera_prima),
            genera_indemnizacion=bool(genera_indemnizacion),
            indemnizacion_negociable=bool(item.get("indemnizacion_negociable", False)),
            indemnizacion_condicional=bool(item.get("indemnizacion_condicional", False)),
            genera_preaviso=bool(genera_preaviso),
            requiere_documento=bool(item.get("requiere_documento", False)),
        )
        out[cfg.codigo] = cfg
    return out


def _parse_regimen_b(data: dict) -> RegimenBConfig:
    regimens = data.get("regimenes_indemnizacion") or {}
    raw_b = regimens.get("B") or {}
    tramos = raw_b.get("tramos") or data.get("indemnizacion_escala_b") or []
    bands = [
        IndemnizationBand(
            desde_anios=Decimal(str(b["desde_anios"])),
            hasta_anios=Decimal(str(b["hasta_anios"])) if b.get("hasta_anios") is not None else None,
            semanas_por_anio=Decimal(str(b["semanas_por_anio"])),
        )
        for b in tramos
    ]
    return RegimenBConfig(
        min_anios_indemnizacion=Decimal(str(raw_b.get("min_anios_indemnizacion", 2))),
        bands=bands,
    )


def _parse_regimen_c(data: dict) -> RegimenCConfig:
    regimens = data.get("regimenes_indemnizacion") or {}
    raw_c = regimens.get("C") or {}
    return RegimenCConfig(
        semanas_primeros_10=Decimal(str(raw_c.get("semanas_primeros_10", "3.4"))),
        semanas_despues_10=Decimal(str(raw_c.get("semanas_despues_10", "1"))),
        min_anios_indemnizacion=Decimal(str(raw_c.get("min_anios_indemnizacion", 0))),
    )


def load_liquidation_rules(path: Path | None = None) -> LiquidationRulesConfig:
    rules_path = path or DEFAULT_RULES
    with open(rules_path, encoding="utf-8") as f:
        data = json.load(f)
    causas = _parse_causas(data.get("causas") or [])
    default_reg = str(data.get("regimen_indemnizacion_default", "C")).upper()
    if default_reg not in ("B", "C"):
        default_reg = "C"
    return LiquidationRulesConfig(
        preaviso_renuncia_dias=int(data.get("preaviso_renuncia_dias", 15)),
        preaviso_tecnico_dias=int(data.get("preaviso_tecnico_dias", 60)),
        preaviso_incumplimiento_semanas=Decimal(
            str(data.get("preaviso_incumplimiento_semanas", 1))
        ),
        prima_semanas_por_anio=Decimal(str(data.get("prima_semanas_por_anio", 1))),
        prima_requiere_indefinido=bool(data.get("prima_requiere_indefinido", True)),
        regimen_indemnizacion_default=default_reg,  # type: ignore[arg-type]
        regimen_b=_parse_regimen_b(data),
        regimen_c=_parse_regimen_c(data),
        causas=causas,
    )


def list_termination_causes(path: Path | None = None) -> list[dict]:
    rules = load_liquidation_rules(path)
    return [
        {
            "codigo": c.codigo,
            "label": c.label,
            "iniciativa": c.iniciativa,
            "genera_prima": c.genera_prima,
            "genera_indemnizacion": c.genera_indemnizacion,
            "indemnizacion_negociable": c.indemnizacion_negociable,
            "indemnizacion_condicional": c.indemnizacion_condicional,
            "genera_preaviso": c.genera_preaviso,
            "requiere_documento": c.requiere_documento,
            # aliases UI legacy
            "prima": c.genera_prima,
            "indemnizacion": c.genera_indemnizacion,
            "preaviso_deduccion": c.genera_preaviso,
        }
        for c in rules.causas.values()
    ]


def get_causa_config(
    codigo: str,
    rules: LiquidationRulesConfig | None = None,
) -> CausaConfig:
    rules = rules or load_liquidation_rules()
    cfg = rules.causas.get(codigo)
    if not cfg:
        raise ValueError(f"Causa de terminación no válida: {codigo}")
    return cfg


def causa_label(codigo: str, rules: LiquidationRulesConfig | None = None) -> str:
    try:
        return get_causa_config(codigo, rules).label
    except ValueError:
        return codigo


def resolve_es_indefinido(inp: LiquidationInput) -> bool:
    if inp.es_indefinido is not None:
        return bool(inp.es_indefinido)
    tipo = (inp.tipo_contrato or "").upper()
    return tipo == "INDEFINIDO"


def resolve_regimen(
    inp: LiquidationInput,
    rules: LiquidationRulesConfig,
) -> RegimenIndemnizacion:
    if inp.regimen_indemnizacion in ("B", "C"):
        return inp.regimen_indemnizacion
    return rules.regimen_indemnizacion_default


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
    """Prima antigüedad — Art. 224: N semanas × salario semanal (mensual×12/52)."""
    semanal = salario_semanal_desde_mensual(salario_mensual)
    return round_amount(anios * semanas_por_anio * semanal, RoundingMode.CENTESIMO)


def calc_preaviso(salario_mensual: Decimal, dias: int) -> Decimal:
    salario_diario = salario_mensual / Decimal("30")
    return round_amount(salario_diario * Decimal(str(dias)), RoundingMode.CENTESIMO)


def semanas_indemnizacion(
    anios: Decimal,
    regimen: RegimenIndemnizacion,
    rules: LiquidationRulesConfig,
) -> Decimal:
    if regimen == "C":
        cfg = rules.regimen_c
        if anios < cfg.min_anios_indemnizacion:
            return Decimal("0")
        if anios <= Decimal("10"):
            return anios * cfg.semanas_primeros_10
        return (
            Decimal("10") * cfg.semanas_primeros_10
            + (anios - Decimal("10")) * cfg.semanas_despues_10
        )

    # Escala B
    cfg_b = rules.regimen_b
    if anios < cfg_b.min_anios_indemnizacion:
        return Decimal("0")
    band_mid = next(
        (
            b
            for b in cfg_b.bands
            if b.desde_anios == Decimal("2") and b.semanas_por_anio > 0
        ),
        None,
    )
    band_high = next(
        (b for b in cfg_b.bands if b.desde_anios == Decimal("10")),
        None,
    )
    rate_mid = band_mid.semanas_por_anio if band_mid else Decimal("3")
    rate_high = band_high.semanas_por_anio if band_high else Decimal("4")
    if anios <= Decimal("10"):
        return anios * rate_mid
    return Decimal("10") * rate_mid + (anios - Decimal("10")) * rate_high


def calc_indemnizacion(
    anios: Decimal,
    salario_mensual: Decimal,
    regimen: RegimenIndemnizacion = "C",
    config: LiquidationRulesConfig | None = None,
) -> Decimal:
    """Indemnización Art. 225 — régimen B (histórico) o C (Ley 44/1995, default)."""
    config = config or load_liquidation_rules()
    semanas = semanas_indemnizacion(anios, regimen, config)
    if semanas <= 0:
        return Decimal("0")
    semanal = salario_semanal_desde_mensual(salario_mensual)
    return round_amount(semanas * semanal, RoundingMode.CENTESIMO)


def resolve_cumplio_preaviso(
    inp: LiquidationInput,
    rules: LiquidationRulesConfig,
) -> tuple[bool, int]:
    """
    Retorna (cumplio, dias_requeridos).
    Si hay fecha de notificación, calcula contra 15 días o 60 (técnico).
    """
    dias_req = (
        rules.preaviso_tecnico_dias if inp.es_tecnico else rules.preaviso_renuncia_dias
    )
    if inp.fecha_notificacion_preaviso is not None:
        delta = (inp.fecha_terminacion - inp.fecha_notificacion_preaviso).days
        cumplio = delta >= dias_req and bool(inp.preaviso_formalizado)
        return cumplio, dias_req
    if inp.cumplio_preaviso is not None:
        return bool(inp.cumplio_preaviso), dias_req
    return True, dias_req


def aplica_prima(causa: CausaConfig, es_indefinido: bool, rules: LiquidationRulesConfig) -> bool:
    if not causa.genera_prima:
        return False
    if rules.prima_requiere_indefinido and not es_indefinido:
        return False
    return True


def aplica_indemnizacion_legal(
    causa: CausaConfig,
    inp: LiquidationInput,
) -> bool:
    """Flags jurídicos + overrides (condicional / forzar)."""
    if causa.indemnizacion_negociable:
        return False  # se maneja por monto acordado
    if inp.calcular_indemnizacion is True:
        return True
    if inp.calcular_indemnizacion is False:
        return False
    if causa.indemnizacion_condicional:
        return False  # requiere override explícito
    return causa.genera_indemnizacion


def run_liquidation(
    inp: LiquidationInput,
    rules: LiquidationRulesConfig | None = None,
) -> PayrollResult:
    rules = rules or load_liquidation_rules()
    causa = get_causa_config(inp.causa, rules)
    anios = antiguedad_anios(inp.fecha_inicio, inp.fecha_terminacion)
    es_indefinido = resolve_es_indefinido(inp)
    regimen = resolve_regimen(inp, rules)
    salario_prima = inp.salario_promedio_prima
    salario_diario = inp.salario_diario_vacaciones or round_amount(
        salario_prima / Decimal("30"), RoundingMode.CENTESIMO
    )
    semanal = salario_semanal_desde_mensual(salario_prima)

    lines: list[LineResult] = []

    if inp.salario_pendiente and inp.salario_pendiente > 0:
        lines.append(
            LineResult(
                "SALARIO_PENDIENTE",
                "INGRESO",
                round_amount(inp.salario_pendiente, RoundingMode.CENTESIMO),
                0,
                "Salario pendiente no pagado",
            )
        )

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

    if aplica_prima(causa, es_indefinido, rules):
        if inp.monto_prima_acordado is not None:
            prima = round_amount(inp.monto_prima_acordado, RoundingMode.CENTESIMO)
        else:
            prima = calc_prima_antiguedad(anios, salario_prima, rules.prima_semanas_por_anio)
        if prima > 0:
            lines.append(
                LineResult("PRIMA_ANTIGUEDAD", "INGRESO", prima, 3, "Art. 224 CT")
            )

    if causa.indemnizacion_negociable and inp.monto_indemnizacion_acordado is not None:
        indemn = round_amount(inp.monto_indemnizacion_acordado, RoundingMode.CENTESIMO)
        if indemn > 0:
            lines.append(
                LineResult(
                    "INDEMNIZACION",
                    "INGRESO",
                    indemn,
                    4,
                    "Mutuo acuerdo — indemnización negociada",
                )
            )
    elif aplica_indemnizacion_legal(causa, inp):
        sal_indem = inp.salario_promedio_indemnizacion or salario_prima
        indemn = calc_indemnizacion(anios, sal_indem, regimen=regimen, config=rules)
        if indemn > 0:
            ref = f"Art. 225 CT escala {regimen}"
            if causa.indemnizacion_condicional and inp.fundamento_indemnizacion:
                ref = f"{ref} — {inp.fundamento_indemnizacion}"
            lines.append(LineResult("INDEMNIZACION", "INGRESO", indemn, 4, ref))

    if causa.genera_preaviso:
        cumplio, dias_req = resolve_cumplio_preaviso(inp, rules)
        if not cumplio:
            preaviso = round_amount(
                semanal * rules.preaviso_incumplimiento_semanas,
                RoundingMode.CENTESIMO,
            )
            if preaviso > 0:
                lines.append(
                    LineResult(
                        "PREAVISO_DEDUCCION",
                        "DESCUENTO",
                        preaviso,
                        5,
                        f"Art. 222 CT — renuncia sin preaviso "
                        f"({dias_req} días requeridos; descuento 1 semana)",
                    )
                )

    return PayrollResult(
        lines=lines,
        config_snapshot={
            "tipo_corrida": "LIQUIDACION",
            "causa": inp.causa,
            "causa_label": causa.label,
            "antiguedad_anios": str(anios),
            "es_indefinido": es_indefinido,
            "tipo_contrato": inp.tipo_contrato,
            "regimen_indemnizacion": regimen,
            "salario_semanal": str(semanal),
            "es_tecnico": inp.es_tecnico,
            "fecha_notificacion_preaviso": (
                inp.fecha_notificacion_preaviso.isoformat()
                if inp.fecha_notificacion_preaviso
                else None
            ),
            "preaviso_formalizado": inp.preaviso_formalizado,
            "fundamento_indemnizacion": inp.fundamento_indemnizacion,
            "notas": inp.notas,
            "documento_ref": inp.documento_ref,
            "flags": {
                "genera_prima": causa.genera_prima,
                "genera_indemnizacion": causa.genera_indemnizacion,
                "indemnizacion_condicional": causa.indemnizacion_condicional,
                "genera_preaviso": causa.genera_preaviso,
            },
        },
    )
