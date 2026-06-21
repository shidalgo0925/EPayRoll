"""Repositorio — tabla estándar attendance_facts + importación + resumen."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from epayroll.attendance.validator import compute_descuento_minutos, validate_fact_row
from epayroll.db.connection import get_connection
from epayroll.time.calculator import DailyAttendance, PeriodSummary, ShiftConfig, calculate_day, summarize_period
from epayroll.time.tz import TZ

DEFAULT_SHIFT = ShiftConfig(codigo="DIURNO", tipo_jornada="DIURNA", horas_max_dia=Decimal("8"))


class AttendanceFactsRepository:
    def resolve_employee_id(
        self,
        organization_id: str,
        *,
        employee_id: str | None = None,
        cedula: str | None = None,
        database_url: str | None = None,
    ) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                if employee_id:
                    cur.execute(
                        """
                        SELECT id FROM employees
                        WHERE id = %s::uuid AND organization_id = %s::uuid AND activo = true
                        """,
                        (employee_id, organization_id),
                    )
                elif cedula:
                    cur.execute(
                        """
                        SELECT id FROM employees
                        WHERE organization_id = %s::uuid AND cedula = %s AND activo = true
                        LIMIT 1
                        """,
                        (organization_id, cedula),
                    )
                else:
                    return None
                row = cur.fetchone()
                return str(row[0]) if row else None

    def upsert_fact(
        self,
        organization_id: str,
        row: dict[str, Any],
        *,
        import_batch_id: str | None = None,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        emp_id = row.get("employee_id") or self.resolve_employee_id(
            organization_id,
            employee_id=row.get("employee_id"),
            cedula=row.get("cedula"),
            database_url=database_url,
        )
        normalized, errors = validate_fact_row(
            row,
            employee_id=emp_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
        if not emp_id and not errors:
            errors.append("empleado no encontrado en la organización")

        no_trabajo = bool(
            normalized.get("ausencia") or normalized.get("incapacidad") or normalized.get("vacaciones")
        )
        vacio = not normalized.get("hora_entrada") and not normalized.get("hora_salida")
        if errors and vacio and not no_trabajo:
            estado = "PENDIENTE"
            errors = []
        elif errors:
            return {
                "id": None,
                "employee_id": emp_id,
                "fecha": normalized.get("fecha"),
                "estado_validacion": "ERROR",
                "errores": errors,
            }
        else:
            estado = "VALIDO"

        fact_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                        """
                        INSERT INTO attendance_facts (
                            id, organization_id, employee_id, fecha, turno,
                            hora_entrada, hora_salida, descanso_minutos, tipo_dia,
                            ausencia, incapacidad, vacaciones, observacion, fuente,
                            import_batch_id, estado_validacion, errores_validacion
                        ) VALUES (
                            %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::attendance_day_type,
                            %s, %s, %s, %s, %s, %s::uuid, %s::attendance_fact_status, %s
                        )
                        ON CONFLICT (employee_id, fecha) DO UPDATE SET
                            turno = EXCLUDED.turno,
                            hora_entrada = EXCLUDED.hora_entrada,
                            hora_salida = EXCLUDED.hora_salida,
                            descanso_minutos = EXCLUDED.descanso_minutos,
                            tipo_dia = EXCLUDED.tipo_dia,
                            ausencia = EXCLUDED.ausencia,
                            incapacidad = EXCLUDED.incapacidad,
                            vacaciones = EXCLUDED.vacaciones,
                            observacion = EXCLUDED.observacion,
                            fuente = EXCLUDED.fuente,
                            import_batch_id = COALESCE(EXCLUDED.import_batch_id, attendance_facts.import_batch_id),
                            estado_validacion = EXCLUDED.estado_validacion,
                            errores_validacion = EXCLUDED.errores_validacion,
                            updated_at = now()
                        RETURNING id
                        """,
                        (
                            fact_id,
                            organization_id,
                            emp_id,
                            normalized["fecha"],
                            normalized.get("turno"),
                            normalized.get("hora_entrada"),
                            normalized.get("hora_salida"),
                            normalized.get("descanso_minutos", 0),
                            normalized.get("tipo_dia", "NORMAL"),
                            normalized.get("ausencia", False),
                            normalized.get("incapacidad", False),
                            normalized.get("vacaciones", False),
                            normalized.get("observacion"),
                            normalized.get("fuente", "MANUAL"),
                            import_batch_id,
                            estado,
                            json.dumps([]),
                        ),
                    )
                returned_id = str(cur.fetchone()[0])
        return {
            "id": returned_id,
            "employee_id": emp_id,
            "fecha": normalized.get("fecha"),
            "estado_validacion": estado,
            "errores": errors,
        }

    def import_rows(
        self,
        organization_id: str,
        rows: list[dict[str, Any]],
        *,
        fuente: str = "CSV",
        nombre_archivo: str | None = None,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        batch_id = str(uuid.uuid4())
        validos = 0
        errores = 0
        results: list[dict[str, Any]] = []

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO attendance_import_batches (
                        id, organization_id, fuente, nombre_archivo,
                        fecha_inicio, fecha_fin, total_filas, estado
                    ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, 'RECIBIDO')
                    """,
                    (batch_id, organization_id, fuente, nombre_archivo, fecha_inicio, fecha_fin, len(rows)),
                )

        for row in rows:
            r = self.upsert_fact(
                organization_id,
                row,
                import_batch_id=batch_id,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                database_url=database_url,
            )
            results.append(r)
            if r["errores"]:
                errores += 1
            else:
                validos += 1

        estado = "VALIDO" if errores == 0 else ("PARCIAL" if validos else "ERROR")
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE attendance_import_batches SET
                        filas_validas = %s, filas_error = %s, estado = %s::attendance_import_status
                    WHERE id = %s::uuid
                    """,
                    (validos, errores, estado, batch_id),
                )

        return {
            "import_batch_id": batch_id,
            "total": len(rows),
            "validos": validos,
            "errores": errores,
            "estado": estado,
            "filas": results,
        }

    def list_facts(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        *,
        employee_id: str | None = None,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                q = """
                    SELECT af.id, af.employee_id, e.cedula, e.nombres, e.apellidos,
                           af.fecha, af.turno, af.hora_entrada, af.hora_salida,
                           af.descanso_minutos, af.tipo_dia::text, af.ausencia, af.incapacidad,
                           af.vacaciones, af.observacion, af.fuente, af.estado_validacion::text,
                           af.errores_validacion
                    FROM attendance_facts af
                    JOIN employees e ON e.id = af.employee_id
                    WHERE af.organization_id = %s::uuid
                      AND af.fecha >= %s AND af.fecha <= %s
                """
                params: list[Any] = [organization_id, fecha_inicio, fecha_fin]
                if employee_id:
                    q += " AND af.employee_id = %s::uuid"
                    params.append(employee_id)
                q += " ORDER BY af.fecha, e.apellidos, e.nombres"
                cur.execute(q, params)
                rows = cur.fetchall()
        return [self._fact_row(r) for r in rows]

    def validate_period(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        facts = self.list_facts(organization_id, fecha_inicio, fecha_fin, database_url=database_url)
        validos = sum(1 for f in facts if f["estado_validacion"] == "VALIDO")
        errores = sum(1 for f in facts if f["estado_validacion"] == "ERROR")
        pendientes = sum(1 for f in facts if f["estado_validacion"] == "PENDIENTE")
        return {
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "total": len(facts),
            "validos": validos,
            "errores": errores,
            "pendientes": pendientes,
            "listo_para_planilla": errores == 0 and pendientes == 0 and validos > 0,
        }

    def _fact_to_daily(self, fact: dict[str, Any], shift: ShiftConfig) -> DailyAttendance:
        fecha = date.fromisoformat(fact["fecha"]) if isinstance(fact["fecha"], str) else fact["fecha"]
        if fact["ausencia"] or fact["vacaciones"]:
            return DailyAttendance(fecha=fecha, dias_trabajados=Decimal("0"))
        if fact["incapacidad"]:
            return calculate_day(fecha, datetime.now(TZ), datetime.now(TZ), shift, es_feriado=False, es_incapacidad=True)

        entrada_t = fact.get("hora_entrada")
        salida_t = fact.get("hora_salida")
        if not entrada_t or not salida_t:
            return DailyAttendance(fecha=fecha, dias_trabajados=Decimal("0"))

        if isinstance(entrada_t, str):
            h, m = map(int, entrada_t.split(":")[:2])
            entrada_t = time(h, m)
        if isinstance(salida_t, str):
            h, m = map(int, salida_t.split(":")[:2])
            salida_t = time(h, m)

        from datetime import timedelta

        entrada = datetime.combine(fecha, entrada_t, tzinfo=TZ)
        salida = datetime.combine(fecha, salida_t, tzinfo=TZ)
        descanso = int(fact.get("descanso_minutos") or 0)
        if descanso:
            worked = (salida - entrada) - timedelta(minutes=descanso)
            if worked.total_seconds() <= 0:
                return DailyAttendance(fecha=fecha, dias_trabajados=Decimal("0"))
            salida = entrada + worked

        es_feriado = fact["tipo_dia"] == "FERIADO"
        daily = calculate_day(
            fecha,
            entrada,
            salida,
            shift,
            es_feriado=es_feriado,
            es_incapacidad=fact["incapacidad"],
        )
        if fact["tipo_dia"] == "DOMINGO" and not es_feriado and not daily.es_domingo:
            daily.horas_domingo = daily.horas_ordinarias + daily.horas_domingo
            daily.horas_ordinarias = Decimal("0")
            daily.es_domingo = True
        return daily

    @staticmethod
    def compute_payroll_dias_trabajados(
        ausencias: int,
        vacaciones: int,
        *,
        es_quincena: bool,
    ) -> Decimal:
        """Días efectivos de pago: quincena 15 − ausencias − vacaciones; mensual 30 − …"""
        base = Decimal("15") if es_quincena else Decimal("30")
        return max(Decimal("0"), base - Decimal(ausencias) - Decimal(vacaciones))

    @staticmethod
    def payroll_dias_pago_nominal(es_quincena: bool) -> Decimal:
        """Días de la quincena/mes para mostrar en planilla (antes de descuentos)."""
        return Decimal("15") if es_quincena else Decimal("30")

    def summarize_employee_for_payroll(
        self,
        organization_id: str,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        *,
        es_quincena: bool,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Resumen de asistencia para corrida de planilla (incluye ausencias en días de pago)."""
        facts = [
            f
            for f in self.list_facts(
                organization_id,
                fecha_inicio,
                fecha_fin,
                employee_id=employee_id,
                database_url=database_url,
            )
            if f["estado_validacion"] == "VALIDO"
        ]
        ausencias = sum(1 for f in facts if f["ausencia"])
        vacaciones = sum(1 for f in facts if f["vacaciones"])
        descuento_minutos = 0
        for fact in facts:
            if fact["ausencia"] or fact["vacaciones"] or fact["incapacidad"]:
                continue
            descuento_minutos += compute_descuento_minutos(
                fact.get("hora_entrada"),
                fact.get("hora_salida"),
                fact.get("observacion"),
            )

        days: list[DailyAttendance] = []
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                for fact in sorted(facts, key=lambda x: x["fecha"]):
                    if fact["ausencia"] or fact["vacaciones"]:
                        continue
                    shift = self._shift_from_codigo(cur, fact.get("turno") or "DIURNO")
                    days.append(self._fact_to_daily(fact, shift))

        summary = summarize_period(days) if days else PeriodSummary(
            dias_trabajados=Decimal("0"),
            horas_extra_diurnas=Decimal("0"),
            horas_extra_nocturnas=Decimal("0"),
            horas_extra_mixta_nocturnas=Decimal("0"),
            horas_domingo=Decimal("0"),
            horas_feriado=Decimal("0"),
            days=[],
        )
        dias_trab = self.compute_payroll_dias_trabajados(
            ausencias, vacaciones, es_quincena=es_quincena
        )
        return {
            "dias_trabajados": dias_trab,
            "ausencias": ausencias,
            "vacaciones": vacaciones,
            "descuento_minutos": descuento_minutos,
            "horas_extra_diurnas": summary.horas_extra_diurnas,
            "horas_extra_nocturnas": summary.horas_extra_nocturnas,
            "horas_extra_mixta_nocturnas": summary.horas_extra_mixta_nocturnas,
            "horas_domingo": summary.horas_domingo,
            "horas_feriado": summary.horas_feriado,
        }

    def process_period_to_daily(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Hechos VALIDO → attendance_daily + resumen quincenal por empleado."""
        validation = self.validate_period(organization_id, fecha_inicio, fecha_fin, database_url)
        if not validation["listo_para_planilla"] and validation["validos"] == 0:
            return {"validation": validation, "employees": [], "message": "Sin hechos válidos"}

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM attendance_daily ad
                    USING employees e
                    WHERE ad.employee_id = e.id
                      AND e.organization_id = %s::uuid
                      AND ad.fecha >= %s AND ad.fecha <= %s
                    """,
                    (organization_id, fecha_inicio, fecha_fin),
                )

        facts = [f for f in self.list_facts(organization_id, fecha_inicio, fecha_fin, database_url=database_url) if f["estado_validacion"] == "VALIDO"]
        by_emp: dict[str, list[dict[str, Any]]] = {}
        for f in facts:
            by_emp.setdefault(f["employee_id"], []).append(f)

        summaries: list[dict[str, Any]] = []
        es_quincena_period = (fecha_fin - fecha_inicio).days <= 16
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                for emp_id, emp_facts in by_emp.items():
                    days: list[DailyAttendance] = []
                    tardanzas = 0
                    descuento_minutos_total = 0
                    ausencias = 0
                    for fact in sorted(emp_facts, key=lambda x: x["fecha"]):
                        if fact["ausencia"]:
                            ausencias += 1
                        desc_dia = compute_descuento_minutos(
                            fact.get("hora_entrada"),
                            fact.get("hora_salida"),
                            fact.get("observacion"),
                        )
                        if desc_dia > 0:
                            tardanzas += 1
                            descuento_minutos_total += desc_dia
                        turno = fact.get("turno") or "DIURNO"
                        shift = self._shift_from_codigo(cur, turno)
                        daily = self._fact_to_daily(fact, shift)
                        days.append(daily)
                        cur.execute(
                            """
                            INSERT INTO attendance_daily (
                                employee_id, fecha, horas_ordinarias, horas_extra_diurna,
                                horas_extra_nocturna, horas_extra_mixta_noct, horas_domingo,
                                horas_feriado, es_feriado, es_domingo, dias_trabajados, calculado_at
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
                                emp_id,
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
                    summary = summarize_period(days)
                    vacaciones = sum(1 for f in emp_facts if f["vacaciones"])
                    dias_planilla = self.compute_payroll_dias_trabajados(
                        ausencias, vacaciones, es_quincena=es_quincena_period
                    )
                    summaries.append(
                        {
                            "employee_id": emp_id,
                            "cedula": emp_facts[0]["cedula"],
                            "nombre": f"{emp_facts[0]['nombres']} {emp_facts[0]['apellidos']}",
                            "dias_trabajados": str(dias_planilla),
                            "horas_extra_diurnas": str(summary.horas_extra_diurnas),
                            "horas_extra_nocturnas": str(summary.horas_extra_nocturnas),
                            "horas_domingo": str(summary.horas_domingo),
                            "horas_feriado": str(summary.horas_feriado),
                            "ausencias": ausencias,
                            "tardanzas": tardanzas,
                            "descuento_minutos": descuento_minutos_total,
                            "incapacidades": sum(1 for f in emp_facts if f["incapacidad"]),
                            "vacaciones": sum(1 for f in emp_facts if f["vacaciones"]),
                        }
                    )

        return {"validation": validation, "employees": summaries, "employee_count": len(summaries)}

    @staticmethod
    def _shift_from_codigo(cur, codigo: str) -> ShiftConfig:
        cur.execute(
            "SELECT codigo, tipo_jornada::text, horas_max_dia, maximo_extras_diarias FROM shift_types WHERE codigo = %s AND activo = true LIMIT 1",
            (codigo,),
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

    @staticmethod
    def _fact_row(row) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "employee_id": str(row[1]),
            "cedula": row[2],
            "nombres": row[3],
            "apellidos": row[4],
            "fecha": row[5].isoformat(),
            "turno": row[6],
            "hora_entrada": row[7].isoformat() if row[7] else None,
            "hora_salida": row[8].isoformat() if row[8] else None,
            "descanso_minutos": row[9],
            "tipo_dia": row[10],
            "ausencia": row[11],
            "incapacidad": row[12],
            "vacaciones": row[13],
            "observacion": row[14],
            "fuente": row[15],
            "estado_validacion": row[16],
            "errores_validacion": row[17],
        }

    def seed_demo_period(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Genera hechos de asistencia demo (lun–sáb) para todos los empleados activos."""
        from datetime import timedelta

        from epayroll.db.repositories import EmployeeRepository

        employees = EmployeeRepository().list_by_org(organization_id, database_url=database_url)
        if not employees:
            return {"seeded": 0, "employees": 0}

        seeded = 0
        for emp in employees:
            d = fecha_inicio
            while d <= fecha_fin:
                if d.weekday() == 6:
                    d += timedelta(days=1)
                    continue
                self.upsert_fact(
                    organization_id,
                    {
                        "employee_id": emp.id,
                        "fecha": d,
                        "turno": "DIURNO",
                        "hora_entrada": "08:00",
                        "hora_salida": "17:00",
                        "descanso_minutos": 60,
                        "tipo_dia": "NORMAL",
                        "fuente": "DEMO",
                    },
                    database_url=database_url,
                )
                seeded += 1
                d += timedelta(days=1)

        proc = self.process_period_to_daily(
            organization_id, fecha_inicio, fecha_fin, database_url=database_url
        )
        return {
            "seeded": seeded,
            "employees": len(employees),
            "processed": proc.get("employee_count", 0),
        }

    def _fact_exists(
        self, cur, employee_id: str, fecha: date
    ) -> bool:
        cur.execute(
            """
            SELECT 1 FROM attendance_facts
            WHERE employee_id = %s::uuid AND fecha = %s
            LIMIT 1
            """,
            (employee_id, fecha),
        )
        return cur.fetchone() is not None

    def _fetch_fact_snapshot(
        self, cur, employee_id: str, fecha: date
    ) -> tuple[bool, bool, bool, Any, Any, Any] | None:
        cur.execute(
            """
            SELECT ausencia, incapacidad, vacaciones, hora_entrada, hora_salida, descanso_minutos
            FROM attendance_facts
            WHERE employee_id = %s::uuid AND fecha = %s
            LIMIT 1
            """,
            (employee_id, fecha),
        )
        row = cur.fetchone()
        return row

    @staticmethod
    def _time_hhmm(value: Any) -> str | None:
        if value is None:
            return None
        if hasattr(value, "strftime"):
            return value.strftime("%H:%M")
        return str(value)[:5]

    @staticmethod
    def _needs_default_apply(snapshot: tuple | None) -> bool:
        if snapshot is None:
            return True
        ausencia, incap, vac, entrada, salida, descanso = snapshot
        if ausencia or incap or vac:
            return False
        if entrada is None and salida is None:
            return True
        # Migrar horario default anterior (descanso 61 min → 60 min, 8 h netas)
        if (
            AttendanceFactsRepository._time_hhmm(entrada) == "08:00"
            and AttendanceFactsRepository._time_hhmm(salida) == "17:00"
            and int(descanso or 0) == 61
        ):
            return True
        return False

    @staticmethod
    def _default_fact_row(employee_id: str, fecha: date, *, fuente: str) -> dict[str, Any]:
        return {
            "employee_id": employee_id,
            "fecha": fecha,
            "turno": "DIURNO",
            "hora_entrada": "08:00",
            "hora_salida": "17:00",
            "descanso_minutos": 60,
            "tipo_dia": "NORMAL",
            "observacion": 'EPAYROLL_ATT_SPLIT:{"amOut":"12:00","pmIn":"13:00"}',
            "fuente": fuente,
        }

    def ensure_period_grid(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        *,
        run_id: str | None = None,
        fuente: str = "MANUAL",
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Crea filas faltantes y aplica horario default (08:00–12:00 / 13:00–17:00, 60 min almuerzo) donde aplica."""
        from datetime import timedelta

        employees = self._employees_for_grid(
            organization_id, run_id=run_id, database_url=database_url
        )
        if not employees:
            return {"created": 0, "updated": 0, "skipped": 0, "employees": 0, "facts": []}

        created = 0
        updated = 0
        skipped = 0
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                for emp in employees:
                    d = fecha_inicio
                    while d <= fecha_fin:
                        if d.weekday() == 6:
                            d += timedelta(days=1)
                            continue
                        snap = self._fetch_fact_snapshot(cur, emp.id, d)
                        if snap is not None and not self._needs_default_apply(snap):
                            skipped += 1
                        else:
                            self.upsert_fact(
                                organization_id,
                                self._default_fact_row(emp.id, d, fuente=fuente),
                                fecha_inicio=fecha_inicio,
                                fecha_fin=fecha_fin,
                                database_url=database_url,
                            )
                            if snap is None:
                                created += 1
                            else:
                                updated += 1
                        d += timedelta(days=1)

        facts = self.list_facts(
            organization_id, fecha_inicio, fecha_fin, database_url=database_url
        )
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "employees": len(employees),
            "run_id": run_id,
            "total": len(facts),
            "facts": facts,
        }

    def _employees_for_grid(
        self,
        organization_id: str,
        *,
        run_id: str | None = None,
        database_url: str | None = None,
    ) -> list[Any]:
        from epayroll.db.repositories import EmployeeRepository

        repo = EmployeeRepository()
        if not run_id:
            return repo.list_by_org(organization_id, database_url=database_url)

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pes.employee_id
                    FROM payroll_employee_summary pes
                    JOIN employees e ON e.id = pes.employee_id
                    WHERE pes.payroll_run_id = %s::uuid
                      AND e.organization_id = %s::uuid
                    ORDER BY COALESCE(e.ficha, ''), e.apellidos, e.nombres
                    """,
                    (run_id, organization_id),
                )
                ids = [str(r[0]) for r in cur.fetchall()]
        if not ids:
            return []
        all_emps = repo.list_by_org(organization_id, database_url=database_url)
        by_id = {e.id: e for e in all_emps}
        return [by_id[eid] for eid in ids if eid in by_id]

    def clear_period_values(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        *,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Borra valores de asistencia del período; conserva empleado + fecha."""
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE attendance_facts SET
                        turno = NULL,
                        hora_entrada = NULL,
                        hora_salida = NULL,
                        descanso_minutos = 0,
                        tipo_dia = 'NORMAL',
                        ausencia = false,
                        incapacidad = false,
                        vacaciones = false,
                        observacion = NULL,
                        estado_validacion = 'PENDIENTE',
                        errores_validacion = '[]'::jsonb,
                        updated_at = now()
                    WHERE organization_id = %s::uuid
                      AND fecha >= %s AND fecha <= %s
                    """,
                    (organization_id, fecha_inicio, fecha_fin),
                )
                cleared = cur.rowcount

        facts = self.list_facts(
            organization_id, fecha_inicio, fecha_fin, database_url=database_url
        )
        return {"cleared": cleared, "total": len(facts), "facts": facts}

    def mark_benefit_days(
        self,
        organization_id: str,
        employee_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        *,
        vacaciones: bool = False,
        incapacidad: bool = False,
        observacion: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Marca días de vacaciones o incapacidad en attendance_facts."""
        from datetime import timedelta

        marked = 0
        current = fecha_inicio
        while current <= fecha_fin:
            self.upsert_fact(
                organization_id,
                {
                    "employee_id": employee_id,
                    "fecha": current.isoformat(),
                    "vacaciones": vacaciones,
                    "incapacidad": incapacidad,
                    "ausencia": False,
                    "fuente": "SISTEMA",
                    "observacion": observacion,
                },
                database_url=database_url,
            )
            marked += 1
            current += timedelta(days=1)
        return {
            "days_marked": marked,
            "vacaciones": vacaciones,
            "incapacidad": incapacidad,
        }
