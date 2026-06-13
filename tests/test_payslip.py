from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from epayroll.payslip.generator import PayslipData, PayslipLine, generate_payslip_pdf


def test_generate_payslip_pdf(tmp_path: Path) -> None:
    data = PayslipData(
        run_id="run-1",
        employee_id="emp-1",
        employee_nombre="Juan Perez",
        employee_cedula="8-888-8888",
        organization_nombre="Demo Corp SA",
        periodo_inicio=date(2026, 6, 1),
        periodo_fin=date(2026, 6, 15),
        fecha_pago=date(2026, 6, 16),
        bruto=Decimal("900.00"),
        deducciones=Decimal("192.00"),
        neto=Decimal("708.00"),
        lines=[
            PayslipLine("SALARIO_BASE", "Salario base", "INGRESO", Decimal("900.00")),
            PayslipLine("CSS_EMPLEADO", "Cuota CSS", "DESCUENTO", Decimal("87.75")),
            PayslipLine("SE_EMPLEADO", "Seguro Educativo", "DESCUENTO", Decimal("11.25")),
            PayslipLine("ISR", "Retencion ISR", "DESCUENTO", Decimal("93.00")),
        ],
    )
    out = tmp_path / "recibo.pdf"
    generate_payslip_pdf(data, out)

    assert out.exists()
    assert out.stat().st_size > 500
    content = out.read_bytes()
    assert content.startswith(b"%PDF")
