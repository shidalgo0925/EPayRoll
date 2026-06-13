# EPayRoll

Plataforma SaaS de gestión laboral, planilla y cumplimiento legal para Panamá — **Easy Technology Services**.

Construida sobre arquitectura multiempresa **EasyNodeOne (EN1)**.

## Documentación maestra

| Documento | Descripción |
|-----------|-------------|
| [EPAYROLL_MASTER_PLAN.md](./docs/EPAYROLL_MASTER_PLAN.md) | Plan rector — visión, pilares, criterios de éxito |
| [EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md](./docs/EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md) | 9 dominios legales, reglas seed, golden tests |
| [EPAYROLL_DATA_MODEL.md](./docs/EPAYROLL_DATA_MODEL.md) | Entidades, relaciones, catálogos |
| [EPAYROLL_TECH_ARCHITECTURE.md](./docs/EPAYROLL_TECH_ARCHITECTURE.md) | Stack, motor de fórmulas, APIs, EN1 |
| [EPAYROLL_ROADMAP.md](./docs/EPAYROLL_ROADMAP.md) | Fases, sprints, dependencias |
| [EPAYROLL_STATUS.md](./docs/EPAYROLL_STATUS.md) | **Estado actual + continuar en apps srv** |

## Principio de diseño

**Configuración sobre código** — las reglas legales viven en tablas maestras con vigencia; el motor las interpreta.

## Fase 6 — Exportacion CSS / DGI

Generador SIPE (24 columnas A-X) con conciliacion GT-08 y Formulario 03 DGI.

| Endpoint | Descripcion |
|----------|-------------|
| `POST /api/v1/exports/sipe/{run_id}` | Genera SIPE + concilia |
| `GET /api/v1/exports/sipe/{run_id}/download` | Descarga archivo TSV |
| `POST /api/v1/exports/dgi/{run_id}` | Genera Form 03 ISR |

Columnas en `docs/seed/sipe_columns.json` — validar con manual CSS antes de produccion.

## Fase 7 — Integraciones Odoo + ACH

| Endpoint | Descripcion |
|----------|-------------|
| `POST /api/v1/organizations/{id}/integrations/odoo/employees/sync` | Sync empleados Odoo |
| `POST /api/v1/integrations/odoo/journal/{run_id}` | Asiento contable JSON |
| `POST /api/v1/employees/{id}/bank-account` | Registrar cuenta bancaria |
| `POST /api/v1/exports/ach/{run_id}` | Generar archivo ACH |
| `GET /api/v1/exports/ach/{run_id}/download` | Descargar ACH |

Formatos en `docs/seed/ach_banco_general.json` y `odoo_account_mapping.json`.

## Fase 8 — Analitica gerencial

| Endpoint | Descripcion |
|----------|-------------|
| `GET /api/v1/organizations/{id}/analytics/dashboard` | Dashboard ejecutivo completo |
| `GET /api/v1/organizations/{id}/analytics/kpis` | Rotacion, ausentismo, horas extra |
| `GET /api/v1/organizations/{id}/analytics/pasivos` | Pasivos laborales consolidados |
| `GET /api/v1/organizations/{id}/analytics/liquidation-projection` | Proyeccion liquidaciones |

Umbrales de alerta en `docs/seed/analytics_config.json`.

## Fase 5 — Vacaciones inteligentes

Acumulacion Art. 52-54 (11 meses / 30 dias), alertas Art. 57 y tope Art. 59.

| Endpoint | Descripcion |
|----------|-------------|
| `POST /api/v1/employees/{id}/vacation/accrue` | Calcula y guarda saldo |
| `GET /api/v1/employees/{id}/vacation/balance` | Consulta saldo |
| `POST /api/v1/employees/{id}/vacation/requests` | Solicitar vacaciones |
| `POST /api/v1/vacation/requests/{id}/approve` | Aprobar solicitud |
| `GET /api/v1/organizations/{id}/vacation/dashboard` | Pasivo + alertas |

Config en `docs/seed/vacation_config.json`.

## Fase 4 — Planilla completa

