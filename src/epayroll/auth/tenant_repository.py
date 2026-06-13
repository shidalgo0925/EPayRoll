from __future__ import annotations

from epayroll.db.connection import get_connection


class TenantRepository:
    def org_tenant_id(self, organization_id: str, database_url: str | None = None) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT tenant_id FROM organizations
                    WHERE id = %s::uuid AND activo = true
                    """,
                    (organization_id,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None

    def employee_org_id(self, employee_id: str, database_url: str | None = None) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT organization_id FROM employees
                    WHERE id = %s::uuid AND activo = true
                    """,
                    (employee_id,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None

    def period_org_id(self, period_id: str, database_url: str | None = None) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT organization_id FROM payroll_periods
                    WHERE id = %s::uuid
                    """,
                    (period_id,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None

    def run_org_id(self, run_id: str, database_url: str | None = None) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pp.organization_id
                    FROM payroll_runs pr
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    WHERE pr.id = %s::uuid
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None

    def vacation_request_org_id(self, request_id: str, database_url: str | None = None) -> str | None:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.organization_id
                    FROM vacation_requests vr
                    JOIN employees e ON e.id = vr.employee_id
                    WHERE vr.id = %s::uuid
                    """,
                    (request_id,),
                )
                row = cur.fetchone()
        return str(row[0]) if row else None
