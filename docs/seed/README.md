# Seed legal EPayRoll — Panamá

Datos iniciales para tablas maestras. Formato JSON con vigencia.

**Estado:** Borrador — requiere validación contable.

## Archivos

| Archivo | Tabla destino | Dominio |
|---------|---------------|---------|
| `contract_types.json` | tipos_contrato | Laboral |
| `payroll_concepts.json` | conceptos_nomina | Laboral |
| `calculation_rules.json` | reglas_calculo | Laboral |
| `shift_types.json` | tipos_horario_turno | Laboral |
| `holidays_2026.json` | feriados | Laboral |
| `css_rates.json` | css_tarifas | CSS |
| `se_rates.json` | se_tarifas | SE |
| `isr_brackets.json` | isr_tramos | ISR |
| `decimo_config.json` | decimo_config | Décimo |

## Uso

Estos archivos alimentarán migraciones/seeds de BD en Fase 2. No contienen lógica — solo configuración.
