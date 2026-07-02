from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.engine.context import PayrollInput
from epayroll.engine.deductions import validate_art161
from epayroll.engine.orchestrator import LineResult, PayrollEngine, PayrollResult

from epayroll.compliance.minimum_wage import validate_salary_base
from epayroll.db.config_loader import load_config
from .connection import get_connection


@dataclass
class EmployeeRecord:
    id: str
    organization_id: str
    cedula: str
    nombres: str
    apellidos: str
    activo: bool
    email: str | None = None
    ficha: str | None = None
    telefono: str | None = None
    fecha_nacimiento: date | None = None
    estado_civil: str | None = None
    direccion: str | None = None
    salario_base: Decimal | None = None
    forma_pago: str | None = None
    fecha_inicio_contrato: date | None = None
    contract_type_codigo: str | None = None
    banco: str | None = None
    cuenta_bancaria: str | None = None


_EMP_SELECT = """
    e.id, e.organization_id, e.cedula, e.nombres, e.apellidos, e.activo,
    e.email, e.ficha, e.telefono, e.fecha_nacimiento, e.estado_civil, e.direccion,
    c.salario_base, c.forma_pago::text, c.fecha_inicio, ct.codigo,
    ba.banco, ba.numero_cuenta
"""

_EMP_JOINS = """
    FROM employees e
    LEFT JOIN LATERAL (
        SELECT salario_base, forma_pago, fecha_inicio, contract_type_id
        FROM contracts
        WHERE employee_id = e.id AND estado = 'ACTIVO'
        ORDER BY fecha_inicio DESC LIMIT 1
    ) c ON true
    LEFT JOIN contract_types ct ON ct.id = c.contract_type_id
    LEFT JOIN LATERAL (
        SELECT banco, numero_cuenta FROM employee_bank_accounts
        WHERE employee_id = e.id AND activo = true
        ORDER BY created_at DESC LIMIT 1
    ) ba ON true
"""


@dataclass
class ContractRecord:
    id: str
    employee_id: str
    contract_type_codigo: str
    salario_base: Decimal
    forma_pago: str
    estado: str


