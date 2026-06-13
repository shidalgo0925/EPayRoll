from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.db.attendance_repository import AttendanceRepository
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
    ) -> None:
        self.payroll_repo = payroll_repo or PayrollRepository()
        self.contracts_repo = contracts_repo or ContractRepository()
        self.employees_repo = employees_repo or EmployeeRepository()
        self.attendance_repo = attendance_repo or AttendanceRepository()

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
        riesgo, tasa_css = self.payroll_repo.get_org_rates(org_id, as_of)
        config = load_config(as_of=as_of)

        mes = overrides.mes if overrides.mes is not None else period["fecha_fin"].month
        es_quincena = (
            overrides.es_quincena
            if overrides.es_quincena is not None
            else contract.forma_pago == "QUINCENAL"
        )

        att_fields: dict[str, Decimal] = {}
        if use_attendance:
            f_ini, f_fin = self.attendance_repo.get_period_dates(payroll_period_id)
            summary = self.attendance_repo.calculate_period(employee_id, f_ini, f_fin)
            att_fields = self.attendance_repo.to_payroll_input_fields(summary)

        anio = period["fecha_fin"].year
        ytd = self.payroll_repo.get_isr_ytd(employee_id, anio, before_mes=mes)

        return PayrollInput(
            salario_mensual=contract.salario_base,
            dias_trabajados=att_fields.get("dias_trabajados", overrides.dias_trabajados),
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
            tasa_riesgo_empresa=riesgo,
            tasa_prima_antiguedad_patronal=config.tasa_prima_antiguedad_patronal,
            acumulado_isr_ytd=ytd["isr_retenido"],
            acumulado_gravable_ytd=ytd["ingreso_gravable"],
            descuento_voluntario=overrides.descuento_voluntario if overrides else Decimal("0"),
        )

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
