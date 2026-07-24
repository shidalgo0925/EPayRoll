from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from epayroll.engine.liquidation import causa_label


def _safe_text(value: str) -> str:
    return value.encode("latin-1", "replace").decode("latin-1")


def _money(value: Any) -> str:
    dec = Decimal(str(value or "0"))
    return f"B/. {dec:,.2f}"


class LiquidacionPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(
            0,
            10,
            _safe_text(f"Liquidacion EPayRoll — Pagina {self.page_no()}"),
            align="C",
        )


def generate_liquidation_pdf(data: dict[str, Any], output: Path | BinaryIO) -> None:
    """Genera PDF de liquidacion laboral (Art. 210)."""
    pdf = LiquidacionPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(26, 46, 80)
    pdf.cell(
        0,
        10,
        _safe_text("LIQUIDACION LABORAL"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(
        0,
        6,
        _safe_text(data.get("organization_nombre") or ""),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="C",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    nombre = f"{data.get('nombres', '')} {data.get('apellidos', '')}".strip()
    pdf.cell(0, 6, _safe_text(f"Empleado: {nombre}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if data.get("cedula"):
        pdf.cell(
            0, 6, _safe_text(f"Cedula: {data['cedula']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
    causa = data.get("causa_label") or causa_label(data.get("causa") or "")
    pdf.cell(0, 6, _safe_text(f"Causa: {causa}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if data.get("regimen_indemnizacion"):
        pdf.cell(
            0,
            6,
            _safe_text(f"Regimen indemnizacion: escala {data['regimen_indemnizacion']}"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    if data.get("tipo_contrato"):
        pdf.cell(
            0,
            6,
            _safe_text(f"Tipo contrato: {data['tipo_contrato']}"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    pdf.cell(
        0,
        6,
        _safe_text(f"Fecha terminacion: {data.get('fecha_terminacion', '—')}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    if data.get("case_id"):
        pdf.cell(
            0, 6, _safe_text(f"Caso: {data['case_id']}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
    if data.get("documento_ref"):
        pdf.cell(
            0,
            6,
            _safe_text(f"Documento: {data['documento_ref']}"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    if data.get("notas"):
        pdf.multi_cell(0, 6, _safe_text(f"Notas: {data['notas']}"))
    pdf.ln(4)

    rows = [
        ("Salario pendiente", data.get("monto_salario_pendiente")),
        ("Vacaciones pendientes", data.get("monto_vacaciones")),
        ("Decimo proporcional", data.get("monto_decimo")),
        ("Prima de antiguedad", data.get("monto_prima")),
        ("Preaviso (deduccion)", data.get("monto_preaviso")),
        ("Indemnizacion", data.get("monto_indemnizacion")),
    ]
    lines = data.get("lines") or []
    if lines:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(26, 46, 80)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(130, 7, _safe_text("  Concepto"), fill=True)
        pdf.cell(
            0, 7, _safe_text("Monto"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R", fill=True
        )
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
        for line in lines:
            label = line.get("concepto") or line.get("descripcion") or "—"
            pdf.cell(130, 7, _safe_text(label))
            pdf.cell(
                0,
                7,
                _money(line.get("monto")),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="R",
            )
    else:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(130, 7, _safe_text("Concepto"))
        pdf.cell(0, 7, _safe_text("Monto"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        pdf.set_font("Helvetica", "", 10)
        for label, amount in rows:
            pdf.cell(130, 7, _safe_text(label))
            pdf.cell(0, 7, _money(amount), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    pdf.ln(3)
    pdf.set_draw_color(26, 46, 80)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    total = data.get("total") or data.get("neto") or "0"
    pdf.cell(130, 8, _safe_text("TOTAL NETO A PAGAR"))
    pdf.cell(0, 8, _money(total), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        4,
        _safe_text(
            "Documento informativo de liquidacion laboral (Art. 210 CT / GT-05/GT-06). "
            "Validar montos con contador antes de pago."
        ),
    )

    if isinstance(output, Path):
        output.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(output))
    else:
        pdf.output(output)


def liquidation_pdf_bytes(data: dict[str, Any]) -> bytes:
    buf = BytesIO()
    generate_liquidation_pdf(data, buf)
    return buf.getvalue()
