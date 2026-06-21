from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.payslip.generator import PayslipData, PayslipLine, generate_payslip_pdf

from .connection import get_connection

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PAYSLIP_DIR = ROOT / "storage" / "payslips"


class PayslipRepository:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or Path(
            os.environ.get("EPAYROLL_PAYSLIP_DIR", str(DEFAULT_PAYSLIP_DIR))
        )

    def get_storage_path(self, run_id: str, employee_id: str) -> Path:
        return self.storage_dir / run_id / f"{employee_id}.pdf"

    def load_payslip_data(
        self,
        run_id: str,
        employee_id: str,
        database_url: str | None = None,
    ) -> PayslipData:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.nombres, e.apellidos, e.cedula, e.ficha, o.razon_social,
                           pp.fecha_inicio, pp.fecha_fin, pp.fecha_pago,
                           pes.bruto, pes.total_deducciones, pes.neto,
                           COALESCE(c.forma_pago::text, 'QUINCENAL'),
                           COALESCE(adj.dias_trabajados, 15),
                           COALESCE(adj.dias_descuento, 0),
                           COALESCE(adj.monto_desc_dias, 0)
                    FROM payroll_employee_summary pes
                    JOIN payroll_runs pr ON pr.id = pes.payroll_run_id
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    JOIN employees e ON e.id = pes.employee_id
                    JOIN organizations o ON o.id = e.organization_id
                    LEFT JOIN LATERAL (
                        SELECT forma_pago FROM contracts
                        WHERE employee_id = pes.employee_id AND estado = 'ACTIVO'
                        ORDER BY fecha_inicio DESC LIMIT 1
                    ) c ON true
                    LEFT JOIN payroll_run_adjustments adj
                        ON adj.payroll_run_id = pes.payroll_run_id
                       AND adj.employee_id = pes.employee_id
                    WHERE pr.id = %s::uuid AND pes.employee_id = %s::uuid
                    """,
                    (run_id, employee_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Corrida o empleado no encontrado en la planilla")

                cur.execute(
                    """
                    SELECT pc.codigo, pc.descripcion, pc.tipo::text, pl.monto, pc.imprime_recibo
                    FROM payroll_lines pl
                    JOIN payroll_concepts pc ON pc.id = pl.concept_id
                    WHERE pl.payroll_run_id = %s::uuid AND pl.employee_id = %s::uuid
                    ORDER BY pl.orden
                    """,
                    (run_id, employee_id),
                )
                line_rows = cur.fetchall()

        lines = [
            PayslipLine(
                concepto=r[0],
                descripcion=r[1],
                tipo=r[2],
                monto=Decimal(str(r[3])),
            )
            for r in line_rows
            if r[4] and r[2] in ("INGRESO", "DESCUENTO")
        ]

        periodo_tipo_quincena = (row[6] - row[5]).days <= 16
        dias_pago_nom = Decimal("15") if periodo_tipo_quincena else Decimal("30")
        dias_trab = Decimal(str(row[12]))
        dias_desc = Decimal(str(row[13]))
        monto_desc = Decimal(str(row[14]))
        if monto_desc == 0 and dias_desc > 0:
            sal_base = next(
                (l.monto for l in lines if l.concepto == "SALARIO_BASE"),
                Decimal(str(row[8])),
            )
            if dias_trab > 0:
                monto_desc = (sal_base / dias_trab * dias_desc).quantize(Decimal("0.01"))

        return PayslipData(
            run_id=run_id,
            employee_id=employee_id,
            employee_nombre=f"{row[0]} {row[1]}",
            employee_cedula=row[2],
            organization_nombre=row[4],
            periodo_inicio=row[5],
            periodo_fin=row[6],
            fecha_pago=row[7],
            bruto=Decimal(str(row[8])),
            deducciones=Decimal(str(row[9])),
            neto=Decimal(str(row[10])),
            lines=lines,
            employee_ficha=row[3] or "",
            dias_pago=dias_pago_nom,
            dias_trabajados=dias_trab,
            dias_descuento=dias_desc,
            monto_desc_dias=monto_desc,
            forma_pago=row[11] or "QUINCENAL",
            numero_comprobante=run_id.replace("-", "")[:10].upper(),
        )

    def generate_and_persist(
        self,
        run_id: str,
        employee_id: str,
        database_url: str | None = None,
    ) -> dict[str, str]:
        data = self.load_payslip_data(run_id, employee_id, database_url=database_url)
        path = self.get_storage_path(run_id, employee_id)
        generate_payslip_pdf(data, path)
        rel_path = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)

        payslip_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO payslips (id, payroll_run_id, employee_id, pdf_url)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
                    ON CONFLICT (payroll_run_id, employee_id) DO UPDATE
                    SET pdf_url = EXCLUDED.pdf_url, fecha_emision = now()
                    RETURNING id
                    """,
                    (payslip_id, run_id, employee_id, rel_path),
                )
                payslip_id = str(cur.fetchone()[0])

        return {
            "payslip_id": payslip_id,
            "run_id": run_id,
            "employee_id": employee_id,
            "pdf_path": rel_path,
        }

    def generate_all_for_run(
        self,
        run_id: str,
        database_url: str | None = None,
    ) -> list[dict[str, str]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT employee_id FROM payroll_employee_summary
                    WHERE payroll_run_id = %s::uuid
                    ORDER BY employee_id
                    """,
                    (run_id,),
                )
                employee_ids = [str(r[0]) for r in cur.fetchall()]

        return [
            self.generate_and_persist(run_id, emp_id, database_url=database_url)
            for emp_id in employee_ids
        ]

    def get_payslip_record(
        self,
        run_id: str,
        employee_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, pdf_url, fecha_emision
                    FROM payslips
                    WHERE payroll_run_id = %s::uuid AND employee_id = %s::uuid
                    """,
                    (run_id, employee_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "payslip_id": str(row[0]),
            "pdf_path": row[1],
            "fecha_emision": row[2].isoformat(),
        }

    def resolve_pdf_path(self, pdf_url: str) -> Path:
        path = Path(pdf_url)
        if path.is_absolute():
            return path
        return ROOT / pdf_url

    @staticmethod
    def serialize(data: PayslipData) -> dict[str, Any]:
        return {
            "run_id": data.run_id,
            "employee_id": data.employee_id,
            "employee_nombre": data.employee_nombre,
            "employee_cedula": data.employee_cedula,
            "employee_ficha": data.employee_ficha,
            "organization_nombre": data.organization_nombre,
            "periodo_inicio": data.periodo_inicio.isoformat(),
            "periodo_fin": data.periodo_fin.isoformat(),
            "fecha_pago": data.fecha_pago.isoformat(),
            "bruto": str(data.bruto),
            "deducciones": str(data.deducciones),
            "neto": str(data.neto),
            "dias_pago": str(data.dias_pago),
            "dias_trabajados": str(data.dias_trabajados),
            "dias_descuento": str(data.dias_descuento),
            "monto_desc_dias": str(data.monto_desc_dias),
            "forma_pago": data.forma_pago,
            "numero_comprobante": data.numero_comprobante,
            "lines": [
                {
                    "concepto": l.concepto,
                    "descripcion": l.descripcion,
                    "tipo": l.tipo,
                    "monto": str(l.monto),
                }
                for l in data.lines
            ],
        }

    def list_for_run(
        self,
        run_id: str,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pes.employee_id, e.ficha, e.nombres, e.apellidos, e.cedula,
                           pes.bruto, pes.neto, ps.id IS NOT NULL, ps.fecha_emision
                    FROM payroll_employee_summary pes
                    JOIN employees e ON e.id = pes.employee_id
                    LEFT JOIN payslips ps
                        ON ps.payroll_run_id = pes.payroll_run_id
                       AND ps.employee_id = pes.employee_id
                    WHERE pes.payroll_run_id = %s::uuid
                    ORDER BY COALESCE(e.ficha, ''), e.apellidos, e.nombres
                    """,
                    (run_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "employee_id": str(r[0]),
                "ficha": r[1] or "",
                "nombre": f"{r[2]} {r[3]}".strip(),
                "cedula": r[4],
                "bruto": str(r[5]),
                "neto": str(r[6]),
                "generado": bool(r[7]),
                "fecha_emision": r[8].isoformat() if r[8] else None,
            }
            for r in rows
        ]
