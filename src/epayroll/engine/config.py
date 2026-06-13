from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .isr import IsrBracket, IsrConfig


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED_DIR = ROOT / "docs" / "seed"


@dataclass
class ConceptDef:
    codigo: str
    descripcion: str
    tipo: str
    orden_visual: int = 0


@dataclass
class RuleDef:
    codigo_concepto: str
    condicion_aplicacion: str
    base_calculo: str
    unidad: str
    aplica_contratos: list[str]
    prioridad_calculo: int
    redondeo: str
    referencia_legal: str | None = None


@dataclass
class EngineConfig:
    as_of: date
    concepts: dict[str, ConceptDef]
    rules: list[RuleDef]
    isr: IsrConfig
    tasa_css_patronal: Decimal
    tasa_prima_antiguedad_patronal: Decimal


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _in_vigencia(data: dict[str, Any], as_of: date) -> bool:
    desde = date.fromisoformat(data["vigencia_desde"])
    hasta_raw = data.get("vigencia_hasta")
    hasta = date.fromisoformat(hasta_raw) if hasta_raw else None
    if as_of < desde:
        return False
    if hasta and as_of > hasta:
        return False
    return True


def load_config_from_seed(seed_dir: Path | None = None, as_of: date | None = None) -> EngineConfig:
    seed_dir = seed_dir or DEFAULT_SEED_DIR
    as_of = as_of or date.today()

    concepts: dict[str, ConceptDef] = {}
    concepts_data = _load_json(seed_dir / "payroll_concepts.json")
    if _in_vigencia(concepts_data, as_of):
        for item in concepts_data["items"]:
            concepts[item["codigo"]] = ConceptDef(
                codigo=item["codigo"],
                descripcion=item["descripcion"],
                tipo=item["tipo"],
                orden_visual=item.get("orden_visual", 0),
            )

    rules: list[RuleDef] = []
    rules_data = _load_json(seed_dir / "calculation_rules.json")
    if _in_vigencia(rules_data, as_of):
        for item in rules_data["items"]:
            rules.append(
                RuleDef(
                    codigo_concepto=item["codigo_concepto"],
                    condicion_aplicacion=item["condicion_aplicacion"],
                    base_calculo=item["base_calculo"],
                    unidad=item["unidad"],
                    aplica_contratos=item.get("aplica_contratos", []),
                    prioridad_calculo=item["prioridad_calculo"],
                    redondeo=item.get("redondeo", "CENTESIMO"),
                    referencia_legal=item.get("referencia_legal"),
                )
            )
    rules.sort(key=lambda r: (r.prioridad_calculo, r.codigo_concepto))

    isr_data = _load_json(seed_dir / "isr_brackets.json")
    brackets = [
        IsrBracket(
            rango_desde=Decimal(str(b["rango_desde"])),
            rango_hasta=Decimal(str(b["rango_hasta"])) if b.get("rango_hasta") else None,
            porcentaje=Decimal(str(b["porcentaje"])),
            excedente_desde=Decimal(str(b.get("excedente_desde", 0))),
            impuesto_fijo_acumulado=Decimal(str(b.get("impuesto_fijo_acumulado", 0))),
        )
        for b in isr_data["items"]
    ]
    isr = IsrConfig(
        factor_anualizacion=isr_data.get("factor_anualizacion", 13),
        deduccion_previa=isr_data.get("deduccion_previa", "css_empleado"),
        brackets=brackets,
    )

    css_data = _load_json(seed_dir / "css_rates.json")
    tasa_css_patronal = Decimal("0.1325")
    tasa_prima = Decimal("0.0192")
    for item in css_data["items"]:
        if item["concepto"] == "CUOTA_CSS_EMPLEADOR" and _in_vigencia(
            {**css_data, "vigencia_desde": item.get("vigencia_desde", css_data["vigencia_desde"])},
            as_of,
        ):
            tasa_css_patronal = Decimal(str(item["porcentaje_empleador"]))
        if item["concepto"] == "PRIMA_ANTIGUEDAD_PATRONAL":
            tasa_prima = Decimal(str(item["porcentaje_empleador"]))

    return EngineConfig(
        as_of=as_of,
        concepts=concepts,
        rules=rules,
        isr=isr,
        tasa_css_patronal=tasa_css_patronal,
        tasa_prima_antiguedad_patronal=tasa_prima,
    )


def config_snapshot(config: EngineConfig) -> dict[str, Any]:
    return {
        "as_of": config.as_of.isoformat(),
        "engine_version": "1.0.0",
        "rules_count": len(config.rules),
        "isr_factor": config.isr.factor_anualizacion,
        "tasa_css_patronal": str(config.tasa_css_patronal),
    }
