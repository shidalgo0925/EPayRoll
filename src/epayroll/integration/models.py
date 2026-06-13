from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BankAccountInfo:
    banco: str
    tipo_cuenta: str
    numero_cuenta: str


@dataclass
class AchPaymentRow:
    secuencia: int
    employee_id: str
    cedula: str
    nombre_completo: str
    neto: Decimal
    tipo_cuenta: str
    numero_cuenta: str
    referencia: str
