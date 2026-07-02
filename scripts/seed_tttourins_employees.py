#!/usr/bin/env python3
"""Carga empleados TTourins desde planilla piloto."""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from epayroll.db.legal_config_repository import LegalConfigRepository
from epayroll.db.repositories import ContractRepository, EmployeeRepository

TTOURINS_ORG = "3566f55b-3ca0-4938-84aa-b4f8157d6341"

# ficha, nombres, apellidos, cedula, salario_mensual, bono_mensual_ref
EMPLOYEES = [
    ("1", "Juan", "Perez", "6-69-13", Decimal("1700.00"), Decimal("0")),
    ("2", "Edwin", "Lopez", "8-937-952", Decimal("825.00"), Decimal("100.00")),
    ("3", "Davis", "Fernandez", "3-738-253", Decimal("825.00"), Decimal("150.00")),
    ("4", "Abigail", "Govea", "8-993-1252", Decimal("650.00"), Decimal("100.00")),
    ("5", "Ibania", "Baltodano", "E-8-93577", Decimal("650.00"), Decimal("100.00")),
    ("6", "Jose", "de la Rosa Barrios", "PENDIENTE-6", Decimal("650.00"), Decimal("0")),
]


def main() -> None:
    legal = LegalConfigRepository()
    legal.seed_org_defaults(TTOURINS_ORG)

    emp_repo = EmployeeRepository()
    contract_repo = ContractRepository()
    inicio = date(2026, 1, 1)

    for ficha, nombres, apellidos, cedula, salario, bono in EMPLOYEES:
        nota = f"Bono mensual ref.: B/. {bono}" if bono > 0 else None
        emp = emp_repo.create(
            organization_id=TTOURINS_ORG,
            cedula=cedula,
            nombres=nombres,
            apellidos=apellidos,
            ficha=ficha,
            direccion=nota,
        )
        contract_repo.create(
            employee_id=emp.id,
            contract_type_codigo="INDEFINIDO",
            salario_base=salario,
            fecha_inicio=inicio,
            forma_pago="QUINCENAL",
        )
        print(f"✓ Ficha {ficha}: {nombres} {apellidos} — B/. {salario}/mes")

    print(f"Importados {len(EMPLOYEES)} empleados en TTourins.")


if __name__ == "__main__":
    main()
