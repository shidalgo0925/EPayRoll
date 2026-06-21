from __future__ import annotations

import uuid
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
                    SELECT id, employee_id, causa, fecha_terminacion,
                           monto_vacaciones, monto_decimo, monto_prima,
                           monto_preaviso, monto_indemnizacion, total
                    FROM termination_cases WHERE id = %s::uuid
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
