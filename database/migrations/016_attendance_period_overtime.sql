-- Horas extra capturadas a nivel período (global por empleado, no por día)

CREATE TABLE IF NOT EXISTS attendance_period_overtime (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_id                 UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    fecha_inicio                DATE NOT NULL,
    fecha_fin                   DATE NOT NULL,
    horas_extra_diurnas         NUMERIC(8, 2) NOT NULL DEFAULT 0,
    horas_extra_nocturnas       NUMERIC(8, 2) NOT NULL DEFAULT 0,
    horas_extra_mixta_nocturnas NUMERIC(8, 2) NOT NULL DEFAULT 0,
    horas_domingo               NUMERIC(8, 2) NOT NULL DEFAULT 0,
    horas_feriado               NUMERIC(8, 2) NOT NULL DEFAULT 0,
    activo                      BOOLEAN NOT NULL DEFAULT true,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, fecha_inicio, fecha_fin)
);

CREATE INDEX IF NOT EXISTS idx_att_period_ot_org_dates
    ON attendance_period_overtime (organization_id, fecha_inicio, fecha_fin);

CREATE TRIGGER trg_attendance_period_overtime_updated_at
    BEFORE UPDATE ON attendance_period_overtime FOR EACH ROW EXECUTE FUNCTION set_updated_at();
