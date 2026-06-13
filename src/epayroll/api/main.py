from __future__ import annotations

import os

from datetime import date
from decimal import Decimal
from typing import Any

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from epayroll import __version__
from epayroll.auth.dependencies import get_auth_context
from epayroll.auth.jwt import encode_jwt
from epayroll.auth.middleware import En1AuthMiddleware
from epayroll.api.schemas import (
    AchExportRequest,
    BankAccountCreate,
    OdooEmployeeSyncRequest,
    IncapacityCreate,
    IncapacityPeriodImpactRequest,
    AttendanceCalculateRequest,
    DecimoRunCreate,
    PeriodCloseRequest,
    PayrollPeriodRunRequest,
    ScheduleAssignRequest,
    TerminationCalculateRequest,
    TimeEntryCreate,
    VacationAccrueRequest,
    VacationApproveRequest,
    VacationSubstituteAssign,
    VacationRequestCreate,
    ContractCreate,
    ContractResponse,
    EmployeeCreate,
    EmployeeResponse,
    LoginRequest,
    LoginResponse,
    SsoConfigResponse,
    SsoExchangeRequest,
    SsoRefreshRequest,
    SsoTokenResponse,
    HealthResponse,
    PayrollPeriodCreate,
    PayrollRunCreate,
)
from epayroll.db.analytics_repository import AnalyticsRepository
from epayroll.db.attendance_repository import AttendanceRepository
from epayroll.db.connection import get_connection, get_database_url
from epayroll.db.export_repository import ExportRepository
from epayroll.db.incapacity_repository import IncapacityRepository
from epayroll.db.integration_repository import IntegrationRepository
from epayroll.db.payslip_repository import PayslipRepository
from epayroll.db.repositories import ContractRepository, EmployeeRepository, PayrollRepository
from epayroll.db.termination_repository import TerminationRepository
from epayroll.db.vacation_repository import VacationRepository
from epayroll.engine.liquidation import LiquidationInput
from epayroll.payroll.service import PayrollRunOverrides, PayrollService

app = FastAPI(
    title="EPayRoll API",
    description="Sistema de planilla Panamá — Easy Technology Services",
    version=__version__,
)
app.add_middleware(En1AuthMiddleware)


class UiNoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.url.path.startswith("/app/"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app.add_middleware(UiNoCacheMiddleware)

employees_repo = EmployeeRepository()
contracts_repo = ContractRepository()
payroll_repo = PayrollRepository()
attendance_repo = AttendanceRepository()
payroll_service = PayrollService(
    payroll_repo=payroll_repo,
    contracts_repo=contracts_repo,
    employees_repo=employees_repo,
    attendance_repo=attendance_repo,
)
termination_repo = TerminationRepository()
payslip_repo = PayslipRepository()
vacation_repo = VacationRepository()
export_repo = ExportRepository()
integration_repo = IntegrationRepository()
incapacity_repo = IncapacityRepository()
analytics_repo = AnalyticsRepository(vacation_repo=vacation_repo)

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000010"
UI_DIR = Path(__file__).resolve().parents[3] / "ui" / "static"


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@app.get("/api/v1/auth/me")
def auth_me(request: Request) -> dict[str, object]:
    """Contexto EN1 resuelto (stub headers o JWT)."""
    ctx = get_auth_context(request)
    return {
        "authenticated": ctx.authenticated,
        "tenant_id": ctx.tenant_id or None,
        "organization_id": ctx.organization_id,
        "user_id": ctx.user_id,
        "roles": list(ctx.roles),
    }


@app.post("/api/v1/auth/login", response_model=LoginResponse)
def auth_login(body: LoginRequest) -> LoginResponse:
    """
    Login EN1 — emite JWT para la UI.
    Requiere EPAYROLL_LOGIN_API_KEY (compartida con EN1 o panel admin).
    """
    expected = os.environ.get("EPAYROLL_LOGIN_API_KEY", "dev-login-key")
    if body.api_key != expected:
        raise HTTPException(status_code=401, detail="API key inválida")

    from epayroll.auth.context import AuthContext
    from epayroll.auth.guard import TenantGuard

    if body.organization_id:
        TenantGuard().assert_org_access(
            AuthContext(tenant_id=body.tenant_id, user_id=body.user_id),
            body.organization_id,
        )

    token = encode_jwt(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        organization_id=body.organization_id,
        roles=body.roles,
    )
    return LoginResponse(
        access_token=token,
        tenant_id=body.tenant_id,
        organization_id=body.organization_id,
        user_id=body.user_id,
    )


@app.get("/api/v1/auth/sso/config", response_model=SsoConfigResponse)
def auth_sso_config(request: Request) -> SsoConfigResponse:
    """Configuración OAuth EN1 para redirect SSO en la UI."""
    from epayroll.auth.settings import get_auth_settings
    from epayroll.auth.sso import default_app_base_url, sso_config_payload

    settings = get_auth_settings()
    base = default_app_base_url() or str(request.base_url).rstrip("/")
    cfg = sso_config_payload(settings, app_base_url=base)
    return SsoConfigResponse(**cfg)


@app.post("/api/v1/auth/sso/exchange", response_model=SsoTokenResponse)
def auth_sso_exchange(body: SsoExchangeRequest) -> SsoTokenResponse:
    """Intercambia authorization code EN1 por tokens (server-side, secret protegido)."""
    from epayroll.auth.jwt import AuthError
    from epayroll.auth.settings import get_auth_settings
    from epayroll.auth.sso import exchange_code

    try:
        payload = exchange_code(body.code, get_auth_settings(), redirect_uri=body.redirect_uri)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return SsoTokenResponse(
        access_token=payload["access_token"],
        token_type=payload.get("token_type", "bearer"),
        expires_in=payload.get("expires_in"),
        refresh_token=payload.get("refresh_token"),
    )


@app.post("/api/v1/auth/sso/refresh", response_model=SsoTokenResponse)
def auth_sso_refresh(body: SsoRefreshRequest) -> SsoTokenResponse:
    """Renueva access_token EN1 con refresh_token."""
    from epayroll.auth.jwt import AuthError
    from epayroll.auth.settings import get_auth_settings
    from epayroll.auth.sso import refresh_tokens

    try:
        payload = refresh_tokens(body.refresh_token, get_auth_settings())
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return SsoTokenResponse(
        access_token=payload["access_token"],
        token_type=payload.get("token_type", "bearer"),
        expires_in=payload.get("expires_in"),
        refresh_token=payload.get("refresh_token"),
    )


@app.get("/health/db")
def health_db() -> dict[str, Any]:
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"database": "connected", "url": get_database_url().split("@")[-1]}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"BD no disponible: {e}") from e


