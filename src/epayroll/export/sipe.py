from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.export.models import PayrollExportBundle, PayrollExportEmployee

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SIPE = ROOT / "docs" / "seed" / "sipe_columns.json"


@dataclass
class SipeColumnDef:
    letra: str
    nombre: str
    fuente: str
    requerido: bool
    concepto: str | None = None
    valor: str | None = None
    concilia: str | None = None


@dataclass
class SipeTemplate:
    formato: str
    separador: str
    columnas: list[SipeColumnDef]


@dataclass
class ReconciliationCheck:
    nombre: str
    interno: Decimal
    sipe: Decimal
    ok: bool
    diferencia: Decimal


@dataclass
class ReconciliationResult:
    valido: bool
    checks: list[ReconciliationCheck] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


def load_sipe_template(path: Path | None = None) -> SipeTemplate:
    cfg_path = path or DEFAULT_SIPE
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    columnas = [
        SipeColumnDef(
            letra=c["letra"],
            nombre=c["nombre"],
            fuente=c["fuente"],
            requerido=c.get("requerido", False),
            concepto=c.get("concepto"),
            valor=c.get("valor"),
            concilia=c.get("concilia"),
        )
        for c in data["columnas"]
    ]
    return SipeTemplate(
        formato=data.get("formato", "TSV"),
        separador=data.get("separador", "\t"),
        columnas=columnas,
    )


def _fmt_money(value: Decimal) -> str:
    return f"{value:.2f}"


def _fmt_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def _resolve_cell(
    col: SipeColumnDef,
    bundle: PayrollExportBundle,
    employee: PayrollExportEmployee,
    secuencia: int,
) -> str:
    if col.fuente == "secuencia":
        return str(secuencia)
    if col.fuente == "constante":
        return col.valor or ""
    if col.fuente == "cedula":
        return employee.cedula
    if col.fuente == "nombres":
        return employee.nombres
    if col.fuente == "apellidos":
        return employee.apellidos
    if col.fuente == "bruto":
        return _fmt_money(employee.bruto)
    if col.fuente == "neto":
        return _fmt_money(employee.neto)
    if col.fuente == "aportes_patronales":
        return _fmt_money(employee.aportes_patronales)
    if col.fuente == "dias_trabajados":
        return _fmt_money(employee.dias_trabajados)
    if col.fuente == "fecha_ingreso":
        return _fmt_date(employee.fecha_ingreso)
    if col.fuente == "horas_extras_total":
        return _fmt_money(bundle.horas_extras_total(employee))
    if col.fuente == "periodo_inicio":
        return bundle.period.fecha_inicio.isoformat()
    if col.fuente == "periodo_fin":
        return bundle.period.fecha_fin.isoformat()
    if col.fuente == "ruc_empleador":
        return bundle.period.ruc_empleador
    if col.fuente == "concepto" and col.concepto:
        return _fmt_money(bundle.concept_amount(employee, col.concepto))
    return ""


def build_sipe_rows(
    bundle: PayrollExportBundle,
    template: SipeTemplate | None = None,
) -> list[list[str]]:
    template = template or load_sipe_template()
    rows: list[list[str]] = []
    header = [c.letra for c in template.columnas]
    rows.append(header)

    for idx, employee in enumerate(bundle.employees, start=1):
        row = [_resolve_cell(col, bundle, employee, idx) for col in template.columnas]
        rows.append(row)
    return rows


def validate_sipe_rows(
    rows: list[list[str]],
    template: SipeTemplate | None = None,
) -> list[str]:
    template = template or load_sipe_template()
    errores: list[str] = []
    if len(rows) < 2:
        return ["SIPE sin filas de empleados"]

    if len(rows[0]) != 24:
        errores.append(f"Se esperaban 24 columnas A-X, hay {len(rows[0])}")

    required_indices = [i for i, c in enumerate(template.columnas) if c.requerido]
    for row_num, row in enumerate(rows[1:], start=1):
        for col_idx in required_indices:
            if col_idx >= len(row) or row[col_idx].strip() == "":
                letra = template.columnas[col_idx].letra
                errores.append(f"Fila {row_num}: columna {letra} obligatoria vacia")
    return errores


def reconcile_sipe(
    bundle: PayrollExportBundle,
    template: SipeTemplate | None = None,
) -> ReconciliationResult:
    """GT-08 — concilia totales SIPE vs planilla interna."""
    template = template or load_sipe_template()
    rows = build_sipe_rows(bundle, template)
    errores = validate_sipe_rows(rows, template)

    col_index = {c.letra: i for i, c in enumerate(template.columnas)}
    concilia_map = {c.concilia: c.letra for c in template.columnas if c.concilia}

    interno = bundle.totales
    sipe_totals: dict[str, Decimal] = {}

    data_rows = rows[1:]
    for key, letra in concilia_map.items():
        idx = col_index[letra]
        total = Decimal("0")
        for row in data_rows:
            raw = row[idx].strip()
            if raw:
                total += Decimal(raw)
        sipe_totals[key] = total

    checks: list[ReconciliationCheck] = []
    for key in ("bruto", "css_empleado", "aportes_patronales"):
        if key not in concilia_map:
            continue
        interno_val = interno.get(key, Decimal("0"))
        sipe_val = sipe_totals.get(key, Decimal("0"))
        diff = abs(interno_val - sipe_val)
        ok = diff <= Decimal("0.01")
        checks.append(
            ReconciliationCheck(
                nombre=key,
                interno=interno_val,
                sipe=sipe_val,
                ok=ok,
                diferencia=diff,
            )
        )
        if not ok:
            errores.append(
                f"Conciliacion {key}: interno {_fmt_money(interno_val)} "
                f"vs SIPE {_fmt_money(sipe_val)}"
            )

    return ReconciliationResult(
        valido=len(errores) == 0 and all(c.ok for c in checks),
        checks=checks,
        errores=errores,
    )


def write_sipe_file(rows: list[list[str]], output_path: Path, template: SipeTemplate | None = None) -> Path:
    template = template or load_sipe_template()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        for row in rows:
            f.write(template.separador.join(row) + "\n")
    return output_path


def generate_sipe_export(
    bundle: PayrollExportBundle,
    output_path: Path,
    template: SipeTemplate | None = None,
) -> dict[str, Any]:
    template = template or load_sipe_template()
    rows = build_sipe_rows(bundle, template)
    validation_errors = validate_sipe_rows(rows, template)
    reconciliation = reconcile_sipe(bundle, template)

    write_sipe_file(rows, output_path, template)

    return {
        "run_id": bundle.run_id,
        "file_path": str(output_path),
        "row_count": len(rows) - 1,
        "column_count": len(template.columnas),
        "valido": reconciliation.valido and len(validation_errors) == 0,
        "validation_errors": validation_errors,
        "reconciliation": {
            "valido": reconciliation.valido,
            "checks": [
                {
                    "nombre": c.nombre,
                    "interno": str(c.interno),
                    "sipe": str(c.sipe),
                    "ok": c.ok,
                    "diferencia": str(c.diferencia),
                }
                for c in reconciliation.checks
            ],
            "errores": reconciliation.errores,
        },
    }
