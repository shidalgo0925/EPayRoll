from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from epayroll.auth.context import AuthContext
from epayroll.auth.guard import TenantAccessError, TenantGuard
from epayroll.auth.jwt import AuthError
from epayroll.auth.rbac import enforce_roles
from epayroll.auth.resolver import PUBLIC_PATHS, enforce_path_tenant_scope, resolve_auth
from epayroll.auth.settings import get_auth_settings

guard = TenantGuard()

BODY_SCOPED_ROUTES = frozenset(
    {
        "/api/v1/payroll/runs",
        "/api/v1/payroll/decimo/runs",
    }
)


class En1AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_auth_settings()
        path = request.url.path

        if not settings.enabled:
            request.state.auth = AuthContext(tenant_id="*", authenticated=False)
            return await call_next(request)

        if path in PUBLIC_PATHS or not path.startswith("/api/v1"):
            request.state.auth = AuthContext.anonymous()
            return await call_next(request)

        try:
            ctx = resolve_auth(request, settings)
            enforce_roles(path, request.method, ctx)
            enforce_path_tenant_scope(request, ctx, guard)
            if request.method in ("POST", "PUT", "PATCH") and path in BODY_SCOPED_ROUTES:
                await self._enforce_body_scope(request, ctx)
            request.state.auth = ctx
        except AuthError as e:
            return JSONResponse(status_code=401, content={"detail": str(e)})
        except TenantAccessError as e:
            return JSONResponse(status_code=e.status_code, content={"detail": str(e)})

        return await call_next(request)

    async def _enforce_body_scope(self, request: Request, ctx: AuthContext) -> None:
        body = await request.body()
        if not body:
            return
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return

        if request.url.path == "/api/v1/payroll/runs":
            employee_id = payload.get("employee_id")
            period_id = payload.get("payroll_period_id")
            if employee_id:
                guard.assert_employee_access(ctx, str(employee_id))
            if period_id:
                guard.assert_period_access(ctx, str(period_id))
        elif request.url.path == "/api/v1/payroll/decimo/runs":
            employee_id = payload.get("employee_id")
            period_id = payload.get("payroll_period_id")
            if employee_id:
                guard.assert_employee_access(ctx, str(employee_id))
            if period_id:
                guard.assert_period_access(ctx, str(period_id))

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive  # noqa: SLF001
