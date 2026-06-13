from __future__ import annotations


class VacationSubstitutionError(ValueError):
    pass


def validate_substitute_assignment(
    titular_employee_id: str,
    substitute_employee_id: str,
    titular_org_id: str,
    substitute_org_id: str,
    substitute_active: bool,
) -> None:
    if titular_employee_id == substitute_employee_id:
        raise VacationSubstitutionError("El sustituto no puede ser el mismo empleado")
    if titular_org_id != substitute_org_id:
        raise VacationSubstitutionError("Sustituto debe pertenecer a la misma organización")
    if not substitute_active:
        raise VacationSubstitutionError("Sustituto no está activo")
