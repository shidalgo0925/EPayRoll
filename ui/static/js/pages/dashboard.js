import { api, getConfig, DEMO_ORG } from "../api.js";

function fmtMoney(v) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return new Intl.NumberFormat("es-PA", { style: "currency", currency: "USD" }).format(n);
}

function fmtPct(v) {
  if (v == null) return "—";
  return `${Number(v).toFixed(1)}%`;
}

export async function renderDashboard(container) {
  container.innerHTML = `<p class="loading">Cargando dashboard…</p>`;
  const cfg = getConfig();
  const year = new Date().getFullYear();
  const fechaInicio = `${year}-01-01`;
  const fechaFin = `${year}-12-31`;

  try {
    const data = await api(
      `/api/v1/organizations/${cfg.orgId || DEMO_ORG}/analytics/dashboard?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`
    );

    const kpis = data.kpis || {};
    const pasivos = data.pasivos || {};
    const alerts = data.alertas || data.alerts || [];

    container.innerHTML = `
      <div class="page-header">
        <h1>Dashboard ejecutivo</h1>
        <p>${data.periodo?.fecha_inicio || fechaInicio} — ${data.periodo?.fecha_fin || fechaFin}</p>
      </div>

      <div class="grid">
        <div class="card">
          <div class="label">Empleados activos</div>
          <div class="value">${data.headcount?.activos ?? "—"}</div>
        </div>
        <div class="card">
          <div class="label">Rotación anual</div>
          <div class="value">${fmtPct(kpis.rotacion?.tasa_pct)}</div>
        </div>
        <div class="card">
          <div class="label">Ausentismo</div>
          <div class="value">${fmtPct(kpis.ausentismo?.tasa_pct)}</div>
        </div>
        <div class="card">
          <div class="label">Horas extra</div>
          <div class="value">${kpis.horas_extra?.total ?? "0"}</div>
          <div class="sub">${kpis.horas_extra?.empleados_con_extras ?? 0} empleados</div>
        </div>
        <div class="card">
          <div class="label">Costo planilla (período)</div>
          <div class="value">${fmtMoney(data.costo_planilla?.total_bruto)}</div>
          <div class="sub">Neto: ${fmtMoney(data.costo_planilla?.total_neto)}</div>
        </div>
        <div class="card">
          <div class="label">Pasivos laborales</div>
          <div class="value">${fmtMoney(pasivos.total)}</div>
        </div>
      </div>

      <div class="panel">
        <h2>Alertas</h2>
        <div id="dash-alerts">
          ${
            alerts.length
              ? alerts
                  .map(
                    (a) =>
                      `<div class="alert alert-warning"><strong>${a.tipo || a.nivel}</strong> — ${a.mensaje}</div>`
                  )
                  .join("")
              : '<p class="loading">Sin alertas activas</p>'
          }
        </div>
      </div>

      <div class="panel">
        <h2>Pasivos desglosados</h2>
        <table>
          <thead><tr><th>Concepto</th><th>Monto</th></tr></thead>
          <tbody>
            ${(pasivos.items || [])
              .map((i) => `<tr><td>${i.concepto}</td><td>${fmtMoney(i.monto)}</td></tr>`)
              .join("")}
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `
      <div class="page-header"><h1>Dashboard ejecutivo</h1></div>
      <div class="alert alert-error">${e.message}</div>
      <p class="loading">Verifica tenant/org en la barra lateral y que exista data demo.</p>
    `;
  }
}
