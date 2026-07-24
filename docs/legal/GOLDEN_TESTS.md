# Golden Tests — EPayRoll Panamá

**Versión:** 1.0 (borrador)  
**Estado:** Pendiente validación contable  
**Padre:** [EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md](../EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md)

Casos de prueba con valores esperados para regresión automática del motor de cálculo.

> ⚠️ Los montos ISR son **ilustrativos**. El contador debe confirmar método exacto de anualización y redondeo mensual.

---

## GT-01 — Planilla quincenal empleado administrativo

**Dominios:** Laboral, CSS, SE, ISR  
**Período:** Quincena 1–15 junio 2026  
**Contrato:** INDEFINIDO, jornada DIURNA

### Input

| Campo | Valor |
|-------|-------|
| Salario mensual | B/. 1,800.00 |
| Días trabajados (quincena) | 15 |
| Horas extras | 0 |
| Acumulado YTD gravable (meses prev.) | B/. 0 (enero en empresa) |
| Riesgo profesional | 1.05% (ADMIN_OFICINA) |
| Tope CSS | Sin tope (null) |

### Cálculo esperado

| Concepto | Fórmula | Monto |
|--------|---------|-------|
| Salario quincenal | 1,800 / 2 | **B/. 900.00** |
| Bruto cotizable | 900.00 | 900.00 |
| CSS empleado | 900 × 9.75% | **B/. 87.75** |
| SE empleado | 900 × 1.25% | **B/. 11.25** |
| ISR mensual proyectado | Anual 900×2×13=23,400 → tramo 15% | **≈ B/. 93.00** *(validar)* |
| **Neto empleado** | 900 − 87.75 − 11.25 − ISR | **≈ B/. 708.00** |
| CSS empleador | 900 × 13.25% | **B/. 119.25** |
| SE empleador | 900 × 1.50% | **B/. 13.50** |
| Riesgo profesional | 900 × 1.05% | **B/. 9.45** |
| Prima antig. patronal | 900 × 1.92% | **B/. 17.28** |

---

## GT-02 — Horas extras diurnas y nocturnas misma semana

**Dominios:** Laboral (Arts. 33, 36)  
**Salario mensual:** B/. 1,600.00 → **salario_hora** = 1,600 / (26 días × 8h) ≈ **B/. 7.69**

### Input

| Campo | Valor |
|-------|-------|
| Horas extra diurnas | 4h |
| Horas extra nocturnas | 2h |

### Cálculo esperado

| Concepto | Fórmula | Monto |
|--------|---------|-------|
| Extra diurna | 7.69 × 1.25 × 4 | **B/. 38.45** |
| Extra nocturna | 7.69 × 1.50 × 2 | **B/. 23.07** |
| **Total extras** | | **B/. 61.52** |

**Validación límite:** 4+2=6h extras semana ≤ 9h (Art. 36) ✅

---

## GT-03 — Trabajo en feriado (3 de noviembre)

**Dominios:** Laboral (Art. 49)  
**Salario_hora:** B/. 10.00  
**Horas trabajadas en feriado:** 8h (jornada ordinaria)

### Cálculo esperado

| Concepto | Monto |
|--------|-------|
| Jornada ordinaria feriado | 8 × 10 × 2.50 (150% total) = **B/. 200.00** |

> Art. 49: 150% incluye remuneración del día de descanso.

---

## GT-04 — Pago décimo tercer mes (15 abril)

**Dominios:** Décimo, CSS  
**Salarios cotizables dic–mar:** B/. 1,800 + 1,800 + 1,850 + 1,900 = **B/. 7,350**

### Cálculo esperado

| Concepto | Fórmula | Monto |
|--------|---------|-------|
| Décimo | 7,350 / 12 | **B/. 612.50** |
| CSS empleado décimo | 612.50 × 7.25% | **B/. 44.41** |
| CSS empleador décimo | 612.50 × 7.25% | **B/. 44.41** |
| SE décimo | Exento | **B/. 0.00** |
| ISR décimo | Exento | **B/. 0.00** |
| **Neto décimo empleado** | 612.50 − 44.41 | **B/. 568.09** |

---

## GT-05 — Liquidación por renuncia

**Dominios:** Laboral, Décimo  
**Antigüedad:** 3 años, 4 meses  
**Salario promedio últimos 5 años (prima):** B/. 1,750/mes  
**Vacaciones pendientes:** 12 días  
**Salario diario vacaciones:** B/. 58.33 (1,750/30)

### Cálculo esperado

| Rubro | Fórmula | Monto |
|-------|---------|-------|
| Vacaciones | 12 × 58.33 | **B/. 700.00** |
| Décimo proporcional | (meses trabajados año / 12) × (salarios acum/12) | **≈ B/. 437.50** *(validar)* |
| Prima antigüedad | 3.33 años × 1 semana × (1,750/4) | **≈ B/. 1,456.88** *(validar)* |
| Preaviso (sin cumplir) | 1 semana si aplica | **B/. 437.50** *(si no notificó)* |
| Indemnización despido | No aplica renuncia | **B/. 0.00** |

---

## GT-06 — Despido injustificado (indemnización)

**Dominios:** Laboral (Art. 225)  
**Antigüedad post 02-abr-1972:** 5 años  
**Salario promedio 6 meses:** B/. 2,000

### Cálculo esperado (escala B)

| Tramo | Monto |
|-------|-------|
| 2–10 años | 3 semanas × 5 años = 15 semanas |
| 15 semanas × (2,000/4 semanas) | **B/. 7,500.00** |

