from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.db.attendance_repository import AttendanceRepository
from epayroll.db.attendance_facts_repository import AttendanceFactsRepository
from epayroll.db.incapacity_repository import IncapacityRepository
from epayroll.db.legal_config_repository import LegalConfigRepository
from epayroll.db.config_loader import load_config
from epayroll.db.repositories import ContractRepository, EmployeeRepository, PayrollRepository
from epayroll.engine.context import PayrollInput
from epayroll.engine.decimo import DecimoInput, run_decimo


@dataclass
class PayrollRunOverrides:
    dias_trabajados: Decimal = Decimal("15")
    es_quincena: bool | None = None
    mes: int | None = None
    horas_extra_diurnas: Decimal = Decimal("0")
    horas_extra_nocturnas: Decimal = Decimal("0")
    horas_extra_mixta_nocturnas: Decimal = Decimal("0")
    horas_domingo: Decimal = Decimal("0")
    horas_feriado: Decimal = Decimal("0")
    descuento_voluntario: Decimal = Decimal("0")


class PayrollService:
    def __init__(
        self,
        payroll_repo: PayrollRepository | None = None,
        contracts_repo: ContractRepository | None = None,
        employees_repo: EmployeeRepository | None = None,
        attendance_repo: AttendanceRepository | None = None,
        incapacity_repo: IncapacityRepository | None = None,
        legal_config_repo: LegalConfigRepository | None = None,
    ) -> None:
        self.payroll_repo = payroll_repo or PayrollRepository()
        self.contracts_repo = contracts_repo or ContractRepository()
        self.employees_repo = employees_repo or EmployeeRepository()
        self.attendance_repo = attendance_repo or AttendanceRepository()
        self.attendance_facts_repo = AttendanceFactsRepository()
        self.incapacity_repo = incapacity_repo or IncapacityRepository()
        self.legal_config_repo = legal_config_repo or LegalConfigRepository()

    def build_payroll_input(
        self,
        employee_id: str,
        payroll_period_id: str,
        overrides: PayrollRunOverrides | None = None,
        use_attendance: bool = False,
    ) -> PayrollInput:
        overrides = overrides or PayrollRunOverrides()
        contract = self.contracts_repo.get_active(employee_id)
        if not contract:
            raise ValueError(f"Empleado {employee_id} sin contrato activo")

        period = self.payroll_repo.get_period(payroll_period_id)
        org_id = period["organization_id"]
        as_of = period["fecha_fin"]
        riesgo_cls, tasa_css = self.payroll_repo.get_org_rates(org_id, as_of)
        org_rates = self.legal_config_repo.resolve_rates_for_payroll(org_id, as_of)
        tasa_css = org_rates.get("tasa_css_patronal", tasa_css)
        riesgo = org_rates.get("tasa_riesgo_empresa", riesgo_cls)
        config = load_config(as_of=as_of)

        mes = overrides.mes if overrides.mes is not None else period["fecha_fin"].month
        es_quincena = (
            overrides.es_quincena
            if overrides.es_quincena is not None
            else contract.forma_pago == "QUINCENAL"
        )

        att_fields: dict[str, Decimal] = {}
        att_meta: dict[str, Any] = {}
        incapacity_meta: dict[str, Any] | None = None
        f_ini = period["fecha_inicio"]
        f_fin = period["fecha_fin"]
        if use_attendance:
            att = self.attendance_facts_repo.summarize_employee_for_payroll(
                org_id,
                employee_id,
                f_ini,
                f_fin,
                es_quincena=es_quincena,
            )
            att_fields = {
                "dias_trabajados": att["dias_trabajados"],
                "horas_extra_diurnas": att["horas_extra_diurnas"],
                "horas_extra_nocturnas": att["horas_extra_nocturnas"],
                "horas_extra_mixta_nocturnas": att["horas_extra_mixta_nocturnas"],
                "horas_domingo": att["horas_domingo"],
                "horas_feriado": att["horas_feriado"],
            }
            att_meta = {
                "ausencias": att["ausencias"],
                "vacaciones": att["vacaciones"],
                "descuento_minutos": att.get("descuento_minutos", 0),
            }

        inc_impact = self.incapacity_repo.calculate_period_impact(
            employee_id, f_ini, f_fin, contract.salario_base
        )
        if inc_impact["dias_incapacidad"] > 0:
            incapacity_meta = inc_impact

        dias_base = att_fields.get("dias_trabajados", overrides.dias_trabajados)
        dias_ajustados = max(Decimal("0"), dias_base - Decimal(str(inc_impact["dias_incapacidad"])))

        anio = period["fecha_fin"].year
        ytd = self.payroll_repo.get_isr_ytd(employee_id, anio, before_mes=mes)

        inp = PayrollInput(
            salario_mensual=contract.salario_base,
            dias_trabajados=dias_ajustados,
            es_quincena=es_quincena,
            mes=mes,
            tipo_contrato=contract.contract_type_codigo,
            horas_extra_diurnas=att_fields.get("horas_extra_diurnas", overrides.horas_extra_diurnas),
            horas_extra_nocturnas=att_fields.get(
                "horas_extra_nocturnas", overrides.horas_extra_nocturnas
            ),
            horas_extra_mixta_nocturnas=att_fields.get(
                "horas_extra_mixta_nocturnas", overrides.horas_extra_mixta_nocturnas
            ),
            horas_domingo=att_fields.get("horas_domingo", overrides.horas_domingo),
            horas_feriado=att_fields.get("horas_feriado", overrides.horas_feriado),
            tasa_css_patronal=tasa_css,
            tasa_css_empleado=org_rates["tasa_css_empleado"],
            tasa_se_empleado=org_rates["tasa_se_empleado"],
            tasa_se_patronal=org_rates["tasa_se_patronal"],
            tasa_riesgo_empresa=riesgo,
            tasa_prima_antiguedad_patronal=config.tasa_prima_antiguedad_patronal,
            acumulado_isr_ytd=ytd["isr_retenido"],
            acumulado_gravable_ytd=ytd["ingreso_gravable"],
            descuento_voluntario=overrides.descuento_voluntario if overrides else Decimal("0"),
        )
        if incapacity_meta is not None:
            inp.metadata["incapacity"] = incapacity_meta
        if att_meta:
            inp.metadata["attendance"] = att_meta
        return inp

    def run_period(
        self,
        payroll_period_id: str,
        employee_ids: list[str] | None = None,
        use_attendance: bool = False,
        overrides: PayrollRunOverrides | None = None,
    ) -> dict[str, Any]:
        period = self.payroll_repo.get_period(payroll_period_id)
        org_id = period["organization_id"]

        if employee_ids:
            targets = employee_ids
        else:
            targets = [e.id for e in self.employees_repo.list_by_org(org_id)]

        if not targets:
            raise ValueError("No hay empleados activos para procesar")

        if use_attendance:
            f_ini = period["fecha_inicio"]
            f_fin = period["fecha_fin"]
            proc = self.attendance_facts_repo.process_period_to_daily(org_id, f_ini, f_fin)
            if not proc.get("employee_count") and proc.get("validation", {}).get("validos", 0) == 0:
                raise ValueError(
                    "Sin hechos de asistencia válidos para el período. "
                    "Importe CSV/API o cargue manualmente antes de correr planilla."
                )

        inputs: list[tuple[str, PayrollInput]] = []
        for emp_id in targets:
            inputs.append(
                (
                    emp_id,
                    self.build_payroll_input(
                        emp_id, payroll_period_id, overrides=overrides, use_attendance=use_attendance
                    ),
                )
            )

        return self.payroll_repo.run_batch(
            payroll_period_id=payroll_period_id,
            employees=inputs,
            record_decimo_accumulation=period["tipo"] != "DECIMO",
        )

    def run_decimo(
        self,
        payroll_period_id: str,
        employee_id: str,
        salarios_cotizables: Decimal | None = None,
        trimestre: int | None = None,
        anio: int | None = None,
    ) -> dict[str, Any]:
        period = self.payroll_repo.get_period(payroll_period_id)
        if salarios_cotizables is None:
            if trimestre is None or anio is None:
                raise ValueError("Indique salarios_cotizables o trimestre+anio")
            acc = self.payroll_repo.get_decimo_accumulation(employee_id, anio, trimestre)
            if not acc:
                raise ValueError("Sin acumulado de décimo para el trimestre indicado")
            salarios_cotizables = acc["salarios_sumados"]

        config = load_config(as_of=period["fecha_fin"])
        tasa = self.payroll_repo.get_decimo_css_rate(as_of=period["fecha_fin"])
        result = run_decimo(DecimoInput(salarios_cotizables=salarios_cotizables, tasa_css_decimo=tasa))

        persisted = self.payroll_repo.run_batch(
            payroll_period_id=payroll_period_id,
            employees=[(employee_id, result)],
            is_decimo=True,
            record_decimo_accumulation=False,
        )

        if trimestre is not None and anio is not None:
            self.payroll_repo.mark_decimo_paid(employee_id, anio, trimestre, period["fecha_pago"])

        return persisted

    def close_period(
        self,
        payroll_period_id: str,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        return self.payroll_repo.close_period(
            payroll_period_id=payroll_period_id,
            run_id=run_id,
        )
