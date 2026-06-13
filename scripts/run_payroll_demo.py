from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from epayroll.engine.context import PayrollInput  # noqa: E402
from epayroll.engine.orchestrator import PayrollEngine  # noqa: E402


def run_gt01() -> None:
    engine = PayrollEngine()
    inp = PayrollInput(
        salario_mensual=Decimal("1800"),
        dias_trabajados=Decimal("15"),
        es_quincena=True,
        mes=6,
        tasa_css_patronal=Decimal("0.1325"),
        tasa_riesgo_empresa=Decimal("0.0105"),
        tasa_prima_antiguedad_patronal=Decimal("0.0192"),
    )
    result = engine.run(inp)
    out = {
        "SALARIO_BASE": str(result.amount("SALARIO_BASE")),
        "CSS_EMPLEADO": str(result.amount("CSS_EMPLEADO")),
        "SE_EMPLEADO": str(result.amount("SE_EMPLEADO")),
        "ISR": str(result.amount("ISR")),
        "bruto": str(result.bruto),
        "neto": str(result.neto),
        "CSS_EMPLEADOR": str(result.amount("CSS_EMPLEADOR")),
        "SE_EMPLEADOR": str(result.amount("SE_EMPLEADOR")),
        "RIESGO_PROFESIONAL": str(result.amount("RIESGO_PROFESIONAL")),
        "PRIMA_ANTIGUEDAD_PATRONAL": str(result.amount("PRIMA_ANTIGUEDAD_PATRONAL")),
        "aportes_patronales": str(result.aportes_patronales),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    run_gt01()
