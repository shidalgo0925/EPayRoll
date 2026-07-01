from __future__ import annotations

import re

from epayroll.auth.context import AuthContext
from epayroll.auth.guard import TenantAccessError

ROLE_RULES: tuple[tuple[re.Pattern[str], frozenset[str], frozenset[str]], ...] = (
    (
        re.compile(r"^/api/v1/payroll/periods/[^/]+/close$"),
        frozenset({"POST"}),
        frozenset({"payroll_admin", "contador", "admin", "rrhh"}),
    ),
    (
        re.compile(r"^/api/v1/exports/(sipe|dgi|ach)/"),
        frozenset({"POST"}),
        frozenset({"payroll_admin", "contador", "admin"}),
    ),
    (
        re.compile(r"^/api/v1/integrations/odoo/journal/[^/]+/push$"),
        frozenset({"POST"}),
        frozenset({"contador", "admin"}),
    ),
    (
        re.compile(r"^/api/v1/me/organizations$"),
        frozenset({"POST"}),
        frozenset({"tenant_admin", "admin", "payroll_admin"}),
    ),
    (
        re.compile(r"^/api/v1/vacation/requests/[^/]+/approve$"),
        frozenset({"POST"}),
        frozenset({"rrhh", "payroll_admin", "admin", "gerente"}),
    ),
)


def enforce_roles(path: str, method: str, ctx: AuthContext) -> None:
    if not ctx.authenticated or ctx.tenant_id == "*":
        return
    upper = method.upper()
    for pattern, methods, roles in ROLE_RULES:
        if upper in methods and pattern.match(path):
            if not ctx.has_any_role(roles):
                raise TenantAccessError(
                    f"Rol insuficiente — se requiere uno de: {', '.join(sorted(roles))}"
                )
            return
