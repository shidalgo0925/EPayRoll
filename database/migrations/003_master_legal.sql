-- EPayRoll Fase 1 — Tablas maestras legales (9 dominios)

-- ---------------------------------------------------------------------------
-- Dominio 1: Laboral
-- ---------------------------------------------------------------------------

CREATE TABLE contract_types (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo                      VARCHAR(50) NOT NULL,
    descripcion                 VARCHAR(255) NOT NULL,
    genera_prima_antiguedad     BOOLEAN NOT NULL DEFAULT false,
    genera_vacaciones           BOOLEAN NOT NULL DEFAULT true,
    genera_decimo_tercer        BOOLEAN NOT NULL DEFAULT true,
    proporcional_prestaciones   BOOLEAN NOT NULL DEFAULT true,
    genera_fondo_cesantia       BOOLEAN NOT NULL DEFAULT false,
    activo                      BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde              DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta              DATE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by                  UUID,
    updated_by                  UUID,
    UNIQUE (codigo, vigencia_desde)
);

CREATE TABLE payroll_concepts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo                  VARCHAR(50) NOT NULL,
    descripcion             VARCHAR(255) NOT NULL,
    tipo                    payroll_concept_type NOT NULL,
    naturaleza              concept_nature NOT NULL DEFAULT 'ORDINARIO',
    imprime_recibo          BOOLEAN NOT NULL DEFAULT true,
    acumulable_aguinaldo    BOOLEAN NOT NULL DEFAULT false,
    acumulable_vacaciones   BOOLEAN NOT NULL DEFAULT false,
    cotizable_css           BOOLEAN NOT NULL DEFAULT false,
    cotizable_se            BOOLEAN NOT NULL DEFAULT false,
    gravable_isr            BOOLEAN NOT NULL DEFAULT false,
    orden_visual            INTEGER NOT NULL DEFAULT 0,
    activo                  BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde          DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta          DATE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by              UUID,
    updated_by              UUID,
    UNIQUE (codigo, vigencia_desde)
);

CREATE TABLE calculation_rules (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id              UUID NOT NULL REFERENCES payroll_concepts(id),
    condicion_aplicacion    TEXT NOT NULL DEFAULT 'true',
    base_calculo            TEXT NOT NULL,
    unidad                  calculation_unit NOT NULL DEFAULT 'FORMULA',
    aplica_contratos        TEXT[] NOT NULL DEFAULT '{}',
    prioridad_calculo       INTEGER NOT NULL DEFAULT 100,
    redondeo                rounding_mode NOT NULL DEFAULT 'CENTESIMO',
    referencia_legal        VARCHAR(255),
    nota                    TEXT,
    activo                  BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde          DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta          DATE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by              UUID,
    updated_by              UUID
);

CREATE INDEX idx_calc_rules_concept ON calculation_rules (concept_id);
CREATE INDEX idx_calc_rules_vigencia ON calculation_rules (vigencia_desde, vigencia_hasta);
CREATE INDEX idx_calc_rules_prioridad ON calculation_rules (prioridad_calculo);

CREATE TABLE shift_types (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo                  VARCHAR(50) NOT NULL,
    descripcion             VARCHAR(255) NOT NULL,
    hora_inicio             TIME NOT NULL,
    hora_fin                TIME NOT NULL,
    tipo_jornada            jornada_type NOT NULL,
    horas_max_dia           NUMERIC(4, 2) NOT NULL,
    horas_max_semana        NUMERIC(4, 2) NOT NULL,
    recargo_domingo         NUMERIC(5, 4) NOT NULL DEFAULT 0.50,
    recargo_feriado         NUMERIC(5, 4) NOT NULL DEFAULT 1.50,
    maximo_extras_diarias   NUMERIC(4, 2) NOT NULL DEFAULT 3.0,
    maximo_extras_semanales NUMERIC(4, 2) NOT NULL DEFAULT 9.0,
    activo                  BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde          DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta          DATE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (codigo, vigencia_desde)
);

CREATE TABLE holidays (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fecha               DATE NOT NULL,
    descripcion         VARCHAR(255) NOT NULL,
    tipo                holiday_type NOT NULL DEFAULT 'FERIADO_NACIONAL',
    recargo_trabajar    NUMERIC(5, 4) NOT NULL DEFAULT 1.50,
    es_recuperable      BOOLEAN NOT NULL DEFAULT false,
    anio                INTEGER NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (fecha, descripcion)
);

CREATE INDEX idx_holidays_fecha ON holidays (fecha);
CREATE INDEX idx_holidays_anio ON holidays (anio);

-- ---------------------------------------------------------------------------
-- Dominio 2–3: CSS y Seguro Educativo
-- ---------------------------------------------------------------------------

