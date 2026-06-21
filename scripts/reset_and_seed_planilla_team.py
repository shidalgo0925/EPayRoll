#!/usr/bin/env python3
"""Borra datos operativos y carga los 5 empleados de planilla demo."""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epayroll.db.attendance_facts_repository import AttendanceFactsRepository
from epayroll.db.connection import get_connection
from epayroll.db.legal_config_repository import LegalConfigRepository
from epayroll.db.repositories import ContractRepository, EmployeeRepository, PayrollRepository
from epayroll.payroll.service import PayrollService

ORG_ID = "00000000-0000-0000-0000-000000000010"

TEAM = [
    {
        "ficha": "1",
        "nombres": "Juan",
        "apellidos": "Pérez Demo",
        "cedula": "8-888-8888",
        "telefono": None,
        "salario": Decimal("1800"),
    },
    {
        "ficha": "2",
        "nombres": "Narciso",
        "apellidos": "Villamil",
        "cedula": "9-219-884",
        "telefono": None,
        "salario": Decimal("425"),
    },
    {
        "ficha": "3",
        "nombres": "Seul",
        "apellidos": "Hidalgo",
        "cedula": "8-382-685",
        "telefono": "61842170",
        "salario": Decimal("1025"),
    },
    {
        "ficha": "4",
        "nombres": "David",
        "apellidos": "Fernandez",
        "cedula": "4",
        "telefono": None,
        "salario": Decimal("825"),
    },
    {
        "ficha": "5",
        "nombres": "Abigail",
        "apellidos": "Govea",
        "cedula": "8-993-1252",
        "telefono": None,
        "salario": Decimal("650"),
    },
]

WIPE_SQL = """
BEGIN;
DELETE FROM sipe_exports;
DELETE FROM dgi_exports;
DELETE FROM bank_exports;
DELETE FROM employee_payroll_acumulado;
DELETE FROM payroll_run_adjustments;
DELETE FROM payroll_lines;
DELETE FROM payroll_employee_summary;
DELETE FROM payslips;
DELETE FROM payroll_runs;
DELETE FROM payroll_periods;
DELETE FROM employee_isr_ytd;
DELETE FROM termination_cases;
DELETE FROM vacation_requests;
DELETE FROM vacation_balances;
DELETE FROM decimo_accumulations;
DELETE FROM seniority_provisions;
DELETE FROM severance_fund;
DELETE FROM attendance_daily;
DELETE FROM attendance_facts;
DELETE FROM attendance_import_batches;
DELETE FROM time_entries;
DELETE FROM absences;
DELETE FROM incapacities;
DELETE FROM employee_schedules;
DELETE FROM employee_concept_assignments;
DELETE FROM contract_amendments;
DELETE FROM salary_changes;
DELETE FROM employee_dependents;
DELETE FROM employee_documents;
DELETE FROM employee_history;
DELETE FROM employee_bank_accounts;
DELETE FROM contracts;
DELETE FROM employees;
DELETE FROM integration_sync_log;
DELETE FROM audit_log;
COMMIT;
"""


def wipe_operational(database_url: str | None = None) -> None:
    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(WIPE_SQL)
    print("OK — datos operativos y empleados borrados")


def seed_team(database_url: str | None = None) -> dict[str, str]:
    emp_repo = EmployeeRepository()
    contract_repo = ContractRepository()
    payroll_repo = PayrollRepository()
    legal_repo = LegalConfigRepository()
    att_repo = AttendanceFactsRepository()

    legal_repo.seed_org_defaults(ORG_ID, database_url=database_url)

    emp_ids: list[str] = []
    for row in TEAM:
        emp = emp_repo.create(
            organization_id=ORG_ID,
            cedula=row["cedula"],
            nombres=row["nombres"],
            apellidos=row["apellidos"],
            ficha=row["ficha"],
            telefono=row["telefono"],
            database_url=database_url,
        )
        contract_repo.create(
            employee_id=emp.id,
            contract_type_codigo="INDEFINIDO",
            salario_base=row["salario"],
            fecha_inicio=date(2026, 1, 1),
            forma_pago="QUINCENAL",
            database_url=database_url,
        )
        emp_ids.append(emp.id)
        print(f"  + {row['ficha']} {row['nombres']} {row['apellidos']} ({row['cedula']}) — B/. {row['salario']}")

    f_ini = date(2026, 6, 1)
    f_fin = date(2026, 6, 15)
    period_id = payroll_repo.create_period(
        organization_id=ORG_ID,
        fecha_inicio=f_ini,
        fecha_fin=f_fin,
        fecha_pago=date(2026, 6, 16),
        database_url=database_url,
    )
    print(f"OK — período {f_ini} → {f_fin} ({period_id})")

    att = att_repo.ensure_period_grid(ORG_ID, f_ini, f_fin, database_url=database_url)
    print(f"OK — asistencia: {att.get('employees', 0)} empleados, {att.get('total', 0)} celdas")

    service = PayrollService()
    run = service.run_period(
        payroll_period_id=period_id,
        use_attendance=False,
    )
    print(
        f"OK — corrida {run['run_id']}: {run['employee_count']} empleado(s), "
        f"neto total B/. {run['totales']['neto']}"
    )
    return {
        "organization_id": ORG_ID,
        "period_id": period_id,
        "run_id": run["run_id"],
        "employee_ids": ",".join(emp_ids),
    }


def main() -> None:
    from epayroll.db.connection import get_database_url

    url = get_database_url()
    print(f"Conectando a {url.split('@')[-1]}...")
    wipe_operational(database_url=url)
    print("Cargando empleados de planilla…")
    result = seed_team(database_url=url)
    print("\nListo. Use en la UI:")
    print(f"  org:     {result['organization_id']}")
    print(f"  período: {result['period_id']}")
    print(f"  corrida: {result['run_id']}")


if __name__ == "__main__":
    main()
