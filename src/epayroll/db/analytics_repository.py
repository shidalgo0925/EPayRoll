from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.analytics.config import load_analytics_config
from epayroll.analytics.dashboard import build_executive_dashboard
from epayroll.analytics.kpis import calc_absenteeism, calc_overtime, calc_turnover
from epayroll.analytics.pasivos import consolidate_pasivos, estimate_prima_total
from epayroll.analytics.projections import EmployeeProjectionInput, project_org_liquidations
from epayroll.db.connection import get_connection
from epayroll.db.vacation_repository import VacationRepository
from epayroll.engine.liquidation import run_liquidation, LiquidationInput
from epayroll.engine.rounding import RoundingMode, round_amount


class AnalyticsRepository:
    def __init__(self, vacation_repo: VacationRepository | None = None) -> None:
        self.vacation_repo = vacation_repo or VacationRepository()

    def kpis(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        data = self._fetch_kpi_inputs(organization_id, fecha_inicio, fecha_fin, database_url)
        turnover = calc_turnover(data["terminaciones"], data["plantilla_inicio"], data["plantilla_fin"])
        absenteeism = calc_absenteeism(data["dias_ausencia"], data["dias_programados"])
        overtime = calc_overtime(data["attendance_rows"], data["empleados_activos"])
        return {
            "organization_id": organization_id,
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "rotacion": {
                "terminaciones": turnover.terminaciones,
                "promedio_plantilla": str(turnover.promedio_plantilla),
                "tasa_pct": str(turnover.tasa_rotacion_pct),
            },
            "ausentismo": {
                "dias_ausencia": str(absenteeism.dias_ausencia),
                "dias_programados": str(absenteeism.dias_programados),
                "tasa_pct": str(absenteeism.tasa_ausentismo_pct),
            },
            "horas_extra": {
                "total": str(overtime.horas_extra_total),
                "promedio_por_empleado": str(overtime.horas_extra_promedio_empleado),
                "empleados_con_extras": overtime.empleados_con_extras,
            },
        }

    def pasivos(
        self,
        organization_id: str,
        fecha_corte: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        fecha_corte = fecha_corte or date.today()
        employees = self._fetch_active_employees(organization_id, database_url)
        vac_total = Decimal("0")
        for emp in employees:
            try:
                bal = self.vacation_repo.accrue_employee(
                    emp["employee_id"], fecha_corte=fecha_corte, database_url=database_url
                )
                vac_total += Decimal(bal["pasivo_estimado"])
            except ValueError:
                continue

        decimo = self._fetch_decimo_pending(organization_id, database_url)
        prima = estimate_prima_total(employees, fecha_corte)
        indemn = self._indemnizacion_contingente(employees, fecha_corte)
        pasivos = consolidate_pasivos(vac_total, decimo, prima, indemn)

        return {
            "organization_id": organization_id,
            "fecha_corte": fecha_corte.isoformat(),
            "employee_count": len(employees),
            "vacaciones": str(pasivos.vacaciones),
            "decimo_pendiente": str(pasivos.decimo_pendiente),
            "prima_antiguedad": str(pasivos.prima_antiguedad),
            "indemnizacion_contingente": str(pasivos.indemnizacion_contingente),
            "total": str(pasivos.total),
            "items": [
                {"concepto": i.concepto, "monto": str(i.monto), "detalle": i.detalle}
                for i in pasivos.items
            ],
        }

    def liquidation_projection(
        self,
        organization_id: str,
        fecha_corte: date | None = None,
        causa: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        fecha_corte = fecha_corte or date.today()
        config = load_analytics_config()
        causa = causa or config.proyeccion_liquidacion_causa_default
        employees = self._build_projection_inputs(organization_id, fecha_corte, database_url)
        return project_org_liquidations(employees, fecha_corte, causa=causa)

    def executive_dashboard(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        fecha_corte: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        fecha_corte = fecha_corte or fecha_fin
        config = load_analytics_config()

        kpi_data = self._fetch_kpi_inputs(organization_id, fecha_inicio, fecha_fin, database_url)
        turnover = calc_turnover(kpi_data["terminaciones"], kpi_data["plantilla_inicio"], kpi_data["plantilla_fin"])
        absenteeism = calc_absenteeism(kpi_data["dias_ausencia"], kpi_data["dias_programados"])
        overtime = calc_overtime(kpi_data["attendance_rows"], kpi_data["empleados_activos"])

        pasivos_raw = self.pasivos(organization_id, fecha_corte, database_url)
        pasivos = consolidate_pasivos(
            Decimal(pasivos_raw["vacaciones"]),
            Decimal(pasivos_raw["decimo_pendiente"]),
            Decimal(pasivos_raw["prima_antiguedad"]),
            Decimal(pasivos_raw["indemnizacion_contingente"]),
        )
        payroll_cost = self._fetch_payroll_cost(organization_id, fecha_inicio, fecha_fin, database_url)
        liquidation = self.liquidation_projection(
            organization_id, fecha_corte, database_url=database_url
        )

        return build_executive_dashboard(
            organization_id=organization_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            fecha_corte=fecha_corte,
            turnover=turnover,
            absenteeism=absenteeism,
            overtime=overtime,
            pasivos=pasivos,
            payroll_cost=payroll_cost,
            liquidation_projection=liquidation,
            employee_count=kpi_data["empleados_activos"],
            config=config,
        )

    def _fetch_active_employees(
        self, organization_id: str, database_url: str | None
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id, e.nombres, e.apellidos, c.fecha_inicio, c.salario_base
                    FROM employees e
                    JOIN contracts c ON c.employee_id = e.id AND c.estado = 'ACTIVO'
                    WHERE e.organization_id = %s::uuid AND e.activo = true
                    ORDER BY e.apellidos, e.nombres
                    """,
                    (organization_id,),
                )
                rows = cur.fetchall()
        return [
            {
                "employee_id": str(r[0]),
                "nombres": r[1],
                "apellidos": r[2],
                "fecha_inicio": r[3],
                "salario_mensual": Decimal(str(r[4])),
            }
            for r in rows
        ]

    def _build_projection_inputs(
        self,
        organization_id: str,
        fecha_corte: date,
        database_url: str | None,
    ) -> list[EmployeeProjectionInput]:
        employees = self._fetch_active_employees(organization_id, database_url)
        result: list[EmployeeProjectionInput] = []
        for emp in employees:
            try:
                bal = self.vacation_repo.accrue_employee(
                    emp["employee_id"], fecha_corte=fecha_corte, database_url=database_url
                )
                dias_vac = Decimal(bal["dias_pendientes"])
            except ValueError:
                dias_vac = Decimal("0")
            salarios_ytd = self._fetch_ytd_bruto(emp["employee_id"], fecha_corte, database_url)
            result.append(
                EmployeeProjectionInput(
                    employee_id=emp["employee_id"],
                    nombres=emp["nombres"],
                    apellidos=emp["apellidos"],
                    fecha_inicio=emp["fecha_inicio"],
                    salario_mensual=emp["salario_mensual"],
                    dias_vacaciones_pendientes=dias_vac,
                    salarios_acumulados_anio=salarios_ytd,
                )
            )
        return result

    def _fetch_kpi_inputs(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None,
    ) -> dict[str, Any]:
        config = load_analytics_config()
        employees = self._fetch_active_employees(organization_id, database_url)
        empleados_activos = len(employees)

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM termination_cases tc
                    JOIN employees e ON e.id = tc.employee_id
                    WHERE e.organization_id = %s::uuid
                      AND tc.fecha_terminacion BETWEEN %s AND %s
                    """,
                    (organization_id, fecha_inicio, fecha_fin),
                )
                terminaciones = int(cur.fetchone()[0])

                cur.execute(
                    """
                    SELECT COALESCE(SUM(
                        CASE
                            WHEN a.horas IS NOT NULL THEN a.horas / %s
                            ELSE 1
                        END
                    ), 0)
                    FROM absences a
                    JOIN employees e ON e.id = a.employee_id
                    WHERE e.organization_id = %s::uuid
                      AND a.fecha BETWEEN %s AND %s
                      AND a.justificada = false
                    """,
                    (Decimal(str(config.horas_jornada)), organization_id, fecha_inicio, fecha_fin),
                )
                dias_ausencia = Decimal(str(cur.fetchone()[0]))

                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(ad.horas_extra_diurna), 0),
                        COALESCE(SUM(ad.horas_extra_nocturna), 0),
                        COALESCE(SUM(ad.horas_extra_mixta_noct), 0),
                        COALESCE(SUM(ad.horas_domingo), 0),
                        COALESCE(SUM(ad.horas_feriado), 0)
                    FROM attendance_daily ad
                    JOIN employees e ON e.id = ad.employee_id
                    WHERE e.organization_id = %s::uuid
                      AND ad.fecha BETWEEN %s AND %s
                    """,
                    (organization_id, fecha_inicio, fecha_fin),
                )
                att = cur.fetchone()

        dias_programados = Decimal(str(empleados_activos * config.dias_laborables_mes))
        attendance_rows: list[dict[str, Decimal]] = []
        if att and any(att):
            attendance_rows.append(
                {
                    "horas_extra_diurna": Decimal(str(att[0])),
                    "horas_extra_nocturna": Decimal(str(att[1])),
                    "horas_extra_mixta_noct": Decimal(str(att[2])),
                    "horas_domingo": Decimal(str(att[3])),
                    "horas_feriado": Decimal(str(att[4])),
                }
            )

        return {
            "terminaciones": terminaciones,
            "plantilla_inicio": empleados_activos,
            "plantilla_fin": empleados_activos,
            "empleados_activos": empleados_activos,
            "dias_ausencia": dias_ausencia,
            "dias_programados": dias_programados,
            "attendance_rows": attendance_rows,
        }

    def _fetch_decimo_pending(self, organization_id: str, database_url: str | None) -> Decimal:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(da.monto_calculado), 0)
                    FROM decimo_accumulations da
                    JOIN employees e ON e.id = da.employee_id
                    WHERE e.organization_id = %s::uuid AND da.pagado = false
                    """,
                    (organization_id,),
                )
                return Decimal(str(cur.fetchone()[0]))

    def _fetch_ytd_bruto(
        self, employee_id: str, fecha_corte: date, database_url: str | None
    ) -> Decimal:
        inicio_anio = date(fecha_corte.year, 1, 1)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(pes.bruto), 0)
                    FROM payroll_employee_summary pes
                    JOIN payroll_runs pr ON pr.id = pes.payroll_run_id
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    WHERE pes.employee_id = %s::uuid
                      AND pp.fecha_fin >= %s
                      AND pp.fecha_fin <= %s
                      AND pp.tipo::text != 'DECIMO'
                    """,
                    (employee_id, inicio_anio, fecha_corte),
                )
                return Decimal(str(cur.fetchone()[0]))

    def _fetch_payroll_cost(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        database_url: str | None,
    ) -> dict[str, Decimal]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(pes.bruto), 0),
                        COALESCE(SUM(pes.aportes_patronales), 0),
                        COALESCE(SUM(pes.neto), 0)
                    FROM payroll_employee_summary pes
                    JOIN payroll_runs pr ON pr.id = pes.payroll_run_id
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    WHERE pp.organization_id = %s::uuid
                      AND pp.fecha_fin BETWEEN %s AND %s
                    """,
                    (organization_id, fecha_inicio, fecha_fin),
                )
                row = cur.fetchone()
        return {
            "bruto": Decimal(str(row[0])),
            "aportes_patronales": Decimal(str(row[1])),
            "neto": Decimal(str(row[2])),
        }

    def _indemnizacion_contingente(
        self,
        employees: list[dict[str, Any]],
        fecha_corte: date,
    ) -> Decimal:
        config = load_analytics_config()
        total = Decimal("0")
        for emp in employees:
            inp = LiquidationInput(
                causa=config.proyeccion_liquidacion_causa_default,
                fecha_inicio=emp["fecha_inicio"],
                fecha_terminacion=fecha_corte,
                salario_promedio_prima=emp["salario_mensual"],
                calcular_indemnizacion=True,
            )
            total += run_liquidation(inp).amount("INDEMNIZACION")
        return round_amount(total, RoundingMode.CENTESIMO)
