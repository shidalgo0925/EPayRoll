const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";
const DEMO_ORG = "00000000-0000-0000-0000-000000000010";

export function getConfig() {
  return {
    tenantId: localStorage.getItem("epayroll_tenant_id") || "",
    orgId: localStorage.getItem("epayroll_org_id") || "",
    apiBase: localStorage.getItem("epayroll_api_base") || "",
  };
}

export function saveConfig({ tenantId, orgId, apiBase }) {
  if (tenantId != null) localStorage.setItem("epayroll_tenant_id", tenantId);
  if (orgId != null) localStorage.setItem("epayroll_org_id", orgId);
  if (apiBase != null) localStorage.setItem("epayroll_api_base", apiBase);
}

export function requireOrgId() {
  const orgId = getConfig().orgId;
  if (!orgId) throw new Error("Seleccione una empresa activa.");
  return orgId;
}

function getJwt() {
  return localStorage.getItem("epayroll_jwt") || "";
}

export async function api(path, options = {}) {
  const cfg = getConfig();
  const base = cfg.apiBase.replace(/\/$/, "");
  const url = `${base}${path}`;
  const token = getJwt();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    if (!cfg.tenantId) throw new Error("Inicie sesión para continuar.");
    headers["X-Tenant-Id"] = cfg.tenantId;
    if (cfg.orgId) headers["X-Organization-Id"] = cfg.orgId;
    headers["X-Roles"] = "payroll_admin,rrhh,contador,tenant_admin";
  }

  const res = await fetch(url, { ...options, headers });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const msg = typeof data === "object" && data?.detail ? data.detail : String(data);
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data;
}

export { DEMO_TENANT, DEMO_ORG };
