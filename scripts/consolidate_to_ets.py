#!/usr/bin/env python3
"""Consolida datos operativos en Easy Technology Services S.A. y limpia orgs de prueba."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

try:
    import psycopg2
except ImportError:
    print("pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

ETS = "00000000-0000-0000-0000-000000000010"
TENANT = "00000000-0000-0000-0000-000000000001"

ORG_TABLES = (
    "employees",
    "payroll_periods",
    "attendance_facts",
    "attendance_import_batches",
)


def main() -> None:
    url = os.environ.get("DATABASE_URL", "postgresql://epayroll:epayroll@localhost:5432/epayroll")
    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()

    for table in ORG_TABLES:
        cur.execute(
            f"""
            UPDATE {table}
            SET organization_id = %s::uuid
            WHERE organization_id != %s::uuid
            """,
            (ETS, ETS),
        )
        print(f"→ {table}: {cur.rowcount} fila(s) movidas a ETS")

    cur.execute(
        """
        UPDATE employees SET activo = true, updated_at = now()
        WHERE organization_id = %s::uuid AND activo = false
        """,
        (ETS,),
    )
    print(f"→ employees reactivados en ETS: {cur.rowcount}")

    cur.execute(
        """
        UPDATE organizations SET activo = false, updated_at = now()
        WHERE id != %s::uuid AND tenant_id = %s::uuid
        """,
        (ETS, TENANT),
    )
    print(f"→ organizations desactivadas: {cur.rowcount}")

    cur.execute(
        """
        UPDATE user_organization_memberships m
        SET activo = false, updated_at = now()
        FROM organizations o
        WHERE m.organization_id = o.id
          AND (o.activo = false OR o.id != %s::uuid)
        """,
        (ETS,),
    )
    print(f"→ memberships desactivadas: {cur.rowcount}")

    for email in ("shidalgo@eastech.services", "shidalgo@easytech.services"):
        cur.execute("SELECT id FROM app_users WHERE email = %s AND activo = true", (email,))
        row = cur.fetchone()
        if not row:
            continue
        user_id = row[0]
        cur.execute(
            """
            INSERT INTO user_organization_memberships (user_id, organization_id, roles)
            VALUES (%s::uuid, %s::uuid, ARRAY['payroll_admin','rrhh','contador','tenant_admin']::text[])
            ON CONFLICT (user_id, organization_id) DO UPDATE SET
                roles = EXCLUDED.roles,
                activo = true,
                updated_at = now()
            """,
            (user_id, ETS),
        )
        cur.execute(
            """
            UPDATE user_organization_memberships
            SET activo = false, updated_at = now()
            WHERE user_id = %s::uuid AND organization_id != %s::uuid
            """,
            (user_id, ETS),
        )
        print(f"→ acceso {email} → solo ETS")

    cur.execute(
        """
        UPDATE app_users SET activo = false, updated_at = now()
        WHERE email = 'shidalgo@easytech.services'
        """
    )

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM employees WHERE organization_id = %s::uuid AND activo", (ETS,))
    print(f"✓ ETS empleados activos: {cur.fetchone()[0]}")
    cur.close()
    conn.close()
    print("Consolidación completada.")


if __name__ == "__main__":
    main()
