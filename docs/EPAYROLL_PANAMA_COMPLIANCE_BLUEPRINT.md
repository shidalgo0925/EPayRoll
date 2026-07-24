# EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md

**Versión:** 1.0 (borrador)  
**Estado:** Fase 0 en progreso — seed JSON cargado, pendiente validación contable  
**Padre:** [EPAYROLL_MASTER_PLAN.md](./EPAYROLL_MASTER_PLAN.md)  
**Propósito:** Fuente oficial de reglas legales para EPayRoll Panamá

> El Código de Trabajo **no es suficiente**. Este documento define los **9 dominios legales** que alimentan tablas maestras y el motor de cálculo.

---

## 1. PRINCIPIO

**Configuración sobre código.** Cada dominio se parametriza en tablas con vigencia. El programador codifica el motor una vez; RRHH/contador administra reglas.

---

## 2. MAPA DE DOMINIOS

| # | Dominio | Norma principal | ¿En Código de Trabajo? |
|---|---------|-----------------|------------------------|
| 1 | Relaciones laborales | Código de Trabajo | Sí |
| 2 | CSS | Ley 51/2005 + reformas 2025 | No |
| 3 | Seguro Educativo | Ley 13/1987 | No |
| 4 | ISR sobre salarios | Código Fiscal Arts. 699–700 | No |
| 5 | Décimo Tercer Mes | Decreto 19/1973 | No |
| 6 | Salario Mínimo | Decretos ejecutivos vigentes | No |
| 7 | Riesgos Profesionales | Clasificación CSS | No |
| 8 | SIPE | Resoluciones CSS | No |
| 9 | DGI / e-Tax | Normativa DGI | No |

---

## 3. DOMINIO 1 — LABORAL (Código de Trabajo)

