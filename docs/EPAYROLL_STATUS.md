# EPayRoll — Estado actual y continuación

**Última actualización:** 2026-06-13  
**Workspace:** `EPayRoll` — Easy Technology Services / EN1  
**Documento vivo:** leer esto al retomar el proyecto (PC local, apps srv o Cursor Remote SSH).

Padre: [EPAYROLL_MASTER_PLAN.md](./EPAYROLL_MASTER_PLAN.md) · Plan de fases: [EPAYROLL_ROADMAP.md](./EPAYROLL_ROADMAP.md)

---

## 1. Dónde estamos (resumen ejecutivo)

| Item | Estado |
|------|--------|
| **MVP backend (Fases 0–8)** | ✅ Código completo |
| **Tests unitarios** | ✅ 40 passed, 1 skipped (`test_db_config` integración BD) |
| **BD + migraciones** | ✅ 8 migraciones SQL (`001`–`008`) |
| **Piloto end-to-end con BD** | ⏳ **BLOQUEADO en PC local** — Docker no instalado |
| **Próximo paso operativo** | Levantar en **apps srv** con Docker + piloto quincenal |
| **Próximo paso producto** | Auth EN1, UI web, validación contador |

### Hitos completados en código

| Fase | Entregable | Tests / notas |
|------|------------|---------------|
| 0 | Blueprint + seed JSON | GT-01…GT-10 documentados |
| 1 | Modelo datos + migraciones | `database/migrations/` |
| 1.5 | API FastAPI + persistencia | `src/epayroll/api/main.py` |
| 2 | Motor de reglas | `tests/test_engine.py` |
| 3 | Asistencia (extras, feriados) | `tests/test_attendance.py` — Art. 200 ⏳ |
| 4 | Planilla, décimo, ISR YTD, liquidación, PDF | `tests/test_payroll_phase4.py`, `test_liquidation.py`, `test_payslip.py` |
| 5 | Vacaciones Arts. 52–59 | `tests/test_vacation.py` — sustituciones ⏳ |
| 6 | SIPE 24 cols + DGI Form 03 | `tests/test_sipe_export.py` (GT-08) |
| 7 | Odoo sync/journal + ACH | `tests/test_integrations.py` — push Odoo API ⏳ |
| 8 | Analítica gerencial | `tests/test_analytics.py` — UI ejecutiva ⏳ |

---

## 2. Bloqueo actual (PC local)

En la sesión del **2026-06-13** se intentó `docker compose up -d` en Windows y falló:

```
docker : El término 'docker' no se reconoce...
```

**Conclusión:** el PC de desarrollo no tiene Docker Desktop instalado. El motor y tests funcionan sin BD; la API persistente requiere PostgreSQL (Docker u nativo).

**Decisión del equipo:** continuar en **apps srv** (servidor con Docker).

---

## 3. Cómo continuar en apps srv

### 3.1 Prerrequisitos del servidor

- Docker + Docker Compose
- Python 3.12+
- Git
- Puertos libres: **5432** (Postgres), **8000** (API)
- Cursor **Remote SSH** al srv (recomendado para que el agente ejecute comandos)

### 3.2 Primera vez — bootstrap completo

```bash
# 1. Clonar o copiar repo
git clone <url-repo> EPayRoll && cd EPayRoll

# 2. PostgreSQL en Docker
docker compose up -d
docker compose ps   # esperar healthy

# 3. Migraciones (Linux)
export DATABASE_URL="postgresql://epayroll:epayroll@localhost:5432/epayroll"
for f in database/migrations/*.sql; do
  echo "→ $f"
  docker exec -i epayroll-db psql -U epayroll -d epayroll -v ON_ERROR_STOP=1 < "$f"
  docker exec -i epayroll-db psql -U epayroll -d epayroll -c \
    "INSERT INTO schema_migrations (version) VALUES ('$(basename "$f" .sql)') ON CONFLICT DO NOTHING;"
done

# Alternativa Windows en srv:
# .\scripts\migrate.ps1 -Docker

# 4. Dependencias + seed
pip install -r requirements.txt
python scripts/seed.py

# 5. Tests (sin BD: 40 pass; con BD: 41 pass)
python -m pytest tests/ -v

# 6. API
export PYTHONPATH=src
python -m uvicorn epayroll.api.main:app --host 0.0.0.0 --port 8000
# Swagger: http://<srv>:8000/docs
```

