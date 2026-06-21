from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.vacation.calculator import calculate_balance, load_vacation_config
from epayroll.vacation.substitutions import validate_substitute_assignment

from .connection import get_connection


def _employee_org_id(employee_id: str, database_url: str | None = None) -> str | None:
    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT organization_id FROM employees WHERE id = %s::uuid", (employee_id,))
            row = cur.fetchone()
            return str(row[0]) if row else None


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
        substitute_employee_id: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, str]:
        if substitute_employee_id:
            self._validate_substitute(request_id, substitute_employee_id, database_url=database_url)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests
                    SET estado = 'APROBADO',
                        aprobado_por = %s::uuid,
                        substitute_employee_id = COALESCE(%s::uuid, substitute_employee_id)
                    WHERE id = %s::uuid AND estado = 'SOLICITADO'
                    RETURNING employee_id
                    """,
                    (aprobado_por, substitute_employee_id, request_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Solicitud no encontrada o no esta en SOLICITADO")
        self._sync_vacation_to_attendance(request_id, database_url=database_url)
        return {"request_id": request_id, "estado": "APROBADO"}

    def reject_request(self, request_id: str, database_url: str | None = None) -> dict[str, str]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests SET estado = 'RECHAZADO'
                    WHERE id = %s::uuid AND estado = 'SOLICITADO'
                    RETURNING id
                    """,
                    (request_id,),
                )
                if not cur.fetchone():
                    raise ValueError("Solicitud no encontrada o no rechazable")
        return {"request_id": request_id, "estado": "RECHAZADO"}

    def mark_gozado(self, request_id: str, database_url: str | None = None) -> dict[str, str]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests SET estado = 'GOZADO'
                    WHERE id = %s::uuid AND estado = 'APROBADO'
                    RETURNING id
                    """,
                    (request_id,),
                )
                if not cur.fetchone():
                    raise ValueError("Solicitud no encontrada o no esta APROBADA")
        return {"request_id": request_id, "estado": "GOZADO"}

    def _sync_vacation_to_attendance(
        self, request_id: str, database_url: str | None = None
    ) -> None:
        req = self.get_request(request_id, database_url=database_url)
        if not req:
            return
        org_id = _employee_org_id(req["employee_id"], database_url=database_url)
        if not org_id:
            return
        from epayroll.db.attendance_facts_repository import AttendanceFactsRepository

        AttendanceFactsRepository().mark_benefit_days(
            org_id,
            req["employee_id"],
            date.fromisoformat(req["fecha_inicio"]),
            date.fromisoformat(req["fecha_fin"]),
            vacaciones=True,
            observacion=f"Vacaciones {req['fecha_inicio']}..{req['fecha_fin']}",
            database_url=database_url,
        )

    def assign_substitute(
        self,
        request_id: str,
        substitute_employee_id: str,
        database_url: str | None = None,
    ) -> dict[str, str]:
        self._validate_substitute(request_id, substitute_employee_id, database_url=database_url)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests
                    SET substitute_employee_id = %s::uuid
                    WHERE id = %s::uuid AND estado IN ('SOLICITADO', 'APROBADO')
                    RETURNING id
                    """,
                    (substitute_employee_id, request_id),
                )
                if not cur.fetchone():
                    raise ValueError("Solicitud no encontrada o no permite sustitución")
        return {"request_id": request_id, "substitute_employee_id": substitute_employee_id}

    def _validate_substitute(
        self,
        request_id: str,
        substitute_employee_id: str,
        database_url: str | None = None,
    ) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT vr.employee_id, e1.organization_id, e2.organization_id, e2.activo
                    FROM vacation_requests vr
                    JOIN employees e1 ON e1.id = vr.employee_id
                    JOIN employees e2 ON e2.id = %s::uuid
                    WHERE vr.id = %s::uuid
                    """,
                    (substitute_employee_id, request_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Solicitud o sustituto no encontrado")
                titular_id, org1, org2, activo = row
                validate_substitute_assignment(
                    str(titular_id),
                    substitute_employee_id,
                    str(org1),
                    str(org2),
                    bool(activo),
                )

    def org_coverage_dashboard(
        self,
        organization_id: str,
        fecha_desde: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Vacaciones aprobadas/solicitadas sin sustituto asignado (cobertura pendiente)."""
        fecha_desde = fecha_desde or date.today()
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT vr.id, vr.employee_id, e.nombres, e.apellidos,
                           vr.fecha_inicio, vr.fecha_fin, vr.dias_solicitados,
                           vr.estado::text, vr.substitute_employee_id
                    FROM vacation_requests vr
                    JOIN employees e ON e.id = vr.employee_id
                    WHERE e.organization_id = %s::uuid
                      AND vr.estado IN ('SOLICITADO', 'APROBADO')
                      AND vr.fecha_fin >= %s
                    ORDER BY vr.fecha_inicio
                    """,
                    (organization_id, fecha_desde),
                )
                rows = cur.fetchall()

        pendientes = []
        cubiertas = []
        for r in rows:
            item = {
                "request_id": str(r[0]),
                "employee_id": str(r[1]),
                "empleado": f"{r[2]} {r[3]}",
                "fecha_inicio": r[4].isoformat(),
                "fecha_fin": r[5].isoformat(),
                "dias_solicitados": str(r[6]),
                "estado": r[7],
                "substitute_employee_id": str(r[8]) if r[8] else None,
            }
            if r[8]:
                cubiertas.append(item)
            else:
                pendientes.append(item)

        return {
            "organization_id": organization_id,
            "fecha_desde": fecha_desde.isoformat(),
            "total_programadas": len(rows),
            "sin_cobertura": len(pendientes),
            "con_cobertura": len(cubiertas),
            "sin_sustituto": len(pendientes),
            "pendientes": pendientes,
            "cubiertas": cubiertas,
            "programadas": pendientes + cubiertas,
            "items": pendientes + cubiertas,
        }

    def list_requests(
        self,
        employee_id: str,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, fecha_inicio, fecha_fin, dias_solicitados, estado::text,
                           created_at, substitute_employee_id
                    FROM vacation_requests
                    WHERE employee_id = %s::uuid
                    ORDER BY fecha_inicio DESC
                    """,
                    (employee_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "request_id": str(r[0]),
                "fecha_inicio": r[1].isoformat(),
                "fecha_fin": r[2].isoformat(),
                "dias_solicitados": str(r[3]),
                "estado": r[4],
                "created_at": r[5].isoformat(),
                "substitute_employee_id": str(r[6]) if r[6] else None,
            }
            for r in rows
        ]

    def get_request(self, request_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, employee_id, fecha_inicio, fecha_fin, dias_solicitados, estado::text,
                           substitute_employee_id
                    FROM vacation_requests WHERE id = %s::uuid
                    """,
                    (request_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "id": str(row[0]),
            "request_id": str(row[0]),
            "employee_id": str(row[1]),
            "fecha_inicio": row[2].isoformat(),
            "fecha_fin": row[3].isoformat(),
            "dias_solicitados": str(row[4]),
            "estado": row[5],
            "substitute_employee_id": str(row[6]) if row[6] else None,
        }

    def update_request(
        self,
        request_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        dias_solicitados: Decimal,
        database_url: str | None = None,
    ) -> dict[str, str]:
        if fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin debe ser >= fecha_inicio")
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests
                    SET fecha_inicio = %s, fecha_fin = %s, dias_solicitados = %s
                    WHERE id = %s::uuid AND estado = 'SOLICITADO'
                    RETURNING id
                    """,
                    (fecha_inicio, fecha_fin, dias_solicitados, request_id),
                )
                if not cur.fetchone():
                    raise ValueError("Solicitud no encontrada o no editable")
        return {"request_id": request_id, "estado": "SOLICITADO"}

    def cancel_request(self, request_id: str, database_url: str | None = None) -> dict[str, str]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE vacation_requests SET estado = 'CANCELADO'
                    WHERE id = %s::uuid AND estado = 'SOLICITADO'
                    RETURNING id
                    """,
                    (request_id,),
                )
                if not cur.fetchone():
                    raise ValueError("Solicitud no encontrada o no cancelable")
        return {"request_id": request_id, "estado": "CANCELADO"}

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
