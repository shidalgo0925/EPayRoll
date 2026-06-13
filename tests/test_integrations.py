from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine
from epayroll.export.models import PayrollExportBundle, PayrollExportEmployee, PayrollExportPeriod
from epayroll.integration.ach import generate_ach_export, load_ach_template
from epayroll.integration.models import BankAccountInfo
from epayroll.integration.odoo import build_journal_entry, parse_odoo_employees


def _bundle_with_one_employee() -> PayrollExportBundle:
    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=Decimal("1800"),
        dias_trabajados=Decimal("15"),
        es_quincena=True,
        mes=6,
        tasa_css_patronal=Decimal("0.1325"),
        tasa_riesgo_empresa=Decimal("0.0105"),
        tasa_prima_antiguedad_patronal=Decimal("0.0192"),
    )
    result = engine.run(inp)
    conceptos = {line.codigo_concepto: line.monto for line in result.lines}
    emp = PayrollExportEmployee(
        employee_id="emp-1",
        cedula="8-888-8888",
        nombres="Juan",
        apellidos="Perez",
        bruto=result.bruto,
        neto=result.neto,
        aportes_patronales=result.aportes_patronales,
        conceptos=conceptos,
    )
    return PayrollExportBundle(
        run_id="run-ach",
        period=PayrollExportPeriod(
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 6, 15),
            fecha_pago=date(2026, 6, 16),
        ),
        employees=[emp],
    )


def test_ach_template_loads():
    tpl = load_ach_template("BANCO_GENERAL")
    assert tpl.banco == "BANCO_GENERAL"
    assert len(tpl.columnas) >= 7


def test_ach_export_generates_file(tmp_path: Path):
    bundle = _bundle_with_one_employee()
    accounts = {
        "emp-1": BankAccountInfo(
            banco="BANCO_GENERAL",
            tipo_cuenta="AHORROS",
            numero_cuenta="04123456789012345678",
        )
    }
    out = tmp_path / "ach.txt"
    result = generate_ach_export(bundle, accounts, out, banco="BANCO_GENERAL")
    assert result["valido"] is True
    assert result["payment_count"] == 1
    assert out.exists()
    rows = out.read_text(encoding="utf-8").strip().split("\n")
    assert len(rows) == 2


def test_ach_validation_rejects_missing_account():
    bundle = _bundle_with_one_employee()
    from epayroll.integration.ach import build_ach_rows

    try:
        build_ach_rows(bundle, {})
        assert False, "expected ValueError"
    except ValueError as e:
        assert "cuenta bancaria" in str(e)


def test_odoo_parse_employees():
    payload = [
        {
            "id": 42,
            "name": "Maria Lopez",
            "identification_id": "8-123-4567",
            "work_email": "maria@corp.com",
            "wage": 2000,
            "contract_date_start": "2026-01-15",
        }
    ]
    rows = parse_odoo_employees(payload)
    assert rows[0]["cedula"] == "8-123-4567"
    assert rows[0]["salario_base"] == Decimal("2000")
    assert rows[0]["odoo_id"] == 42


def test_odoo_journal_balanced():
    bundle = _bundle_with_one_employee()
    entry = build_journal_entry(bundle)
    assert entry["balanced"] is True
    assert Decimal(entry["total_debit"]) == Decimal(entry["total_credit"])
    assert len(entry["lines"]) > 0