@app.post("/api/v1/organizations/{organization_id}/employees", response_model=EmployeeResponse)
def create_employee(organization_id: str, body: EmployeeCreate) -> EmployeeResponse:
    try:
        emp = employees_repo.create(
            organization_id=organization_id,
            cedula=body.cedula,
            nombres=body.nombres,
            apellidos=body.apellidos,
            email=body.email,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return EmployeeResponse(**emp.__dict__)


@app.get("/api/v1/organizations/{organization_id}/employees", response_model=list[EmployeeResponse])
def list_employees(organization_id: str) -> list[EmployeeResponse]:
    try:
        rows = employees_repo.list_by_org(organization_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return [EmployeeResponse(**r.__dict__) for r in rows]


@app.post("/api/v1/employees/{employee_id}/contracts", response_model=ContractResponse)
def create_contract(employee_id: str, body: ContractCreate) -> ContractResponse:
    try:
        c = contracts_repo.create(
            employee_id=employee_id,
            contract_type_codigo=body.contract_type_codigo,
            salario_base=body.salario_base,
            fecha_inicio=body.fecha_inicio,
            forma_pago=body.forma_pago,
            categoria_salario_minimo=body.categoria_salario_minimo,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ContractResponse(**c.__dict__)


@app.post("/api/v1/organizations/{organization_id}/payroll-periods")
def create_payroll_period(organization_id: str, body: PayrollPeriodCreate) -> dict[str, str]:
    try:
        period_id = payroll_repo.create_period(
            organization_id=organization_id,
            fecha_inicio=body.fecha_inicio,
            fecha_fin=body.fecha_fin,
            fecha_pago=body.fecha_pago,
            tipo=body.tipo,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"payroll_period_id": period_id}


@app.post("/api/v1/payroll/periods/{period_id}/run")
def run_period_payroll(period_id: str, body: PayrollPeriodRunRequest) -> dict[str, Any]:
    """Ejecuta planilla para todos los empleados activos del período (Fase 4)."""
    overrides = PayrollRunOverrides(
        dias_trabajados=body.dias_trabajados,
        es_quincena=body.es_quincena,
        mes=body.mes,
        descuento_voluntario=body.descuento_voluntario,
    )
    try:
        return payroll_service.run_period(
            payroll_period_id=period_id,
            employee_ids=body.employee_ids,
            use_attendance=body.use_attendance,
            overrides=overrides,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/payroll/periods/{period_id}/close")
def close_payroll_period(period_id: str, body: PeriodCloseRequest | None = None) -> dict[str, Any]:
    """Genera recibos PDF y cierra el periodo (CALCULADO -> CERRADO)."""
    try:
        return payroll_service.close_period(
            payroll_period_id=period_id,
            run_id=body.run_id if body else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/payroll/runs/{run_id}/payslips/generate")
def generate_payslips(run_id: str) -> dict[str, Any]:
    """Genera recibos PDF para todos los empleados de una corrida."""
    try:
        payslips = payslip_repo.generate_all_for_run(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"run_id": run_id, "payslips_generated": len(payslips), "payslips": payslips}


@app.get("/api/v1/payroll/runs/{run_id}/payslips/{employee_id}")
def download_payslip(run_id: str, employee_id: str) -> FileResponse:
    """Descarga recibo PDF; lo genera si aun no existe."""
    record = payslip_repo.get_payslip_record(run_id, employee_id)
    if not record:
        try:
            payslip_repo.generate_and_persist(run_id, employee_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        record = payslip_repo.get_payslip_record(run_id, employee_id)
    if not record or not record.get("pdf_path"):
        raise HTTPException(status_code=404, detail="Recibo no encontrado")

    path = payslip_repo.resolve_pdf_path(record["pdf_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no encontrado en disco")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"recibo_{employee_id}.pdf",
    )


@app.post("/api/v1/payroll/decimo/runs")
def run_decimo_payroll(body: DecimoRunCreate) -> dict[str, Any]:
    """Pago décimo tercer mes — GT-04."""
    try:
        return payroll_service.run_decimo(
            payroll_period_id=body.payroll_period_id,
            employee_id=body.employee_id,
            salarios_cotizables=body.salarios_cotizables,
            trimestre=body.trimestre,
            anio=body.anio,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/payroll/runs")
def execute_payroll_run(body: PayrollRunCreate) -> dict[str, Any]:
    overrides = PayrollRunOverrides(
        dias_trabajados=body.dias_trabajados,
        es_quincena=body.es_quincena,
        mes=body.mes,
        horas_extra_diurnas=body.horas_extra_diurnas,
        horas_extra_nocturnas=body.horas_extra_nocturnas,
        horas_extra_mixta_nocturnas=body.horas_extra_mixta_nocturnas,
        horas_domingo=body.horas_domingo,
        horas_feriado=body.horas_feriado,
        descuento_voluntario=body.descuento_voluntario,
    )
    try:
        inp = payroll_service.build_payroll_input(
            employee_id=body.employee_id,
            payroll_period_id=body.payroll_period_id,
            overrides=overrides,
            use_attendance=body.use_attendance,
        )
        result = payroll_repo.run_and_persist(
            payroll_period_id=body.payroll_period_id,
            employee_id=body.employee_id,
            payroll_input=inp,
        )
        if body.use_attendance:
            f_ini, f_fin = attendance_repo.get_period_dates(body.payroll_period_id)
            result["attendance"] = {
                k: str(v)
                for k, v in attendance_repo.to_payroll_input_fields(
                    attendance_repo.get_period_summary(body.employee_id, f_ini, f_fin)
                ).items()
            }
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/employees/{employee_id}/termination/calculate")
def calculate_termination(employee_id: str, body: TerminationCalculateRequest) -> dict[str, Any]:
    """Calcula liquidación — GT-05 / GT-06."""
    contract = contracts_repo.get_active(employee_id)
    fecha_inicio = body.fecha_inicio
    if not fecha_inicio and contract:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fecha_inicio FROM contracts WHERE id = %s::uuid",
                    (contract.id,),
                )
                row = cur.fetchone()
                if row:
                    fecha_inicio = row[0]
    if not fecha_inicio:
        raise HTTPException(status_code=400, detail="fecha_inicio requerida")

    salario = body.salario_promedio_prima
    if salario is None and contract:
        salario = contract.salario_base
    if salario is None:
        raise HTTPException(status_code=400, detail="salario_promedio_prima requerido")

    inp = LiquidationInput(
        causa=body.causa,
        fecha_inicio=fecha_inicio,
        fecha_terminacion=body.fecha_terminacion,
        salario_promedio_prima=salario,
        dias_vacaciones_pendientes=body.dias_vacaciones_pendientes,
        salario_diario_vacaciones=body.salario_diario_vacaciones,
        salarios_acumulados_anio=body.salarios_acumulados_anio,
        salario_promedio_indemnizacion=body.salario_promedio_indemnizacion,
        cumplio_preaviso=body.cumplio_preaviso,
    )
    result = termination_repo.calculate(inp)
    if body.persist:
        try:
            return termination_repo.persist(
                employee_id=employee_id,
                contract_id=contract.id if contract else None,
                inp=inp,
                result=result,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    return TerminationRepository._format_result("", result)


@app.get("/api/v1/termination/{case_id}")
def get_termination(case_id: str) -> dict[str, Any]:
    result = termination_repo.get(case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Liquidación no encontrada")
    return result


@app.get("/api/v1/payroll/runs/{run_id}")
def get_payroll_run(run_id: str) -> dict[str, Any]:
    result = payroll_repo.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Corrida no encontrada")
    return result


@app.post("/api/v1/employees/{employee_id}/vacation/accrue")
def accrue_vacation(
    employee_id: str,
    body: VacationAccrueRequest | None = None,
) -> dict[str, Any]:
    """Calcula y persiste saldo vacaciones — Art. 52-54 CT (11 meses / 30 dias)."""
    try:
        return vacation_repo.accrue_employee(
            employee_id=employee_id,
            fecha_corte=body.fecha_corte if body else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/employees/{employee_id}/vacation/balance")
def get_vacation_balance(
    employee_id: str,
    fecha_corte: date | None = None,
) -> dict[str, Any]:
    try:
        return vacation_repo.get_balance(employee_id, fecha_corte=fecha_corte)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/employees/{employee_id}/vacation/requests")
def create_vacation_request(employee_id: str, body: VacationRequestCreate) -> dict[str, str]:
    try:
        return vacation_repo.create_request(
            employee_id=employee_id,
            fecha_inicio=body.fecha_inicio,
            fecha_fin=body.fecha_fin,
            dias_solicitados=body.dias_solicitados,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/employees/{employee_id}/vacation/requests")
def list_vacation_requests(employee_id: str) -> list[dict[str, Any]]:
    try:
        return vacation_repo.list_requests(employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/vacation/requests/{request_id}/approve")
def approve_vacation_request(
    request_id: str,
    body: VacationApproveRequest | None = None,
) -> dict[str, str]:
    try:
        return vacation_repo.approve_request(
            request_id,
            aprobado_por=body.aprobado_por if body else None,
            substitute_employee_id=body.substitute_employee_id if body else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/vacation/requests/{request_id}/substitute")
def assign_vacation_substitute(
    request_id: str,
    body: VacationSubstituteAssign,
) -> dict[str, str]:
    """Asigna empleado sustituto para cobertura operativa (Fase 5.5)."""
    try:
        return vacation_repo.assign_substitute(request_id, body.substitute_employee_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/organizations/{organization_id}/vacation/coverage")
def vacation_coverage_dashboard(
    organization_id: str,
    fecha_desde: date | None = None,
) -> dict[str, Any]:
    """Vacaciones programadas con/sin sustituto asignado."""
    try:
        return vacation_repo.org_coverage_dashboard(organization_id, fecha_desde=fecha_desde)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/organizations/{organization_id}/vacation/dashboard")
def vacation_dashboard(
    organization_id: str,
    fecha_corte: date | None = None,
) -> dict[str, Any]:
    """Pasivo vacaciones + alertas Art. 57/59 por organizacion."""
    try:
        return vacation_repo.org_dashboard(organization_id, fecha_corte=fecha_corte)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/organizations/{organization_id}/analytics/dashboard")
def analytics_dashboard(
    organization_id: str,
    fecha_inicio: date,
    fecha_fin: date,
    fecha_corte: date | None = None,
) -> dict[str, Any]:
    """Dashboard ejecutivo: KPIs, pasivos, costo planilla y proyeccion liquidaciones."""
    try:
        return analytics_repo.executive_dashboard(
            organization_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            fecha_corte=fecha_corte,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/organizations/{organization_id}/analytics/kpis")
def analytics_kpis(
    organization_id: str,
    fecha_inicio: date,
    fecha_fin: date,
) -> dict[str, Any]:
    """KPIs: rotacion, ausentismo y horas extras."""
    try:
        return analytics_repo.kpis(organization_id, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/organizations/{organization_id}/analytics/pasivos")
def analytics_pasivos(
    organization_id: str,
    fecha_corte: date | None = None,
) -> dict[str, Any]:
    """Pasivos laborales consolidados (vacaciones, decimo, prima, indemnizacion contingente)."""
    try:
        return analytics_repo.pasivos(organization_id, fecha_corte=fecha_corte)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/organizations/{organization_id}/analytics/liquidation-projection")
def analytics_liquidation_projection(
    organization_id: str,
    fecha_corte: date | None = None,
    causa: str | None = None,
) -> dict[str, Any]:
    """Proyeccion de liquidaciones por empleado activo."""
    try:
        return analytics_repo.liquidation_projection(
            organization_id, fecha_corte=fecha_corte, causa=causa
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/exports/sipe/{run_id}")
def export_sipe(run_id: str) -> dict[str, Any]:
    """Genera archivo SIPE (24 cols A-X) + conciliacion GT-08."""
    try:
        return export_repo.export_sipe(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/exports/sipe/{run_id}")
def get_sipe_export(run_id: str) -> dict[str, Any]:
    result = export_repo.get_sipe_export(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Export SIPE no encontrado")
    return result


@app.get("/api/v1/exports/sipe/{run_id}/download")
def download_sipe(run_id: str) -> FileResponse:
    record = export_repo.get_sipe_export(run_id)
    if not record or not record.get("archivo_path"):
        try:
            export_repo.export_sipe(run_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        record = export_repo.get_sipe_export(run_id)
    if not record or not record.get("archivo_path"):
        raise HTTPException(status_code=404, detail="Export SIPE no encontrado")
    path = export_repo.resolve_path(record["archivo_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo SIPE no encontrado")
    return FileResponse(path, media_type="text/plain", filename=f"sipe_{run_id}.txt")


@app.post("/api/v1/exports/dgi/{run_id}")
def export_dgi(run_id: str) -> dict[str, Any]:
    """Genera Formulario 03 DGI — retenciones ISR."""
    try:
        return export_repo.export_dgi(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/employees/{employee_id}/bank-account")
def upsert_bank_account(employee_id: str, body: BankAccountCreate) -> dict[str, str]:
    try:
        return integration_repo.upsert_bank_account(
            employee_id=employee_id,
            banco=body.banco,
            numero_cuenta=body.numero_cuenta,
            tipo_cuenta=body.tipo_cuenta,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/v1/exports/ach/{run_id}")
def export_ach(run_id: str, body: AchExportRequest | None = None) -> dict[str, Any]:
    """Genera archivo ACH parametrizable por banco."""
    banco = body.banco if body else "BANCO_GENERAL"
    try:
        return integration_repo.export_ach(run_id, banco=banco)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/exports/ach/{run_id}/download")
def download_ach(run_id: str) -> FileResponse:
    record = integration_repo.get_ach_export(run_id)
    if not record or not record.get("archivo_path"):
        raise HTTPException(status_code=404, detail="Export ACH no encontrado")
    path = export_repo.resolve_path(record["archivo_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo ACH no encontrado")
    return FileResponse(path, media_type="text/plain", filename=f"ach_{run_id}.txt")


@app.post("/api/v1/organizations/{organization_id}/integrations/odoo/employees/sync")
def sync_odoo_employees(organization_id: str, body: OdooEmployeeSyncRequest) -> dict[str, Any]:
    """Importa empleados desde payload estilo Odoo hr.employee."""
    try:
        return integration_repo.sync_odoo_employees(organization_id, body.employees)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/integrations/odoo/journal/{run_id}/push")
def odoo_journal_push(run_id: str) -> dict[str, Any]:
    """Push automático del asiento contable a Odoo (requiere ODOO_PUSH_URL + ODOO_API_KEY)."""
    from epayroll.integration.odoo_push import OdooPushError

    try:
        return integration_repo.push_odoo_journal(run_id)
    except OdooPushError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/integrations/odoo/journal/{run_id}")
def odoo_journal_entry(run_id: str) -> dict[str, Any]:
    """Genera asiento contable Odoo (JSON) desde corrida de planilla."""
    try:
        return integration_repo.build_odoo_journal(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/employees/{employee_id}/schedules")
def assign_schedule(employee_id: str, body: ScheduleAssignRequest) -> dict[str, str]:
    try:
        sid = attendance_repo.assign_schedule(
            employee_id=employee_id,
            shift_codigo=body.shift_codigo,
            fecha_inicio=body.fecha_inicio,
            fecha_fin=body.fecha_fin,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"schedule_id": sid}


@app.post("/api/v1/employees/{employee_id}/time-entries")
def create_time_entry(employee_id: str, body: TimeEntryCreate) -> dict[str, str]:
    try:
        eid = attendance_repo.create_time_entry(
            employee_id=employee_id,
            timestamp_entrada=body.timestamp_entrada,
            timestamp_salida=body.timestamp_salida,
            fuente=body.fuente,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"time_entry_id": eid}


@app.post("/api/v1/employees/{employee_id}/attendance/calculate")
def calculate_attendance(employee_id: str, body: AttendanceCalculateRequest) -> dict[str, Any]:
    try:
        summary = attendance_repo.calculate_period(
            employee_id=employee_id,
            fecha_inicio=body.fecha_inicio,
            fecha_fin=body.fecha_fin,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "dias_trabajados": str(summary.dias_trabajados),
        "horas_extra_diurnas": str(summary.horas_extra_diurnas),
        "horas_extra_nocturnas": str(summary.horas_extra_nocturnas),
        "horas_domingo": str(summary.horas_domingo),
        "horas_feriado": str(summary.horas_feriado),
        "days": attendance_repo.list_daily(employee_id, body.fecha_inicio, body.fecha_fin),
    }


@app.get("/api/v1/employees/{employee_id}/attendance")
def get_attendance(
    employee_id: str,
    fecha_inicio: date,
    fecha_fin: date,
) -> dict[str, Any]:
    try:
        summary = attendance_repo.get_period_summary(employee_id, fecha_inicio, fecha_fin)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "dias_trabajados": str(summary.dias_trabajados),
        "horas_extra_diurnas": str(summary.horas_extra_diurnas),
        "horas_extra_nocturnas": str(summary.horas_extra_nocturnas),
        "horas_domingo": str(summary.horas_domingo),
        "horas_feriado": str(summary.horas_feriado),
        "days": attendance_repo.list_daily(employee_id, fecha_inicio, fecha_fin),
    }


@app.post("/api/v1/employees/{employee_id}/incapacities")
def create_incapacity(employee_id: str, body: IncapacityCreate) -> dict[str, str]:
    """Registra incapacidad — Art. 200 / CSS."""
    try:
        return incapacity_repo.create(
            employee_id=employee_id,
            fecha_inicio=body.fecha_inicio,
            fecha_fin=body.fecha_fin,
            tipo=body.tipo,
            certificado_ref=body.certificado_ref,
            dias_subsidio_css=body.dias_subsidio_css,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/v1/employees/{employee_id}/incapacities")
def list_incapacities(employee_id: str) -> list[dict[str, Any]]:
    try:
        return incapacity_repo.list_for_employee(employee_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/employees/{employee_id}/license-fund/balance")
def license_fund_balance(employee_id: str, anio: int | None = None) -> dict[str, str]:
    """Saldo fondo licencia Art. 200 (12h / 26 jornadas)."""
    try:
        return incapacity_repo.get_license_fund_balance(employee_id, anio=anio)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/employees/{employee_id}/incapacities/period-impact")
def incapacity_period_impact(
    employee_id: str,
    body: IncapacityPeriodImpactRequest,
) -> dict[str, Any]:
    """Calcula impacto GT-10 en un período (días, pagos empleador/CSS)."""
    salario = body.salario_mensual
    if salario is None:
        contract = contracts_repo.get_active(employee_id)
        if not contract:
            raise HTTPException(status_code=400, detail="Sin contrato activo ni salario_mensual")
        salario = contract.salario_base
    try:
        return incapacity_repo.calculate_period_impact(
            employee_id=employee_id,
            fecha_inicio=body.fecha_inicio,
            fecha_fin=body.fecha_fin,
            salario_mensual=salario,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/v1/demo/setup")
def demo_setup() -> dict[str, Any]:
    """Crea empleado demo GT-01 si no existe (requiere seed en BD)."""
    existing = employees_repo.list_by_org(DEMO_ORG_ID)
    if existing:
        emp = existing[0]
        contract = contracts_repo.get_active(emp.id)
        return {
            "organization_id": DEMO_ORG_ID,
            "employee_id": emp.id,
            "contract_id": contract.id if contract else None,
            "message": "Demo ya existía",
        }
    emp = employees_repo.create(
        organization_id=DEMO_ORG_ID,
        cedula="8-888-8888",
        nombres="Juan",
        apellidos="Pérez Demo",
    )
    contract = contracts_repo.create(
        employee_id=emp.id,
        contract_type_codigo="INDEFINIDO",
        salario_base=Decimal("1800"),
        fecha_inicio=date(2026, 1, 1),
        forma_pago="QUINCENAL",
    )
    period_id = payroll_repo.create_period(
        organization_id=DEMO_ORG_ID,
        fecha_inicio=date(2026, 6, 1),
        fecha_fin=date(2026, 6, 15),
        fecha_pago=date(2026, 6, 16),
    )
    return {
        "organization_id": DEMO_ORG_ID,
        "employee_id": emp.id,
        "contract_id": contract.id,
        "payroll_period_id": period_id,
        "message": "Demo creado — ejecutar POST /api/v1/payroll/runs",
    }


@app.get("/")
def ui_redirect() -> RedirectResponse:
    return RedirectResponse(url="/app/", status_code=302)


if UI_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
