from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)
    organization_id: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    tenant_nombre: str | None = None
    organization_id: str | None = None
    user_id: str
    email: str
    expires_in_hours: int = 8
    organizations: list["OrganizationSummary"] = Field(default_factory=list)


class OrganizationSummary(BaseModel):
    id: str
    tenant_id: str
    razon_social: str
    ruc: str | None = None
    periodo_pago: str = "QUINCENAL"
    moneda: str = "PAB"
    zona_horaria: str = "America/Panama"


class OrganizationCreate(BaseModel):
    razon_social: str = Field(min_length=2, max_length=255)
    ruc: str | None = Field(default=None, max_length=50)
    periodo_pago: str = Field(default="QUINCENAL", pattern="^(MENSUAL|QUINCENAL|SEMANAL|HORA)$")


class OrganizationUpdate(BaseModel):
    razon_social: str | None = Field(default=None, min_length=2, max_length=255)
    ruc: str | None = Field(default=None, max_length=50)
    periodo_pago: str | None = Field(default=None, pattern="^(MENSUAL|QUINCENAL|SEMANAL|HORA)$")
    moneda: str | None = Field(default=None, min_length=3, max_length=3)
    zona_horaria: str | None = Field(default=None, min_length=3, max_length=64)


class OrganizationResponse(BaseModel):
    id: str
    tenant_id: str
    razon_social: str
    ruc: str | None = None
    activo: bool = True
    periodo_pago: str = "QUINCENAL"
    moneda: str = "PAB"
    zona_horaria: str = "America/Panama"


class UserMembershipInput(BaseModel):
    organization_id: str
    roles: list[str] = Field(default_factory=lambda: ["payroll_admin"])


class UserMembershipResponse(BaseModel):
    organization_id: str
    razon_social: str
    roles: list[str] = Field(default_factory=list)
    activo: bool = True


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)
    nombres: str | None = Field(default=None, max_length=255)
    is_superuser: bool = False
    memberships: list[UserMembershipInput] = Field(default_factory=list)


class UserUpdate(BaseModel):
    nombres: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=256)
    activo: bool | None = None
    is_superuser: bool | None = None
    memberships: list[UserMembershipInput] | None = None


class UserResponse(BaseModel):
    id: str
    tenant_id: str
    email: str
    nombres: str | None = None
    activo: bool = True
    is_superuser: bool = False
    protected: bool = False
    memberships: list[UserMembershipResponse] = Field(default_factory=list)


class RoleOption(BaseModel):
    id: str
    label: str


class SsoConfigResponse(BaseModel):
    enabled: bool
    authorize_url: str | None = None
    client_id: str | None = None
    redirect_uri: str | None = None
    scopes: str | None = None


class SsoExchangeRequest(BaseModel):
    code: str
    redirect_uri: str | None = None


class SsoTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int | None = None
    refresh_token: str | None = None


class SsoRefreshRequest(BaseModel):
    refresh_token: str


class EmployeeCreate(BaseModel):
    cedula: str
    nombres: str
    apellidos: str
    email: str | None = None
    ficha: str | None = None
    telefono: str | None = None
    fecha_nacimiento: date | None = None
    estado_civil: str | None = None
    direccion: str | None = None


class EmployeeUpdate(BaseModel):
    cedula: str | None = None
    nombres: str | None = None
    apellidos: str | None = None
    email: str | None = None
    ficha: str | None = None
    telefono: str | None = None
    fecha_nacimiento: date | None = None
    estado_civil: str | None = None
    direccion: str | None = None


class EmployeeResponse(BaseModel):
    id: str
    organization_id: str
    cedula: str
    nombres: str
    apellidos: str
    email: str | None = None
    ficha: str | None = None
    telefono: str | None = None
    fecha_nacimiento: date | None = None
    estado_civil: str | None = None
    direccion: str | None = None
    activo: bool
    salario_base: Decimal | None = None
    salario_quincenal: Decimal | None = None
    forma_pago: str | None = None
    fecha_inicio_contrato: date | None = None
    contract_type_codigo: str | None = None
    banco: str | None = None
    cuenta_bancaria: str | None = None


class EmployeeCloneFromRequest(BaseModel):
    """Empresa origen desde la cual copiar empleados activos."""

    source_organization_id: str


class EmployeeCloneItem(BaseModel):
    source_employee_id: str
    new_employee_id: str
    cedula: str
    nombres: str
    apellidos: str


class EmployeeCloneSkipped(BaseModel):
    source_employee_id: str
    cedula: str
    nombres: str
    apellidos: str
    reason: str


class EmployeeCloneResponse(BaseModel):
    source_organization_id: str
    target_organization_id: str
    cloned_count: int
    skipped_count: int
    cloned: list[EmployeeCloneItem]
    skipped: list[EmployeeCloneSkipped]


class ContractCreate(BaseModel):
    contract_type_codigo: str = "INDEFINIDO"
    salario_base: Decimal
    fecha_inicio: date
    forma_pago: str = "QUINCENAL"
    categoria_salario_minimo: str | None = None


class ContractResponse(BaseModel):
    id: str
    employee_id: str
    contract_type_codigo: str
    salario_base: Decimal
    forma_pago: str
    estado: str


