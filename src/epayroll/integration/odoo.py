from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.export.models import PayrollExportBundle

ROOT = Path(__file__).resolve().parents[3]
MAPPING_FILE = ROOT / "docs" / "seed" / "odoo_account_mapping.json"


@dataclass
class OdooAccountMapping:
    concepto: str
    cuenta_debe: str | None
    cuenta_haber: str | None
    tipo: str


def load_odoo_mapping(path: Path | None = None) -> tuple[str, list[OdooAccountMapping]]:
    with open(path or MAPPING_FILE, encoding="utf-8") as f:
        data = json.load(f)
    mappings = [
        OdooAccountMapping(
            concepto=m["concepto"],
            cuenta_debe=m.get("cuenta_debe"),
            cuenta_haber=m.get("cuenta_haber"),
            tipo=m["tipo"],
        )
        for m in data["cuentas"]
    ]
    return data.get("journal_code", "NOM"), mappings


def build_journal_entry(
    bundle: PayrollExportBundle,
    referencia: str | None = None,
) -> dict[str, Any]:
    """Genera asiento contable Odoo (JSON) desde totales de corrida."""
    journal_code, mappings = load_odoo_mapping()
    ref = referencia or f"Planilla {bundle.period.fecha_inicio} - {bundle.period.fecha_fin}"

    line_totals: dict[str, Decimal] = {}
    for emp in bundle.employees:
        for codigo, monto in emp.conceptos.items():
            line_totals[codigo] = line_totals.get(codigo, Decimal("0")) + monto

    neto_total = sum((e.neto for e in bundle.employees), Decimal("0"))
    line_totals["NETO_PAGAR"] = neto_total

    odoo_lines: list[dict[str, Any]] = []
    for mapping in mappings:
        monto = line_totals.get(mapping.concepto, Decimal("0"))
        if monto <= 0:
            continue
        if mapping.tipo == "DEBE" and mapping.cuenta_debe:
            odoo_lines.append(
                {"account_code": mapping.cuenta_debe, "debit": str(monto), "credit": "0.00", "name": mapping.concepto}
            )
        elif mapping.tipo == "HABER" and mapping.cuenta_haber:
            odoo_lines.append(
                {"account_code": mapping.cuenta_haber, "debit": "0.00", "credit": str(monto), "name": mapping.concepto}
            )
        elif mapping.tipo == "DEBE_HABER" and mapping.cuenta_debe and mapping.cuenta_haber:
            odoo_lines.append(
                {"account_code": mapping.cuenta_debe, "debit": str(monto), "credit": "0.00", "name": mapping.concepto}
            )
            odoo_lines.append(
                {"account_code": mapping.cuenta_haber, "debit": "0.00", "credit": str(monto), "name": mapping.concepto}
            )

    total_debe = sum((Decimal(l["debit"]) for l in odoo_lines), Decimal("0"))
    total_haber = sum((Decimal(l["credit"]) for l in odoo_lines), Decimal("0"))

    return {
        "model": "account.move",
        "journal_code": journal_code,
        "ref": ref,
        "date": (bundle.period.fecha_pago or bundle.period.fecha_fin).isoformat(),
        "run_id": bundle.run_id,
        "lines": odoo_lines,
        "total_debit": str(total_debe),
        "total_credit": str(total_haber),
        "balanced": abs(total_debe - total_haber) <= Decimal("0.01"),
    }


def parse_odoo_employees(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza payload estilo Odoo hr.employee -> formato EPayRoll."""
    normalized: list[dict[str, Any]] = []
    for item in payload:
        normalized.append(
            {
                "cedula": item.get("identification_id") or item.get("cedula") or "",
                "nombres": item.get("name", "").split(" ")[0] if item.get("name") else item.get("nombres", ""),
                "apellidos": " ".join(item.get("name", "").split(" ")[1:]) if item.get("name") else item.get("apellidos", ""),
                "email": item.get("work_email") or item.get("email"),
                "salario_base": Decimal(str(item.get("wage") or item.get("salario_base") or "0")),
                "fecha_inicio": item.get("contract_date_start") or item.get("fecha_inicio"),
                "contract_type_codigo": item.get("contract_type") or "INDEFINIDO",
                "forma_pago": item.get("forma_pago") or "QUINCENAL",
                "odoo_id": item.get("id"),
            }
        )
    return normalized
