from __future__ import annotations

import re
from typing import Callable

from starlette.requests import Request

from epayroll.auth.context import AuthContext
from epayroll.auth.guard import TenantAccessError, TenantGuard
from epayroll.auth.jwt import AuthError, decode_jwt, encode_jwt, parse_bearer_token
from epayroll.auth.jwks import decode_en1_jwt
from epayroll.auth.settings import AuthSettings, get_auth_settings

PUBLIC_PATHS = frozenset({
    "/health",
    "/health/db",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/login",
    "/api/v1/auth/sso/config",
    "/api/v1/auth/sso/exchange",
    "/api/v1/auth/sso/refresh",
})
UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

PATH_RULES: tuple[tuple[re.Pattern[str], Callable[[TenantGuard, AuthContext, re.Match[str]], None]], ...] = (
    (re.compile(rf"^/api/v1/organizations/(?P<organization_id>{UUID})"), lambda g, c, m: g.assert_org_access(c, m.group("organization_id"))),
    (re.compile(rf"^/api/v1/employees/(?P<employee_id>{UUID})"), lambda g, c, m: g.assert_employee_access(c, m.group("employee_id"))),
    (re.compile(rf"^/api/v1/payroll/periods/(?P<period_id>{UUID})"), lambda g, c, m: g.assert_period_access(c, m.group("period_id"))),
    (re.compile(rf"^/api/v1/payroll/runs/(?P<run_id>{UUID})"), lambda g, c, m: g.assert_run_access(c, m.group("run_id"))),
    (re.compile(rf"^/api/v1/exports/sipe/(?P<run_id>{UUID})"), lambda g, c, m: g.assert_run_access(c, m.group("run_id"))),
    (re.compile(rf"^/api/v1/exports/dgi/(?P<run_id>{UUID})"), lambda g, c, m: g.assert_run_access(c, m.group("run_id"))),
    (re.compile(rf"^/api/v1/exports/ach/(?P<run_id>{UUID})"), lambda g, c, m: g.assert_run_access(c, m.group("run_id"))),
    (re.compile(rf"^/api/v1/integrations/odoo/journal/(?P<run_id>{UUID})"), lambda g, c, m: g.assert_run_access(c, m.group("run_id"))),
    (re.compile(rf"^/api/v1/vacation/requests/(?P<request_id>{UUID})"), lambda g, c, m: g.assert_vacation_request_access(c, m.group("request_id"))),
)


def resolve_auth(request: Request, settings: AuthSettings | None = None) -> AuthContext:
    settings = settings or get_auth_settings()
    if not settings.enabled:
        return AuthContext(tenant_id="*", authenticated=False)

    bearer: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header:
        bearer = parse_bearer_token(auth_header)
    if bearer:
        if settings.mode == "en1":
            return decode_en1_jwt(bearer, settings)
        return decode_jwt(bearer, settings)

    mode = settings.mode
    if mode == "stub":
        tenant_id = request.headers.get("X-Tenant-Id", "").strip()
        if not tenant_id:
            raise AuthError("Header X-Tenant-Id requerido (modo stub EN1)")
        org_id = request.headers.get("X-Organization-Id", "").strip() or None
        user_id = request.headers.get("X-User-Id", "").strip() or None
        roles_raw = request.headers.get("X-Roles", "").strip()
        roles = tuple(r.strip() for r in roles_raw.split(",") if r.strip()) if roles_raw else ()
        return AuthContext(
            tenant_id=tenant_id,
            user_id=user_id,
            organization_id=org_id,
            roles=roles,
        )

    if mode in ("jwt", "en1"):
        token = parse_bearer_token(request.headers.get("Authorization"))
        if not token:
            raise AuthError("Bearer token requerido")
        if mode == "en1":
            return decode_en1_jwt(token, settings)
        return decode_jwt(token, settings)

    raise AuthError(f"EPAYROLL_AUTH_MODE inválido: {mode}")


def enforce_path_tenant_scope(request: Request, ctx: AuthContext, guard: TenantGuard) -> None:
    if not ctx.authenticated or ctx.tenant_id == "*":
        return
    path = request.url.path
    for pattern, checker in PATH_RULES:
        match = pattern.match(path)
        if match:
            checker(guard, ctx, match)
            return
