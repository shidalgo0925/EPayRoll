# Motor de cálculo EPayRoll (Fase 2)

Motor genérico que **interpreta reglas** desde `docs/seed/` (o PostgreSQL en producción).

## Módulos

| Módulo | Responsabilidad |
|--------|-----------------|
| `evaluator.py` | Expresiones seguras (`salario_hora * 1.25`, `min(...)`) |
| `context.py` | Variables de corrida por empleado |
| `config.py` | Carga reglas vigentes desde JSON/seed |
| `isr.py` | Motor ISR (anualización ×13, tabla progresiva) |
| `orchestrator.py` | Corrida por prioridad, snapshot config |
| `rounding.py` | CENTESIMO / DECIMO / ENTERO |

## Uso

```python
from decimal import Decimal
from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine

engine = PayrollEngine()
result = engine.run(PayrollInput(
    salario_mensual=Decimal("1800"),
    dias_trabajados=Decimal("15"),
    es_quincena=True,
))
print(result.neto)
```

## Demo CLI

```powershell
python scripts/run_payroll_demo.py
```

## Tests (golden)

```powershell
python -m pytest tests/ -v
```

| Test | Caso |
|------|------|
| GT-01 | Quincena B/. 1,800 — CSS, SE, ISR, aportes patronales |
| GT-02 | Horas extras diurnas + nocturnas |

## ISR

Método Fase 2: anualizar bruto (×13), restar CSS anual, aplicar tabla Art. 700, dividir /13.

> Monto ISR difiere del estimado ilustrativo en GOLDEN_TESTS (~93) — nuestro cálculo con deducción CSS da **B/. 116.75**. Pendiente validación contador.
