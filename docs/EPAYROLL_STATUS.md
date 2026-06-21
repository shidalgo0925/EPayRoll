# EPayRoll — Estado actual y continuación

**Última actualización:** 2026-06-21  
**Workspace:** `EPayRoll` — Easy Technology Services / EN1  
**Documento vivo:** leer esto al retomar el proyecto (PC local, apps srv o Cursor Remote SSH).

Padre: [EPAYROLL_MASTER_PLAN.md](./EPAYROLL_MASTER_PLAN.md) · Plan de fases: [EPAYROLL_ROADMAP.md](./EPAYROLL_ROADMAP.md)

---

## 1. Dónde estamos (resumen ejecutivo)

| Item | Estado |
|------|--------|
| **MVP backend (Fases 0–8)** | ✅ Código completo |
| **Tests unitarios** | ✅ 75 passed, 1 skipped (`test_db_config` integración BD) |
| **BD + migraciones** | ✅ 12 migraciones SQL (`001`–`012`) |
| **Producción** | ✅ https://eplanilla.etsrv.site/app/ |
| **Git** | ✅ `git@github.com:shidalgo0925/EPayRoll.git` (main) |
| **Próximo paso operativo** | SIPE portal CSS · validación contador |
| **Próximo paso producto** | SIPE portal CSS · post-MVP operativo |
| **Al final del roadmap** | Validación contador — `python scripts/golden_report.py` (GT-01…GT-10, firma ISR/SIPE) |

### Hitos completados en código

| Fase | Entregable | Tests / notas |
|------|------------|---------------|
| 0 | Blueprint + seed JSON | GT-01…GT-10 documentados |
| 1 | Modelo datos + migraciones | `database/migrations/` |
| 1.5 | API FastAPI + persistencia | `src/epayroll/api/main.py` |
| 1.5 | Auth EN1 stub/JWT/en1 + RBAC + SSO OAuth | `src/epayroll/auth/` — `tests/test_sso.py` |
| 2 | Motor de reglas | `tests/test_engine.py` |
| 3 | Asistencia (extras, feriados) | `tests/test_attendance.py` |
| 3.5 | Incapacidades Art. 200 + fondo licencia | `tests/test_incapacity.py` — GT-10 |
| 4 | Planilla, décimo, ISR YTD, liquidación, PDF | `tests/test_payroll_phase4.py`, `test_liquidation.py`, `test_payslip.py` |
| 5.5 | Sustituciones vacaciones + cobertura | `tests/test_vacation_substitutions.py` |
| 6 | SIPE 24 cols + DGI Form 03 | `tests/test_sipe_export.py` (GT-08) |
| 7 | Odoo sync/journal + ACH + push API | `tests/test_integrations.py`, `tests/test_odoo_push.py` |
| 8 | Analítica gerencial + UI ejecutiva | `tests/test_analytics.py`, dashboard `/app` |

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

### 3.4 Piloto end-to-end (checklist)