> + salarios caídos según Art. 218 si aplica juicio.

### GT-06b — Escala C (Ley 44/1995, default producto)

**Régimen:** `C`  
**Antigüedad:** 5 años · salario B/. 2,000  
**Salario semanal:** `2000 × 12 / 52` = **B/. 461.54**  
**Semanas:** `5 × 3.4` = 17  
**Indemnización:** 17 × 461.54 = **B/. 7,846.18**

### GT-05b — Prima solo indefinido + semanal 12/52

**Salario:** B/. 1,750 · antigüedad 3.33 años · indefinido  
**Semanal:** 1750 × 12 / 52 = **403.85**  
**Prima:** 3.33 × 403.85 = **B/. 1,344.82**  
Si contrato DEFINIDO/OBRA → prima **0**.

### GT-05e — Despido justificado con prima

Si indefinido → vacaciones + décimo + **prima**; sin indemnización.

### GT-05f — Suspensión prolongada

Sin indemnización automática. Solo con `calcular_indemnizacion=true` + `fundamento_indemnizacion`.

---

## GT-05b — Renuncia justificada + indemnización

**Causa:** `RENUNCIA_JUSTIFICADA`  
Mismos rubros que renuncia voluntaria **más** indemnización Art. 225 (como despido injustificado). Sin descuento de preaviso.

## GT-05c — Mutuo acuerdo (indemnización negociada)

**Causa:** `MUTUO_ACUERDO`  
Vacaciones + décimo + prima (o prima acordada) + **indemnización digitada** por el contador. Requiere `documento_ref` al guardar.

## GT-05d — Vencimiento / fin de obra

**Causas:** `VENCIMIENTO_CONTRATO`, `FIN_OBRA`  
Vacaciones + décimo + salario pendiente. Prima solo si el tipo de contrato `genera_prima_antiguedad`.

---

## GT-07 — Salario bajo mínimo legal

**Dominios:** Salario mínimo  
**Actividad:** Comercio, región Panamá, categoría dependiente  
**Salario mínimo vigente (ejemplo):** B/. 340.00/mes *(validar Decreto 13/2025)*  
**Salario contrato:** B/. 300.00

### Resultado esperado

| Validación | Resultado |
|------------|-----------|
| Alerta al crear contrato | ⚠️ Salario < mínimo |
| Bloqueo cierre planilla | ❌ Rechazado |
| Mensaje | "Salario inferior al mínimo legal para categoría X" |

---

## GT-08 — Conciliación SIPE vs planilla interna

**Dominios:** SIPE, CSS  
**Empleados:** 10  
**Período:** Junio 2026

### Validaciones

- [ ] Suma columna salario SIPE = suma bruto interno
- [ ] Suma CSS empleado SIPE = suma descuentos internos
- [ ] Suma CSS empleador SIPE = suma aportes patronales internos
- [ ] 24 columnas A–X completas sin null en campos obligatorios
- [ ] Formato aceptado en portal CSS (ambiente prueba)

---

## GT-09 — Retención ISR YTD — mes 12 ajuste

**Dominios:** ISR  
**Salario mensual:** B/. 3,000  
**Mes:** Diciembre (mes 12)

### Proceso

1. Anualizar: 3,000 × 13 = B/. 39,000
2. Tramo 15% sobre (39,000 − 11,000) = 28,000 × 15% = **B/. 4,200 anual**
3. Retención mensual teórica: 4,200 / 13 ≈ **B/. 323.08**
4. Mes 12: ajuste = impuesto anual real − suma retenida ene–nov

### Validación

| Campo | Esperado |
|-------|----------|
| Suma retenciones ene–nov + dic | = impuesto anual exacto |
| Diferencia ajuste dic | ≤ B/. 0.01 (redondeo) |

---

## GT-10 — Incapacidad CSS — subsidio parcial

**Dominios:** Laboral (Art. 200), CSS  
**Fondo licencia agotado:** Sí  
**Días incapacidad CSS:** 15 días  
**Salario diario:** B/. 60.00

### Comportamiento esperado

| Período | Pagador | % salario |
|---------|---------|-----------|
| Días 1–2 | Empleador (fondo licencia si disponible) | 100% |
| Días 3–15 | CSS subsidio | Según tabla CSS *(validar)* |
| Planilla | No generar salario ordinario esos días | — |
| Registro | incapacities table + audit trail | — |

---

## Matriz de cobertura

| Test | Fase objetivo | Automatizable |
|------|---------------|---------------|
| GT-01 | Fase 4 | ✅ |
| GT-02 | Fase 3–4 | ✅ |
| GT-03 | Fase 3–4 | ✅ |
| GT-04 | Fase 4 | ✅ |
| GT-05 | Fase 4 | ⚠️ parcial |
| GT-06 | Fase 4 | ⚠️ parcial |
| GT-07 | Fase 1.5 | ✅ |
| GT-08 | Fase 6 | ⚠️ integración |
| GT-09 | Fase 4 | ✅ |
| GT-10 | Fase 3–4 | ⚠️ parcial |

---

## Checklist validación contador

- [ ] GT-01 montos CSS/SE confirmados
- [ ] GT-01 ISR mensual confirmado
- [ ] GT-04 tasa CSS décimo 7.25% confirmada
- [ ] GT-05 fórmulas liquidación confirmadas
- [ ] GT-07 montos salario mínimo por categoría cargados
- [ ] GT-09 método ajuste diciembre confirmado
- [ ] GT-10 tabla subsidios CSS confirmada

**Validado por:** ___________________  
**Fecha:** ___________________
