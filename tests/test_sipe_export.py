from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine
from epayroll.export.models import PayrollExportBundle, PayrollExportEmployee, PayrollExportPeriod
from epayroll.export.sipe import (
    build_sipe_rows,
    generate_sipe_export,
    load_sipe_template,
    reconcile_sipe,
    validate_sipe_rows,
)


def _employee_from_engine(salario: Decimal = Decimal("1800"), suffix: str = "1") -> PayrollExportEmployee:
    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=salario,
        dias_trabajados=Decimal("15"),
        es_quincena=True,
        mes=6,
        tasa_css_patronal=Decimal("0.1325"),
        tasa_riesgo_empresa=Decimal("0.0105"),
        tasa_prima_antiguedad_patronal=Decimal("0.0192"),
    )
    result = engine.run(inp)
    conceptos = {line.codigo_concepto: line.monto for line in result.lines}
    return PayrollExportEmployee(
        employee_id=f"emp-{suffix}",
        cedula=f"8-888-888{suffix}",
        nombres="Juan",
        apellidos=f"Perez {suffix}",
        bruto=result.bruto,
        neto=result.neto,
        aportes_patronales=result.aportes_patronales,
        conceptos=conceptos,
        dias_trabajados=Decimal("15"),
        fecha_ingreso=date(2026, 1, 1),
    )


def test_sipe_24_columnas():
    template = load_sipe_template()
    assert len(template.columnas) == 24
    assert template.columnas[0].letra == "A"
    assert template.columnas[-1].letra == "X"


def test_gt08_conciliacion_10_empleados(tmp_path: Path):
    """GT-08: conciliacion SIPE vs planilla interna."""
    employees = [_employee_from_engine(Decimal("1800"), str(i)) for i in range(10)]
    bundle = PayrollExportBundle(
        run_id="run-gt08",
        period=PayrollExportPeriod(
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 6, 15),
            ruc_empleador="1234567-1-123456",
        ),
        employees=employees,
    )

    rows = build_sipe_rows(bundle)
    assert len(rows) == 11
    assert len(rows[0]) == 24
    assert validate_sipe_rows(rows) == []

    recon = reconcile_sipe(bundle)
    assert recon.valido is True
    assert len(recon.checks) == 3
    assert all(c.ok for c in recon.checks)

    out = tmp_path / "sipe.txt"
    result = generate_sipe_export(bundle, out)
    assert result["valido"] is True
    assert result["row_count"] == 10
    assert out.exists()


def test_gt08_totales_cuadran():
    emp = _employee_from_engine()
    bundle = PayrollExportBundle(
        run_id="run-1",
        period=PayrollExportPeriod(date(2026, 6, 1), date(2026, 6, 15)),
        employees=[emp],
    )
    tot = bundle.totales
    assert tot["bruto"] == emp.bruto
    assert tot["css_empleado"] == emp.conceptos["CSS_EMPLEADO"]
    assert tot["aportes_patronales"] == emp.aportes_patronales
