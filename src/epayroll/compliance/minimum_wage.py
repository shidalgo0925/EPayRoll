from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SEED_PATH = ROOT / "docs" / "seed" / "minimum_wage.json"


@dataclass(frozen=True)
class MinimumWageCategory:
    codigo: str
    descripcion: str
    monto_mensual: Decimal
    region: str
    actividad: str


class MinimumWageError(ValueError):
    pass


@lru_cache
def load_minimum_wage_config() -> dict:
    with SEED_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_minimum_wage(
    categoria_codigo: str | None = None,
    fecha: date | None = None,
) -> MinimumWageCategory:
    cfg = load_minimum_wage_config()
    codigo = categoria_codigo or cfg.get("default_categoria") or "DEPENDIENTE_GENERAL"
    for cat in cfg.get("categorias", []):
        if cat["codigo"] == codigo:
            return MinimumWageCategory(
                codigo=cat["codigo"],
                descripcion=cat.get("descripcion", codigo),
                monto_mensual=Decimal(str(cat["monto_mensual"])),
                region=cat.get("region", "PANAMA"),
                actividad=cat.get("actividad", "GENERAL"),
            )
    raise MinimumWageError(f"Categoría salario mínimo no encontrada: {codigo}")


def validate_salary_base(
    salario_base: Decimal,
    categoria_codigo: str | None = None,
    fecha: date | None = None,
) -> None:
    """GT-07 — rechaza salario inferior al mínimo legal parametrizado."""
    cat = get_minimum_wage(categoria_codigo, fecha)
    if salario_base < cat.monto_mensual:
        raise MinimumWageError(
            f"Salario B/. {salario_base} inferior al mínimo legal B/. {cat.monto_mensual} "
            f"para categoría {cat.descripcion} ({cat.codigo})"
        )
