-- EPayRoll — Planilla operativa: ficha, ajustes por corrida, tasas y cuentas por org

ALTER TABLE employees ADD COLUMN IF NOT EXISTS ficha VARCHAR(30);

CREATE INDEX IF NOT EXISTS idx_employees_ficha ON employees (organization_id, ficha)
    WHERE ficha IS NOT NULL;

-- Tasas legales parametrizables por organización (override sobre seed global)
CREATE TABLE organization_legal_rates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    codigo              VARCHAR(80) NOT NULL,
    descripcion         VARCHAR(255),
    porcentaje_empleado NUMERIC(8, 4),
    porcentaje_empleador NUMERIC(8, 4),
    vigencia_desde      DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta      DATE,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, codigo, vigencia_desde)
);

CREATE INDEX idx_org_legal_rates_org ON organization_legal_rates (organization_id, activo);

CREATE TRIGGER trg_org_legal_rates_updated_at
    BEFORE UPDATE ON organization_legal_rates FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Cuentas contables por concepto (planilla / Odoo) por organización
CREATE TABLE organization_account_codes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    concepto_codigo     VARCHAR(50) NOT NULL,
    cuenta_codigo       VARCHAR(20) NOT NULL,
    etiqueta            VARCHAR(100),
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, concepto_codigo)
);

CREATE TRIGGER trg_org_account_codes_updated_at
    BEFORE UPDATE ON organization_account_codes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Ajustes operativos por empleado/corrida (préstamos, banco, días, DEV ISR)
CREATE TABLE payroll_run_adjustments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id         UUID NOT NULL REFERENCES employees(id),
    dias_trabajados     NUMERIC(6, 2),
    dias_descuento      NUMERIC(6, 2) NOT NULL DEFAULT 0,
    monto_desc_dias     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    dev_isr             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    prestamo_empleado   NUMERIC(14, 2) NOT NULL DEFAULT 0,
    desc_prestamo       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    descuento_banco     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    saldo_prestamo      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    notas               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payroll_run_id, employee_id)
);

CREATE INDEX idx_payroll_adj_run ON payroll_run_adjustments (payroll_run_id);

CREATE TRIGGER trg_payroll_run_adjustments_updated_at
    BEFORE UPDATE ON payroll_run_adjustments FOR EACH ROW EXECUTE FUNCTION set_updated_at();
