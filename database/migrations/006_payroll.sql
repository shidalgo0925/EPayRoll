-- EPayRoll Fase 1 — Planilla

CREATE TABLE payroll_periods (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id),
    tipo                payroll_period_type NOT NULL DEFAULT 'QUINCENAL',
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE NOT NULL,
    fecha_pago          DATE NOT NULL,
    estado              payroll_period_status NOT NULL DEFAULT 'BORRADOR',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fecha_fin >= fecha_inicio)
);

CREATE INDEX idx_payroll_periods_org ON payroll_periods (organization_id, fecha_inicio DESC);

CREATE TRIGGER trg_payroll_periods_updated_at
    BEFORE UPDATE ON payroll_periods FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE payroll_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_period_id       UUID NOT NULL REFERENCES payroll_periods(id),
    fecha_ejecucion         TIMESTAMPTZ NOT NULL DEFAULT now(),
    ejecutado_por           UUID,
    version_motor           VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    config_snapshot         JSONB NOT NULL DEFAULT '{}',
    estado                  VARCHAR(30) NOT NULL DEFAULT 'COMPLETADO',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_payroll_runs_period ON payroll_runs (payroll_period_id);

CREATE TABLE payroll_lines (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id         UUID NOT NULL REFERENCES employees(id),
    concept_id          UUID NOT NULL REFERENCES payroll_concepts(id),
    cantidad            NUMERIC(12, 4) NOT NULL DEFAULT 1,
    base_calculo        NUMERIC(14, 4),
    monto               NUMERIC(14, 2) NOT NULL,
    orden               INTEGER NOT NULL DEFAULT 0,
    referencia_legal    VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_payroll_lines_run_emp ON payroll_lines (payroll_run_id, employee_id);
CREATE INDEX idx_payroll_lines_concept ON payroll_lines (concept_id);

CREATE TABLE payroll_employee_summary (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id          UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id             UUID NOT NULL REFERENCES employees(id),
    bruto                   NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total_deducciones       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    neto                    NUMERIC(14, 2) NOT NULL DEFAULT 0,
    aportes_patronales      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payroll_run_id, employee_id)
);

CREATE TABLE payslips (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
    employee_id         UUID NOT NULL REFERENCES employees(id),
    pdf_url             TEXT,
    fecha_emision       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payroll_run_id, employee_id)
);

-- Acumulados ISR YTD por empleado
CREATE TABLE employee_isr_ytd (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id),
    anio                INTEGER NOT NULL,
    mes                 INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    ingreso_gravable    NUMERIC(14, 2) NOT NULL DEFAULT 0,
    isr_retenido        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, anio, mes)
);