- [x] `GET /api/v1/demo/setup` — empleado demo GT-01
- [x] `POST /api/v1/payroll/periods/{id}/run` — corrida quincenal batch
- [x] `POST /api/v1/payroll/periods/{id}/close` — recibos PDF
- [x] `POST /api/v1/exports/sipe/{run_id}` — SIPE + conciliación GT-08
- [x] `POST /api/v1/exports/dgi/{run_id}` — Form 03
- [x] `POST /api/v1/employees/{id}/bank-account` + `POST /api/v1/exports/ach/{run_id}` (banco `BANCO_GENERAL`)
- [x] `GET /api/v1/organizations/{id}/analytics/dashboard?fecha_inicio=...&fecha_fin=...`

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
| `009_vacation_substitutions.sql` | Sustitutos vacaciones |
| `010_planilla_operational.sql` | Ficha, ajustes corrida, tasas/cuentas org |
| `011_attendance_facts.sql` | Tabla estándar asistencia |
| `012_rules_org_rates.sql` | Reglas motor con tasas variables |

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
| ~~**P0**~~ | ~~Piloto end-to-end en apps srv~~ | 4 | ✅ Checklist §3.4 |
| ~~**P0**~~ | ~~Validación contador golden tests~~ | 0, 4, 6 | ⏸️ **Al final** — `golden_report.py` listo |
| ~~**P0**~~ | ~~Servicio systemd API~~ | DevOps | ✅ `scripts/install_systemd.sh` |
| ~~**P1**~~ | ~~Auth EN1 + tenant isolation~~ | 1.5 | ✅ stub + JWT (`src/epayroll/auth/`) |
| ~~**P1**~~ | ~~UI web (React o EN1)~~ | — | ✅ MVP estático `/app` |
| ~~**P1**~~ | ~~UI EN1 integrada (SSO)~~ | — | ✅ OAuth + JWKS + botón EN1 en UI |
| ~~**P2**~~ | ~~Incapacidades Art. 200~~ | 3.5 | ✅ GT-10 `time/incapacity.py` + API |
| ~~**P2**~~ | ~~Sustituciones vacaciones~~ | 5.5 | ✅ API cobertura + sustituto |
| ~~**P2**~~ | ~~Push automático Odoo API~~ | 7 | ✅ `POST .../odoo/journal/{id}/push` |
| ~~**P2**~~ | ~~Validación salario mínimo~~ | 1.5 | ✅ GT-07 `compliance/minimum_wage.py` |
| ~~**P3**~~ | ~~UI dashboard ejecutivo~~ | 8 | ✅ KPIs, alertas, pasivos, proyección |
| ~~**P3**~~ | ~~UI vacaciones + incapacidades~~ | 3, 5 | ✅ Pantallas `/app` |
| ~~**P3**~~ | ~~Dockerizar API~~ | DevOps | ✅ `Dockerfile` + compose |
| ~~**P1**~~ | ~~UI liquidaciones~~ | 4 | ✅ Pantalla `/app` — GT-05/GT-06 |
| ~~**P1**~~ | ~~Operación multi-empleado~~ | 4 | ✅ Alta + contrato, corrida batch multi-emp |
| ~~**P1**~~ | ~~Planilla operador (26 cols)~~ | 4 | ✅ Vista web + ajustes inline |
| ~~**P1**~~ | ~~Asistencia estándar (facts table)~~ | 3 | ✅ CSV/API + UI + use_attendance |
| ~~**P1**~~ | ~~Tasas legales por org en motor~~ | 2 | ✅ `organization_legal_rates` + reglas variables |
| **P2** | Planilla honorarios (sin nómina CSS) | 4 | ❌ |
| **P2** | SIPE portal CSS | 6 | Prueba en ambiente CSS |

---

## 6. Comandos útiles (cualquier entorno)

```powershell
# Tests (no requieren BD)
python -m pytest tests/ -v

# Informe golden para contador (genera storage/reports/golden_YYYYMMDD.md)
python scripts/golden_report.py

# Servicio permanente (Linux apps srv)
sudo bash scripts/install_systemd.sh
journalctl -u epayroll-api -f

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
EPAYROLL_DB_PORT=5432
PYTHONPATH=src
EPAYROLL_AUTH_MODE=stub
# Headers: X-Tenant-Id (requerido), X-Organization-Id, X-User-Id, X-Roles
# Demo tenant seed: 00000000-0000-0000-0000-000000000001
```

Ver `.env.example` en la raíz del repo.

---

## 9. Historial de sesiones (bitácora breve)

| Fecha | Qué se hizo |
|-------|-------------|
| 2026-06-13 | Fases 3–8 implementadas (asistencia → analítica). 40 tests pass. |
| 2026-06-13 | Intento Docker en PC local — falló (CLI no instalada). |
| 2026-06-13 | Piloto end-to-end apps srv completado (puertos 5433/8001). |
| 2026-06-13 | Sustituciones vacaciones + push Odoo API. 70 tests pass. |
| 2026-06-21 | Planilla operador: vista 26 cols, config legal por org, ficha/teléfono. Sin export Excel — solo UI web. |

---

*Actualizar este archivo al completar el piloto en srv o al cerrar items del backlog.*
