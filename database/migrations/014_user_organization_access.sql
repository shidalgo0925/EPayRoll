-- Usuarios de aplicación y membresía por empresa (multi-tenant UX)

CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS app_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           CITEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    nombres         VARCHAR(255),
    activo          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_users_tenant ON app_users (tenant_id);

CREATE TRIGGER trg_app_users_updated_at
    BEFORE UPDATE ON app_users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS user_organization_memberships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    roles           TEXT[] NOT NULL DEFAULT ARRAY['payroll_admin']::TEXT[],
    activo          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, organization_id)
);

CREATE INDEX IF NOT EXISTS idx_user_org_memberships_user ON user_organization_memberships (user_id);
CREATE INDEX IF NOT EXISTS idx_user_org_memberships_org ON user_organization_memberships (organization_id);

CREATE TRIGGER trg_user_org_memberships_updated_at
    BEFORE UPDATE ON user_organization_memberships FOR EACH ROW EXECUTE FUNCTION set_updated_at();
