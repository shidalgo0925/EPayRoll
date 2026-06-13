from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = ROOT / "docs" / "seed" / "analytics_config.json"


@dataclass(frozen=True)
class AnalyticsThresholds:
    rotacion_pct_anual_alerta: Decimal
    ausentismo_pct_alerta: Decimal
    horas_extra_promedio_mes_alerta: Decimal
    pasivo_por_empleado_alerta: Decimal


@dataclass(frozen=True)
class AnalyticsConfig:
    dias_laborables_mes: int
    horas_jornada: int
    umbrales: AnalyticsThresholds
    proyeccion_liquidacion_causa_default: str


def load_analytics_config(path: Path | None = None) -> AnalyticsConfig:
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        data = json.load(f)
    u = data["umbrales"]
    return AnalyticsConfig(
        dias_laborables_mes=data.get("dias_laborables_mes", 22),
        horas_jornada=data.get("horas_jornada", 8),
        umbrales=AnalyticsThresholds(
            rotacion_pct_anual_alerta=Decimal(str(u.get("rotacion_pct_anual_alerta", 15))),
            ausentismo_pct_alerta=Decimal(str(u.get("ausentismo_pct_alerta", 5))),
            horas_extra_promedio_mes_alerta=Decimal(str(u.get("horas_extra_promedio_mes_alerta", 20))),
            pasivo_por_empleado_alerta=Decimal(str(u.get("pasivo_por_empleado_alerta", 5000))),
        ),
        proyeccion_liquidacion_causa_default=data.get(
            "proyeccion_liquidacion_causa_default", "DESPIDO_INJUSTIFICADO"
        ),
    )