### 3.3 Verificación rápida post-bootstrap

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/api/v1/demo/setup
```

### 3.4 Piloto end-to-end (checklist — **SIGUIENTE TAREA**)

Marcar cuando funcione en apps srv:

- [ ] `GET /api/v1/demo/setup` — empleado demo GT-01
- [ ] `POST /api/v1/payroll/periods/{id}/run` — corrida quincenal batch
- [ ] `POST /api/v1/payroll/periods/{id}/close` — recibos PDF
- [ ] `POST /api/v1/exports/sipe/{run_id}` — SIPE + conciliación GT-08
- [ ] `POST /api/v1/exports/dgi/{run_id}` — Form 03
- [ ] `POST /api/v1/employees/{id}/bank-account` + `POST /api/v1/exports/ach/{run_id}`
- [ ] `GET /api/v1/organizations/{id}/analytics/dashboard?fecha_inicio=...&fecha_fin=...`

**Org demo seed:** `00000000-0000-0000-0000-000000000010`

---

## 4. Mapa de código (referencia rápida)

```
src/epayroll/
  engine/          # Motor planilla, ISR, décimo, liquidación, Art. 161
  time/            # Asistencia, extras, feriados
  vacation/        # Vacaciones Arts. 52–59
  payroll/         # Servicio batch por período
  export/          # SIPE, DGI
  integration/     # ACH, Odoo
  analytics/       # KPIs, pasivos, dashboard ejecutivo
  payslip/         # PDF recibos (fpdf2)
  api/main.py      # Todos los endpoints REST
  db/              # Repositorios PostgreSQL

docs/seed/         # Reglas legales parametrizables (JSON)
database/migrations/  # 001_init … 008_integrations
tests/             # Golden tests automatizados
storage/           # payslips/, exports/ (gitignored)
```

### Migraciones SQL

| Archivo | Contenido |
|---------|-----------|
| `001_init.sql` | Enums, auditoría |
| `002_tenant_organization.sql` | Tenant, org EN1 |
| `003_master_legal.sql` | 9 dominios legales |
| `004_employees_contracts.sql` | Empleados, contratos |
| `005_attendance.sql` | Turnos, marcaciones, ausencias |
| `006_payroll.sql` | Períodos, corridas, líneas, ISR YTD |
| `007_benefits_compliance.sql` | Vacaciones, décimo, liquidaciones, exports |
| `008_integrations.sql` | Cuentas bancarias, sync Odoo |

### Seeds JSON clave

| Archivo | Uso |
|---------|-----|
| `payroll_concepts.json` | Conceptos planilla |
| `calculation_rules.json` | Fórmulas motor |
| `sipe_columns.json` | 24 columnas SIPE A–X |
| `vacation_config.json` | Arts. 52–59 |
| `ach_banco_general.json` | Template ACH |
| `odoo_account_mapping.json` | Asiento contable |
| `analytics_config.json` | Umbrales dashboard |

---

## 5. Backlog priorizado (post-MVP backend)

| Prioridad | Item | Fase | Notas |
|-----------|------|------|-------|
| **P0** | Piloto end-to-end en apps srv | 4 | Checklist §3.4 |
| **P0** | Validación contador golden tests | 0, 4, 6 | GT-01 ISR, SIPE portal CSS |
| **P1** | Auth EN1 + tenant isolation | 1.5 | Bloquea producción multi-tenant |
| **P1** | UI web (React o EN1) | — | Consumir API existente |
| **P2** | Incapacidades Art. 200 | 3.5 | Fondo licencia |
| **P2** | Sustituciones vacaciones | 5.5 | Cobertura MVP |
| **P2** | Push automático Odoo API | 7 | Payload JSON ya listo |
| **P2** | Validación salario mínimo | 1.5 | Decreto vigente |
| **P3** | UI dashboard ejecutivo | 8 | API JSON lista |
| **P3** | Dockerizar API (no solo BD) | DevOps | `docker-compose` servicio `api` |

---

## 6. Comandos útiles (cualquier entorno)

```powershell
# Tests (no requieren BD)
python -m pytest tests/ -v

# Demo motor sin BD
python scripts/run_payroll_demo.py

# API local (requiere PostgreSQL)
$env:PYTHONPATH = "src"
$env:DATABASE_URL = "postgresql://epayroll:epayroll@localhost:5432/epayroll"
.\scripts\run_api.ps1
```

---

## 7. Patrón de trabajo con el agente Cursor

1. Abrir proyecto en Cursor (ideal: **Remote SSH** al apps srv).
2. Decir **`go`** para avanzar la siguiente tarea del backlog.
3. Referenciar este doc: *"continúa según EPAYROLL_STATUS.md"*.
4. Tras piloto en srv, marcar checklist §3.4 y actualizar §1 de este documento.

### Qué pedir en la primera sesión en srv

> "Bootstrap EPayRoll con Docker según docs/EPAYROLL_STATUS.md y ejecuta el piloto end-to-end §3.4"

---

## 8. Variables de entorno

```env
DATABASE_URL=postgresql://epayroll:epayroll@localhost:5432/epayroll
PYTHONPATH=src
```

Ver `.env.example` en la raíz del repo.

---

## 9. Historial de sesiones (bitácora breve)

| Fecha | Qué se hizo |
|-------|-------------|
| 2026-06-13 | Fases 3–8 implementadas (asistencia → analítica). 40 tests pass. |
| 2026-06-13 | Intento Docker en PC local — falló (CLI no instalada). |
| 2026-06-13 | Decisión: continuar despliegue en apps srv. Este doc creado. |

---

*Actualizar este archivo al completar el piloto en srv o al cerrar items del backlog.*
