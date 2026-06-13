from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class RoundingMode(str, Enum):
    CENTESIMO = "CENTESIMO"
    DECIMO = "DECIMO"
    ENTERO = "ENTERO"


def round_amount(value: Decimal, mode: RoundingMode = RoundingMode.CENTESIMO) -> Decimal:
    if mode == RoundingMode.CENTESIMO:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if mode == RoundingMode.DECIMO:
        return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
