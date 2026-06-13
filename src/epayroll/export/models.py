from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class PayrollExportEmployee:
    employee_id: str
    cedula: str
    nombres: str
    apellidos: str
    bruto: Decimal
    neto: Decimal
    aportes_patronales: Decimal
    conceptos: dict[str, Decimal] = field(default_factory=dict)
    dias_trabajados: Decimal = Decimal("0")
    fecha_ingreso: date | None = None


@dataclass
class PayrollExportPeriod:
    fecha_inicio: date
    fecha_fin: date
    fecha_pago: date | None = None
    ruc_empleador: str = ""


@dataclass
class PayrollExportBundle:
    run_id: str
    period: PayrollExportPeriod
    employees: list[PayrollExportEmployee]

    @property
    def totales(self) -> dict[str, Decimal]:
        bruto = sum((e.bruto for e in self.employees), Decimal("0"))
        css_empleado = sum((e.conceptos.get("CSS_EMPLEADO", Decimal("0")) for e in self.employees), Decimal("0"))
        css_patronal = sum((e.conceptos.get("CSS_EMPLEADOR", Decimal("0")) for e in self.employees), Decimal("0"))
        riesgo = sum((e.conceptos.get("RIESGO_PROFESIONAL", Decimal("0")) for e in self.employees), Decimal("0"))
        prima = sum((e.conceptos.get("PRIMA_ANTIGUEDAD_PATRONAL", Decimal("0")) for e in self.employees), Decimal("0"))
        aportes = sum((e.aportes_patronales for e in self.employees), Decimal("0"))
        isr = sum((e.conceptos.get("ISR", Decimal("0")) for e in self.employees), Decimal("0"))
        return {
            "bruto": bruto,
            "css_empleado": css_empleado,
            "css_patronal": css_patronal,
            "riesgo": riesgo,
            "prima": prima,
            "aportes_patronales": aportes,
            "isr": isr,
        }

    def concept_amount(self, employee: PayrollExportEmployee, codigo: str) -> Decimal:
        return employee.conceptos.get(codigo, Decimal("0"))

    def horas_extras_total(self, employee: PayrollExportEmployee) -> Decimal:
        codes = (
            "HORA_EXTRA_DIURNA",
            "HORA_EXTRA_NOCTURNA",
            "HORA_EXTRA_MIXTA_NOCTURNA",
        )
        return sum((employee.conceptos.get(c, Decimal("0")) for c in codes), Decimal("0"))
