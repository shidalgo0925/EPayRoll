from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.db.connection import get_connection
from epayroll.time.incapacity import (
    _q2,
    calculate_incapacity_payment,
    count_calendar_days,
    dias_incapacidad_en_periodo,
    license_fund_balance,
    load_incapacity_config,
)


class IncapacityRepository:
    def create(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        tipo: str = "CSS",
        certificado_ref: str | None = None,
        dias_subsidio_css: int | None = None,
        database_url: str | None = None,
    ) -> dict[str, str]:
        if fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin debe ser >= fecha_inicio")
        cfg = load_incapacity_config()
        if tipo not in cfg.get("tipos", []):
            raise ValueError(f"Tipo incapacidad inválido: {tipo}")

        inc_id = str(uuid.uuid4())
        dias = count_calendar_days(fecha_inicio, fecha_fin)
        if dias_subsidio_css is None and tipo == "CSS":
            dias_subsidio_css = max(0, dias - int(cfg["pago_incapacidad"]["dias_empleador_fondo"]))

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incapacities (
                        id, employee_id, fecha_inicio, fecha_fin, tipo,
                        certificado_ref, dias_subsidio_css
                    ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (inc_id, employee_id, fecha_inicio, fecha_fin, tipo, certificado_ref, dias_subsidio_css),
                )
                inc_id = str(cur.fetchone()[0])
        self._sync_to_attendance(employee_id, fecha_inicio, fecha_fin, database_url=database_url)
        return {
            "incapacity_id": inc_id,
            "employee_id": employee_id,
            "dias_calendario": str(dias),
        }

    def list_for_employee(
        self,
        employee_id: str,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, fecha_inicio, fecha_fin, tipo, certificado_ref,
                           dias_subsidio_css, created_at
                    FROM incapacities
                    WHERE employee_id = %s::uuid
                    ORDER BY fecha_inicio DESC
                    """,
                    (employee_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "fecha_inicio": r[1].isoformat(),
                "fecha_fin": r[2].isoformat(),
                "tipo": r[3],
                "certificado_ref": r[4],
                "dias_subsidio_css": r[5],
                "created_at": r[6].isoformat(),
            }
            for r in rows
        ]

    def get(self, incapacity_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, employee_id, fecha_inicio, fecha_fin, tipo, certificado_ref,
                           dias_subsidio_css, created_at
                    FROM incapacities WHERE id = %s::uuid
                    """,
                    (incapacity_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "id": str(row[0]),
            "employee_id": str(row[1]),
            "fecha_inicio": row[2].isoformat(),
            "fecha_fin": row[3].isoformat(),
            "tipo": row[4],
            "certificado_ref": row[5],
            "dias_subsidio_css": row[6],
            "created_at": row[7].isoformat(),
        }

    def update(
        self,
        incapacity_id: str,
        *,
        fecha_inicio: date,
        fecha_fin: date,
        tipo: str = "CSS",
        certificado_ref: str | None = None,
        dias_subsidio_css: int | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        if fecha_fin < fecha_inicio:
            raise ValueError("fecha_fin debe ser >= fecha_inicio")
        cfg = load_incapacity_config()
        if tipo not in cfg.get("tipos", []):
            raise ValueError(f"Tipo incapacidad inválido: {tipo}")
        dias = count_calendar_days(fecha_inicio, fecha_fin)
        if dias_subsidio_css is None and tipo == "CSS":
            dias_subsidio_css = max(0, dias - int(cfg["pago_incapacidad"]["dias_empleador_fondo"]))
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE incapacities
                    SET fecha_inicio = %s, fecha_fin = %s, tipo = %s,
                        certificado_ref = %s, dias_subsidio_css = %s
                    WHERE id = %s::uuid
                    RETURNING id
                    """,
                    (fecha_inicio, fecha_fin, tipo, certificado_ref, dias_subsidio_css, incapacity_id),
                )
                if not cur.fetchone():
                    raise ValueError("Incapacidad no encontrada")
        result = self.get(incapacity_id, database_url=database_url)
        assert result is not None
        self._sync_to_attendance(
            result["employee_id"],
            date.fromisoformat(result["fecha_inicio"]),
            date.fromisoformat(result["fecha_fin"]),
            database_url=database_url,
        )
        return result

    def delete(self, incapacity_id: str, database_url: str | None = None) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM incapacities WHERE id = %s::uuid", (incapacity_id,))
                if cur.rowcount == 0:
                    raise ValueError("Incapacidad no encontrada")

    def _jornadas_trabajadas_anio(
        self,
        employee_id: str,
        anio: int,
        database_url: str | None = None,
    ) -> Decimal:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(dias_trabajados), 0)
                    FROM attendance_daily
                    WHERE employee_id = %s::uuid
                      AND EXTRACT(YEAR FROM fecha) = %s
                    """,
                    (employee_id, anio),
                )
                row = cur.fetchone()
        return Decimal(str(row[0] if row else 0))

    def _horas_fondo_usadas(
        self,
        employee_id: str,
        anio: int,
        database_url: str | None = None,
    ) -> Decimal:
        cfg = load_incapacity_config()
        horas_jornada = Decimal(str(cfg["fondo_licencia"]["horas_jornada_referencia"]))
        dias_emp = int(cfg["pago_incapacidad"]["dias_empleador_fondo"])
        total = Decimal("0")
        for inc in self.list_for_employee(employee_id, database_url=database_url):
            if date.fromisoformat(inc["fecha_inicio"]).year != anio:
                continue
            dias = count_calendar_days(
                date.fromisoformat(inc["fecha_inicio"]),
                date.fromisoformat(inc["fecha_fin"]),
            )
            dias_cargo_emp = min(dias, dias_emp)
            total += horas_jornada * Decimal(dias_cargo_emp)
        return total

    def get_license_fund_balance(
        self,
        employee_id: str,
        anio: int | None = None,
        database_url: str | None = None,
    ) -> dict[str, str]:
        anio = anio or date.today().year
        jornadas = self._jornadas_trabajadas_anio(employee_id, anio, database_url)
        usadas = self._horas_fondo_usadas(employee_id, anio, database_url)
        bal = license_fund_balance(jornadas, usadas)
        return {
            "anio": str(anio),
            "jornadas_trabajadas": str(bal.jornadas_acumuladas),
            "horas_acumuladas": str(bal.horas_acumuladas),
            "horas_usadas": str(bal.horas_usadas),
            "horas_disponibles": str(bal.horas_disponibles),
            "tope_anual_horas": str(bal.tope_anual),
        }

    def calculate_period_impact(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        salario_mensual: Decimal,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Impacto planilla: reduce días trabajados y calcula pagos GT-10."""
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fecha_inicio, fecha_fin FROM incapacities
                    WHERE employee_id = %s::uuid
                      AND fecha_fin >= %s AND fecha_inicio <= %s
                    """,
                    (employee_id, fecha_inicio, fecha_fin),
                )
                rows = cur.fetchall()

        incap_ranges = [(r[0], r[1]) for r in rows]
        dias_inc = dias_incapacidad_en_periodo(fecha_inicio, fecha_fin, incap_ranges)
        salario_diario = _q2(salario_mensual / Decimal("30"))

        anio = fecha_fin.year
        bal = license_fund_balance(
            self._jornadas_trabajadas_anio(employee_id, anio, database_url),
            self._horas_fondo_usadas(employee_id, anio, database_url),
        )
        fondo_agotado = bal.horas_disponibles <= Decimal("0")

        split = calculate_incapacity_payment(dias_inc, salario_diario, fondo_agotado=fondo_agotado)

        return {
            "dias_incapacidad": dias_inc,
            "dias_trabajados_ajuste": str(-dias_inc),
            "salario_diario": str(salario_diario),
            "fondo_licencia_agotado": fondo_agotado,
            "pago_empleador": {
                "dias": split.dias_empleador,
                "monto": str(split.monto_empleador),
                "fondo_horas_usadas": str(split.fondo_licencia_usado_horas),
            },
            "pago_css": {
                "dias": split.dias_css,
                "monto_subsidio": str(split.monto_css_subsidio),
            },
            "incapacidades_en_periodo": len(rows),
        }

    def _sync_to_attendance(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT organization_id FROM employees WHERE id = %s::uuid",
                    (employee_id,),
                )
                row = cur.fetchone()
                if not row:
                    return
                org_id = str(row[0])
        from epayroll.db.attendance_facts_repository import AttendanceFactsRepository

        AttendanceFactsRepository().mark_benefit_days(
            org_id,
            employee_id,
            fecha_inicio,
            fecha_fin,
            incapacidad=True,
            observacion=f"Incapacidad {fecha_inicio.isoformat()}..{fecha_fin.isoformat()}",
            database_url=database_url,
        )
