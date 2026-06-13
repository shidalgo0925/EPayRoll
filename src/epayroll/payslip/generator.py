from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos


@dataclass
class PayslipLine:
    concepto: str
    descripcion: str
    tipo: str
    monto: Decimal


@dataclass
class PayslipData:
    run_id: str
    employee_id: str
    employee_nombre: str
    employee_cedula: str
    organization_nombre: str
    periodo_inicio: date
    periodo_fin: date
    fecha_pago: date
    bruto: Decimal
    deducciones: Decimal
    neto: Decimal
    lines: list[PayslipLine]


def _safe_text(value: str) -> str:
    return value.encode("latin-1", "replace").decode("latin-1")


def _money(value: Decimal) -> str:
    return f"B/. {value:,.2f}"


class PayslipPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, _safe_text(f"Pagina {self.page_no()}"), align="C")


def generate_payslip_pdf(data: PayslipData, output_path: Path) -> Path:
    """Genera recibo PDF de pago para un empleado."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = PayslipPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, _safe_text("EPayRoll - Recibo de Pago"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, _safe_text(data.organization_nombre), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(
        0,
        7,
        _safe_text(
            f"Periodo: {data.periodo_inicio.isoformat()} al {data.periodo_fin.isoformat()}"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.cell(0, 7, _safe_text(f"Fecha de pago: {data.fecha_pago.isoformat()}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _safe_text("Empleado"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, _safe_text(f"Nombre: {data.employee_nombre}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, _safe_text(f"Cedula: {data.employee_cedula}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    ingresos = [l for l in data.lines if l.tipo == "INGRESO"]
    descuentos = [l for l in data.lines if l.tipo == "DESCUENTO"]

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _safe_text("Ingresos"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    for line in ingresos:
        pdf.cell(120, 6, _safe_text(line.descripcion or line.concepto))
        pdf.cell(0, 6, _money(line.monto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, _safe_text("Descuentos"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    for line in descuentos:
        pdf.cell(120, 6, _safe_text(line.descripcion or line.concepto))
        pdf.cell(0, 6, _money(line.monto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(120, 7, _safe_text("Bruto"))
    pdf.cell(0, 7, _money(data.bruto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.cell(120, 7, _safe_text("Total descuentos"))
    pdf.cell(0, 7, _money(data.deducciones), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.cell(120, 7, _safe_text("Neto a pagar"))
    pdf.cell(0, 7, _money(data.neto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    pdf.output(str(output_path))
    return output_path
