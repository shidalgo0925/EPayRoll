from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from epayroll.analytics.config import AnalyticsConfig, load_analytics_config
from epayroll.analytics.kpis import AbsenteeismMetrics, OvertimeMetrics, TurnoverMetrics
from epayroll.analytics.pasivos import PasivosConsolidados
from epayroll.engine.rounding import RoundingMode, round_amount


def _serialize_pasivos(pasivos: PasivosConsolidados) -> dict[str, Any]:
    return {
        "vacaciones": str(pasivos.vacaciones),
        "decimo_pendiente": str(pasivos.decimo_pendiente),
        "prima_antiguedad": str(pasivos.prima_antiguedad),
        "indemnizacion_contingente": str(pasivos.indemnizacion_contingente),
        "total": str(pasivos.total),
        "items": [
            {"concepto": i.concepto, "monto": str(i.monto), "detalle": i.detalle}
            for i in pasivos.items
        ],
    }


def _build_alerts(
    config: AnalyticsConfig,
    turnover: TurnoverMetrics,
    absenteeism: AbsenteeismMetrics,
    overtime: OvertimeMetrics,
    pasivos: PasivosConsolidados,
    employee_count: int,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    u = config.umbrales

    if turnover.tasa_rotacion_pct >= u.rotacion_pct_anual_alerta:
        alerts.append(
            {
                "tipo": "ROTACION",
                "nivel": "ALERTA",
                "mensaje": f"Tasa de rotacion {turnover.tasa_rotacion_pct}% supera umbral {u.rotacion_pct_anual_alerta}%",
            }
        )
    if absenteeism.tasa_ausentismo_pct >= u.ausentismo_pct_alerta:
        alerts.append(
            {
                "tipo": "AUSENTISMO",
                "nivel": "ALERTA",
                "mensaje": f"Ausentismo {absenteeism.tasa_ausentismo_pct}% supera umbral {u.ausentismo_pct_alerta}%",
            }
        )
    if overtime.horas_extra_promedio_empleado >= u.horas_extra_promedio_mes_alerta:
        alerts.append(
            {
                "tipo": "HORAS_EXTRA",
                "nivel": "ALERTA",
                "mensaje": (
                    f"Promedio horas extra {overtime.horas_extra_promedio_empleado} "
                    f"supera umbral {u.horas_extra_promedio_mes_alerta}"
                ),
            }
        )
    if employee_count > 0:
        pasivo_por_emp = pasivos.total / Decimal(str(employee_count))
        if pasivo_por_emp >= u.pasivo_por_empleado_alerta:
            alerts.append(
                {
                    "tipo": "PASIVO_LABORAL",
                    "nivel": "ALERTA",
                    "mensaje": (
                        f"Pasivo por empleado {round_amount(pasivo_por_emp, RoundingMode.CENTESIMO)} "
                        f"supera umbral {u.pasivo_por_empleado_alerta}"
                    ),
                }
            )
    return alerts


def build_executive_dashboard(
    organization_id: str,
    fecha_inicio: date,
    fecha_fin: date,
    fecha_corte: date,
    turnover: TurnoverMetrics,
    absenteeism: AbsenteeismMetrics,
    overtime: OvertimeMetrics,
    pasivos: PasivosConsolidados,
    payroll_cost: dict[str, Decimal],
    liquidation_projection: dict[str, Any],
    employee_count: int,
    config: AnalyticsConfig | None = None,
) -> dict[str, Any]:
    config = config or load_analytics_config()
    alerts = _build_alerts(config, turnover, absenteeism, overtime, pasivos, employee_count)

    return {
        "organization_id": organization_id,
        "periodo": {
            "fecha_inicio": fecha_inicio.isoformat(),
            "fecha_fin": fecha_fin.isoformat(),
            "fecha_corte": fecha_corte.isoformat(),
        },
        "headcount": {
            "activos": employee_count,
            "plantilla_inicio": turnover.plantilla_inicio,
            "plantilla_fin": turnover.plantilla_fin,
        },
        "kpis": {
            "rotacion": {
                "terminaciones": turnover.terminaciones,
                "promedio_plantilla": str(turnover.promedio_plantilla),
                "tasa_pct": str(turnover.tasa_rotacion_pct),
            },
            "ausentismo": {
                "dias_ausencia": str(absenteeism.dias_ausencia),
                "dias_programados": str(absenteeism.dias_programados),
                "tasa_pct": str(absenteeism.tasa_ausentismo_pct),
            },
            "horas_extra": {
                "total": str(overtime.horas_extra_total),
                "promedio_por_empleado": str(overtime.horas_extra_promedio_empleado),
                "empleados_con_extras": overtime.empleados_con_extras,
                "desglose": {
                    "diurna": str(overtime.horas_extra_diurna),
                    "nocturna": str(overtime.horas_extra_nocturna),
                    "domingo_feriado": str(overtime.horas_domingo_feriado),
                },
            },
        },
        "costo_planilla_periodo": {
            "bruto": str(payroll_cost.get("bruto", Decimal("0"))),
            "aportes_patronales": str(payroll_cost.get("aportes_patronales", Decimal("0"))),
            "neto": str(payroll_cost.get("neto", Decimal("0"))),
        },
        "pasivos_laborales": _serialize_pasivos(pasivos),
        "proyeccion_liquidaciones": liquidation_projection,
        "alertas": alerts,
        "umbrales": {
            "rotacion_pct": str(config.umbrales.rotacion_pct_anual_alerta),
            "ausentismo_pct": str(config.umbrales.ausentismo_pct_alerta),
            "horas_extra_promedio": str(config.umbrales.horas_extra_promedio_mes_alerta),
            "pasivo_por_empleado": str(config.umbrales.pasivo_por_empleado_alerta),
        },
    }
