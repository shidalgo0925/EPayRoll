from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from epayroll.db.connection import get_connection
from epayroll.engine.context import PayrollInput
from epayroll.time.calculator import DailyAttendance, PeriodSummary, ShiftConfig, calculate_day, summarize_period


DEFAULT_SHIFT = ShiftConfig(codigo="DIURNO", tipo_jornada="DIURNA", horas_max_dia=Decimal("8"))


class AttendanceRepository:
    def assign_schedule(
        self,
        employee_id: str,
        shift_codigo: str,
        fecha_inicio: date,
        fecha_fin: date | None = None,
        database_url: str | None = None,
    ) -> str:
        schedule_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM shift_types WHERE codigo = %s AND activo = true LIMIT 1",
                    (shift_codigo,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Turno no encontrado: {shift_codigo}")
                cur.execute(
                    """
                    INSERT INTO employee_schedules (id, employee_id, shift_type_id, fecha_inicio, fecha_fin)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    RETURNING id
                    """,
                    (schedule_id, employee_id, row[0], fecha_inicio, fecha_fin),
                )
                return str(cur.fetchone()[0])

    def create_time_entry(
        self,
        employee_id: str,
        timestamp_entrada: datetime,
        timestamp_salida: datetime | None,
        fuente: str = "MANUAL",
        database_url: str | None = None,
    ) -> str:
        entry_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO time_entries (id, employee_id, timestamp_entrada, timestamp_salida, fuente)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    RETURNING id
                    """,
                    (entry_id, employee_id, timestamp_entrada, timestamp_salida, fuente),
                )
                return str(cur.fetchone()[0])

    def _shift_for_date(self, cur, employee_id: str, fecha: date) -> ShiftConfig:
        cur.execute(
            """
            SELECT st.codigo, st.tipo_jornada::text, st.horas_max_dia, st.maximo_extras_diarias
            FROM employee_schedules es
            JOIN shift_types st ON st.id = es.shift_type_id
            WHERE es.employee_id = %s::uuid
              AND es.fecha_inicio <= %s
              AND (es.fecha_fin IS NULL OR es.fecha_fin >= %s)
            ORDER BY es.fecha_inicio DESC LIMIT 1
            """,
            (employee_id, fecha, fecha),
        )
        row = cur.fetchone()
        if not row:
            return DEFAULT_SHIFT
        return ShiftConfig(
            codigo=row[0],
            tipo_jornada=row[1],
            horas_max_dia=Decimal(str(row[2])),
            maximo_extras_diarias=Decimal(str(row[3])),
        )

    def _is_holiday(self, cur, fecha: date) -> bool:
        cur.execute("SELECT 1 FROM holidays WHERE fecha = %s AND activo = true LIMIT 1", (fecha,))
        return cur.fetchone() is not None

    def _is_incapacity(self, cur, employee_id: str, fecha: date) -> bool:
        cur.execute(
            """
            SELECT 1 FROM incapacities
            WHERE employee_id = %s::uuid AND fecha_inicio <= %s AND fecha_fin >= %s
            LIMIT 1
            """,
            (employee_id, fecha, fecha),
        )
        return cur.fetchone() is not None

    def _has_facts(
        self,
        cur,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> bool:
        cur.execute(
            """
            SELECT 1 FROM attendance_facts
            WHERE employee_id = %s::uuid
              AND fecha >= %s AND fecha <= %s
              AND estado_validacion = 'VALIDO'
            LIMIT 1
            """,
            (employee_id, fecha_inicio, fecha_fin),
        )
        return cur.fetchone() is not None

    def calculate_period(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> PeriodSummary:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                if self._has_facts(cur, employee_id, fecha_inicio, fecha_fin):
                    from epayroll.db.attendance_facts_repository import AttendanceFactsRepository

                    org_row = self._org_for_employee(cur, employee_id)
                    if org_row:
                        AttendanceFactsRepository().process_period_to_daily(
                            org_row, fecha_inicio, fecha_fin, database_url=database_url
                        )
                    return self.get_period_summary(employee_id, fecha_inicio, fecha_fin, database_url)

        days: list[DailyAttendance] = []
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT timestamp_entrada, timestamp_salida
                    FROM time_entries
                    WHERE employee_id = %s::uuid
                      AND timestamp_entrada::date >= %s
                      AND timestamp_entrada::date <= %s
                      AND timestamp_salida IS NOT NULL
                    ORDER BY timestamp_entrada
                    """,
                    (employee_id, fecha_inicio, fecha_fin),
                )
                entries = cur.fetchall()

                by_date: dict[date, list[tuple[datetime, datetime]]] = {}
                for entrada, salida in entries:
                    d = entrada.date()
                    by_date.setdefault(d, []).append((entrada, salida))

                for d, punches in sorted(by_date.items()):
                    shift = self._shift_for_date(cur, employee_id, d)
                    es_feriado = self._is_holiday(cur, d)
                    es_incap = self._is_incapacity(cur, employee_id, d)
                    # Consolidar múltiples marcaciones del mismo día
                    day_start = min(p[0] for p in punches)
                    day_end = max(p[1] for p in punches)
                    daily = calculate_day(d, day_start, day_end, shift, es_feriado, es_incap)
                    days.append(daily)
                    self._upsert_daily(cur, employee_id, daily)

        return summarize_period(days)

    @staticmethod
    def _org_for_employee(cur, employee_id: str) -> str | None:
        cur.execute("SELECT organization_id FROM employees WHERE id = %s::uuid", (employee_id,))
        row = cur.fetchone()
        return str(row[0]) if row else None

    def _upsert_daily(self, cur, employee_id: str, daily: DailyAttendance) -> None:
        cur.execute(
            """
            INSERT INTO attendance_daily (
                employee_id, fecha, horas_ordinarias, horas_extra_diurna, horas_extra_nocturna,
                horas_extra_mixta_noct, horas_domingo, horas_feriado,
                es_feriado, es_domingo, dias_trabajados, calculado_at
            ) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (employee_id, fecha) DO UPDATE SET
                horas_ordinarias = EXCLUDED.horas_ordinarias,
                horas_extra_diurna = EXCLUDED.horas_extra_diurna,
                horas_extra_nocturna = EXCLUDED.horas_extra_nocturna,
                horas_extra_mixta_noct = EXCLUDED.horas_extra_mixta_noct,
                horas_domingo = EXCLUDED.horas_domingo,
                horas_feriado = EXCLUDED.horas_feriado,
                es_feriado = EXCLUDED.es_feriado,
                es_domingo = EXCLUDED.es_domingo,
                dias_trabajados = EXCLUDED.dias_trabajados,
                calculado_at = now()
            """,
            (
                employee_id,
                daily.fecha,
                daily.horas_ordinarias,
                daily.horas_extra_diurna,
                daily.horas_extra_nocturna,
                daily.horas_extra_mixta_noct,
                daily.horas_domingo,
                daily.horas_feriado,
                daily.es_feriado,
                daily.es_domingo,
                daily.dias_trabajados,
            ),
        )

    def get_period_summary(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> PeriodSummary:
        """Lee attendance_daily ya calculado o recalcula si vacío."""
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM attendance_daily
                    WHERE employee_id = %s::uuid AND fecha >= %s AND fecha <= %s
                    """,
                    (employee_id, fecha_inicio, fecha_fin),
                )
                count = cur.fetchone()[0]
        if count == 0:
            return self.calculate_period(employee_id, fecha_inicio, fecha_fin, database_url)

        days: list[DailyAttendance] = []
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fecha, horas_ordinarias, horas_extra_diurna, horas_extra_nocturna,
                           horas_extra_mixta_noct, horas_domingo, horas_feriado,
                           es_feriado, es_domingo, dias_trabajados
                    FROM attendance_daily
                    WHERE employee_id = %s::uuid AND fecha >= %s AND fecha <= %s
                    ORDER BY fecha
                    """,
                    (employee_id, fecha_inicio, fecha_fin),
                )
                for row in cur.fetchall():
                    days.append(
                        DailyAttendance(
                            fecha=row[0],
                            horas_ordinarias=Decimal(str(row[1])),
                            horas_extra_diurna=Decimal(str(row[2])),
                            horas_extra_nocturna=Decimal(str(row[3])),
                            horas_extra_mixta_noct=Decimal(str(row[4])),
                            horas_domingo=Decimal(str(row[5])),
                            horas_feriado=Decimal(str(row[6])),
                            es_feriado=row[7],
                            es_domingo=row[8],
                            dias_trabajados=Decimal(str(row[9])),
                        )
                    )
        return summarize_period(days)

    def to_payroll_input_fields(self, summary: PeriodSummary) -> dict[str, Decimal]:
        return {
            "dias_trabajados": summary.dias_trabajados,
            "horas_extra_diurnas": summary.horas_extra_diurnas,
            "horas_extra_nocturnas": summary.horas_extra_nocturnas,
            "horas_extra_mixta_nocturnas": summary.horas_extra_mixta_nocturnas,
            "horas_domingo": summary.horas_domingo,
            "horas_feriado": summary.horas_feriado,
        }

    def get_period_dates(self, payroll_period_id: str, database_url: str | None = None) -> tuple[date, date]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fecha_inicio, fecha_fin FROM payroll_periods WHERE id = %s::uuid",
                    (payroll_period_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Período de planilla no encontrado")
                return row[0], row[1]

    def list_daily(
        self,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        summary = self.get_period_summary(employee_id, fecha_inicio, fecha_fin, database_url)
        return [
            {
                "fecha": d.fecha.isoformat(),
                "horas_ordinarias": str(d.horas_ordinarias),
                "horas_extra_diurna": str(d.horas_extra_diurna),
                "horas_extra_nocturna": str(d.horas_extra_nocturna),
                "horas_domingo": str(d.horas_domingo),
                "horas_feriado": str(d.horas_feriado),
                "dias_trabajados": str(d.dias_trabajados),
            }
            for d in summary.days
        ]
