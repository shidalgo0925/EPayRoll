-- EPayRoll Fase 1 — Asistencia y tiempo

CREATE TABLE employee_schedules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    shift_type_id       UUID NOT NULL REFERENCES shift_types(id),
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_schedules_employee ON employee_schedules (employee_id, fecha_inicio);

CREATE TABLE time_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    timestamp_entrada   TIMESTAMPTZ NOT NULL,
    timestamp_salida    TIMESTAMPTZ,
    fuente              VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_time_entries_employee ON time_entries (employee_id, timestamp_entrada);

CREATE TABLE attendance_daily (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id             UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    fecha                   DATE NOT NULL,
    horas_ordinarias        NUMERIC(5, 2) NOT NULL DEFAULT 0,
    horas_extra_diurna      NUMERIC(5, 2) NOT NULL DEFAULT 0,
    horas_extra_nocturna    NUMERIC(5, 2) NOT NULL DEFAULT 0,
    horas_extra_mixta_noct  NUMERIC(5, 2) NOT NULL DEFAULT 0,
    horas_domingo           NUMERIC(5, 2) NOT NULL DEFAULT 0,
    horas_feriado           NUMERIC(5, 2) NOT NULL DEFAULT 0,
    es_feriado              BOOLEAN NOT NULL DEFAULT false,
    es_domingo              BOOLEAN NOT NULL DEFAULT false,
    dias_trabajados         NUMERIC(3, 1) NOT NULL DEFAULT 0,
    calculado_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, fecha)
);

CREATE INDEX idx_attendance_daily_emp_fecha ON attendance_daily (employee_id, fecha);

CREATE TABLE absences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    fecha               DATE NOT NULL,
    tipo                VARCHAR(50) NOT NULL,
    justificada         BOOLEAN NOT NULL DEFAULT false,
    horas               NUMERIC(5, 2),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE incapacities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE NOT NULL,
    tipo                VARCHAR(50) NOT NULL,
    certificado_ref     VARCHAR(100),
    dias_subsidio_css   INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
