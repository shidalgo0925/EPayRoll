from __future__ import annotations

from datetime import date
from decimal import Decimal

from epayroll.analytics.config import load_analytics_config
from epayroll.analytics.dashboard import build_executive_dashboard
from epayroll.analytics.kpis import calc_absenteeism, calc_overtime, calc_turnover
from epayroll.analytics.pasivos import consolidate_pasivos, estimate_prima_total
from epayroll.analytics.projections import EmployeeProjectionInput, project_liquidation, project_org_liquidations


def test_turnover_rate():
    m = calc_turnover(terminaciones=2, plantilla_inicio=10, plantilla_fin=10)
    assert m.tasa_rotacion_pct == Decimal("20.00")
    assert m.promedio_plantilla == Decimal("10.00")


def test_absenteeism_rate():
    m = calc_absenteeism(dias_ausencia=Decimal("11"), dias_programados=Decimal("220"))
    assert m.tasa_ausentismo_pct == Decimal("5.00")


def test_overtime_aggregation():
    rows = [
        {
            "horas_extra_diurna": Decimal("5"),
            "horas_extra_nocturna": Decimal("2"),
            "horas_extra_mixta_noct": Decimal("0"),
            "horas_domingo": Decimal("4"),
            "horas_feriado": Decimal("0"),
        },
        {
            "horas_extra_diurna": Decimal("0"),
            "horas_extra_nocturna": Decimal("0"),
            "horas_extra_mixta_noct": Decimal("0"),
            "horas_domingo": Decimal("0"),
            "horas_feriado": Decimal("0"),
        },
    ]
    m = calc_overtime(rows, empleados_activos=5)
    assert m.horas_extra_total == Decimal("11.00")
    assert m.empleados_con_extras == 1
    assert m.horas_extra_promedio_empleado == Decimal("2.20")


def test_consolidate_pasivos():
    p = consolidate_pasivos(
        vacaciones=Decimal("10000"),
        decimo_pendiente=Decimal("5000"),
        prima_antiguedad=Decimal("8000"),
        indemnizacion_contingente=Decimal("15000"),
    )
    assert p.total == Decimal("38000.00")
    assert len(p.items) == 4


def test_prima_estimate():
    employees = [
        {
            "fecha_inicio": date(2020, 1, 1),
            "salario_mensual": Decimal("2000"),
        }
    ]
    total = estimate_prima_total(employees, date(2025, 6, 1))
    assert total > Decimal("0")


def test_liquidation_projection():
    emp = EmployeeProjectionInput(
        employee_id="emp-1",
        nombres="Juan",
        apellidos="Perez",
        fecha_inicio=date(2020, 6, 1),
        salario_mensual=Decimal("2000"),
        dias_vacaciones_pendientes=Decimal("10"),
        salarios_acumulados_anio=Decimal("6000"),
    )
    row = project_liquidation(emp, date(2025, 6, 1))
    assert Decimal(row["total"]) > Decimal("0")
    assert row["causa"] == "DESPIDO_INJUSTIFICADO"


def test_org_liquidation_projection():
    employees = [
        EmployeeProjectionInput(
            employee_id="emp-1",
            nombres="A",
            apellidos="Uno",
            fecha_inicio=date(2020, 1, 1),
            salario_mensual=Decimal("1800"),
            dias_vacaciones_pendientes=Decimal("5"),
            salarios_acumulados_anio=Decimal("4500"),
        ),
        EmployeeProjectionInput(
            employee_id="emp-2",
            nombres="B",
            apellidos="Dos",
            fecha_inicio=date(2021, 1, 1),
            salario_mensual=Decimal("1500"),
            dias_vacaciones_pendientes=Decimal("0"),
            salarios_acumulados_anio=Decimal("3000"),
        ),
    ]
    result = project_org_liquidations(employees, date(2025, 6, 1))
    assert result["employee_count"] == 2
    assert Decimal(result["total_proyectado"]) > Decimal("0")


def test_executive_dashboard_alerts():
    config = load_analytics_config()
    turnover = calc_turnover(5, 10, 10)
    absenteeism = calc_absenteeism(Decimal("20"), Decimal("200"))
    overtime = calc_overtime(
        [{"horas_extra_diurna": Decimal("150"), "horas_extra_nocturna": Decimal("0"),
          "horas_extra_mixta_noct": Decimal("0"), "horas_domingo": Decimal("0"),
          "horas_feriado": Decimal("0")}],
        empleados_activos=5,
    )
    pasivos = consolidate_pasivos(
        Decimal("30000"), Decimal("10000"), Decimal("20000"), Decimal("50000")
    )
    dash = build_executive_dashboard(
        organization_id="org-1",
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=date(2026, 6, 30),
        fecha_corte=date(2026, 6, 30),
        turnover=turnover,
        absenteeism=absenteeism,
        overtime=overtime,
        pasivos=pasivos,
        payroll_cost={"bruto": Decimal("50000"), "aportes_patronales": Decimal("7000"), "neto": Decimal("40000")},
        liquidation_projection={"total_proyectado": "100000", "employee_count": 5},
        employee_count=5,
        config=config,
    )
    tipos = {a["tipo"] for a in dash["alertas"]}
    assert "ROTACION" in tipos
    assert "AUSENTISMO" in tipos
    assert "HORAS_EXTRA" in tipos
    assert "PASIVO_LABORAL" in tipos
