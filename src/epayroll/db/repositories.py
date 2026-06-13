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

from .config_loader import load_config
from .connection import get_connection


@dataclass
class EmployeeRecord:
    id: str
    organization_id: str
    cedula: str
    nombres: str
    apellidos: str
    activo: bool


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
        database_url: str | None = None,
    ) -> EmployeeRecord:
        emp_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO employees (id, organization_id, cedula, nombres, apellidos, email)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)
                    RETURNING id, organization_id, cedula, nombres, apellidos, activo
                    """,
                    (emp_id, organization_id, cedula, nombres, apellidos, email),
                )
                row = cur.fetchone()
        return EmployeeRecord(str(row[0]), str(row[1]), row[2], row[3], row[4], row[5])

    def list_by_org(self, organization_id: str, database_url: str | None = None) -> list[EmployeeRecord]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, organization_id, cedula, nombres, apellidos, activo
                    FROM employees WHERE organization_id = %s::uuid AND activo = true
                    ORDER BY apellidos, nombres
                    """,
                    (organization_id,),
                )
                return [
                    EmployeeRecord(str(r[0]), str(r[1]), r[2], r[3], r[4], r[5])
                    for r in cur.fetchall()
                ]


class ContractRepository:
    def create(
        self,
        employee_id: str,
        contract_type_codigo: str,
        salario_base: Decimal,
        fecha_inicio: date,
        forma_pago: str = "QUINCENAL",
        database_url: str | None = None,
    ) -> ContractRecord:
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
                riesgo = Decimal(str(row[0])) if row else Decimal("0.0105")
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

        resolved_run = run_id or self.get_latest_run_id(payroll_period_id, database_url=database_url)
        if not resolved_run:
            raise ValueError("No hay corrida de planilla para este periodo")

        payslip_repo = PayslipRepository()
        payslips = payslip_repo.generate_all_for_run(resolved_run, database_url=database_url)
        self.set_period_status(payroll_period_id, "CERRADO", database_url=database_url)

        return {
            "payroll_period_id": payroll_period_id,
            "run_id": resolved_run,
            "estado": "CERRADO",
            "payslips_generated": len(payslips),
            "payslips": payslips,
        }

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
