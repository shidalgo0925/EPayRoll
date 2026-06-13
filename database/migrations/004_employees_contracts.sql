-- EPayRoll Fase 1 — Empleados y contratos

CREATE TABLE employees (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id),
    cedula              VARCHAR(50) NOT NULL,
    nombres             VARCHAR(150) NOT NULL,
    apellidos           VARCHAR(150) NOT NULL,
    fecha_nacimiento    DATE,
    estado_civil        VARCHAR(30),
    direccion           TEXT,
    telefono            VARCHAR(30),
    email               CITEXT,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, cedula)
);

CREATE INDEX idx_employees_org ON employees (organization_id);

CREATE TRIGGER trg_employees_updated_at
    BEFORE UPDATE ON employees FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE employee_dependents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    nombre              VARCHAR(200) NOT NULL,
    parentesco          VARCHAR(50) NOT NULL,
    fecha_nacimiento    DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE employee_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    tipo_documento      VARCHAR(80) NOT NULL,
    archivo_url         TEXT,
    fecha_vencimiento   DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE employee_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    tipo_evento         VARCHAR(80) NOT NULL,
    fecha               DATE NOT NULL,
    descripcion         TEXT,
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE contracts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id),
    contract_type_id    UUID NOT NULL REFERENCES contract_types(id),
    shift_type_id       UUID REFERENCES shift_types(id),
    sm_occupation_id    UUID REFERENCES sm_occupations(id),
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE,
    salario_base        NUMERIC(12, 2) NOT NULL,
    forma_pago          payment_frequency NOT NULL DEFAULT 'MENSUAL',
    estado              contract_status NOT NULL DEFAULT 'ACTIVO',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_contracts_employee ON contracts (employee_id);
CREATE INDEX idx_contracts_estado ON contracts (employee_id, estado) WHERE estado = 'ACTIVO';

CREATE TRIGGER trg_contracts_updated_at
    BEFORE UPDATE ON contracts FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE contract_amendments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id         UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    tipo                VARCHAR(80) NOT NULL,
    valor_anterior      TEXT,
    valor_nuevo         TEXT,
    fecha_vigencia      DATE NOT NULL,
    motivo              TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          UUID
);

CREATE TABLE salary_changes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id         UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    salario_anterior    NUMERIC(12, 2) NOT NULL,
    salario_nuevo       NUMERIC(12, 2) NOT NULL,
    fecha_vigencia      DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          UUID
);

CREATE TABLE employee_concept_assignments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    concept_id          UUID NOT NULL REFERENCES payroll_concepts(id),
    valor_fijo          NUMERIC(12, 2),
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, concept_id, fecha_inicio)
);

CREATE INDEX idx_emp_concept_active ON employee_concept_assignments (employee_id, activo)
    WHERE activo = true;
