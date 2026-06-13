from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    cedula: str
    nombres: str
    apellidos: str
    email: str | None = None


class EmployeeResponse(BaseModel):
    id: str
    organization_id: str
    cedula: str
    nombres: str
    apellidos: str
    activo: bool


class ContractCreate(BaseModel):
    contract_type_codigo: str = "INDEFINIDO"
    salario_base: Decimal
    fecha_inicio: date
    forma_pago: str = "QUINCENAL"


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


class HealthResponse(BaseModel):
    status: str
    version: str


class MessageResponse(BaseModel):
    detail: str
