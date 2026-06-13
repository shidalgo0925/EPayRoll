from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEED = ROOT / "docs" / "seed" / "deduction_limits.json"


@dataclass(frozen=True)
class DeductionLimitsConfig:
    tope_descuentos_voluntarios_pct: Decimal
    conceptos_legales_obligatorios: frozenset[str]


@dataclass
class DeductionValidationResult:
    valid: bool
    errors: list[str]
    max_voluntario_permitido: Decimal
    descuentos_voluntarios: Decimal
    descuentos_legales: Decimal


def load_deduction_limits(seed_path: Path | None = None) -> DeductionLimitsConfig:
    path = seed_path or DEFAULT_SEED
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return DeductionLimitsConfig(
        tope_descuentos_voluntarios_pct=Decimal(str(data["tope_descuentos_voluntarios_pct"])),
        conceptos_legales_obligatorios=frozenset(data["conceptos_legales_obligatorios"]),
    )


def validate_art161(
    bruto: Decimal,
    deductions_by_concept: dict[str, Decimal],
    config: DeductionLimitsConfig | None = None,
    extra_voluntary: Decimal = Decimal("0"),
) -> DeductionValidationResult:
    """
    Art. 161 CT — descuentos autorizados limitados al 50% del salario bruto.
    CSS, SE e ISR son obligatorios y no cuentan contra el tope voluntario.
    """
    config = config or load_deduction_limits()
    legal = Decimal("0")
    voluntary = extra_voluntary

    for codigo, monto in deductions_by_concept.items():
        if monto <= 0:
            continue
        if codigo in config.conceptos_legales_obligatorios:
            legal += monto
        else:
            voluntary += monto

    max_vol = round(bruto * config.tope_descuentos_voluntarios_pct, 2)
    errors: list[str] = []

    if voluntary > max_vol:
        errors.append(
            f"Descuentos voluntarios B/. {voluntary} exceden tope Art. 161 "
            f"(50% de B/. {bruto} = B/. {max_vol})"
        )
    if legal + voluntary > bruto:
        errors.append(
            f"Total descuentos B/. {legal + voluntary} supera bruto B/. {bruto}"
        )

    return DeductionValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        max_voluntario_permitido=max_vol,
        descuentos_voluntarios=voluntary,
        descuentos_legales=legal,
    )