Corrida multi-empleado por período, décimo tercer mes e ISR YTD.

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/v1/payroll/periods/{id}/run` | Planilla batch (todos los empleados activos) |
| `POST /api/v1/payroll/decimo/runs` | Pago décimo (GT-04) |
| `POST /api/v1/payroll/periods/{id}/close` | Genera recibos PDF + cierra periodo |
| `GET /api/v1/payroll/runs/{id}/payslips/{employee_id}` | Descarga recibo PDF |
| `POST /api/v1/payroll/runs/{id}/payslips/generate` | Genera recibos sin cerrar |
| `POST /api/v1/employees/{id}/termination/calculate` | Liquidación GT-05/GT-06 |
| `POST /api/v1/payroll/runs` | Corrida individual (con YTD ISR + Art. 161) |

```powershell
# Batch quincena
POST /api/v1/payroll/periods/{period_id}/run
{ "use_attendance": true, "dias_trabajados": 15 }

# Décimo abril (GT-04)
POST /api/v1/payroll/decimo/runs
{ "payroll_period_id": "...", "employee_id": "...", "salarios_cotizables": 7350 }

# Cerrar periodo (genera PDFs, estado CERRADO)
POST /api/v1/payroll/periods/{period_id}/close

# Descargar recibo
GET /api/v1/payroll/runs/{run_id}/payslips/{employee_id}
```

## Fase 3 — Asistencia y tiempo

Módulo `src/epayroll/time/` — cálculo diario desde marcaciones (Arts. 30-36, 48-49 CT).

| Endpoint | Descripción |
|----------|-------------|
| `POST /api/v1/employees/{id}/schedules` | Asignar turno |
| `POST /api/v1/employees/{id}/time-entries` | Registrar marcación |
| `POST /api/v1/employees/{id}/attendance/calculate` | Calcular asistencia del período |
| `GET /api/v1/employees/{id}/attendance` | Consultar resumen diario |
| `POST /api/v1/payroll/runs` | Con `"use_attendance": true` usa asistencia del período |

Flujo demo con asistencia:

```powershell
# Tras run_api.ps1 y GET /api/v1/demo/setup
# 1. POST .../schedules  2. POST .../time-entries  3. POST .../attendance/calculate
# 4. POST /api/v1/payroll/runs con use_attendance: true
```

## Fase 1.5 — Core operativo + API

```powershell
docker compose up -d
.\scripts\migrate.ps1 -Docker
pip install -r requirements.txt
python scripts/seed.py
.\scripts\run_api.ps1
# Swagger: http://127.0.0.1:8000/docs
```

| Endpoint | Descripción |
|----------|-------------|
| `GET /health/db` | Verifica PostgreSQL |
| `GET /api/v1/demo/setup` | Crea empleado demo GT-01 |
| `POST /api/v1/payroll/runs` | Ejecuta motor + persiste en BD |
| `GET /api/v1/payroll/runs/{id}` | Consulta corrida |

## Motor de cálculo (Fase 2)

Python — ver [`src/epayroll/engine/README.md`](./src/epayroll/engine/README.md)

```powershell
python -m pytest tests/ -v
python scripts/run_payroll_demo.py
```

## Base de datos (Fase 1)

PostgreSQL 16 — ver [`database/README.md`](./database/README.md)

```powershell
docker compose up -d
.\scripts\migrate.ps1 -Docker
pip install -r requirements.txt
python scripts/seed.py
```

## Seed legal (Fase 0)

JSON de tablas maestras en [`docs/seed/`](./docs/seed/) — requiere validación contable.

## Legal

- [Código de Trabajo PDF](./docs/legal/codigo-de-trabajo.pdf)
- [Golden Tests](./docs/legal/GOLDEN_TESTS.md)

## Estado

Ver **[docs/EPAYROLL_STATUS.md](./docs/EPAYROLL_STATUS.md)** para estado detallado, checklist piloto y pasos en apps srv.

**Fase 0** — Blueprint + seed JSON ✅  
**Fase 1** — Migraciones SQL + seed loader ✅  
**Fase 2** — Motor de reglas + GT-01/GT-02 ✅  
**Fase 1.5** — API FastAPI + persistencia corrida ✅  
**Fase 3** — Asistencia automática ✅ (GT-02/GT-03; incapacidades Art. 200 pendiente)  
**Fase 4** — Planilla completa ✅ (piloto end-to-end en apps srv pendiente)  
**Fase 5** — Vacaciones inteligentes ✅ (sustituciones pendiente)  
**Fase 6** — Exportacion SIPE + DGI Form 03 ✅ (validacion portal CSS pendiente)  
**Fase 7** — Integraciones Odoo + ACH ✅ (API Odoo push pendiente)  
**Fase 8** — Analitica gerencial ✅ (UI ejecutiva pendiente)  
**Post-MVP** — Auth EN1, UI web, piloto en apps srv con Docker
