from __future__ import annotations

from epayroll.auth.context import AuthContext
from epayroll.auth.tenant_repository import TenantRepository


class TenantAccessError(Exception):
    def __init__(self, message: str, status_code: int = 403) -> None:
        super().__init__(message)
        self.status_code = status_code


class TenantGuard:
    def __init__(self, repo: TenantRepository | None = None) -> None:
        self.repo = repo or TenantRepository()

    _ADMIN_ROLES = frozenset({"payroll_admin", "contador", "admin", "rrhh", "gerente", "tenant_admin"})

    def assert_tenant_access(self, ctx: AuthContext, tenant_id: str) -> None:
        if ctx.tenant_id != tenant_id:
            raise TenantAccessError("Tenant no autorizado")

    def assert_org_access(self, ctx: AuthContext, organization_id: str) -> None:
        tenant_id = self.repo.org_tenant_id(organization_id)
        if not tenant_id:
            raise TenantAccessError("Organización no encontrada", status_code=404)
        if tenant_id != ctx.tenant_id:
            raise TenantAccessError("Organización fuera del tenant")
        if ctx.organization_id and ctx.organization_id != organization_id:
            if not ctx.has_any_role(self._ADMIN_ROLES):
                raise TenantAccessError("Organización no autorizada para este token")

    def assert_employee_access(self, ctx: AuthContext, employee_id: str) -> None:
        org_id = self.repo.employee_org_id(employee_id)
        if not org_id:
            raise TenantAccessError("Empleado no encontrado", status_code=404)
        self.assert_org_access(ctx, org_id)

    def assert_period_access(self, ctx: AuthContext, period_id: str) -> None:
        org_id = self.repo.period_org_id(period_id)
        if not org_id:
            raise TenantAccessError("Período no encontrado", status_code=404)
        self.assert_org_access(ctx, org_id)

    def assert_run_access(self, ctx: AuthContext, run_id: str) -> None:
        org_id = self.repo.run_org_id(run_id)
        if not org_id:
            raise TenantAccessError("Corrida no encontrada", status_code=404)
        self.assert_org_access(ctx, org_id)

    def assert_vacation_request_access(self, ctx: AuthContext, request_id: str) -> None:
        org_id = self.repo.vacation_request_org_id(request_id)
        if not org_id:
            raise TenantAccessError("Solicitud no encontrada", status_code=404)
        self.assert_org_access(ctx, org_id)
