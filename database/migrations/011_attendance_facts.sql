-- EPayRoll — Tabla estándar de asistencia (hechos, no cálculos)
-- Fuente única entre relojes/API/Excel/manual y el motor de planilla.

CREATE TYPE attendance_day_type AS ENUM ('NORMAL', 'DOMINGO', 'FERIADO');
CREATE TYPE attendance_fact_status AS ENUM ('PENDIENTE', 'VALIDO', 'ERROR');
CREATE TYPE attendance_import_status AS ENUM ('RECIBIDO', 'VALIDANDO', 'VALIDO', 'PARCIAL', 'ERROR');

CREATE TABLE attendance_import_batches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    fuente              VARCHAR(50) NOT NULL DEFAULT 'MANUAL',
    nombre_archivo      VARCHAR(255),
    fecha_inicio        DATE,
    fecha_fin           DATE,
    total_filas         INTEGER NOT NULL DEFAULT 0,
    filas_validas       INTEGER NOT NULL DEFAULT 0,
    filas_error         INTEGER NOT NULL DEFAULT 0,
    estado              attendance_import_status NOT NULL DEFAULT 'RECIBIDO',
    notas               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_att_import_batches_org ON attendance_import_batches (organization_id, created_at DESC);

CREATE TABLE attendance_facts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    fecha               DATE NOT NULL,
    turno               VARCHAR(80),
    hora_entrada        TIME,
    hora_salida         TIME,
    descanso_minutos    INTEGER NOT NULL DEFAULT 0,
    tipo_dia            attendance_day_type NOT NULL DEFAULT 'NORMAL',
    ausencia            BOOLEAN NOT NULL DEFAULT false,
    incapacidad         BOOLEAN NOT NULL DEFAULT false,
    vacaciones          BOOLEAN NOT NULL DEFAULT false,
    observacion         TEXT,
    fuente              VARCHAR(50) NOT NULL DEFAULT 'MANUAL',
    import_batch_id     UUID REFERENCES attendance_import_batches(id) ON DELETE SET NULL,
    estado_validacion   attendance_fact_status NOT NULL DEFAULT 'PENDIENTE',
    errores_validacion  JSONB NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, fecha)
);

CREATE INDEX idx_attendance_facts_org_fecha ON attendance_facts (organization_id, fecha);
CREATE INDEX idx_attendance_facts_emp_fecha ON attendance_facts (employee_id, fecha);
CREATE INDEX idx_attendance_facts_batch ON attendance_facts (import_batch_id);
CREATE INDEX idx_attendance_facts_estado ON attendance_facts (organization_id, estado_validacion);

CREATE TRIGGER trg_attendance_facts_updated_at
    BEFORE UPDATE ON attendance_facts FOR EACH ROW EXECUTE FUNCTION set_updated_at();
