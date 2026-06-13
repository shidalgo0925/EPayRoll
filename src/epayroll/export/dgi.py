from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.export.models import PayrollExportBundle, PayrollExportEmployee

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DGI = ROOT / "docs" / "seed" / "dgi_form03.json"


@dataclass
class DgiColumnDef:
    nombre: str
    fuente: str
    requerido: bool
    concepto: str | None = None


def load_dgi_template(path: Path | None = None) -> list[DgiColumnDef]:
    with open(path or DEFAULT_DGI, encoding="utf-8") as f:
        data = json.load(f)
    return [
        DgiColumnDef(
            nombre=c["nombre"],
            fuente=c["fuente"],
            requerido=c.get("requerido", False),
            concepto=c.get("concepto"),
        )
        for c in data["columnas"]
    ]


def _periodo_label(bundle: PayrollExportBundle) -> str:
    return f"{bundle.period.fecha_inicio.strftime('%Y%m')}"


def build_form03_rows(
    bundle: PayrollExportBundle,
    columns: list[DgiColumnDef] | None = None,
) -> list[list[str]]:
    columns = columns or load_dgi_template()
    rows = [[c.nombre for c in columns]]
    for employee in bundle.employees:
        row: list[str] = []
        for col in columns:
            if col.fuente == "cedula":
                row.append(employee.cedula)
            elif col.fuente == "nombre_completo":
                row.append(f"{employee.nombres} {employee.apellidos}".strip())
            elif col.fuente == "bruto":
                row.append(f"{employee.bruto:.2f}")
            elif col.fuente == "concepto" and col.concepto:
                row.append(f"{employee.conceptos.get(col.concepto, Decimal('0')):.2f}")
            elif col.fuente == "periodo":
                row.append(_periodo_label(bundle))
            else:
                row.append("")
        rows.append(row)
    return rows


def generate_dgi_export(
    bundle: PayrollExportBundle,
    output_path: Path,
) -> dict[str, Any]:
    rows = build_form03_rows(bundle)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        for row in rows:
            f.write("\t".join(row) + "\n")

    total_isr = sum((e.conceptos.get("ISR", Decimal("0")) for e in bundle.employees), Decimal("0"))
    return {
        "run_id": bundle.run_id,
        "formulario": "FORM_03",
        "periodo": _periodo_label(bundle),
        "file_path": str(output_path),
        "row_count": len(rows) - 1,
        "monto_total_isr": str(total_isr),
    }
