"""Vacation substitutions Fase 5.5."""

from __future__ import annotations

import pytest

from epayroll.vacation.substitutions import VacationSubstitutionError, validate_substitute_assignment


def test_substitute_must_differ_from_titular():
    with pytest.raises(VacationSubstitutionError, match="mismo empleado"):
        validate_substitute_assignment("emp-a", "emp-a", "org-1", "org-1", True)


def test_substitute_same_organization():
    with pytest.raises(VacationSubstitutionError, match="misma organización"):
        validate_substitute_assignment("emp-a", "emp-b", "org-1", "org-2", True)


def test_substitute_must_be_active():
    with pytest.raises(VacationSubstitutionError, match="activo"):
        validate_substitute_assignment("emp-a", "emp-b", "org-1", "org-1", False)


def test_valid_substitute():
    validate_substitute_assignment("emp-a", "emp-b", "org-1", "org-1", True)
