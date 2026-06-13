# Base de datos EPayRoll

PostgreSQL 16 — esquema Fase 1.

## Inicio rápido (Docker)

```powershell
# 1. Levantar PostgreSQL
docker compose up -d

# 2. Esperar healthcheck (~5s)
docker compose ps

# 3. Aplicar migraciones
.\scripts\migrate.ps1 -Docker

# 4. Cargar seed legal
pip install -r requirements.txt
python scripts/seed.py
```

## Estructura

```
database/
  migrations/
    001_init.sql              — enums, auditoría
    002_tenant_organization.sql
    003_master_legal.sql      — 9 dominios (tablas maestras)
    004_employees_contracts.sql
    005_attendance.sql
    006_payroll.sql
    007_benefits_compliance.sql
    008_integrations.sql      — cuentas bancarias, sync Odoo
```

## Convenciones

- **PK:** UUID (`gen_random_uuid()`)
- **Vigencia:** `vigencia_desde`, `vigencia_hasta` en tablas legales
- **Multi-tenant:** `tenant_id` → `organizations` → entidades operativas
- **Histórico legal:** no DELETE; desactivar con vigencia

## Seed

El script `scripts/seed.py` carga JSON desde `docs/seed/`:

| JSON | Tabla |
|------|-------|
| contract_types.json | contract_types |
| payroll_concepts.json | payroll_concepts |
| calculation_rules.json | calculation_rules |
| shift_types.json | shift_types |
| holidays_2026.json | holidays |
| css_rates.json | css_rates |
| se_rates.json | se_rates |
| isr_brackets.json | isr_config + isr_brackets |
| decimo_config.json | decimo_config |
| professional_risk_rates.json | professional_risk_rates |

Incluye tenant demo: `demo-easytech`.

## Verificación

```powershell
docker exec -it epayroll-db psql -U epayroll -d epayroll -c "\dt"
docker exec -it epayroll-db psql -U epayroll -d epayroll -c "SELECT codigo FROM payroll_concepts ORDER BY orden_visual;"
```

## Sin Docker

Requiere `psql` instalado y PostgreSQL 16+.

```powershell
$env:DATABASE_URL = "postgresql://user:pass@localhost:5432/epayroll"
.\scripts\migrate.ps1
python scripts/seed.py
```
