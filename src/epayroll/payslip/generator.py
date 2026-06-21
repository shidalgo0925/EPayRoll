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
    employee_ficha: str = ""
    dias_pago: Decimal = Decimal("0")
    dias_trabajados: Decimal = Decimal("0")
    dias_descuento: Decimal = Decimal("0")
    monto_desc_dias: Decimal = Decimal("0")
    forma_pago: str = "QUINCENAL"
    numero_comprobante: str = ""


def _safe_text(value: str) -> str:
    return value.encode("latin-1", "replace").decode("latin-1")


def _money(value: Decimal) -> str:
    return f"B/. {value:,.2f}"


class ComprobantePDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, _safe_text(f"Comprobante generado por EPayRoll — Página {self.page_no()}"), align="C")


def _draw_section_title(pdf: FPDF, title: str) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(26, 46, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, _safe_text(f"  {title}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.set_text_color(0, 0, 0)


def _draw_money_row(pdf: FPDF, label: str, amount: Decimal, *, bold: bool = False) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", 10)
    pdf.cell(130, 7, _safe_text(label))
    pdf.cell(0, 7, _money(amount), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")


def generate_payslip_pdf(data: PayslipData, output_path: Path) -> Path:
    """Genera comprobante de pago PDF para un empleado."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = ComprobantePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(26, 46, 80)
    pdf.cell(0, 10, _safe_text("COMPROBANTE DE PAGO"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 6, _safe_text(data.organization_nombre), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    ref = data.numero_comprobante or data.run_id[:8].upper()
    pdf.cell(
        0,
        5,
        _safe_text(
            f"No. {ref}  |  Periodo {data.periodo_inicio.isoformat()} al {data.periodo_fin.isoformat()}"
            f"  |  Pago {data.fecha_pago.isoformat()}"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(5)

    _draw_section_title(pdf, "DATOS DEL EMPLEADO")
    pdf.set_font("Helvetica", "", 10)
    if data.employee_ficha:
        pdf.cell(0, 6, _safe_text(f"Ficha: {data.employee_ficha}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, _safe_text(f"Nombre: {data.employee_nombre}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, _safe_text(f"Cédula: {data.employee_cedula}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 6, _safe_text(f"Forma de pago: {data.forma_pago}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if data.dias_pago > 0:
        pdf.cell(
            0,
            6,
            _safe_text(
                f"Días de pago: {data.dias_pago}  |  Días efectivos: {data.dias_trabajados}"
                + (f"  |  Días descontados: {data.dias_descuento}" if data.dias_descuento > 0 else "")
            ),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    if data.monto_desc_dias > 0:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(
            0,
            5,
            _safe_text(
                f"Descuento por ausencia/vacación ({data.dias_descuento} día(s)): {_money(data.monto_desc_dias)}"
                " — ya reflejado en el salario devengado."
            ),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.set_font("Helvetica", "", 10)
    pdf.ln(3)

    ingresos = [l for l in data.lines if l.tipo == "INGRESO"]
    descuentos = [l for l in data.lines if l.tipo == "DESCUENTO"]

    _draw_section_title(pdf, "INGRESOS DEVENGADOS")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(130, 6, _safe_text("Concepto"))
    pdf.cell(0, 6, _safe_text("Monto"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.set_font("Helvetica", "", 9)
    for line in ingresos:
        pdf.cell(130, 6, _safe_text(line.descripcion or line.concepto))
        pdf.cell(0, 6, _money(line.monto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    if not ingresos:
        pdf.cell(0, 6, _safe_text("— Sin ingresos —"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    _draw_section_title(pdf, "DEDUCCIONES")
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(130, 6, _safe_text("Concepto"))
    pdf.cell(0, 6, _safe_text("Monto"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    pdf.set_font("Helvetica", "", 9)
    for line in descuentos:
        pdf.cell(130, 6, _safe_text(line.descripcion or line.concepto))
        pdf.cell(0, 6, _money(line.monto), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
    if not descuentos:
        pdf.cell(0, 6, _safe_text("— Sin deducciones —"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    _draw_section_title(pdf, "RESUMEN")
    _draw_money_row(pdf, "Total ingresos (bruto)", data.bruto)
    _draw_money_row(pdf, "Total deducciones", data.deducciones)
    pdf.ln(1)
    pdf.set_draw_color(26, 46, 80)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    _draw_money_row(pdf, "NETO A PAGAR", data.neto, bold=True)

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        4,
        _safe_text(
            "Este documento es un comprobante de pago de planilla. "
            "Conserve este comprobante para sus registros. "
            "No constituye cheque ni orden de pago bancaria."
        ),
    )

    pdf.output(str(output_path))
    return output_path
