# EPAYROLL_TECH_ARCHITECTURE.md

**Versión:** 1.0 (borrador)  
**Estado:** En elaboración — Fase 1–2  
**Padre:** [EPAYROLL_MASTER_PLAN.md](./EPAYROLL_MASTER_PLAN.md)  
**Propósito:** Stack, APIs, motor de fórmulas, EN1 e integraciones

---

## 1. PRINCIPIOS TÉCNICOS

1. **Configuración sobre código** — reglas en BD, no en source
2. **Reproducibilidad** — cada corrida guarda snapshot de config vigente
3. **Auditabilidad** — logs inmutables, sin hard delete en datos legales
4. **Tenant isolation** — aislamiento estricto por EN1
5. **Idempotencia** — recalcular planilla produce mismo resultado con misma config

---

## 2. STACK (FASE 1 — DECIDIDO)

| Capa | Decisión Fase 1 | Notas |
|------|-----------------|-------|
| **Base de datos** | **PostgreSQL 16** | Migraciones SQL numeradas en `database/migrations/` |
| **IDs** | **UUID** | `gen_random_uuid()` |
| **Seed legal** | **Python 3 + psycopg2** | `scripts/seed.py` ← `docs/seed/*.json` |
| **Backend API** | **FastAPI + Uvicorn** | Fase 1.5 |
| Frontend | Pendiente Fase 1.5 | React + TypeScript (propuesto) |
| Cache | Pendiente | Redis en Fase 4+ |

**Decisión registrada:** Junio 2026 — PostgreSQL + SQL migrations + JSON seed.

---

## 3. ARQUITECTURA EN1 (MULTITENANT)

```
                    ┌──────────────┐
                    │   EN1 Core   │
                    │ Auth · Tenant│
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────┐
   │ EPayRoll  │    │ EClassOne │    │  Otros    │
   │  Module   │    │  Module   │    │  SaaS     │
   └───────────┘    └───────────┘    └───────────┘
```

### 3.1 Integración EN1

| Aspecto | Requerimiento |
|---------|---------------|
| Autenticación | SSO / JWT emitido por EN1 |
| Tenant context | Header o claim `tenant_id`, `organization_id` |
| RBAC | Roles: `admin`, `contador`, `rrhh`, `gerente`, `empleado` |
| Catálogos | Compartidos EN1 vs. específicos EPayRoll |

### 3.2 Aislamiento de datos

- Row-level security por `tenant_id`
- Queries siempre filtradas por contexto EN1
- Sin cross-tenant en APIs ni reportes

---

## 4. MÓDULOS DE APLICACIÓN

| Módulo | Responsabilidad |
|--------|-----------------|
| `Core` | Empleados, contratos, organizaciones |
| `Time` | Asistencia, turnos, marcaciones |
| `PayrollEngine` | Motor de reglas y corrida |
| `Benefits` | Vacaciones, décimo, liquidaciones, cesantía |
| `Compliance` | CSS, SE, ISR, SIPE, DGI |
| `Analytics` | Dashboards, pasivos, KPIs |
| `Integration` | Odoo, bancos, webhooks |

---

## 5. MOTOR DE REGLAS Y FÓRMULAS

**Implementado (Fase 2):** `src/epayroll/engine/`

| Componente | Archivo | Estado |
|------------|---------|--------|
| Evaluador seguro | `evaluator.py` | ✅ |
| Contexto variables | `context.py` | ✅ |
| Carga config JSON/seed | `config.py` | ✅ |
| Motor ISR | `isr.py` | ✅ |
| Orquestador corrida | `orchestrator.py` | ✅ |
| Golden tests | `tests/test_engine.py` | ✅ GT-01, GT-02 |

### 5.1 Responsabilidades del motor (código)

- Cargar config vigente para `fecha_planilla`
- Resolver dependencias entre conceptos (orden topológico)
- Evaluar condiciones (`horas_extra_diurnas > 0`)
- Evaluar fórmulas (`salario_hora * 1.25`)
- Aplicar prioridades y redondeo
- Validar topes (CSS, descuentos Art. 161)
- Persistir snapshot + resultados

### 5.2 Lenguaje de expresiones

