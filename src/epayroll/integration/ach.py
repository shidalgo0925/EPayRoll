from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from epayroll.export.models import PayrollExportBundle
from epayroll.integration.models import AchPaymentRow, BankAccountInfo

ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = ROOT / "docs" / "seed"


@dataclass
class AchColumnDef:
    nombre: str
    fuente: str
    requerido: bool
    valor: str | None = None


@dataclass
class AchTemplate:
    banco: str
    separador: str
    columnas: list[AchColumnDef]


def load_ach_template(banco: str = "BANCO_GENERAL") -> AchTemplate:
    filename = {
        "BANCO_GENERAL": "ach_banco_general.json",
        "BANISTMO": "ach_banco_general.json",
    }.get(banco.upper(), "ach_banco_general.json")
    path = SEED_DIR / filename
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return AchTemplate(
        banco=data.get("banco", banco),
        separador=data.get("separador", "\t"),
        columnas=[
            AchColumnDef(
                nombre=c["nombre"],
                fuente=c["fuente"],
                requerido=c.get("requerido", False),
                valor=c.get("valor"),
            )
            for c in data["columnas"]
        ],
    )


def build_ach_rows(
    bundle: PayrollExportBundle,
    bank_accounts: dict[str, BankAccountInfo],
    referencia_prefix: str = "NOM",
) -> list[AchPaymentRow]:
    rows: list[AchPaymentRow] = []
    for idx, emp in enumerate(bundle.employees, start=1):
        if emp.neto <= 0:
            continue
        acct = bank_accounts.get(emp.employee_id)
        if not acct:
            raise ValueError(f"Empleado {emp.cedula} sin cuenta bancaria activa")
        rows.append(
            AchPaymentRow(
                secuencia=idx,
                employee_id=emp.employee_id,
                cedula=emp.cedula,
                nombre_completo=f"{emp.nombres} {emp.apellidos}".strip(),
                neto=emp.neto,
                tipo_cuenta=acct.tipo_cuenta,
                numero_cuenta=acct.numero_cuenta,
                referencia=f"{referencia_prefix}-{bundle.period.fecha_fin.strftime('%Y%m')}-{idx}",
            )
        )
    return rows


def _resolve_ach_cell(col: AchColumnDef, row: AchPaymentRow) -> str:
    if col.fuente == "constante":
        return col.valor or ""
    mapping = {
        "secuencia": str(row.secuencia),
        "tipo_cuenta": row.tipo_cuenta,
        "numero_cuenta": row.numero_cuenta,
        "nombre_completo": row.nombre_completo,
        "cedula": row.cedula,
        "neto": f"{row.neto:.2f}",
        "referencia": row.referencia,
    }
    return mapping.get(col.fuente, "")


def render_ach_file(rows: list[AchPaymentRow], template: AchTemplate) -> list[list[str]]:
    output: list[list[str]] = []
    output.append([c.nombre for c in template.columnas])
    for row in rows:
        output.append([_resolve_ach_cell(col, row) for col in template.columnas])
    return output


def validate_ach_rows(rows: list[list[str]]) -> list[str]:
    if len(rows) < 2:
        return ["ACH sin pagos a transferir"]
    errores: list[str] = []
    for i, row in enumerate(rows[1:], start=1):
        if len(row) < 6:
            errores.append(f"Fila {i}: columnas incompletas")
            continue
        monto = row[5] if len(row) > 5 else ""
        if not monto or Decimal(monto) <= 0:
            errores.append(f"Fila {i}: monto invalido")
        cuenta = row[2] if len(row) > 2 else ""
        if not cuenta.strip():
            errores.append(f"Fila {i}: numero_cuenta vacio")
    return errores


def generate_ach_export(
    bundle: PayrollExportBundle,
    bank_accounts: dict[str, BankAccountInfo],
    output_path: Path,
    banco: str = "BANCO_GENERAL",
) -> dict:
    template = load_ach_template(banco)
    ach_rows = build_ach_rows(bundle, bank_accounts)
    file_rows = render_ach_file(ach_rows, template)
    errors = validate_ach_rows(file_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        for row in file_rows:
            f.write(template.separador.join(row) + "\n")

    total = sum((r.neto for r in ach_rows), Decimal("0"))
    return {
        "banco": template.banco,
        "run_id": bundle.run_id,
        "file_path": str(output_path),
        "payment_count": len(ach_rows),
        "monto_total": str(total),
        "valido": len(errors) == 0,
        "errores": errors,
    }
