from __future__ import annotations

import json
import os
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.db.export_repository import ExportRepository
from epayroll.integration.ach import generate_ach_export
from epayroll.integration.models import BankAccountInfo
from epayroll.integration.odoo import build_journal_entry, parse_odoo_employees

from epayroll.db.repositories import ContractRepository, EmployeeRepository

from .connection import get_connection

ROOT = Path(__file__).resolve().parents[3]


class IntegrationRepository:
    def __init__(self) -> None:
        self.export_repo = ExportRepository()
        self.employees_repo = EmployeeRepository()
        self.contracts_repo = ContractRepository()

    def upsert_bank_account(
        self,
        employee_id: str,
        banco: str,
        numero_cuenta: str,
        tipo_cuenta: str = "AHORROS",
        database_url: str | None = None,
    ) -> dict[str, str]:
        account_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO employee_bank_accounts (id, employee_id, banco, tipo_cuenta, numero_cuenta)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    ON CONFLICT (employee_id, banco, numero_cuenta) DO UPDATE
                    SET tipo_cuenta = EXCLUDED.tipo_cuenta, activo = true, updated_at = now()
                    RETURNING id
                    """,
                    (account_id, employee_id, banco, tipo_cuenta, numero_cuenta),
                )
                account_id = str(cur.fetchone()[0])
        return {"account_id": account_id, "employee_id": employee_id, "banco": banco}

    def load_bank_accounts(
        self,
        run_id: str,
        banco: str,
        database_url: str | None = None,
    ) -> dict[str, BankAccountInfo]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT eba.employee_id, eba.tipo_cuenta, eba.numero_cuenta
                    FROM payroll_employee_summary pes
                    JOIN employee_bank_accounts eba ON eba.employee_id = pes.employee_id
                    WHERE pes.payroll_run_id = %s::uuid
                      AND eba.banco = %s AND eba.activo = true
                    """,
                    (run_id, banco),
                )
                rows = cur.fetchall()
        return {
            str(r[0]): BankAccountInfo(banco=banco, tipo_cuenta=r[1], numero_cuenta=r[2])
            for r in rows
        }

    def export_ach(
        self,
        run_id: str,
        banco: str = "BANCO_GENERAL",
        database_url: str | None = None,
    ) -> dict[str, Any]:
        bundle = self.export_repo.load_run_bundle(run_id, database_url=database_url)
        accounts = self.load_bank_accounts(run_id, banco, database_url=database_url)
        if not accounts:
            raise ValueError("No hay cuentas bancarias activas para los empleados de esta corrida")

        storage = Path(os.environ.get("EPAYROLL_EXPORT_DIR", str(ROOT / "storage" / "exports")))
        output_path = storage / "ach" / banco.lower() / f"{run_id}.txt"
        result = generate_ach_export(bundle, accounts, output_path, banco=banco)
        rel_path = str(output_path.relative_to(ROOT)) if output_path.is_relative_to(ROOT) else str(output_path)

        export_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bank_exports (id, payroll_run_id, banco, archivo_path, estado)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    """,
                    (
                        export_id,
                        run_id,
                        banco,
                        rel_path,
                        "GENERADO" if result["valido"] else "ERROR",
                    ),
                )
        result["export_id"] = export_id
        result["archivo_path"] = rel_path
        return result

    def get_ach_export(self, run_id: str, database_url: str | None = None) -> dict[str, Any] | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, banco, archivo_path, estado, created_at
                    FROM bank_exports
                    WHERE payroll_run_id = %s::uuid
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
        return {
            "export_id": str(row[0]),
            "banco": row[1],
            "archivo_path": row[2],
            "estado": row[3],
            "created_at": row[4].isoformat(),
        }

    def build_odoo_journal(self, run_id: str, database_url: str | None = None) -> dict[str, Any]:
        bundle = self.export_repo.load_run_bundle(run_id, database_url=database_url)
        return build_journal_entry(bundle)

    def sync_odoo_employees(
        self,
        organization_id: str,
        payload: list[dict[str, Any]],
        database_url: str | None = None,
    ) -> dict[str, Any]:
        from datetime import date

        records = parse_odoo_employees(payload)
        ok = 0
        errors: list[str] = []

        for rec in records:
            try:
                if not rec["cedula"]:
                    raise ValueError("cedula requerida")
                existing = [
                    e
                    for e in self.employees_repo.list_by_org(organization_id, database_url=database_url)
                    if e.cedula == rec["cedula"]
                ]
                if existing:
                    emp_id = existing[0].id
                else:
                    emp = self.employees_repo.create(
                        organization_id=organization_id,
                        cedula=rec["cedula"],
                        nombres=rec["nombres"] or "Sin nombre",
                        apellidos=rec["apellidos"] or "-",
                        email=rec.get("email"),
                        database_url=database_url,
                    )
                    emp_id = emp.id

                if rec["salario_base"] > 0:
                    active = self.contracts_repo.get_active(emp_id, database_url=database_url)
                    if not active:
                        f_ini = rec.get("fecha_inicio") or date.today()
                        if isinstance(f_ini, str):
                            f_ini = date.fromisoformat(f_ini)
                        self.contracts_repo.create(
                            employee_id=emp_id,
                            contract_type_codigo=rec.get("contract_type_codigo") or "INDEFINIDO",
                            salario_base=rec["salario_base"],
                            fecha_inicio=f_ini,
                            forma_pago=rec.get("forma_pago") or "QUINCENAL",
                            database_url=database_url,
                        )
                ok += 1
            except Exception as e:
                errors.append(f"{rec.get('cedula', '?')}: {e}")

        log_id = str(uuid.uuid4())
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO integration_sync_log (
                        id, organization_id, integracion, direccion, registros_ok, registros_error, detalle
                    ) VALUES (%s::uuid, %s::uuid, 'ODOO', 'INBOUND', %s, %s, %s)
                    """,
                    (log_id, organization_id, ok, len(errors), json.dumps({"errores": errors})),
                )

        return {
            "sync_id": log_id,
            "registros_ok": ok,
            "registros_error": len(errors),
            "errores": errors,
        }