**Decisión Fase 2:** DSL Python sandbox via `ast` — operadores aritméticos, comparaciones, `min()`, `max()`.

Variables definidas en `context.py`. Funciones externas solo si se registran explícitamente.

### 5.3 Catálogo de variables (seed)

```
salario_base, salario_hora, salario_diario
dias_trabajados, horas_ordinarias
horas_extra_diurnas, horas_extra_nocturnas, horas_extra_mixtas
dias_dominio_trabajados, dias_feriado_trabajados
bruto_parcial, acumulado_ytd_gravable
css_empleado_acumulado, isr_retenido_ytd
antiguedad_anos, antiguedad_meses
```

### 5.4 Redondeo

| Valor | Uso |
|-------|-----|
| `CENTESIMO` | Default monetario B/. |
| `DECIMO` | Casos específicos |
| `ENTERO` | Unidades discretas |

---

## 6. MOTORES ESPECIALIZADOS

| Motor | Separado del salario ordinario | Razón |
|-------|-------------------------------|-------|
| **Décimo** | Sí | Fechas fijas, acumulación trimestral, exenciones |
| **ISR** | Sí | Anualización ×13, YTD, ajuste cierre |
| **Vacaciones** | Sí | 11 meses, planificación, pasivo |
| **Liquidación** | Sí | Causa terminación determina rubros |

Convergen en `PayrollRunOrchestrator` — un solo punto de entrada.

---

## 7. APIs (BORRADOR)

### 7.1 Core

```
GET    /api/v1/employees
POST   /api/v1/employees
GET    /api/v1/contracts
POST   /api/v1/contracts
```

### 7.2 Planilla

```
POST   /api/v1/payroll/periods
POST   /api/v1/payroll/runs              # ejecutar corrida
GET    /api/v1/payroll/runs/{id}
GET    /api/v1/payroll/runs/{id}/payslips/{employeeId}
POST   /api/v1/payroll/runs/{id}/close   # cerrar período
```

### 7.3 Configuración legal (admin)

```
GET    /api/v1/config/concepts
PUT    /api/v1/config/rules/{id}
GET    /api/v1/config/css-rates?vigencia=2026-06-01
```

### 7.4 Exportación

```
POST   /api/v1/exports/sipe/{runId}
POST   /api/v1/exports/dgi/{runId}
POST   /api/v1/exports/bank/{runId}
```

---

## 8. SEGURIDAD

| Control | Implementación |
|---------|----------------|
| Autenticación | EN1 SSO / JWT |
| Autorización | RBAC por módulo y organización |
| Datos sensibles | Cifrado en reposo (cedula, salarios) |
| Auditoría | Todo cambio en reglas y planillas |
| Rate limiting | APIs públicas / integraciones |

---

## 9. INTEGRACIONES

### 9.1 Odoo (Fase 7 — prioridad)

- Sync empleados / contratos (webhook o polling)
- Asiento contable al cierre planilla
- Mapeo conceptos nómina → cuentas contables

### 9.2 Bancos ACH

- Formato parametrizable por banco (tabla `bank_export_formats`)
- No hardcodear layout por banco

### 9.3 CSS / DGI

- Generadores de archivo desde templates versionados
- Validación pre-vuelo contra reglas SIPE

---

## 10. OBSERVABILIDAD

- Logs estructurados por corrida (`run_id`, `tenant_id`)
- Métricas: tiempo corrida, empleados procesados, errores
- Alertas: corrida fallida, discrepancia SIPE

---

## 11. TESTING

| Tipo | Alcance |
|------|---------|
| Unit | Evaluador fórmulas, redondeo, prioridades |
| Integration | Corrida completa con seed legal |
| Golden | 10 casos Compliance Blueprint §14 |
| Regression | Cada cambio en tablas maestras |

---

## 12. PENDIENTES

- [ ] Decisión stack final
- [ ] Contrato API EN1 (auth, tenant)
- [ ] POC motor fórmulas (2 semanas)
- [ ] Estrategia migraciones BD (Flyway / EF / Prisma)
- [ ] CI/CD pipeline

---

*Documento hijo de EPAYROLL_MASTER_PLAN — Easy Technology Services*