class PayrollPeriodCreate(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    fecha_pago: date
    tipo: str = "QUINCENAL"


class PayrollPeriodUpdate(BaseModel):
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    fecha_pago: date | None = None
    tipo: str | None = None


class PeriodCloseRequest(BaseModel):
    run_id: str | None = None


class PayrollPeriodRunRequest(BaseModel):
    employee_ids: list[str] | None = None
    use_attendance: bool = False
    dias_trabajados: Decimal = Field(default=Decimal("15"))
    es_quincena: bool | None = None
    mes: int | None = Field(default=None, ge=1, le=12)
    descuento_voluntario: Decimal = Decimal("0")


class DecimoRunCreate(BaseModel):
    payroll_period_id: str
    employee_id: str
    salarios_cotizables: Decimal | None = None
    trimestre: int | None = Field(default=None, ge=1, le=3)
    anio: int | None = None


class PayrollRunCreate(BaseModel):
    payroll_period_id: str
    employee_id: str
    use_attendance: bool = False
    dias_trabajados: Decimal = Field(default=Decimal("15"))
    es_quincena: bool = True
    mes: int = Field(default=6, ge=1, le=12)
    horas_extra_diurnas: Decimal = Decimal("0")
    horas_extra_nocturnas: Decimal = Decimal("0")
    horas_extra_mixta_nocturnas: Decimal = Decimal("0")
    horas_domingo: Decimal = Decimal("0")
    horas_feriado: Decimal = Decimal("0")
    descuento_voluntario: Decimal = Decimal("0")


class TerminationCalculateRequest(BaseModel):
    causa: str = "RENUNCIA"
    fecha_terminacion: date
    fecha_inicio: date | None = None
    salario_promedio_prima: Decimal | None = None
    dias_vacaciones_pendientes: Decimal = Decimal("0")
    salario_diario_vacaciones: Decimal | None = None
    salarios_acumulados_anio: Decimal = Decimal("0")
    salario_promedio_indemnizacion: Decimal | None = None
    cumplio_preaviso: bool = True
    persist: bool = False


class VacationRequestCreate(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    dias_solicitados: Decimal


class VacationRequestUpdate(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    dias_solicitados: Decimal


class VacationApproveRequest(BaseModel):
    substitute_employee_id: str | None = None
    aprobado_por: str | None = None


class VacationSubstituteAssign(BaseModel):
    substitute_employee_id: str


class VacationAccrueRequest(BaseModel):
    fecha_corte: date | None = None


class BankAccountCreate(BaseModel):
    banco: str = "BANCO_GENERAL"
    numero_cuenta: str
    tipo_cuenta: str = "AHORROS"


class AchExportRequest(BaseModel):
    banco: str = "BANCO_GENERAL"


class OdooEmployeeSyncRequest(BaseModel):
    employees: list[dict[str, Any]]


class ScheduleAssignRequest(BaseModel):
    shift_codigo: str = "DIURNO"
    fecha_inicio: date
    fecha_fin: date | None = None


class TimeEntryCreate(BaseModel):
    timestamp_entrada: datetime
    timestamp_salida: datetime
    fuente: str = "MANUAL"


class AttendanceCalculateRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date


class AttendanceFactCreate(BaseModel):
    cedula: str | None = None
    employee_id: str | None = None
    fecha: date
    turno: str | None = "DIURNO"
    hora_entrada: str | None = None
    hora_salida: str | None = None
    descanso_minutos: int = 60
    tipo_dia: str = "NORMAL"
    ausencia: bool = False
    incapacidad: bool = False
    vacaciones: bool = False
    observacion: str | None = None
    fuente: str = "MANUAL"


class AttendanceFactsImportRequest(BaseModel):
    csv_content: str
    fuente: str = "CSV"
    nombre_archivo: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None


class AttendanceFactsBulkRequest(BaseModel):
    facts: list[AttendanceFactCreate]
    fuente: str = "API"


class AttendanceGridSaveRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    facts: list[AttendanceFactCreate]
    fuente: str = "MANUAL"


class AttendancePeriodProcessRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    run_id: str | None = None


class AttendancePeriodOvertimeRow(BaseModel):
    employee_id: str
    horas_extra_diurnas: Decimal = Decimal("0")
    horas_extra_nocturnas: Decimal = Decimal("0")
    horas_extra_mixta_nocturnas: Decimal = Decimal("0")
    horas_domingo: Decimal = Decimal("0")
    horas_feriado: Decimal = Decimal("0")


class AttendancePeriodOvertimeSaveRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    rows: list[AttendancePeriodOvertimeRow]


class IncapacityCreate(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo: str = "CSS"
    certificado_ref: str | None = None
    dias_subsidio_css: int | None = None


class IncapacityUpdate(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo: str = "CSS"
    certificado_ref: str | None = None
    dias_subsidio_css: int | None = None


class IncapacityPeriodImpactRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    salario_mensual: Decimal | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


class MessageResponse(BaseModel):
    detail: str


class LegalRateUpsert(BaseModel):
    codigo: str
    descripcion: str | None = None
    porcentaje_empleado: Decimal | None = None
    porcentaje_empleador: Decimal | None = None
    vigencia_desde: date | None = None


class AccountCodeUpsert(BaseModel):
    concepto_codigo: str
    cuenta_codigo: str
    etiqueta: str | None = None


class PayrollAdjustmentUpdate(BaseModel):
    dias_trabajados: Decimal | None = None
    dias_descuento: Decimal = Decimal("0")
    monto_desc_dias: Decimal = Decimal("0")
    dev_isr: Decimal = Decimal("0")
    prestamo_empleado: Decimal = Decimal("0")
    desc_prestamo: Decimal = Decimal("0")
    descuento_banco: Decimal = Decimal("0")
    saldo_prestamo: Decimal = Decimal("0")
    notas: str | None = None