class EmployeeRepository:
    def create(
        self,
        organization_id: str,
        cedula: str,
        nombres: str,
        apellidos: str,
        email: str | None = None,
        ficha: str | None = None,
        telefono: str | None = None,
        fecha_nacimiento: date | None = None,
        estado_civil: str | None = None,
        direccion: str | None = None,
        database_url: str | None = None,
    ) -> EmployeeRecord:
        emp_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO employees (
                        id, organization_id, cedula, nombres, apellidos, email,
                        ficha, telefono, fecha_nacimiento, estado_civil, direccion
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        emp_id,
                        organization_id,
                        cedula,
                        nombres,
                        apellidos,
                        email,
                        ficha,
                        telefono,
                        fecha_nacimiento,
                        estado_civil,
                        direccion,
                    ),
                )
                emp_id = str(cur.fetchone()[0])
        return self.get_by_id(emp_id, database_url=database_url)  # type: ignore[return-value]

    @staticmethod
    def _row_to_record(row) -> EmployeeRecord:
        return EmployeeRecord(
            id=str(row[0]),
            organization_id=str(row[1]),
            cedula=row[2],
            nombres=row[3],
            apellidos=row[4],
            activo=row[5],
            email=row[6],
            ficha=row[7],
            telefono=row[8],
            fecha_nacimiento=row[9],
            estado_civil=row[10],
            direccion=row[11],
            salario_base=Decimal(str(row[12])) if row[12] is not None else None,
            forma_pago=row[13],
            fecha_inicio_contrato=row[14],
            contract_type_codigo=row[15],
            banco=row[16],
            cuenta_bancaria=row[17],
        )

    def list_by_org(self, organization_id: str, database_url: str | None = None) -> list[EmployeeRecord]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_EMP_SELECT}
                    {_EMP_JOINS}
                    WHERE e.organization_id = %s::uuid AND e.activo = true
                    ORDER BY COALESCE(e.ficha, ''), e.apellidos, e.nombres
                    """,
                    (organization_id,),
                )
                return [self._row_to_record(r) for r in cur.fetchall()]

    def get_by_id(self, employee_id: str, database_url: str | None = None) -> EmployeeRecord | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_EMP_SELECT}
                    {_EMP_JOINS}
                    WHERE e.id = %s::uuid
                    """,
                    (employee_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return self._row_to_record(row)

    def update(
        self,
        employee_id: str,
        *,
        cedula: str | None = None,
        nombres: str | None = None,
        apellidos: str | None = None,
        email: str | None = None,
        ficha: str | None = None,
        telefono: str | None = None,
        fecha_nacimiento: date | None = None,
        estado_civil: str | None = None,
        direccion: str | None = None,
        database_url: str | None = None,
    ) -> EmployeeRecord:
        fields: list[str] = []
        values: list[Any] = []
        if cedula is not None:
            fields.append("cedula = %s")
            values.append(cedula)
        if nombres is not None:
            fields.append("nombres = %s")
            values.append(nombres)
        if apellidos is not None:
            fields.append("apellidos = %s")
            values.append(apellidos)
        if email is not None:
            fields.append("email = %s")
            values.append(email or None)
        if ficha is not None:
            fields.append("ficha = %s")
            values.append(ficha or None)
        if telefono is not None:
            fields.append("telefono = %s")
            values.append(telefono or None)
        if fecha_nacimiento is not None:
            fields.append("fecha_nacimiento = %s")
            values.append(fecha_nacimiento)
        if estado_civil is not None:
            fields.append("estado_civil = %s")
            values.append(estado_civil or None)
        if direccion is not None:
            fields.append("direccion = %s")
            values.append(direccion or None)
        if not fields:
            raise ValueError("Sin campos para actualizar")
        values.append(employee_id)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE employees SET {", ".join(fields)}
                    WHERE id = %s::uuid AND activo = true
                    RETURNING id
                    """,
                    values,
                )
                if not cur.fetchone():
                    raise ValueError("Empleado no encontrado")
        return self.get_by_id(employee_id, database_url=database_url)  # type: ignore[return-value]

    def deactivate(self, employee_id: str, database_url: str | None = None) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE employees SET activo = false WHERE id = %s::uuid AND activo = true",
                    (employee_id,),
                )
                if cur.rowcount == 0:
                    raise ValueError("Empleado no encontrado")

    def clone_from_organization(
        self,
        source_organization_id: str,
        target_organization_id: str,
        *,
        contracts_repo: ContractRepository | None = None,
        integration_repo: Any | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Copia empleados activos de una empresa a otra (solo maestro, sin planilla/asistencia)."""
        if source_organization_id == target_organization_id:
            raise ValueError("Origen y destino deben ser empresas distintas")

        contracts_repo = contracts_repo or ContractRepository()
        source_rows = self.list_by_org(source_organization_id, database_url=database_url)
        cloned: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for emp in source_rows:
            if self._cedula_exists_in_org(target_organization_id, emp.cedula, database_url=database_url):
                skipped.append(
                    {
                        "source_employee_id": emp.id,
                        "cedula": emp.cedula,
                        "nombres": emp.nombres,
                        "apellidos": emp.apellidos,
                        "reason": "cedula_duplicada",
                    }
                )
                continue

            new_emp = self.create(
                organization_id=target_organization_id,
                cedula=emp.cedula,
                nombres=emp.nombres,
                apellidos=emp.apellidos,
                email=emp.email,
                ficha=emp.ficha,
                telefono=emp.telefono,
                fecha_nacimiento=emp.fecha_nacimiento,
                estado_civil=emp.estado_civil,
                direccion=emp.direccion,
                database_url=database_url,
            )

            # Contrato activo del origen (salario, tipo, forma de pago).
            if emp.salario_base is not None and emp.fecha_inicio_contrato is not None:
                contracts_repo.create(
                    new_emp.id,
                    emp.contract_type_codigo or "INDEFINIDO",
                    emp.salario_base,
                    emp.fecha_inicio_contrato,
                    forma_pago=emp.forma_pago or "QUINCENAL",
                    database_url=database_url,
                )

            # Cuenta bancaria principal, si existe.
            if integration_repo and emp.banco and emp.cuenta_bancaria:
                integration_repo.upsert_bank_account(
                    new_emp.id,
                    emp.banco,
                    emp.cuenta_bancaria,
                    database_url=database_url,
                )

            cloned.append(
                {
                    "source_employee_id": emp.id,
                    "new_employee_id": new_emp.id,
                    "cedula": emp.cedula,
                    "nombres": emp.nombres,
                    "apellidos": emp.apellidos,
                }
            )

        return {
            "source_organization_id": source_organization_id,
            "target_organization_id": target_organization_id,
            "cloned_count": len(cloned),
            "skipped_count": len(skipped),
            "cloned": cloned,
            "skipped": skipped,
        }

    def _cedula_exists_in_org(
        self,
        organization_id: str,
        cedula: str,
        database_url: str | None = None,
    ) -> bool:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM employees
                    WHERE organization_id = %s::uuid AND cedula = %s AND activo = true
                    LIMIT 1
                    """,
                    (organization_id, cedula),
                )
                return cur.fetchone() is not None


class ContractRepository:
    def create(
        self,
        employee_id: str,
        contract_type_codigo: str,
        salario_base: Decimal,
        fecha_inicio: date,
        forma_pago: str = "QUINCENAL",
        categoria_salario_minimo: str | None = None,
        database_url: str | None = None,
    ) -> ContractRecord:
        validate_salary_base(salario_base, categoria_salario_minimo, fecha_inicio)
        contract_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM contract_types WHERE codigo = %s AND activo = true LIMIT 1",
                    (contract_type_codigo,),
                )
                ct = cur.fetchone()
                if not ct:
                    raise ValueError(f"Tipo contrato no encontrado: {contract_type_codigo}")
                cur.execute(
                    """
                    INSERT INTO contracts (id, employee_id, contract_type_id, fecha_inicio, salario_base, forma_pago, estado)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::payment_frequency, 'ACTIVO')
                    RETURNING id, employee_id
                    """,
                    (contract_id, employee_id, ct[0], fecha_inicio, salario_base, forma_pago),
                )
                row = cur.fetchone()
        return ContractRecord(
            id=str(row[0]),
            employee_id=str(row[1]),
            contract_type_codigo=contract_type_codigo,
            salario_base=salario_base,
            forma_pago=forma_pago,
            estado="ACTIVO",
        )

    def get_active(self, employee_id: str, database_url: str | None = None) -> ContractRecord | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id, c.employee_id, ct.codigo, c.salario_base, c.forma_pago::text, c.estado::text
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
                return ContractRecord(str(row[0]), str(row[1]), row[2], row[3], row[4], row[5])

    def upsert_active(
        self,
        employee_id: str,
        contract_type_codigo: str,
        salario_base: Decimal,
        fecha_inicio: date,
        forma_pago: str = "QUINCENAL",
        categoria_salario_minimo: str | None = None,
        database_url: str | None = None,
    ) -> ContractRecord:
        """Crea o actualiza el contrato activo del empleado."""
        validate_salary_base(salario_base, categoria_salario_minimo, fecha_inicio)
        existing = self.get_active(employee_id, database_url=database_url)
        if existing:
            with get_connection(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE contracts
                        SET salario_base = %s,
                            forma_pago = %s::payment_frequency,
                            fecha_inicio = %s,
                            updated_at = now()
                        WHERE id = %s::uuid
                        """,
                        (salario_base, forma_pago, fecha_inicio, existing.id),
                    )
            return ContractRecord(
                existing.id,
                employee_id,
                existing.contract_type_codigo,
                salario_base,
                forma_pago,
                "ACTIVO",
            )
        return self.create(
            employee_id,
            contract_type_codigo,
            salario_base,
            fecha_inicio,
            forma_pago=forma_pago,
            categoria_salario_minimo=categoria_salario_minimo,
            database_url=database_url,
        )