**Fuente:** Decreto Gabinete 252/1971, modificaciones Ley 44/1995  
**Referencia:** [MITRADEL — Código de Trabajo](https://www.mitradel.gob.pa/trabajadores/codigo-detrabajo/)

### 3.1 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `tipos_contrato` | código, descripción, genera_prima_antiguedad, genera_vacaciones, genera_decimo, proporcional_prestaciones, activo |
| `conceptos_nomina` | código, tipo (INGRESO/DESCUENTO/APORTE/PROVISION), naturaleza, imprime_recibo, acumulable_aguinaldo, acumulable_vacaciones, orden_visual |
| `reglas_calculo` | concepto, condición, base_cálculo, unidad, aplica_contratos, prioridad, redondeo, vigencia |
| `tipos_horario_turno` | código, hora_inicio, hora_fin, tipo_jornada, recargo_domingo, recargo_feriado, max_extras_diarias/semanales |
| `feriados` | fecha, descripción, tipo, recargo_trabajar, es_recuperable, año |
| `asignaciones_empleado_concepto` | empleado, concepto, valor_fijo, fecha_inicio, fecha_fin |

### 3.2 Reglas seed — Jornada y horas extras

| Artículo | Regla | Valor seed |
|----------|-------|------------|
| Art. 30 | Períodos diurno / nocturno / mixto | 6am–6pm / 6pm–6am |
| Art. 31 | Jornada máxima | 8h/48h diurna · 7h/42h nocturna · 7.5h/45h mixta |
| Art. 33 | Recargo horas extras | +25% diurna · +50% nocturna/mixta diurna · +75% nocturna/mixta nocturna |
| Art. 36 | Límite extras | 3h/día · 9h/semana; exceso +75% adicional |
| Art. 37 | Pago extras | Hasta 5 días antes del día de pago |

### 3.3 Reglas seed — Descansos y feriados

| Artículo | Regla | Valor seed |
|----------|-------|------------|
| Art. 39 | Descanso intrajornada | 30 min – 2 horas |
| Art. 48 | Trabajo domingo | +50% jornada ordinaria |
| Art. 49 | Trabajo feriado | +150% (incluye día descanso) |
| Art. 46 | Feriados nacionales | 1 y 9 ene, carnaval, viernes santo, 1 mayo, 3 y 5 nov, 10 y 28 nov, 8 y 25 dic, toma posesión |
| Art. 50 | Recargos combinados | Primero domingo/feriado, luego extras |

### 3.4 Reglas seed — Vacaciones

| Artículo | Regla | Valor seed |
|----------|-------|------------|
| Art. 52–54 | Derecho | 30 días / 11 meses continuos |
| Art. 54 | Cálculo pago | Promedio 11 meses o último salario (más favorable) |
| Art. 57 | Planificación | Empleador señala con 2 meses anticipación |
| Art. 59 | Acumulación | Hasta 2 períodos; mínimo 15 días primer período |
| Art. 59 | Renuncia | No renunciable a cambio de dinero (salvo acumulación acordada) |

### 3.5 Reglas seed — Salario y retenciones permitidas

| Artículo | Regla |
|----------|-------|
| Art. 140 | Definición amplia de salario |
| Art. 142 | Pago por unidad de tiempo o piezas |
| Art. 147 | Qué NO es salario (viáticos, herramientas) |
| Art. 148 | Pago máximo cada quincena |
| Art. 161 | Retenciones permitidas: ISR, CSS, descuentos autorizados con topes |

### 3.6 Reglas seed — Terminación y prestaciones

| Artículo | Regla | Valor seed |
|----------|-------|------------|
| Art. 210 | Causas de terminación | 10 causas en `liquidation_rules.json` |
| Art. 222 | Preaviso renuncia | 15 días (2 meses si técnico) |
| Art. 224 | Prima antigüedad | 1 semana salario / año |
| Art. 226 | Base prima | Promedio últimos 5 años |
| Art. 225 | Indemnización despido injustificado | Escala por antigüedad |
| Arts. 229 A–D | Fondo cesantía | Cotización trimestral |

### 3.7 Reglas seed — Incapacidad

| Artículo | Regla | Valor seed |
|----------|-------|------------|
| Art. 200 | Fondo licencia | 12h / 26 jornadas (144h/año); acumulable 2 años |

---

## 4. DOMINIO 2 — CSS

**Norma:** Ley 51 de 2005, Reglamento, reformas (Ley 462/2025 — cuota patronal 13.25% hasta feb/2027)

### 4.1 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `css_tarifas` | concepto, porcentaje_empleado, porcentaje_empleador, sobre_base (fórmula), tope_mensual, vigencia_desde/hasta |
| `css_base_cotizable` | concepto_nomina, incluye_en_base, vigencia |

### 4.2 Seed vigente (validar con CSS antes de producción)

| Concepto | Empleado | Empleador |
|----------|----------|-----------|
| Cuota CSS | 9.75% | 12.25% base / **13.25%** temporal Ley 462 |
| Riesgos profesionales | — | 1.05% – 5.67% (por actividad) |
| Prima antigüedad (patronal) | — | ~1.92% |

### 4.3 Base cotizable

Incluye (validar reglamento): salario base, comisiones devengadas, horas extras, bonificaciones regulares, décimo en mes de pago.

**Tope mensual:** parametrizable — verificar valor vigente con CSS.

---

## 5. DOMINIO 3 — SEGURO EDUCATIVO

**Norma:** Ley 13 de 1987

### 5.1 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `se_tarifas` | porcentaje_empleado, porcentaje_empleador, sobre_base, vigencia |

### 5.2 Seed

| Parte | Porcentaje |
|-------|------------|
| Trabajador | 1.25% |
| Empleador | 1.50% |

> Módulo **separado** del Código de Trabajo. No mezclar con CSS en una sola tabla sin discriminación.

---

## 6. DOMINIO 4 — ISR

**Norma:** Código Fiscal Arts. 699–700 (BDO / DGI)

### 6.1 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `isr_tramos` | rango_desde, rango_hasta, porcentaje, excedente, impuesto_fijo, vigencia |
| `isr_config` | método (anual/mensual), factor_anualización (13), deducciones_previas |

### 6.2 Seed — Tabla anual personas naturales

| Ingreso anual gravable | Tarifa |
|------------------------|--------|
| Hasta B/. 11,000 | 0% |
| B/. 11,000.01 – 50,000 | 15% sobre excedente |
| Más de B/. 50,000 | B/. 5,850 + 25% sobre excedente |

### 6.3 Motor ISR — comportamiento

- Anualizar salario (× 13 incluyendo décimo)
- Descontar CSS antes de aplicar tarifa
- Retención mensual con acumulados YTD
- Ajuste de cierre anual
- Décimo: **exento ISR** en pago del décimo (validar norma vigente)

---

## 7. DOMINIO 5 — DÉCIMO TERCER MES

**Norma:** Decreto 19/1973

> **Motor propio.** No mezclar con salario ordinario.

### 7.1 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `decimo_config` | fechas_pago, meses_acumulacion, formula_proporcional, vigencia |
| `decimo_acumulados` | empleado, periodo, salarios_cotizables, monto_calculado, pagado |

### 7.2 Reglas

| Regla | Valor |
|-------|-------|
| Frecuencia | 3 partidas: **15 abr, 15 ago, 15 dic** |
| Cálculo | Suma salarios cotizables últimos 4 meses del trimestre ÷ 12 |
| CSS en pago décimo | Cotiza CSS (~7.25%) — **no SE, no ISR** |
| Proporcional | Al terminar relación laboral antes de fecha de pago |
| Liquidación | Parte proporcional acumulada |

---

## 8. DOMINIO 6 — SALARIO MÍNIMO

**Norma:** Decretos ejecutivos (Arts. 172–180 CT + Decreto 13/2025 u otimo vigente)

> **No existe un único salario mínimo.**

### 8.1 Cadena de resolución

```
Empresa → Actividad económica → Región → Ocupación/Categoría → Salario mínimo vigente
```

### 8.2 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `sm_actividades` | código, descripción |
| `sm_regiones` | código, descripción |
| `sm_ocupaciones` | código, actividad, región, monto, tipo (mensual/hora), vigencia |

### 8.3 Validación

- Al crear contrato
- Al cerrar planilla
- Alerta si salario < mínimo legal para categoría

---

## 9. DOMINIO 7 — RIESGOS PROFESIONALES

**Norma:** Clasificación CSS por actividad económica

### 9.1 Tablas maestras

| Tabla | Campos clave |
|-------|--------------|
| `riesgo_actividad` | codigo_css, descripcion, porcentaje, vigencia |
| `empresa_clasificacion` | empresa, codigo_actividad, porcentaje_riesgo, vigencia |

### 9.2 Ejemplos (parametrizar — no hardcodear)

| Actividad | Riesgo típico |
|-----------|---------------|
| Oficina administrativa | ~1.05% |
| Construcción | mayor |
| Taller industrial | variable |
| Refrigeración / campo | variable |

---

## 10. DOMINIO 8 — SIPE

**Norma:** Resoluciones CSS — formato planilla preelaborada

### 10.1 Módulo exclusivo

- Generación archivo planilla CSS (formato oficial — 24 columnas A–X)
- Validaciones pre-exportación
- Conciliación planilla interna vs. SIPE
- Histórico de envíos
- SIPE complementaria (correcciones períodos anteriores)

> **No depende de Excel manual.**

---

## 11. DOMINIO 9 — DGI

**Norma:** Código Fiscal + e-Tax 2.0

### 11.1 Módulo exclusivo

- Retenciones ISR acumuladas
- Formulario 03
- Exportación e-Tax
- Ajustes de cierre anual
- Histórico por empleado YTD

---

## 12. FLUJO DEL MOTOR DE CÁLCULO

```
INICIO
  │
  ▼
1. CARGAR CONFIGURACIÓN VIGENTE (reglas, ISR, CSS, SE, feriados según fecha planilla)
  │
  ▼
2. POR CADA EMPLEADO ACTIVO
     - Contrato vigente → tipo contrato
     - Asignaciones de conceptos
     - Clasificación riesgo / salario mínimo
  │
  ▼
3. CALCULAR ASISTENCIA
     - Días trabajados, extras, domingos/feriados, incapacidades
  │
  ▼
4. APLICAR REGLAS EN PRIORIDAD
     1 Salario base → 2 Extras → 3 Recargos → 4 Provisiones
     → 5 Descuentos legales (CSS, SE, ISR) → 6 Otros descuentos
  │
  ▼
5. MOTOR DÉCIMO (si corresponde fecha o acumulación)
  │
  ▼
6. REDONDEO, TOPES, VALIDACIÓN SALARIO MÍNIMO
  │
  ▼
7. GENERAR RESULTADOS
     - Recibo · Acumulados · Exportación SIPE/DGI · Banco
  │
FIN
```

---

## 13. PRIORIDADES DE CÁLCULO (DEFAULT)

| Prioridad | Grupo |
|-----------|-------|
| 1 | Salario base / ordinario |
| 2 | Horas extras |
| 3 | Recargos (domingo, feriado) |
| 4 | Ingresos variables / bonos |
| 5 | Provisiones (vacaciones, décimo acumulado) |
| 6 | CSS empleado |
| 7 | Seguro Educativo empleado |
| 8 | ISR |
| 9 | Otros descuentos (Art. 161) |
| 10 | Aportes empleador (CSS, SE, riesgo, cesantía) |

---

## 14. GOLDEN TESTS (pendiente validación contador)

| # | Caso | Dominios |
|---|------|----------|
| GT-01 | Planilla quincenal empleado administrativo | Laboral, CSS, SE, ISR |
| GT-02 | Horas extras diurnas + nocturnas misma semana | Laboral |
| GT-03 | Trabajo domingo + feriado mismo mes | Laboral |
| GT-04 | Pago décimo abril — exenciones ISR/SE | Décimo, CSS |
| GT-05 | Liquidación renuncia — vacaciones + décimo + prima | Laboral, Décimo |
| GT-06 | Liquidación despido injustificado + indemnización | Laboral |
| GT-07 | Salario bajo mínimo — alerta | Salario mínimo |
| GT-08 | Exportación SIPE vs. planilla interna | SIPE, CSS |
| GT-09 | Retención ISR YTD — ajuste mes 12 | ISR |
| GT-10 | Incapacidad CSS — subsidio parcial | Laboral, CSS |

---

## 15. SEED DE DATOS

Archivos JSON versionados en [`docs/seed/`](../seed/):

| Archivo | Estado |
|---------|--------|
| `contract_types.json` | ✅ Borrador |
| `payroll_concepts.json` | ✅ Borrador |
| `calculation_rules.json` | ✅ Borrador |
| `shift_types.json` | ✅ Borrador |
| `holidays_2026.json` | ✅ Borrador |
| `css_rates.json` | ✅ Borrador |
| `se_rates.json` | ✅ Borrador |
| `isr_brackets.json` | ✅ Borrador |
| `decimo_config.json` | ✅ Borrador |
| `professional_risk_rates.json` | ✅ Borrador |

Golden tests detallados: [`docs/legal/GOLDEN_TESTS.md`](./legal/GOLDEN_TESTS.md)

---

## 16. FUENTES PENDIENTES DE CARGAR

- [x] Código de Trabajo → [`docs/legal/codigo-de-trabajo.pdf`](./legal/codigo-de-trabajo.pdf)
- [ ] Ley 51/2005 CSS (PDF)
- [ ] Ley 13/1987 Seguro Educativo (PDF)
- [ ] Código Fiscal Arts. 699–700 (PDF)
- [ ] Decreto 19/1973 Décimo (PDF)
- [ ] Decreto salario mínimo vigente — montos por categoría
- [ ] Resolución SIPE / manual columnas CSS
- [ ] Guía Formulario 03 DGI / e-Tax

---

*Documento hijo de EPAYROLL_MASTER_PLAN — Easy Technology Services*
