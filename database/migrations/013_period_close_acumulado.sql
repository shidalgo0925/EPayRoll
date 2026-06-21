-- Cierre de período: corrida oficial + histórico por empleado/período

ALTER TABLE payroll_periods
    ADD COLUMN IF NOT EXISTS cerrado_run_id UUID REFERENCES payroll_runs(id),
    ADD COLUMN IF NOT EXISTS cerrado_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS employee_payroll_acumulado (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id),
    employee_id         UUID NOT NULL REFERENCES employees(id),
    payroll_period_id   UUID NOT NULL REFERENCES payroll_periods(id),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id),
    anio                INT NOT NULL,
    mes                 INT NOT NULL,
    bruto               NUMERIC(14, 2) NOT NULL,
    neto                NUMERIC(14, 2) NOT NULL,
    dias_trabajados     NUMERIC(6, 2) NOT NULL DEFAULT 0,
    dias_ausencia       INT NOT NULL DEFAULT 0,
    dias_vacaciones     INT NOT NULL DEFAULT 0,
    monto_desc_ausencia NUMERIC(14, 2) NOT NULL DEFAULT 0,
    isr_retenido        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    css_empleado        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    ingreso_gravable    NUMERIC(14, 2) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (payroll_period_id, employee_id)
);

CREATE INDEX IF NOT EXISTS idx_emp_payroll_acum_emp_anio
    ON employee_payroll_acumulado (employee_id, anio, mes);
