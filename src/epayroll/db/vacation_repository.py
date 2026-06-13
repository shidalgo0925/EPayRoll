from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.vacation.calculator import calculate_balance, load_vacation_config

from .connection import get_connection


class VacationRepository:
    def _employee_contract(
        self, cur, employee_id: str
    ) -> tuple[date, Decimal, bool] | None:
        cur.execute(
            """
            SELECT c.fecha_inicio, c.salario_base, ct.genera_vacaciones
            FROM contracts c
            JOIN contract_types ct ON ct.id = c.contract_type_id
            WHERE c.employee_id = %s::uuid AND c.estado = 'ACTIVO'
            ORDER BY c.fecha_inicio DESC LIMIT 1
            """,
            (employee_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row[0], Decimal(str(row[1])), bool(row[2])

    def _dias_gozados(self, cur, employee_id: str) -> Decimal:
        cur.execute(
            """
            SELECT COALESCE(SUM(dias_solicitados), 0)
            FROM vacation_requests
            WHERE employee_id = %s::uuid AND estado IN ('APROBADO', 'GOZADO')
            """,
            (employee_id,),
        )
        return Decimal(str(cur.fetchone()[0]))

    def _proxima_vacacion(self, cur, employee_id: str, as_of: date) -> date | None:
        cur.execute(
            """
            SELECT fecha_inicio FROM vacation_requests
            WHERE employee_id = %s::uuid
              AND estado = 'APROBADO'
              AND fecha_inicio >= %s
            ORDER BY fecha_inicio ASC LIMIT 1
            """,
            (employee_id, as_of),
        )
        row = cur.fetchone()
        return row[0] if row else None

    def accrue_employee(
        self,
        employee_id: str,
        fecha_corte: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        fecha_corte = fecha_corte or date.today()
        config = load_vacation_config()

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                contract = self._employee_contract(cur, employee_id)
                if not contract:
                    raise ValueError("Empleado sin contrato activo")
                fecha_inicio, salario, genera = contract
                if not genera:
                    raise ValueError("Tipo de contrato no genera vacaciones")

                gozados = self._dias_gozados(cur, employee_id)
                proxima = self._proxima_vacacion(cur, employee_id, fecha_corte)
                result = calculate_balance(
                    fecha_inicio=fecha_inicio,
                    fecha_corte=fecha_corte,
                    dias_gozados=gozados,
                    salario_mensual=salario,
                    proxima_vacacion_inicio=proxima,
                    config=config,
                )

                cur.execute(
                    """
                    INSERT INTO vacation_balances (
                        employee_id, dias_ganados, dias_gozados, dias_pendientes, fecha_corte
                    ) VALUES (%s::uuid, %s, %s, %s, %s)
                    ON CONFLICT (employee_id, fecha_corte) DO UPDATE
                    SET dias_ganados = EXCLUDED.dias_ganados,
                        dias_gozados = EXCLUDED.dias_gozados,
                        dias_pendientes = EXCLUDED.dias_pendientes,
                        updated_at = now()
                    RETURNING id
                    """,
                    (
                        employee_id,
                        result.dias_ganados,
                        result.dias_gozados,
                        result.dias_pendientes,
                        fecha_corte,
                    ),
                )
                balance_id = str(cur.fetchone()[0])

        return self._format_balance(employee_id, balance_id, result)

    def get_balance(
        self,
        employee_id: str,
        fecha_corte: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        return self.accrue_employee(employee_id, fecha_corte=fecha_corte, database_url=database_url)

    def create_request(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        dias_solicitados: Decimal,
        database_url: str | None = None,
    ) -> dict[str, str]:
        if fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin debe ser >= fecha_inicio")

        request_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vacation_requests (
                        id, employee_id, fecha_inicio, fecha_fin, dias_solicitados, estado
                    ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, 'SOLICITADO')
                    RETURNING id
                    """,
                    (request_id, employee_id, fecha_inicio, fecha_fin, dias_solicitados),
                )
        return {"request_id": request_id, "estado": "SOLICITADO"}

    def approve_request(
        self,
        request_id: str,
        aprobado_por: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, str]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests
                    SET estado = 'APROBADO', aprobado_por = %s::uuid
                    WHERE id = %s::uuid AND estado = 'SOLICITADO'
                    RETURNING employee_id
                    """,
                    (aprobado_por, request_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Solicitud no encontrada o no esta en SOLICITADO")
        return {"request_id": request_id, "estado": "APROBADO"}

    def list_requests(
        self,
        employee_id: str,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, fecha_inicio, fecha_fin, dias_solicitados, estado::text, created_at
                    FROM vacation_requests
                    WHERE employee_id = %s::uuid
                    ORDER BY fecha_inicio DESC
                    """,
                    (employee_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "request_id": str(r[0]),
                "fecha_inicio": r[1].isoformat(),
                "fecha_fin": r[2].isoformat(),
                "dias_solicitados": str(r[3]),
                "estado": r[4],
                "created_at": r[5].isoformat(),
            }
            for r in rows
        ]

    def org_dashboard(
        self,
        organization_id: str,
        fecha_corte: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        fecha_corte = fecha_corte or date.today()
        employees: list[dict[str, Any]] = []
        total_pasivo = Decimal("0")
        alertas = 0

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id FROM employees e
                    WHERE e.organization_id = %s::uuid AND e.activo = true
                    ORDER BY e.apellidos, e.nombres
                    """,
                    (organization_id,),
                )
                emp_ids = [str(r[0]) for r in cur.fetchall()]

        for emp_id in emp_ids:
            try:
                bal = self.accrue_employee(emp_id, fecha_corte=fecha_corte, database_url=database_url)
                employees.append(bal)
                total_pasivo += Decimal(bal["pasivo_estimado"])
                if bal.get("alerta_art57"):
                    alertas += 1
            except ValueError:
                continue

        return {
            "organization_id": organization_id,
            "fecha_corte": fecha_corte.isoformat(),
            "employee_count": len(employees),
            "pasivo_total": str(round(total_pasivo, 2)),
            "alertas_art57": alertas,
            "employees": employees,
        }

    @staticmethod
    def _format_balance(
        employee_id: str,
        balance_id: str,
        result,
    ) -> dict[str, Any]:
        return {
            "balance_id": balance_id,
            "employee_id": employee_id,
            "fecha_corte": result.fecha_corte.isoformat(),
            "meses_servicio": result.meses_servicio,
            "periodos_ganados": result.periodos_ganados,
            "dias_ganados": str(result.dias_ganados),
            "dias_gozados": str(result.dias_gozados),
            "dias_pendientes": str(result.dias_pendientes),
            "excede_art59": result.excede_art59,
            "max_dias_acumulables": str(result.max_dias_acumulables),
            "dias_sobre_tope": str(result.dias_sobre_tope),
            "pasivo_estimado": str(result.pasivo_estimado),
            "alerta_art57": result.alerta_art57,
            "alerta_mensaje": result.alerta_mensaje,
        }