class PayrollRepository:
    def create_period(
        self,
        organization_id: str,
        fecha_inicio: date,
        fecha_fin: date,
        fecha_pago: date,
        tipo: str = "QUINCENAL",
        database_url: str | None = None,
    ) -> str:
        period_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_periods (id, organization_id, tipo, fecha_inicio, fecha_fin, fecha_pago, estado)
                    VALUES (%s::uuid, %s::uuid, %s::payroll_period_type, %s, %s, %s, 'BORRADOR')
                    RETURNING id
                    """,
                    (period_id, organization_id, tipo, fecha_inicio, fecha_fin, fecha_pago),
                )
                return str(cur.fetchone()[0])

    def get_org_rates(self, organization_id: str, as_of: date, database_url: str | None = None) -> tuple[Decimal, Decimal]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT porcentaje_riesgo FROM organization_risk_classification
                    WHERE organization_id = %s::uuid
                      AND vigencia_desde <= %s
                      AND (vigencia_hasta IS NULL OR vigencia_hasta >= %s)
                    ORDER BY vigencia_desde DESC LIMIT 1
                    """,
                    (organization_id, as_of, as_of),
                )
                row = cur.fetchone()
                riesgo = Decimal(str(row[0])) if row else Decimal("0.0098")
        config = load_config(as_of=as_of, database_url=database_url)
        return riesgo, config.tasa_css_patronal

    def get_period(self, payroll_period_id: str, database_url: str | None = None) -> dict[str, Any]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, organization_id, tipo::text, fecha_inicio, fecha_fin, fecha_pago, estado::text
                    FROM payroll_periods WHERE id = %s::uuid
                    """,
                    (payroll_period_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Período no encontrado: {payroll_period_id}")
        return {
            "id": str(row[0]),
            "organization_id": str(row[1]),
            "tipo": row[2],
            "fecha_inicio": row[3],
            "fecha_fin": row[4],
            "fecha_pago": row[5],
            "estado": row[6],
        }

    def list_periods(
        self,
        organization_id: str,
        limit: int = 30,
        database_url: str | None = None,
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tipo::text, fecha_inicio, fecha_fin, fecha_pago, estado::text
                    FROM payroll_periods
                    WHERE organization_id = %s::uuid
                    ORDER BY fecha_inicio DESC
                    LIMIT %s
                    """,
                    (organization_id, limit),
                )
                rows = cur.fetchall()
        return [
            {
                "id": str(r[0]),
                "tipo": r[1],
                "fecha_inicio": r[2].isoformat(),
                "fecha_fin": r[3].isoformat(),
                "fecha_pago": r[4].isoformat(),
                "estado": r[5],
            }
            for r in rows
        ]

    def get_latest_run_id(self, payroll_period_id: str, database_url: str | None = None) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM payroll_runs
                    WHERE payroll_period_id = %s::uuid
                    ORDER BY fecha_ejecucion DESC
                    LIMIT 1
                    """,
                    (payroll_period_id,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None

    def set_period_status(
        self,
        payroll_period_id: str,
        estado: str,
        database_url: str | None = None,
    ) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE payroll_periods SET estado = %s::payroll_period_status WHERE id = %s::uuid",
                    (estado, payroll_period_id),
                )

    def update_period(
        self,
        payroll_period_id: str,
        *,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        fecha_pago: date | None = None,
        tipo: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        period = self.get_period(payroll_period_id, database_url=database_url)
        if period["estado"] != "BORRADOR":
            raise ValueError("Solo se pueden editar períodos en estado BORRADOR")

        fields: list[str] = []
        params: list[Any] = []
        if fecha_inicio is not None:
            fields.append("fecha_inicio = %s")
            params.append(fecha_inicio)
        if fecha_fin is not None:
            fields.append("fecha_fin = %s")
            params.append(fecha_fin)
        if fecha_pago is not None:
            fields.append("fecha_pago = %s")
            params.append(fecha_pago)
        if tipo is not None:
            fields.append("tipo = %s::payroll_period_type")
            params.append(tipo)
        if not fields:
            return period

        params.append(payroll_period_id)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE payroll_periods SET {', '.join(fields)} WHERE id = %s::uuid",
                    params,
                )
        return self.get_period(payroll_period_id, database_url=database_url)

    def delete_period(self, payroll_period_id: str, database_url: str | None = None) -> None:
        self.get_period(payroll_period_id, database_url=database_url)
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM sipe_exports
                    WHERE payroll_run_id IN (
                        SELECT id FROM payroll_runs WHERE payroll_period_id = %s::uuid
                    )
                    """,
                    (payroll_period_id,),
                )
                cur.execute(
                    """
                    DELETE FROM dgi_exports
                    WHERE payroll_run_id IN (
                        SELECT id FROM payroll_runs WHERE payroll_period_id = %s::uuid
                    )
                    """,
                    (payroll_period_id,),
                )
                cur.execute(
                    """
                    DELETE FROM bank_exports
                    WHERE payroll_run_id IN (
                        SELECT id FROM payroll_runs WHERE payroll_period_id = %s::uuid
                    )
                    """,
                    (payroll_period_id,),
                )
                cur.execute(
                    "DELETE FROM payroll_runs WHERE payroll_period_id = %s::uuid",
                    (payroll_period_id,),
                )
                cur.execute(
                    "DELETE FROM payroll_periods WHERE id = %s::uuid",
                    (payroll_period_id,),
                )

    def close_period(
        self,
        payroll_period_id: str,
        run_id: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        from epayroll.db.payslip_repository import PayslipRepository

        period = self.get_period(payroll_period_id, database_url=database_url)
        if period["estado"] != "CALCULADO":
            raise ValueError(
                f"El periodo debe estar en CALCULADO para cerrar (actual: {period['estado']})"
            )

        from datetime import date

        org_id = period["organization_id"]
        emp_repo = EmployeeRepository()
        contract_repo = ContractRepository()
        for emp in emp_repo.list_by_org(org_id, database_url=database_url):
            contract = contract_repo.get_active(emp.id, database_url=database_url)
            if contract:
                validate_salary_base(contract.salario_base, None, date.today())

        resolved_run = run_id or self.get_latest_run_id(payroll_period_id, database_url=database_url)
        if not resolved_run:
            raise ValueError("No hay corrida de planilla para este periodo")

        payslip_repo = PayslipRepository()
        payslips = payslip_repo.generate_all_for_run(resolved_run, database_url=database_url)
        self._persist_period_close_snapshot(
            payroll_period_id, resolved_run, org_id, period, database_url=database_url
        )
        self.set_period_status(payroll_period_id, "CERRADO", database_url=database_url)

        return {
            "payroll_period_id": payroll_period_id,
            "run_id": resolved_run,
            "estado": "CERRADO",
            "payslips_generated": len(payslips),
            "payslips": payslips,
            "acumulados_guardados": True,
        }

    def _persist_period_close_snapshot(
        self,
        payroll_period_id: str,
        run_id: str,
        org_id: str,
        period: dict[str, Any],
        database_url: str | None = None,
    ) -> None:
        """Congela la corrida oficial y guarda histórico por empleado (liquidación, ISR, décimo)."""
        as_of = period["fecha_fin"]
        anio = as_of.year
        mes = as_of.month
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE payroll_periods
                    SET cerrado_run_id = %s::uuid, cerrado_at = now()
                    WHERE id = %s::uuid
                    """,
                    (run_id, payroll_period_id),
                )
                cur.execute(
                    """
                    INSERT INTO employee_payroll_acumulado (
                        organization_id, employee_id, payroll_period_id, payroll_run_id,
                        anio, mes, bruto, neto, dias_trabajados, dias_ausencia,
                        dias_vacaciones, monto_desc_ausencia, isr_retenido, css_empleado,
                        ingreso_gravable
                    )
                    SELECT
                        %s::uuid,
                        pes.employee_id,
                        %s::uuid,
                        %s::uuid,
                        %s,
                        %s,
                        pes.bruto,
                        pes.neto,
                        COALESCE(adj.dias_trabajados, 15),
                        COALESCE(
                            (SELECT COUNT(*)::int FROM attendance_facts af
                             WHERE af.employee_id = pes.employee_id
                               AND af.fecha >= %s AND af.fecha <= %s
                               AND af.ausencia = true), 0
                        ),
                        COALESCE(
                            (SELECT COUNT(*)::int FROM attendance_facts af
                             WHERE af.employee_id = pes.employee_id
                               AND af.fecha >= %s AND af.fecha <= %s
                               AND af.vacaciones = true), 0
                        ),
                        COALESCE(adj.monto_desc_dias, 0),
                        COALESCE((
                            SELECT pl.monto FROM payroll_lines pl
                            JOIN payroll_concepts pc ON pc.id = pl.concept_id
                            WHERE pl.payroll_run_id = pes.payroll_run_id
                              AND pl.employee_id = pes.employee_id
                              AND pc.codigo = 'ISR'
                            LIMIT 1
                        ), 0),
                        COALESCE((
                            SELECT pl.monto FROM payroll_lines pl
                            JOIN payroll_concepts pc ON pc.id = pl.concept_id
                            WHERE pl.payroll_run_id = pes.payroll_run_id
                              AND pl.employee_id = pes.employee_id
                              AND pc.codigo = 'CSS_EMPLEADO'
                            LIMIT 1
                        ), 0),
                        pes.bruto
                    FROM payroll_employee_summary pes
                    LEFT JOIN payroll_run_adjustments adj
                        ON adj.payroll_run_id = pes.payroll_run_id
                       AND adj.employee_id = pes.employee_id
                    WHERE pes.payroll_run_id = %s::uuid
                    ON CONFLICT (payroll_period_id, employee_id) DO UPDATE SET
                        payroll_run_id = EXCLUDED.payroll_run_id,
                        bruto = EXCLUDED.bruto,
                        neto = EXCLUDED.neto,
                        dias_trabajados = EXCLUDED.dias_trabajados,
                        dias_ausencia = EXCLUDED.dias_ausencia,
                        dias_vacaciones = EXCLUDED.dias_vacaciones,
                        monto_desc_ausencia = EXCLUDED.monto_desc_ausencia,
                        isr_retenido = EXCLUDED.isr_retenido,
                        css_empleado = EXCLUDED.css_empleado,
                        ingreso_gravable = EXCLUDED.ingreso_gravable
                    """,
                    (
                        org_id,
                        payroll_period_id,
                        run_id,
                        anio,
                        mes,
                        period["fecha_inicio"],
                        period["fecha_fin"],
                        period["fecha_inicio"],
                        period["fecha_fin"],
                        run_id,
                    ),
                )

    def get_isr_ytd(
        self,
        employee_id: str,
        anio: int,
        before_mes: int,
        database_url: str | None = None,
    ) -> dict[str, Decimal]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(ingreso_gravable), 0), COALESCE(SUM(isr_retenido), 0)
                    FROM employee_isr_ytd
                    WHERE employee_id = %s::uuid AND anio = %s AND mes < %s
                    """,
                    (employee_id, anio, before_mes),
                )
                row = cur.fetchone()
        return {
            "ingreso_gravable": Decimal(str(row[0])),
            "isr_retenido": Decimal(str(row[1])),
        }

    def get_decimo_accumulation(
        self,
        employee_id: str,
        anio: int,
        trimestre: int,
        database_url: str | None = None,
    ) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT salarios_sumados, monto_calculado, pagado
                    FROM decimo_accumulations
                    WHERE employee_id = %s::uuid AND anio = %s AND trimestre = %s
                    """,
                    (employee_id, anio, trimestre),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "salarios_sumados": Decimal(str(row[0])),
            "monto_calculado": Decimal(str(row[1])),
            "pagado": row[2],
        }

    def get_decimo_css_rate(self, as_of: date, database_url: str | None = None) -> Decimal:
        try:
            with get_connection(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT tasa_css_decimo FROM decimo_config
                        WHERE vigencia_desde <= %s AND (vigencia_hasta IS NULL OR vigencia_hasta >= %s)
                        ORDER BY vigencia_desde DESC LIMIT 1
                        """,
                        (as_of, as_of),
                    )
                    row = cur.fetchone()
                    if row:
                        return Decimal(str(row[0]))
        except Exception:
            pass
        return Decimal("0.0725")

    def mark_decimo_paid(
        self,
        employee_id: str,
        anio: int,
        trimestre: int,
        fecha_pago: date,
        database_url: str | None = None,
    ) -> None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE decimo_accumulations
                    SET pagado = true, fecha_pago = %s, monto_calculado = salarios_sumados / 12
                    WHERE employee_id = %s::uuid AND anio = %s AND trimestre = %s
                    """,
                    (fecha_pago, employee_id, anio, trimestre),
                )

    def run_and_persist(
        self,
        payroll_period_id: str,
        employee_id: str,
        payroll_input: PayrollInput,
        ejecutado_por: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        batch = self.run_batch(
            payroll_period_id=payroll_period_id,
            employees=[(employee_id, payroll_input)],
            ejecutado_por=ejecutado_por,
            database_url=database_url,
        )
        emp = batch["employees"][0]
        return {
            "run_id": batch["run_id"],
            "bruto": emp["bruto"],
            "deducciones": emp["deducciones"],
            "neto": emp["neto"],
            "aportes_patronales": emp["aportes_patronales"],
            "lines": emp["lines"],
        }

    def run_batch(
        self,
        payroll_period_id: str,
        employees: list[tuple[str, PayrollInput | PayrollResult]],
        ejecutado_por: str | None = None,
        is_decimo: bool = False,
        record_decimo_accumulation: bool = True,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        period = self.get_period(payroll_period_id, database_url=database_url)
        as_of = period["fecha_fin"]
        config = load_config(as_of=as_of, database_url=database_url)
        engine = PayrollEngine(config=config)

        run_id = str(uuid.uuid4())
        employee_results: list[dict[str, Any]] = []
        totals = {
            "bruto": Decimal("0"),
            "deducciones": Decimal("0"),
            "neto": Decimal("0"),
            "aportes_patronales": Decimal("0"),
        }

        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_runs (id, payroll_period_id, ejecutado_por, version_motor, config_snapshot, estado)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, 'COMPLETADO')
                    """,
                    (
                        run_id,
                        payroll_period_id,
                        ejecutado_por,
                        PayrollEngine.VERSION,
                        json.dumps({"tipo_corrida": "DECIMO" if is_decimo else "ORDINARIA"}),
                    ),
                )
                concept_map = self._concept_id_map(cur)

                for employee_id, payload in employees:
                    if isinstance(payload, PayrollResult):
                        result = payload
                        payroll_inp = None
                    else:
                        result = engine.run(payload)
                        monto_desc_tiempo = self._upsert_run_adjustment(
                            cur, run_id, employee_id, payload
                        )
                        result = self._apply_attendance_time_discount(result, monto_desc_tiempo)
                        result = self._apply_voluntary_and_validate(result, payload)
                        if not is_decimo:
                            self._upsert_isr_ytd(cur, employee_id, payload, result, as_of)

                    self._persist_employee_lines(cur, run_id, employee_id, result, concept_map)

                    if record_decimo_accumulation and not is_decimo:
                        self._accumulate_decimo(cur, employee_id, as_of, result.bruto)

                    emp_summary = {
                        "employee_id": employee_id,
                        "bruto": str(result.bruto),
                        "deducciones": str(result.deducciones),
                        "neto": str(result.neto),
                        "aportes_patronales": str(result.aportes_patronales),
                        "lines": [
                            {"concepto": l.codigo_concepto, "tipo": l.tipo, "monto": str(l.monto)}
                            for l in result.lines
                        ],
                    }
                    employee_results.append(emp_summary)
                    totals["bruto"] += result.bruto
                    totals["deducciones"] += result.deducciones
                    totals["neto"] += result.neto
                    totals["aportes_patronales"] += result.aportes_patronales

                cur.execute(
                    "UPDATE payroll_periods SET estado = 'CALCULADO' WHERE id = %s::uuid",
                    (payroll_period_id,),
                )

        return {
            "run_id": run_id,
            "payroll_period_id": payroll_period_id,
            "employee_count": len(employee_results),
            "employees": employee_results,
            "totales": {k: str(v) for k, v in totals.items()},
        }

    def _apply_voluntary_and_validate(
        self, result: PayrollResult, payroll_input: PayrollInput
    ) -> PayrollResult:
        if payroll_input.descuento_voluntario > 0:
            result.lines.append(
                LineResult(
                    codigo_concepto="DESCUENTO_VOLUNTARIO",
                    tipo="DESCUENTO",
                    monto=payroll_input.descuento_voluntario,
                    prioridad=9,
                    referencia_legal="Art. 161 CT",
                )
            )
        deductions = {l.codigo_concepto: l.monto for l in result.lines if l.tipo == "DESCUENTO"}
        validation = validate_art161(result.bruto, deductions)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))
        return result

    def _upsert_run_adjustment(
        self,
        cur,
        run_id: str,
        employee_id: str,
        payroll_input: PayrollInput,
    ) -> Decimal:
        from epayroll.attendance.payroll_descuento import monto_descuento_tiempo
        from epayroll.engine.rounding import RoundingMode, round_amount

        att = payroll_input.metadata.get("attendance") or {}
        aus = int(att.get("ausencias", 0))
        vac = int(att.get("vacaciones", 0))
        dias_desc = aus + vac
        desc_min = int(att.get("descuento_minutos", 0))
        sal_diario = payroll_input.salario_mensual / payroll_input.dias_mes
        monto_desc_dias = (
            round_amount(sal_diario * Decimal(dias_desc), RoundingMode.CENTESIMO)
            if dias_desc
            else Decimal("0")
        )
        monto_desc_tiempo = monto_descuento_tiempo(payroll_input.salario_mensual, desc_min)
        cur.execute(
            """
            INSERT INTO payroll_run_adjustments (
                payroll_run_id, employee_id, dias_trabajados, dias_descuento,
                monto_desc_dias, descuento_minutos, monto_desc_tiempo,
                dev_isr, prestamo_empleado, desc_prestamo,
                descuento_banco, saldo_prestamo
            ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, 0, 0, 0, 0, 0)
            ON CONFLICT (payroll_run_id, employee_id) DO UPDATE SET
                dias_trabajados = EXCLUDED.dias_trabajados,
                dias_descuento = EXCLUDED.dias_descuento,
                monto_desc_dias = EXCLUDED.monto_desc_dias,
                descuento_minutos = EXCLUDED.descuento_minutos,
                monto_desc_tiempo = EXCLUDED.monto_desc_tiempo,
                updated_at = now()
            """,
            (
                run_id,
                employee_id,
                payroll_input.dias_trabajados,
                dias_desc,
                monto_desc_dias,
                desc_min,
                monto_desc_tiempo,
            ),
        )
        return monto_desc_tiempo

    def _apply_attendance_time_discount(
        self, result: PayrollResult, monto_desc_tiempo: Decimal
    ) -> PayrollResult:
        if monto_desc_tiempo <= 0:
            return result
        result.lines.append(
            LineResult(
                codigo_concepto="DESCUENTO_ASISTENCIA",
                tipo="DESCUENTO",
                monto=monto_desc_tiempo,
                prioridad=8,
                referencia_legal="Tardanza / salida anticipada",
            )
        )
        return result

    def _persist_employee_lines(
        self,
        cur,
        run_id: str,
        employee_id: str,
        result: PayrollResult,
        concept_map: dict[str, str],
    ) -> None:
        for line in result.lines:
            concept_id = concept_map.get(line.codigo_concepto)
            if not concept_id:
                continue
            cur.execute(
                """
                INSERT INTO payroll_lines (payroll_run_id, employee_id, concept_id, cantidad, monto, orden, referencia_legal)
                VALUES (%s::uuid, %s::uuid, %s, 1, %s, %s, %s)
                """,
                (run_id, employee_id, concept_id, line.monto, line.prioridad, line.referencia_legal),
            )
        cur.execute(
            """
            INSERT INTO payroll_employee_summary (payroll_run_id, employee_id, bruto, total_deducciones, neto, aportes_patronales)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
            """,
            (run_id, employee_id, result.bruto, result.deducciones, result.neto, result.aportes_patronales),
        )

    def _upsert_isr_ytd(self, cur, employee_id: str, inp: PayrollInput, result: PayrollResult, as_of: date) -> None:
        isr = result.amount("ISR")
        bruto_mes = result.bruto
        if inp.es_quincena:
            bruto_mes = bruto_mes * Decimal("2")
        cur.execute(
            """
            INSERT INTO employee_isr_ytd (employee_id, anio, mes, ingreso_gravable, isr_retenido)
            VALUES (%s::uuid, %s, %s, %s, %s)
            ON CONFLICT (employee_id, anio, mes) DO UPDATE
            SET ingreso_gravable = EXCLUDED.ingreso_gravable,
                isr_retenido = EXCLUDED.isr_retenido
            """,
            (employee_id, as_of.year, inp.mes, bruto_mes, isr),
        )

    def _accumulate_decimo(self, cur, employee_id: str, as_of: date, bruto: Decimal) -> None:
        trimestre = _decimo_trimestre(as_of.month)
        if trimestre is None:
            return
        anio = as_of.year if as_of.month != 12 else as_of.year
        if as_of.month == 12:
            anio = as_of.year
        cur.execute(
            """
            INSERT INTO decimo_accumulations (employee_id, anio, trimestre, salarios_sumados, monto_calculado)
            VALUES (%s::uuid, %s, %s, %s, 0)
            ON CONFLICT (employee_id, anio, trimestre) DO UPDATE
            SET salarios_sumados = decimo_accumulations.salarios_sumados + EXCLUDED.salarios_sumados
            """,
            (employee_id, anio, trimestre, bruto),
        )

    def _concept_id_map(self, cur) -> dict[str, str]:
        cur.execute("SELECT id, codigo FROM payroll_concepts WHERE activo = true")
        return {row[1]: str(row[0]) for row in cur.fetchall()}

    def get_run(self, run_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pr.config_snapshot, pr.payroll_period_id
                    FROM payroll_runs pr
                    WHERE pr.id = %s::uuid
                    """,
                    (run_id,),
                )
                run_row = cur.fetchone()
                if not run_row:
                    return None
                cur.execute(
                    """
                    SELECT pes.employee_id, pes.bruto, pes.total_deducciones, pes.neto, pes.aportes_patronales
                    FROM payroll_employee_summary pes
                    WHERE pes.payroll_run_id = %s::uuid
                    ORDER BY pes.employee_id
                    """,
                    (run_id,),
                )
                summaries = cur.fetchall()
                cur.execute(
                    """
                    SELECT pl.employee_id, pc.codigo, pc.tipo::text, pl.monto
                    FROM payroll_lines pl
                    JOIN payroll_concepts pc ON pc.id = pl.concept_id
                    WHERE pl.payroll_run_id = %s::uuid
                    ORDER BY pl.employee_id, pl.orden
                    """,
                    (run_id,),
                )
                line_rows = cur.fetchall()

        employees: list[dict[str, Any]] = []
        lines_by_emp: dict[str, list[dict[str, str]]] = {}
        for emp_id, codigo, tipo, monto in line_rows:
            eid = str(emp_id)
            lines_by_emp.setdefault(eid, []).append(
                {"concepto": codigo, "tipo": tipo, "monto": str(monto)}
            )

        totales = {"bruto": Decimal("0"), "deducciones": Decimal("0"), "neto": Decimal("0"), "aportes_patronales": Decimal("0")}
        for emp_id, bruto, ded, neto, aportes in summaries:
            eid = str(emp_id)
            employees.append(
                {
                    "employee_id": eid,
                    "bruto": str(bruto),
                    "deducciones": str(ded),
                    "neto": str(neto),
                    "aportes_patronales": str(aportes),
                    "lines": lines_by_emp.get(eid, []),
                }
            )
            totales["bruto"] += Decimal(str(bruto))
            totales["deducciones"] += Decimal(str(ded))
            totales["neto"] += Decimal(str(neto))
            totales["aportes_patronales"] += Decimal(str(aportes))

        first = employees[0] if len(employees) == 1 else None
        return {
            "run_id": run_id,
            "payroll_period_id": str(run_row[1]),
            "employee_count": len(employees),
            "employees": employees,
            "totales": {k: str(v) for k, v in totales.items()},
            "config_snapshot": run_row[0],
            # Compatibilidad corrida individual
            "bruto": first["bruto"] if first else "0",
            "deducciones": first["deducciones"] if first else "0",
            "neto": first["neto"] if first else "0",
            "aportes_patronales": first["aportes_patronales"] if first else "0",
            "lines": first["lines"] if first else [],
        }


def _decimo_trimestre(mes: int) -> int | None:
    """Mapeo mes → trimestre de acumulación décimo (Decreto 19/1973)."""
    if mes in (12, 1, 2, 3):
        return 1
    if mes in (4, 5, 6, 7):
        return 2
    if mes in (8, 9, 10, 11):
        return 3
    return None
