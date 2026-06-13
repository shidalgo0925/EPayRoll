const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";
const DEMO_ORG = "00000000-0000-0000-0000-000000000010";

export function getConfig() {
  return {
    tenantId: localStorage.getItem("epayroll_tenant_id") || DEMO_TENANT,
    orgId: localStorage.getItem("epayroll_org_id") || DEMO_ORG,
    apiBase: localStorage.getItem("epayroll_api_base") || "",
  };
}

export function saveConfig({ tenantId, orgId, apiBase }) {
  if (tenantId != null) localStorage.setItem("epayroll_tenant_id", tenantId);
  if (orgId != null) localStorage.setItem("epayroll_org_id", orgId);
  if (apiBase != null) localStorage.setItem("epayroll_api_base", apiBase);
}

export async function api(path, options = {}) {
  const cfg = getConfig();
  const base = cfg.apiBase.replace(/\/$/, "");
  const url = `${base}${path}`;
  const headers = {
    "Content-Type": "application/json",
    "X-Tenant-Id": cfg.tenantId,
    ...(options.headers || {}),
  };
  if (cfg.orgId) headers["X-Organization-Id"] = cfg.orgId;

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
