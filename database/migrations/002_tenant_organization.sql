-- EPayRoll Fase 1 — Tenant y organización (EN1)

CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          VARCHAR(255) NOT NULL,
    slug            CITEXT NOT NULL UNIQUE,
    config          JSONB NOT NULL DEFAULT '{}',
    activo          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_tenants_updated_at
    BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE sm_activities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo          VARCHAR(50) NOT NULL UNIQUE,
    descripcion     VARCHAR(255) NOT NULL,
    activo          BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde  DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta  DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID,
    updated_by      UUID
);

CREATE TABLE sm_regions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo          VARCHAR(50) NOT NULL UNIQUE,
    descripcion     VARCHAR(255) NOT NULL,
    activo          BOOLEAN NOT NULL DEFAULT true,
    vigencia_desde  DATE NOT NULL DEFAULT CURRENT_DATE,
    vigencia_hasta  DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organizations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    razon_social            VARCHAR(255) NOT NULL,
    ruc                     VARCHAR(50),
    actividad_economica_id    UUID REFERENCES sm_activities(id),
    region_id               UUID REFERENCES sm_regions(id),
    codigo_css_actividad    VARCHAR(50),
    activo                  BOOLEAN NOT NULL DEFAULT true,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, ruc)
);

CREATE INDEX idx_organizations_tenant ON organizations (tenant_id);

CREATE TRIGGER trg_organizations_updated_at
    BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE organization_settings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    periodo_pago        payment_frequency NOT NULL DEFAULT 'QUINCENAL',
    moneda              CHAR(3) NOT NULL DEFAULT 'PAB',
    zona_horaria        VARCHAR(64) NOT NULL DEFAULT 'America/Panama',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_organization_settings_updated_at
    BEFORE UPDATE ON organization_settings FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE organization_risk_classification (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    codigo_actividad    VARCHAR(50) NOT NULL,
    porcentaje_riesgo   NUMERIC(6, 4) NOT NULL,
    vigencia_desde      DATE NOT NULL,
    vigencia_hasta      DATE,
    activo              BOOLEAN NOT NULL DEFAULT true,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_org_risk_org_vigencia ON organization_risk_classification (organization_id, vigencia_desde, vigencia_hasta);
