-- EPayRoll Fase 7 — Integraciones bancarias

CREATE TABLE employee_bank_accounts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    banco               VARCHAR(50) NOT NULL,
    tipo_cuenta         VARCHAR(20) NOT NULL DEFAULT 'AHORROS',
    numero_cuenta       VARCHAR(50) NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, banco, numero_cuenta)
);

CREATE INDEX idx_employee_bank_accounts_emp ON employee_bank_accounts (employee_id) WHERE activo = true;

CREATE TRIGGER trg_employee_bank_accounts_updated_at
    BEFORE UPDATE ON employee_bank_accounts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE integration_sync_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id),
    integracion         VARCHAR(50) NOT NULL,
    direccion           VARCHAR(20) NOT NULL DEFAULT 'INBOUND',
    registros_ok        INTEGER NOT NULL DEFAULT 0,
    registros_error     INTEGER NOT NULL DEFAULT 0,
    detalle             JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
