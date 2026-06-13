-- EPayRoll Fase 1 — Prestaciones, liquidaciones y exportaciones

CREATE TABLE vacation_balances (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    dias_ganados        NUMERIC(6, 2) NOT NULL DEFAULT 0,
    dias_gozados          NUMERIC(6, 2) NOT NULL DEFAULT 0,
    dias_pendientes     NUMERIC(6, 2) NOT NULL DEFAULT 0,
    fecha_corte         DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, fecha_corte)
);

CREATE TABLE vacation_requests (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE NOT NULL,
    dias_solicitados    NUMERIC(5, 2) NOT NULL,
    estado              vacation_request_status NOT NULL DEFAULT 'SOLICITADO',
    aprobado_por        UUID,
    notificado_mitradel BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE decimo_accumulations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    anio                INTEGER NOT NULL,
    trimestre           INTEGER NOT NULL CHECK (trimestre IN (1, 2, 3)),
    salarios_sumados    NUMERIC(14, 2) NOT NULL DEFAULT 0,
    monto_calculado     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    pagado              BOOLEAN NOT NULL DEFAULT false,
    fecha_pago          DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (employee_id, anio, trimestre)
);

CREATE TABLE seniority_provisions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id             UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    semanas_acumuladas      NUMERIC(8, 2) NOT NULL DEFAULT 0,
    monto_provisionado      NUMERIC(14, 2) NOT NULL DEFAULT 0,
    fecha_corte             DATE NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE severance_fund (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id                 UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    cotizaciones_trimestrales   JSONB NOT NULL DEFAULT '[]',
    saldo                       NUMERIC(14, 2) NOT NULL DEFAULT 0,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE termination_cases (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id             UUID NOT NULL REFERENCES employees(id),
    contract_id             UUID REFERENCES contracts(id),
    fecha_terminacion       DATE NOT NULL,
    causa                   VARCHAR(100) NOT NULL,
    monto_vacaciones        NUMERIC(14, 2) NOT NULL DEFAULT 0,
    monto_decimo            NUMERIC(14, 2) NOT NULL DEFAULT 0,
    monto_prima             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    monto_preaviso          NUMERIC(14, 2) NOT NULL DEFAULT 0,
    monto_indemnizacion     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    total                   NUMERIC(14, 2) NOT NULL DEFAULT 0,
    calculado_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by              UUID
);

-- ---------------------------------------------------------------------------
-- Exportaciones cumplimiento
-- ---------------------------------------------------------------------------

CREATE TABLE sipe_exports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id),
    archivo_path        TEXT,
    fecha_generacion    TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_envio         TIMESTAMPTZ,
    estado              export_status NOT NULL DEFAULT 'PENDIENTE',
    errores             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dgi_exports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id),
    formulario          VARCHAR(50) NOT NULL DEFAULT 'FORM_03',
    periodo             VARCHAR(20) NOT NULL,
    monto_total         NUMERIC(14, 2) NOT NULL,
    archivo_path        TEXT,
    estado              export_status NOT NULL DEFAULT 'PENDIENTE',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bank_exports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payroll_run_id      UUID NOT NULL REFERENCES payroll_runs(id),
    banco               VARCHAR(50) NOT NULL,
    archivo_path        TEXT,
    estado              export_status NOT NULL DEFAULT 'PENDIENTE',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
