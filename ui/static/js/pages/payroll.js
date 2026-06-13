import { api, getConfig, DEMO_ORG } from "../api.js";

let state = {
  periodId: localStorage.getItem("epayroll_period_id") || "",
  runId: localStorage.getItem("epayroll_run_id") || "",
  employeeId: localStorage.getItem("epayroll_employee_id") || "",
};

function saveState() {
  localStorage.setItem("epayroll_period_id", state.periodId);
  localStorage.setItem("epayroll_run_id", state.runId);
  localStorage.setItem("epayroll_employee_id", state.employeeId);
}

function setOutput(text, isError = false) {
  const el = document.getElementById("payroll-output");
  if (el) {
    el.className = isError ? "alert alert-error" : "alert alert-success";
    el.textContent = typeof text === "string" ? text : JSON.stringify(text, null, 2);
  }
}

async function runAction(label, fn) {
  setOutput(`⏳ ${label}…`);
  try {
    const result = await fn();
    setOutput(`✅ ${label}\n\n${JSON.stringify(result, null, 2)}`);
    return result;
  } catch (e) {
    setOutput(`❌ ${label}: ${e.message}`, true);
    throw e;
  }
}

export function renderPayroll(container) {
  const cfg = getConfig();

  container.innerHTML = `
    <div class="page-header">
      <h1>Planilla</h1>
      <p>Flujo piloto: setup → corrida batch → cierre → exportaciones</p>
    </div>

    <div class="panel">
      <h2>Estado de sesión</h2>
      <table>
        <tbody>
          <tr><td>Organización</td><td><code>${cfg.orgId || DEMO_ORG}</code></td></tr>
          <tr><td>Período</td><td><code id="st-period">${state.periodId || "—"}</code></td></tr>
          <tr><td>Corrida</td><td><code id="st-run">${state.runId || "—"}</code></td></tr>
          <tr><td>Empleado</td><td><code id="st-employee">${state.employeeId || "—"}</code></td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>Acciones</h2>
      <div class="btn-row">
        <button class="btn" id="btn-setup">1. Setup demo GT-01</button>
        <button class="btn" id="btn-run">2. Corrida quincenal</button>
        <button class="btn" id="btn-close">3. Cerrar período</button>
        <button class="btn btn-secondary" id="btn-sipe">Export SIPE</button>
        <button class="btn btn-secondary" id="btn-dgi">Export DGI</button>
        <button class="btn btn-secondary" id="btn-ach">Export ACH</button>
      </div>
      <pre class="output" id="payroll-output">Listo.</pre>
    </div>
  `;

  const updateStatus = () => {
    document.getElementById("st-period").textContent = state.periodId || "—";
    document.getElementById("st-run").textContent = state.runId || "—";
    document.getElementById("st-employee").textContent = state.employeeId || "—";
  };

  document.getElementById("btn-setup").onclick = async () => {
    const r = await runAction("Setup demo", () => api("/api/v1/demo/setup"));
    state.periodId = r.payroll_period_id || state.periodId;
    state.employeeId = r.employee_id || state.employeeId;
    saveState();
    updateStatus();
  };

  document.getElementById("btn-run").onclick = async () => {
    if (!state.periodId) {
      setOutput("Primero ejecuta Setup demo", true);
      return;
    }
    const r = await runAction("Corrida batch", () =>
      api(`/api/v1/payroll/periods/${state.periodId}/run`, {
        method: "POST",
        body: JSON.stringify({ use_attendance: false, dias_trabajados: 15 }),
      })
    );
    state.runId = r.run_id;
    saveState();
    updateStatus();
  };

  document.getElementById("btn-close").onclick = async () => {
    if (!state.periodId) {
      setOutput("Sin período activo", true);
      return;
    }
    await runAction("Cierre período", () =>
      api(`/api/v1/payroll/periods/${state.periodId}/close`, {
        method: "POST",
        body: "{}",
      })
    );
  };

  document.getElementById("btn-sipe").onclick = async () => {
    if (!state.runId) {
      setOutput("Sin corrida — ejecuta paso 2", true);
      return;
    }
    await runAction("Export SIPE", () =>
      api(`/api/v1/exports/sipe/${state.runId}`, { method: "POST", body: "{}" })
    );
  };

  document.getElementById("btn-dgi").onclick = async () => {
    if (!state.runId) {
      setOutput("Sin corrida", true);
      return;
    }
    await runAction("Export DGI", () =>
      api(`/api/v1/exports/dgi/${state.runId}`, { method: "POST", body: "{}" })
    );
  };

  document.getElementById("btn-ach").onclick = async () => {
    if (!state.runId || !state.employeeId) {
      setOutput("Sin corrida/empleado", true);
      return;
    }
    await runAction("Registro cuenta + ACH", async () => {
      await api(`/api/v1/employees/${state.employeeId}/bank-account`, {
        method: "POST",
        body: JSON.stringify({
          banco: "BANCO_GENERAL",
          numero_cuenta: "1234567890",
          tipo_cuenta: "AHORROS",
        }),
      });
      return api(`/api/v1/exports/ach/${state.runId}`, {
        method: "POST",
        body: JSON.stringify({ banco: "BANCO_GENERAL" }),
      });
    });
  };
}
