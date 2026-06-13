"""GT-07 — validación salario mínimo legal."""

from __future__ import annotations

from decimal import Decimal

import pytest

from epayroll.compliance.minimum_wage import MinimumWageError, get_minimum_wage, validate_salary_base


def test_minimum_wage_category_loads():
    cat = get_minimum_wage("DEPENDIENTE_COMERCIO")
    assert cat.monto_mensual == Decimal("340.00")


def test_gt07_rejects_below_minimum():
    with pytest.raises(MinimumWageError, match="inferior al mínimo"):
        validate_salary_base(Decimal("300.00"), "DEPENDIENTE_COMERCIO")


def test_accepts_at_minimum():
    validate_salary_base(Decimal("340.00"), "DEPENDIENTE_COMERCIO")


def test_accepts_above_minimum():
    validate_salary_base(Decimal("1800.00"), "DEPENDIENTE_COMERCIO")