CREATE TABLE css_rates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concepto            VARCHAR(80) NOT NULL,
    porcentaje_empleado NUMERIC(6, 4) NOT NULL DEFAULT 0,
    porcentaje_empleador NUMERIC(6, 4) NOT NULL DEFAULT 0,
    sobre_base          VARCHAR(100) NOT NULL DEFAULT 'bruto_cotizable',
    tope_mensual        NUMERIC(12, 2),
    referencia_legal    VARCHAR(255),
    nota                TEXT,
    activo              BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde      DATE NOT NULL,
    vigencia_hasta      DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_css_rates_vigencia ON css_rates (vigencia_desde, vigencia_hasta);
CREATE UNIQUE INDEX uq_css_rates_concepto_vigencia ON css_rates (concepto, vigencia_desde);

CREATE TABLE css_contributable_concepts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concept_id          UUID NOT NULL REFERENCES payroll_concepts(id),
    incluye_en_base     BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde      DATE NOT NULL,
    vigencia_hasta      DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE se_rates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    concepto            VARCHAR(80) NOT NULL,
    porcentaje          NUMERIC(6, 4) NOT NULL,
    parte               VARCHAR(20) NOT NULL CHECK (parte IN ('EMPLEADO', 'EMPLEADOR')),
    sobre_base          VARCHAR(100) NOT NULL DEFAULT 'bruto_cotizable_se',
    referencia_legal    VARCHAR(255),
    activo              BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde      DATE NOT NULL,
    vigencia_hasta      DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Dominio 4: ISR
-- ---------------------------------------------------------------------------

CREATE TABLE isr_config (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metodo                  VARCHAR(50) NOT NULL DEFAULT 'ANUAL_PROYECTADO',
    factor_anualizacion     INTEGER NOT NULL DEFAULT 13,
    deduccion_previa        VARCHAR(50) NOT NULL DEFAULT 'css_empleado',
    referencia_legal        VARCHAR(255),
    vigencia_desde          DATE NOT NULL,
    vigencia_hasta          DATE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE isr_brackets (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id                   UUID NOT NULL REFERENCES isr_config(id) ON DELETE CASCADE,
    rango_desde                 NUMERIC(14, 2) NOT NULL,
    rango_hasta                 NUMERIC(14, 2),
    porcentaje                  NUMERIC(6, 4) NOT NULL,
    excedente_desde             NUMERIC(14, 2) NOT NULL DEFAULT 0,
    impuesto_fijo_acumulado     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    orden                       INTEGER NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_isr_brackets_config ON isr_brackets (config_id, orden);

-- ---------------------------------------------------------------------------
-- Dominio 5: Décimo
-- ---------------------------------------------------------------------------

CREATE TABLE decimo_config (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fechas_pago             JSONB NOT NULL,
    meses_acumulacion       JSONB NOT NULL,
    formula                 TEXT NOT NULL DEFAULT 'sum(salarios_cotizables_periodo) / 12',
    cotiza_css              BOOLEAN NOT NULL DEFAULT true,
    tasa_css_decimo         NUMERIC(6, 4) NOT NULL DEFAULT 0.0725,
    cotiza_se               BOOLEAN NOT NULL DEFAULT false,
    gravable_isr            BOOLEAN NOT NULL DEFAULT false,
    proporcional_liquidacion BOOLEAN NOT NULL DEFAULT true,
    referencia_legal        VARCHAR(255),
    vigencia_desde          DATE NOT NULL,
    vigencia_hasta          DATE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Dominio 6: Salario mínimo
-- ---------------------------------------------------------------------------

CREATE TABLE sm_occupations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actividad_id        UUID NOT NULL REFERENCES sm_activities(id),
    region_id           UUID NOT NULL REFERENCES sm_regions(id),
    codigo              VARCHAR(50) NOT NULL,
    descripcion         VARCHAR(255) NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (actividad_id, region_id, codigo)
);

CREATE TABLE sm_rates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occupation_id       UUID NOT NULL REFERENCES sm_occupations(id),
    monto               NUMERIC(12, 2) NOT NULL,
    tipo_pago           payment_frequency NOT NULL DEFAULT 'MENSUAL',
    vigencia_desde      DATE NOT NULL,
    vigencia_hasta      DATE,
    referencia_decreto  VARCHAR(100),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sm_rates_vigencia ON sm_rates (vigencia_desde, vigencia_hasta);

-- ---------------------------------------------------------------------------
-- Dominio 7: Riesgo profesional
-- ---------------------------------------------------------------------------

CREATE TABLE professional_risk_rates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo_actividad    VARCHAR(50) NOT NULL,
    descripcion         VARCHAR(255) NOT NULL,
    porcentaje_riesgo   NUMERIC(6, 4) NOT NULL,
    activo              BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde      DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta      DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (codigo_actividad, vigencia_desde)
);
