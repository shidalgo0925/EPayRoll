#!/usr/bin/env python3
"""Borra datos operativos y regenera tabla default de asistencia (empleado + fecha, sin valores)."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epayroll.db.attendance_facts_repository import AttendanceFactsRepository
from epayroll.db.connection import get_connection


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL requerido", file=sys.stderr)
        sys.exit(1)

    sql_path = ROOT / "scripts" / "reset_operational_data.sql"
    sql = sql_path.read_text(encoding="utf-8")
    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

    repo = AttendanceFactsRepository()
    today = date.today()
    y, m = today.year, today.month
    fecha_inicio = date(y, m, 1)
    fecha_fin = date(y, m, 15) if m != 2 else date(y, m, 14)

    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT organization_id::text
                FROM employees
                WHERE activo = true
                """
            )
            org_ids = [r[0] for r in cur.fetchall()]

    att_total = 0
    for org_id in org_ids:
        r = repo.ensure_period_grid(
            org_id, fecha_inicio, fecha_fin, fuente="MANUAL", database_url=database_url
        )
        att_total += r.get("total", 0)
        print(f"  org {org_id}: {r.get('employees', 0)} empleados, {r.get('total', 0)} filas asistencia")

    print(f"OK — datos operativos borrados. Asistencia default: {att_total} filas ({fecha_inicio} → {fecha_fin})")


if __name__ == "__main__":
    main()
