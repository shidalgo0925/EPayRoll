#!/usr/bin/env python3
"""Informe golden tests para validación contador (P0)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "storage" / "reports"

GOLDEN_MODULES = [
    ("GT-01/GT-02", "tests/test_engine.py", "GT-01 montos CSS/SE, GT-02 extras"),
    ("GT-02/GT-03", "tests/test_attendance.py", "GT-02 extras, GT-03 feriados"),
    ("GT-04/GT-09", "tests/test_payroll_phase4.py", "GT-04 décimo, GT-09 ISR YTD"),
    ("GT-05/GT-06", "tests/test_liquidation.py", "GT-05 renuncia, GT-06 despido"),
    ("GT-08 SIPE", "tests/test_sipe_export.py", "Conciliación SIPE 24 columnas"),
    ("GT-07 salario mínimo", "tests/test_minimum_wage.py", "Salario mínimo por categoría"),
    ("GT-10 incapacidades Art. 200", "tests/test_incapacity.py", "Subsidios CSS / fondo licencia"),
    ("Vacaciones sustituciones", "tests/test_vacation_substitutions.py", "Cobertura sustitutos"),
    ("Odoo push", "tests/test_odoo_push.py", "Asiento contable integración"),
    ("EN1 SSO + RBAC", "tests/test_sso.py", "JWKS, OAuth, roles"),
]

CONTADOR_CHECKLIST = [
    "GT-01 montos CSS/SE confirmados",
    "GT-01 ISR mensual confirmado",
    "GT-04 tasa CSS décimo 7.25% confirmada",
    "GT-05 fórmulas liquidación confirmadas",
    "GT-07 montos salario mínimo por categoría cargados",
    "GT-09 método ajuste diciembre confirmado",
    "GT-10 tabla subsidios CSS confirmada",
]


def _run_module(module: str) -> tuple[int, str]:
    path = ROOT / module
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(path), "-v", "--tb=no", "-q"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or result.stderr).strip()
    return result.returncode, output


def build_report(write_file: Path | None = None) -> tuple[str, int]:
    lines: list[str] = []
    failed = 0
    passed_count = 0

    lines.append("# EPayRoll — Informe Golden Tests")
    lines.append(f"Generado: {datetime.now(tz=UTC).isoformat()}")
    lines.append(f"Proyecto: {ROOT}")
    lines.append("")
    lines.append("> Montos ISR/SIPE requieren firma del contador antes de producción.")
    lines.append("> Referencia: `docs/legal/GOLDEN_TESTS.md`")
    lines.append("")

    for label, module, nota in GOLDEN_MODULES:
        path = ROOT / module
        lines.append(f"## {label}")
        lines.append(f"Módulo: `{module}` — {nota}")
        if not path.exists():
            lines.append("Estado: ⏭ Omitido (archivo no existe)")
            lines.append("")
            continue
        code, output = _run_module(module)
        if code == 0:
            passed_count += 1
            lines.append("Estado: ✅ PASS")
        else:
            failed += 1
            lines.append("Estado: ❌ FAIL")
        lines.append("")
        lines.append("```")
        lines.append(output)
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Checklist validación contador")
    lines.append("")
    for item in CONTADOR_CHECKLIST:
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append("**Validado por:** ___________________")
    lines.append("**Fecha:** ___________________")
    lines.append("")
    lines.append("---")
    lines.append("")
    summary = f"Resumen: {passed_count}/{len(GOLDEN_MODULES)} módulos PASS"
    if failed:
        summary += f" — {failed} FAIL"
    else:
        summary += " — listo para revisión contable"
    lines.append(summary)

    report = "\n".join(lines)
    if write_file:
        write_file.parent.mkdir(parents=True, exist_ok=True)
        write_file.write_text(report, encoding="utf-8")
    return report, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Informe golden tests para contador")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Ruta del informe Markdown (default: storage/reports/golden_YYYYMMDD.md)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Solo escribir archivo, no stdout")
    args = parser.parse_args()

    out_path = args.output
    if out_path is None:
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d")
        out_path = DEFAULT_OUTPUT / f"golden_{stamp}.md"

    report, failed = build_report(write_file=out_path)
    if not args.quiet:
        print(report)
        print(f"\nInforme guardado: {out_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
