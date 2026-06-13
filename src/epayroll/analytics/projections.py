from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from epayroll.engine.liquidation import LiquidationInput, run_liquidation
from epayroll.engine.rounding import RoundingMode, round_amount


@dataclass
class EmployeeProjectionInput:
    employee_id: str
    nombres: str
    apellidos: str
    fecha_inicio: date
    salario_mensual: Decimal
    dias_vacaciones_pendientes: Decimal
    salarios_acumulados_anio: Decimal


def project_liquidation(
    emp: EmployeeProjectionInput,
    fecha_corte: date,
    causa: str = "DESPIDO_INJUSTIFICADO",
) -> dict:
    inp = LiquidationInput(
        causa=causa,
        fecha_inicio=emp.fecha_inicio,
        fecha_terminacion=fecha_corte,
        salario_promedio_prima=emp.salario_mensual,
        dias_vacaciones_pendientes=emp.dias_vacaciones_pendientes,
        salarios_acumulados_anio=emp.salarios_acumulados_anio,
        cumplio_preaviso=True,
    )
    result = run_liquidation(inp)
    return {
        "employee_id": emp.employee_id,
        "nombre": f"{emp.nombres} {emp.apellidos}".strip(),
        "causa": causa,
        "fecha_corte": fecha_corte.isoformat(),
        "antiguedad_anios": result.config_snapshot.get("antiguedad_anios"),
        "vacaciones": str(result.amount("VACACIONES_LIQUIDACION")),
        "decimo": str(result.amount("DECIMO_PROPORCIONAL")),
        "prima": str(result.amount("PRIMA_ANTIGUEDAD")),
        "indemnizacion": str(result.amount("INDEMNIZACION")),
        "total": str(result.neto),
    }


def project_org_liquidations(
    employees: list[EmployeeProjectionInput],
    fecha_corte: date,
    causa: str = "DESPIDO_INJUSTIFICADO",
) -> dict:
    rows = [project_liquidation(emp, fecha_corte, causa=causa) for emp in employees]
    total = sum(Decimal(r["total"]) for r in rows)
    return {
        "fecha_corte": fecha_corte.isoformat(),
        "causa": causa,
        "employee_count": len(rows),
        "total_proyectado": str(round_amount(total, RoundingMode.CENTESIMO)),
        "employees": rows,
    }
