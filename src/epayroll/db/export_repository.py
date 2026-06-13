from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.export.dgi import generate_dgi_export
from epayroll.export.models import PayrollExportBundle, PayrollExportEmployee, PayrollExportPeriod
from epayroll.export.sipe import generate_sipe_export

from .connection import get_connection

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_DIR = ROOT / "storage" / "exports"


class ExportRepository:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or Path(
            os.environ.get("EPAYROLL_EXPORT_DIR", str(DEFAULT_EXPORT_DIR))
        )

    def load_run_bundle(self, run_id: str, database_url: str | None = None) -> PayrollExportBundle:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pp.fecha_inicio, pp.fecha_fin, pp.fecha_pago, o.ruc
                    FROM payroll_runs pr
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    JOIN organizations o ON o.id = pp.organization_id
                    WHERE pr.id = %s::uuid
                    """,
                    (run_id,),
                )
                period_row = cur.fetchone()
                if not period_row:
                    raise ValueError(f"Corrida no encontrada: {run_id}")

                cur.execute(
                    """
                    SELECT pes.employee_id, e.cedula, e.nombres, e.apellidos,
                           pes.bruto, pes.neto, pes.aportes_patronales,
                           c.fecha_inicio
                    FROM payroll_employee_summary pes
                    JOIN employees e ON e.id = pes.employee_id
                    LEFT JOIN LATERAL (
                        SELECT fecha_inicio FROM contracts
                        WHERE employee_id = pes.employee_id AND estado = 'ACTIVO'
                        ORDER BY fecha_inicio DESC LIMIT 1
                    ) c ON true
                    WHERE pes.payroll_run_id = %s::uuid
                    ORDER BY e.apellidos, e.nombres
                    """,
                    (run_id,),
                )
                emp_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT pl.employee_id, pc.codigo, pl.monto
                    FROM payroll_lines pl
                    JOIN payroll_concepts pc ON pc.id = pl.concept_id
                    WHERE pl.payroll_run_id = %s::uuid
                    """,
                    (run_id,),
                )
                line_rows = cur.fetchall()

        concepts_by_emp: dict[str, dict[str, Decimal]] = {}
        for emp_id, codigo, monto in line_rows:
            eid = str(emp_id)
            concepts_by_emp.setdefault(eid, {})[codigo] = Decimal(str(monto))

        employees: list[PayrollExportEmployee] = []
        for row in emp_rows:
            eid = str(row[0])
            employees.append(
                PayrollExportEmployee(
                    employee_id=eid,
                    cedula=row[1],
                    nombres=row[2],
                    apellidos=row[3],
                    bruto=Decimal(str(row[4])),
                    neto=Decimal(str(row[5])),
                    aportes_patronales=Decimal(str(row[6])),
                    conceptos=concepts_by_emp.get(eid, {}),
                    dias_trabajados=Decimal("15"),
                    fecha_ingreso=row[7],
                )
            )

        period = PayrollExportPeriod(
            fecha_inicio=period_row[0],
            fecha_fin=period_row[1],
            fecha_pago=period_row[2],
            ruc_empleador=period_row[3] or "",
        )
        return PayrollExportBundle(run_id=run_id, period=period, employees=employees)

    def export_sipe(self, run_id: str, database_url: str | None = None) -> dict[str, Any]:
        bundle = self.load_run_bundle(run_id, database_url=database_url)
        output_path = self.storage_dir / "sipe" / f"{run_id}.txt"
        result = generate_sipe_export(bundle, output_path)
        rel_path = str(output_path.relative_to(ROOT)) if output_path.is_relative_to(ROOT) else str(output_path)

        export_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sipe_exports (id, payroll_run_id, archivo_path, estado, errores)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    """,
                    (
                        export_id,
                        run_id,
                        rel_path,
                        "GENERADO" if result["valido"] else "ERROR",
                        None if result["valido"] else result.get("reconciliation", {}).get("errores"),
                    ),
                )
        result["export_id"] = export_id
        result["archivo_path"] = rel_path
        return result

    def export_dgi(self, run_id: str, database_url: str | None = None) -> dict[str, Any]:
        bundle = self.load_run_bundle(run_id, database_url=database_url)
        output_path = self.storage_dir / "dgi" / f"{run_id}_form03.txt"
        result = generate_dgi_export(bundle, output_path)
        rel_path = str(output_path.relative_to(ROOT)) if output_path.is_relative_to(ROOT) else str(output_path)

        export_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dgi_exports (id, payroll_run_id, formulario, periodo, monto_total, archivo_path, estado)
                    VALUES (%s::uuid, %s::uuid, 'FORM_03', %s, %s, %s, 'GENERADO')
                    """,
                    (
                        export_id,
                        run_id,
                        result["periodo"],
                        Decimal(result["monto_total_isr"]),
                        rel_path,
                    ),
                )
        result["export_id"] = export_id
        result["archivo_path"] = rel_path
        return result

    def get_sipe_export(self, run_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, archivo_path, estado, errores, fecha_generacion
                    FROM sipe_exports
                    WHERE payroll_run_id = %s::uuid
                    ORDER BY fecha_generacion DESC LIMIT 1
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "export_id": str(row[0]),
            "archivo_path": row[1],
            "estado": row[2],
            "errores": row[3],
            "fecha_generacion": row[4].isoformat(),
        }

    def resolve_path(self, rel_path: str) -> Path:
        path = Path(rel_path)
        if path.is_absolute():
            return path
        return ROOT / rel_path
