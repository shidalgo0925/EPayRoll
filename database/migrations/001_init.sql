-- EPayRoll Fase 1 — Extensiones, enums y auditoría
-- PostgreSQL 16+

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

CREATE TYPE payroll_concept_type AS ENUM (
    'INGRESO', 'DESCUENTO', 'APORTE_EMPLEADOR', 'PROVISION'
);

CREATE TYPE concept_nature AS ENUM (
    'ORDINARIO', 'EXTRAORDINARIO', 'NO_SALARIAL'
);

CREATE TYPE calculation_unit AS ENUM (
    'UNIDAD', 'PORCENTAJE', 'VALOR_FIJO', 'FORMULA', 'MOTOR_ISR'
);

CREATE TYPE rounding_mode AS ENUM (
    'CENTESIMO', 'DECIMO', 'ENTERO'
);

CREATE TYPE jornada_type AS ENUM (
    'DIURNA', 'NOCTURNA', 'MIXTA'
);

CREATE TYPE holiday_type AS ENUM (
    'FERIADO_NACIONAL', 'FERIADO_LOCAL', 'PUENTE'
);

CREATE TYPE payment_frequency AS ENUM (
    'MENSUAL', 'QUINCENAL', 'SEMANAL', 'HORA'
);

CREATE TYPE contract_status AS ENUM (
    'ACTIVO', 'SUSPENDIDO', 'TERMINADO'
);

CREATE TYPE payroll_period_status AS ENUM (
    'BORRADOR', 'CALCULADO', 'CERRADO', 'ANULADO'
);

CREATE TYPE payroll_period_type AS ENUM (
    'QUINCENAL', 'MENSUAL', 'SEMANAL', 'DECIMO', 'LIQUIDACION'
);

CREATE TYPE vacation_request_status AS ENUM (
    'SOLICITADO', 'APROBADO', 'RECHAZADO', 'GOZADO', 'CANCELADO'
);

CREATE TYPE export_status AS ENUM (
    'PENDIENTE', 'GENERADO', 'ENVIADO', 'ERROR'
);

-- ---------------------------------------------------------------------------
-- Auditoría (append-only)
-- ---------------------------------------------------------------------------

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID,
    entity_type     VARCHAR(100) NOT NULL,
    entity_id       UUID NOT NULL,
    action          VARCHAR(20) NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
    user_id         UUID,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    old_values      JSONB,
    new_values      JSONB,
    metadata        JSONB
);

CREATE INDEX idx_audit_log_entity ON audit_log (entity_type, entity_id);
CREATE INDEX idx_audit_log_tenant_occurred ON audit_log (tenant_id, occurred_at DESC);

CREATE TABLE rule_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_table      VARCHAR(100) NOT NULL,
    rule_id         UUID NOT NULL,
    version         INTEGER NOT NULL,
    snapshot        JSONB NOT NULL,
    vigencia_desde  DATE NOT NULL,
    vigencia_hasta  DATE,
    approved_by     UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (rule_table, rule_id, version)
);

-- Helper: columnas de auditoría estándar en tablas maestras
-- created_at, updated_at, created_by, updated_by, activo, vigencia_desde, vigencia_hasta

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE schema_migrations (
    version             VARCHAR(20) PRIMARY KEY,
    applied_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
