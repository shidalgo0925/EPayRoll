import { getConfig, saveConfig, api, DEMO_TENANT, DEMO_ORG } from "./api.js";
import { renderDashboard } from "./pages/dashboard.js";
import { renderEmployees } from "./pages/employees.js";
import { renderPayroll } from "./pages/payroll.js";

const pages = {
  dashboard: { title: "Dashboard", render: renderDashboard },
  employees: { title: "Empleados", render: renderEmployees },
  payroll: { title: "Planilla", render: renderPayroll },
};

let current = "dashboard";

async function checkHealth() {
  const el = document.getElementById("api-status");
  try {
    const h = await api("/health");
    el.innerHTML = `<span class="status-dot ok"></span>API ${h.version}`;
  } catch {
    el.innerHTML = `<span class="status-dot err"></span>API offline`;
  }
}

function bindConfig() {
  const cfg = getConfig();
  const tenant = document.getElementById("cfg-tenant");
  const org = document.getElementById("cfg-org");
  const base = document.getElementById("cfg-base");

  tenant.value = cfg.tenantId;
  org.value = cfg.orgId;
  base.value = cfg.apiBase;
  base.placeholder = window.location.origin;

  const persist = () => {
    saveConfig({
      tenantId: tenant.value.trim(),
      orgId: org.value.trim(),
      apiBase: base.value.trim(),
    });
    checkHealth();
  };

  tenant.onchange = persist;
  org.onchange = persist;
  base.onchange = persist;
}

async function navigate(name) {
  current = name;
  document.querySelectorAll("nav button").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === name);
  });
  const main = document.getElementById("page-content");
  const page = pages[name];
  try {
    await page.render(main);
  } catch (e) {
    main.innerHTML = `<div class="alert alert-error">Error cargando página: ${e.message}</div>`;
  }
}

document.querySelectorAll("nav button").forEach((btn) => {
  btn.onclick = () => navigate(btn.dataset.page);
});

bindConfig();
checkHealth();
navigate(current);
