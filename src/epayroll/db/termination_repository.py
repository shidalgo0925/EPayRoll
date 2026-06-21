from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.engine.liquidation import LiquidationInput, run_liquidation
from epayroll.engine.orchestrator import PayrollResult

from .connection import get_connection


class TerminationRepository:
    def calculate(self, inp: LiquidationInput) -> PayrollResult:
        return run_liquidation(inp)

    def persist(
        self,
        employee_id: str,
        contract_id: str | None,
        inp: LiquidationInput,
        result: PayrollResult,
        created_by: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        case_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO termination_cases (
                        id, employee_id, contract_id, fecha_terminacion, causa,
                        monto_vacaciones, monto_decimo, monto_prima,
                        monto_preaviso, monto_indemnizacion, total, created_by
                    ) VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s::uuid
                    )
                    RETURNING id
                    """,
                    (
                        case_id,
                        employee_id,
                        contract_id,
                        inp.fecha_terminacion,
                        inp.causa,
                        result.amount("VACACIONES_LIQUIDACION"),
                        result.amount("DECIMO_PROPORCIONAL"),
                        result.amount("PRIMA_ANTIGUEDAD"),
                        result.amount("PREAVISO_DEDUCCION"),
                        result.amount("INDEMNIZACION"),
                        result.neto,
                        created_by,
                    ),
                )
                if contract_id:
                    cur.execute(
                        """
                        UPDATE contracts SET estado = 'TERMINADO', fecha_fin = %s
                        WHERE id = %s::uuid
                        """,
                        (inp.fecha_terminacion, contract_id),
                    )
                cur.execute(
                    "UPDATE employees SET activo = false WHERE id = %s::uuid",
                    (employee_id,),
                )
        return self._format_result(case_id, result)

    def get(self, case_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tc.id, tc.employee_id, tc.causa, tc.fecha_terminacion,
                           tc.monto_vacaciones, tc.monto_decimo, tc.monto_prima,
                           tc.monto_preaviso, tc.monto_indemnizacion, tc.total,
                           e.nombres, e.apellidos, e.cedula, o.razon_social
                    FROM termination_cases tc
                    JOIN employees e ON e.id = tc.employee_id
                    JOIN organizations o ON o.id = e.organization_id
                    WHERE tc.id = %s::uuid
                    """,
                    (case_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "case_id": str(row[0]),
            "employee_id": str(row[1]),
            "causa": row[2],
            "fecha_terminacion": row[3].isoformat(),
            "monto_vacaciones": str(row[4]),
            "monto_decimo": str(row[5]),
            "monto_prima": str(row[6]),
            "monto_preaviso": str(row[7]),
            "monto_indemnizacion": str(row[8]),
            "total": str(row[9]),
            "nombres": row[10],
            "apellidos": row[11],
            "cedula": row[12],
            "organization_nombre": row[13],
        }

    def get_employee_context(
        self,
        employee_id: str,
        fecha_corte: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        fecha_corte = fecha_corte or date.today()
        inicio_anio = date(fecha_corte.year, 1, 1)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.nombres, e.apellidos, e.cedula, e.activo,
                           c.id, c.fecha_inicio, c.salario_base, c.forma_pago::text
                    FROM employees e
                    LEFT JOIN LATERAL (
                        SELECT id, fecha_inicio, salario_base, forma_pago
                        FROM contracts
                        WHERE employee_id = e.id AND estado = 'ACTIVO'
                        ORDER BY fecha_inicio DESC LIMIT 1
                    ) c ON true
                    WHERE e.id = %s::uuid
                    """,
                    (employee_id,),
                )
                emp = cur.fetchone()
                if not emp:
                    raise ValueError("Empleado no encontrado")
                cur.execute(
                    """
                    SELECT COALESCE(SUM(pes.bruto), 0)
                    FROM payroll_employee_summary pes
                    JOIN payroll_runs pr ON pr.id = pes.payroll_run_id
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    WHERE pes.employee_id = %s::uuid
                      AND pp.fecha_fin >= %s AND pp.fecha_fin <= %s
                      AND pp.tipo::text NOT IN ('DECIMO', 'LIQUIDACION')
                    """,
                    (employee_id, inicio_anio, fecha_corte),
                )
                salarios_ytd = Decimal(str(cur.fetchone()[0]))
        from epayroll.db.vacation_repository import VacationRepository

        vac = VacationRepository()
        try:
            balance = vac.get_balance(employee_id, fecha_corte=fecha_corte, database_url=database_url)
            dias_vac = balance.get("dias_pendientes", "0")
        except ValueError:
            dias_vac = "0"
            balance = None
        salario = Decimal(str(emp[6])) if emp[6] is not None else None
        return {
            "employee_id": employee_id,
            "nombres": emp[0],
            "apellidos": emp[1],
            "cedula": emp[2],
            "activo": emp[3],
            "contract_id": str(emp[4]) if emp[4] else None,
            "fecha_inicio_contrato": emp[5].isoformat() if emp[5] else None,
            "salario_base": str(salario) if salario is not None else None,
            "forma_pago": emp[7],
            "salarios_acumulados_anio": str(salarios_ytd),
            "dias_vacaciones_pendientes": str(dias_vac),
            "vacation_balance": balance,
            "fecha_corte": fecha_corte.isoformat(),
        }

    def list_by_org(
        self,
        organization_id: str,
        limit: int = 50,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tc.id, tc.employee_id, e.nombres, e.apellidos, tc.causa,
                           tc.fecha_terminacion, tc.total
                    FROM termination_cases tc
                    JOIN employees e ON e.id = tc.employee_id
                    WHERE e.organization_id = %s::uuid
                    ORDER BY tc.fecha_terminacion DESC
                    LIMIT %s
                    """,
                    (organization_id, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "case_id": str(r[0]),
                "employee_id": str(r[1]),
                "nombres": r[2],
                "apellidos": r[3],
                "causa": r[4],
                "fecha_terminacion": r[5].isoformat(),
                "total": str(r[6]),
            }
            for r in rows
        ]

    @staticmethod
    def _format_result(case_id: str, result: PayrollResult) -> dict[str, Any]:
        return {
            "case_id": case_id,
            "bruto": str(result.bruto),
            "deducciones": str(result.deducciones),
            "neto": str(result.neto),
            "lines": [
                {"concepto": l.codigo_concepto, "tipo": l.tipo, "monto": str(l.monto)}
                for l in result.lines
            ],
            "config_snapshot": result.config_snapshot,
        }
