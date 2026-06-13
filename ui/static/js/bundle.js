/* EPayRoll UI — bundle único (sin ES modules, evita caché rota) */
(function () {
  "use strict";

  const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";
  const DEMO_ORG = "00000000-0000-0000-0000-000000000010";
  const FETCH_TIMEOUT_MS = 15000;

  function getConfig() {
    let apiBase = localStorage.getItem("epayroll_api_base") || "";
    if (apiBase.includes("localhost") && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
      apiBase = "";
      localStorage.setItem("epayroll_api_base", "");
    }
    return {
      tenantId: localStorage.getItem("epayroll_tenant_id") || DEMO_TENANT,
      orgId: localStorage.getItem("epayroll_org_id") || DEMO_ORG,
      apiBase,
    };
  }

  function saveConfig({ tenantId, orgId, apiBase }) {
    if (tenantId != null) localStorage.setItem("epayroll_tenant_id", tenantId);
    if (orgId != null) localStorage.setItem("epayroll_org_id", orgId);
    if (apiBase != null) localStorage.setItem("epayroll_api_base", apiBase);
  }

  function getJwt() {
    return localStorage.getItem("epayroll_jwt") || "";
  }

  function setJwt(token) {
    if (token) localStorage.setItem("epayroll_jwt", token);
    else localStorage.removeItem("epayroll_jwt");
  }

  async function api(path, options = {}) {
    const cfg = getConfig();
    const base = cfg.apiBase.replace(/\/$/, "");
    const url = `${base}${path}`;
    const token = getJwt();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    } else {
      headers["X-Tenant-Id"] = cfg.tenantId;
      if (cfg.orgId) headers["X-Organization-Id"] = cfg.orgId;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal, headers });
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
    } catch (e) {
      if (e.name === "AbortError") throw new Error("Tiempo de espera agotado — verifica URL del servidor");
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  function fmtMoney(v) {
    if (v == null || v === "") return "—";
    const n = Number(v);
    if (Number.isNaN(n)) return String(v);
    return new Intl.NumberFormat("es-PA", { style: "currency", currency: "USD" }).format(n);
  }

  function getRefreshToken() {
    return localStorage.getItem("epayroll_refresh_token") || "";
  }

  function setRefreshToken(token) {
    if (token) localStorage.setItem("epayroll_refresh_token", token);
    else localStorage.removeItem("epayroll_refresh_token");
  }

  function randomState() {
    return crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
  }

  async function loadSsoConfig() {
    try {
      return await api("/api/v1/auth/sso/config");
    } catch {
      return { enabled: false };
    }
  }

  async function exchangeSsoCode(code, redirectUri) {
    const cfg = getConfig();
    const base = cfg.apiBase.replace(/\/$/, "");
    const res = await fetch(`${base}/api/v1/auth/sso/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, redirect_uri: redirectUri }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "SSO fallido");
    return data;
  }

  function storeTokens(data) {
    setJwt(data.access_token);
    if (data.refresh_token) setRefreshToken(data.refresh_token);
  }

  async function startEn1Sso(ssoCfg) {
    const state = randomState();
    sessionStorage.setItem("epayroll_sso_state", state);
    const redirect = ssoCfg.redirect_uri || `${location.origin}/app/`;
    const params = new URLSearchParams({
      response_type: "code",
      client_id: ssoCfg.client_id,
      redirect_uri: redirect,
      state,
      scope: ssoCfg.scopes || "openid profile email",
    });
    location.href = `${ssoCfg.authorize_url}?${params}`;
  }

  async function handleSsoCallback() {
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    if (!code) return false;
    const state = params.get("state");
    const expected = sessionStorage.getItem("epayroll_sso_state");
    if (expected && state && expected !== state) {
      throw new Error("State SSO inválido");
    }
    const ssoCfg = await loadSsoConfig();
    const redirect = ssoCfg.redirect_uri || `${location.origin}/app/`;
    const tokens = await exchangeSsoCode(code, redirect);
    storeTokens(tokens);
    sessionStorage.removeItem("epayroll_sso_state");
    history.replaceState({}, "", location.pathname);
    document.getElementById("login-modal")?.classList.add("hidden");
    return true;
  }

  function fmtPct(v) {
    if (v == null) return "—";
    return `${Number(v).toFixed(1)}%`;
  }

  function dashboardPeriodDefaults() {
    const year = new Date().getFullYear();
    return { fechaInicio: `${year}-01-01`, fechaFin: `${year}-12-31` };
  }

  async function loadDashboard(container, fechaInicio, fechaFin) {
    const cfg = getConfig();
    const data = await api(
      `/api/v1/organizations/${cfg.orgId || DEMO_ORG}/analytics/dashboard?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`
    );

    const kpis = data.kpis || {};
    const pasivos = data.pasivos_laborales || data.pasivos || {};
    const costo = data.costo_planilla_periodo || data.costo_planilla || {};
    const alerts = data.alertas || data.alerts || [];
    const umbrales = data.umbrales || {};
    const proy = data.proyeccion_liquidaciones || {};
    const extra = kpis.horas_extra?.desglose || {};
    const hc = data.headcount || {};

    const proyRows = (proy.employees || []).slice(0, 8);
    const proyMore = (proy.employees || []).length - proyRows.length;

    container.innerHTML = `
      <div class="page-header dash-header">
        <div>
          <h1>Dashboard ejecutivo</h1>
          <p>Corte ${data.periodo?.fecha_corte || fechaFin} · ${data.periodo?.fecha_inicio || fechaInicio} — ${data.periodo?.fecha_fin || fechaFin}</p>
        </div>
        <form id="dash-filter" class="dash-filter">
          <label>Desde<input type="date" name="inicio" value="${fechaInicio}" /></label>
          <label>Hasta<input type="date" name="fin" value="${fechaFin}" /></label>
          <button type="submit" class="btn">Actualizar</button>
        </form>
      </div>

      <div class="grid">
        <div class="card">
          <div class="label">Empleados activos</div>
          <div class="value">${hc.activos ?? "—"}</div>
          <div class="sub">Plantilla ${hc.plantilla_inicio ?? "—"} → ${hc.plantilla_fin ?? "—"}</div>
        </div>
        <div class="card">
          <div class="label">Rotación anual</div>
          <div class="value">${fmtPct(kpis.rotacion?.tasa_pct)}</div>
          <div class="sub">${kpis.rotacion?.terminaciones ?? 0} terminaciones · umbral ${umbrales.rotacion_pct ?? "—"}%</div>
        </div>
        <div class="card">
          <div class="label">Ausentismo</div>
          <div class="value">${fmtPct(kpis.ausentismo?.tasa_pct)}</div>
          <div class="sub">${kpis.ausentismo?.dias_ausencia ?? 0} días · umbral ${umbrales.ausentismo_pct ?? "—"}%</div>
        </div>
        <div class="card">
          <div class="label">Horas extra</div>
          <div class="value">${kpis.horas_extra?.total ?? "0"}</div>
          <div class="sub">${kpis.horas_extra?.empleados_con_extras ?? 0} empleados · prom ${kpis.horas_extra?.promedio_por_empleado ?? "0"}</div>
        </div>
        <div class="card">
          <div class="label">Costo planilla</div>
          <div class="value">${fmtMoney(costo.bruto || costo.total_bruto)}</div>
          <div class="sub">Neto ${fmtMoney(costo.neto || costo.total_neto)} · Patronal ${fmtMoney(costo.aportes_patronales)}</div>
        </div>
        <div class="card">
          <div class="label">Pasivos laborales</div>
          <div class="value">${fmtMoney(pasivos.total)}</div>
          <div class="sub">Umbral/emp ${fmtMoney(umbrales.pasivo_por_empleado)}</div>
        </div>
      </div>

      <div class="dash-columns">
        <div class="panel">
          <h2>Alertas</h2>
          ${alerts.length ? alerts.map((a) => `<div class="alert alert-warning"><strong>${a.tipo || a.nivel}</strong> — ${a.mensaje}</div>`).join("") : '<p class="loading">Sin alertas activas</p>'}
        </div>
        <div class="panel">
          <h2>Horas extra — desglose</h2>
          <table class="compact">
            <tbody>
              <tr><td>Diurna</td><td>${extra.diurna ?? "0"} h</td></tr>
              <tr><td>Nocturna</td><td>${extra.nocturna ?? "0"} h</td></tr>
              <tr><td>Domingo / feriado</td><td>${extra.domingo_feriado ?? "0"} h</td></tr>
            </tbody>
          </table>
          <p class="loading" style="margin-top:0.75rem">Umbral prom/mes: ${umbrales.horas_extra_promedio ?? "—"} h</p>
        </div>
      </div>

      <div class="panel">
        <h2>Pasivos desglosados</h2>
        <table>
          <thead><tr><th>Concepto</th><th>Monto</th></tr></thead>
          <tbody>
            ${(pasivos.items || []).map((i) => `<tr><td>${i.concepto}</td><td>${fmtMoney(i.monto)}</td></tr>`).join("")}
          </tbody>
        </table>
      </div>

      <div class="panel">
        <h2>Proyección liquidaciones (${proy.causa || "—"})</h2>
        <p class="loading" style="margin-bottom:0.75rem">Total proyectado: <strong style="color:var(--text)">${fmtMoney(proy.total_proyectado)}</strong> · ${proy.employee_count ?? 0} empleados</p>
        <table>
          <thead><tr><th>Empleado</th><th>Vacaciones</th><th>Décimo</th><th>Prima</th><th>Total</th></tr></thead>
          <tbody>
            ${proyRows.length ? proyRows.map((e) => `<tr>
              <td>${e.nombres || ""} ${e.apellidos || ""}</td>
              <td>${fmtMoney(e.vacaciones)}</td>
              <td>${fmtMoney(e.decimo)}</td>
              <td>${fmtMoney(e.prima_antiguedad)}</td>
              <td>${fmtMoney(e.total)}</td>
            </tr>`).join("") : `<tr><td colspan="5">Sin proyección (ejecuta setup demo en Planilla)</td></tr>`}
          </tbody>
        </table>
        ${proyMore > 0 ? `<p class="loading">+ ${proyMore} empleado(s) más</p>` : ""}
      </div>`;

    document.getElementById("dash-filter").onsubmit = (ev) => {
      ev.preventDefault();
      const fd = new FormData(ev.target);
      renderDashboard(container, fd.get("inicio"), fd.get("fin"));
    };
  }

  async function renderDashboard(container, fechaInicio, fechaFin) {
    if (!fechaInicio || !fechaFin) {
      const d = dashboardPeriodDefaults();
      fechaInicio = d.fechaInicio;
      fechaFin = d.fechaFin;
    }
    container.innerHTML = `<p class="loading">Cargando dashboard…</p>`;
    try {
      await loadDashboard(container, fechaInicio, fechaFin);
    } catch (e) {
      container.innerHTML = `
        <div class="page-header"><h1>Dashboard ejecutivo</h1></div>
        <div class="alert alert-error">${e.message}</div>
        <p class="loading">Verifica tenant/org en la barra lateral. Tenant demo: ${DEMO_TENANT}</p>`;
    }
  }

  async function renderEmployees(container) {
    container.innerHTML = `<p class="loading">Cargando empleados…</p>`;
    const cfg = getConfig();
    try {
      const rows = await api(`/api/v1/organizations/${cfg.orgId || DEMO_ORG}/employees`);
      container.innerHTML = `
        <div class="page-header"><h1>Empleados</h1><p>${rows.length} activo(s)</p></div>
        <div class="panel"><table><thead><tr><th>Cédula</th><th>Nombre</th><th>ID</th></tr></thead><tbody>
          ${rows.length ? rows.map((e) => `<tr><td>${e.cedula}</td><td>${e.nombres} ${e.apellidos}</td><td><code style="font-size:0.7rem;color:var(--muted)">${e.id}</code></td></tr>`).join("") : `<tr><td colspan="3">Sin empleados — Planilla → Setup demo</td></tr>`}
        </tbody></table></div>`;
    } catch (e) {
      container.innerHTML = `<div class="page-header"><h1>Empleados</h1></div><div class="alert alert-error">${e.message}</div>`;
    }
  }

  const payrollState = {
    periodId: localStorage.getItem("epayroll_period_id") || "",
    runId: localStorage.getItem("epayroll_run_id") || "",
    employeeId: localStorage.getItem("epayroll_employee_id") || "",
  };

  function savePayrollState() {
    localStorage.setItem("epayroll_period_id", payrollState.periodId);
    localStorage.setItem("epayroll_run_id", payrollState.runId);
    localStorage.setItem("epayroll_employee_id", payrollState.employeeId);
  }

  function renderPayroll(container) {
    const cfg = getConfig();
    container.innerHTML = `
      <div class="page-header"><h1>Planilla</h1><p>Flujo piloto: setup → corrida → cierre → exportaciones</p></div>
      <div class="panel"><h2>Estado</h2><table><tbody>
        <tr><td>Organización</td><td><code>${cfg.orgId || DEMO_ORG}</code></td></tr>
        <tr><td>Período</td><td><code id="st-period">${payrollState.periodId || "—"}</code></td></tr>
        <tr><td>Corrida</td><td><code id="st-run">${payrollState.runId || "—"}</code></td></tr>
        <tr><td>Empleado</td><td><code id="st-employee">${payrollState.employeeId || "—"}</code></td></tr>
      </tbody></table></div>
      <div class="panel"><h2>Acciones</h2>
        <div class="btn-row">
          <button class="btn" id="btn-setup">1. Setup demo</button>
          <button class="btn" id="btn-run">2. Corrida quincenal</button>
          <button class="btn" id="btn-close">3. Cerrar período</button>
          <button class="btn btn-secondary" id="btn-sipe">SIPE</button>
          <button class="btn btn-secondary" id="btn-dgi">DGI</button>
          <button class="btn btn-secondary" id="btn-ach">ACH</button>
        </div>
        <pre class="output" id="payroll-output">Listo.</pre>
      </div>`;

    const out = (text, err) => {
      const el = document.getElementById("payroll-output");
      el.className = err ? "alert alert-error" : "alert alert-success";
      el.textContent = text;
    };
    const sync = () => {
      document.getElementById("st-period").textContent = payrollState.periodId || "—";
      document.getElementById("st-run").textContent = payrollState.runId || "—";
      document.getElementById("st-employee").textContent = payrollState.employeeId || "—";
    };
    const act = async (label, fn) => {
      out(`⏳ ${label}…`);
      try {
        const r = await fn();
        out(`✅ ${label}\n\n${JSON.stringify(r, null, 2)}`);
        return r;
      } catch (e) {
        out(`❌ ${label}: ${e.message}`, true);
        throw e;
      }
    };

    document.getElementById("btn-setup").onclick = async () => {
      const r = await act("Setup demo", () => api("/api/v1/demo/setup"));
      payrollState.periodId = r.payroll_period_id || payrollState.periodId;
      payrollState.employeeId = r.employee_id || payrollState.employeeId;
      savePayrollState();
      sync();
    };
    document.getElementById("btn-run").onclick = async () => {
      if (!payrollState.periodId) return out("Primero: Setup demo", true);
      const r = await act("Corrida batch", () =>
        api(`/api/v1/payroll/periods/${payrollState.periodId}/run`, {
          method: "POST",
          body: JSON.stringify({ use_attendance: false, dias_trabajados: 15 }),
        })
      );
      payrollState.runId = r.run_id;
      savePayrollState();
      sync();
    };
    document.getElementById("btn-close").onclick = () =>
      act("Cierre período", () =>
        api(`/api/v1/payroll/periods/${payrollState.periodId}/close`, { method: "POST", body: "{}" })
      );
    document.getElementById("btn-sipe").onclick = () =>
      act("SIPE", () => api(`/api/v1/exports/sipe/${payrollState.runId}`, { method: "POST", body: "{}" }));
    document.getElementById("btn-dgi").onclick = () =>
      act("DGI", () => api(`/api/v1/exports/dgi/${payrollState.runId}`, { method: "POST", body: "{}" }));
    document.getElementById("btn-ach").onclick = () =>
      act("ACH", async () => {
        await api(`/api/v1/employees/${payrollState.employeeId}/bank-account`, {
          method: "POST",
          body: JSON.stringify({ banco: "BANCO_GENERAL", numero_cuenta: "1234567890", tipo_cuenta: "AHORROS" }),
        });
        return api(`/api/v1/exports/ach/${payrollState.runId}`, {
          method: "POST",
          body: JSON.stringify({ banco: "BANCO_GENERAL" }),
        });
      });
  }

  const pages = { dashboard: renderDashboard, employees: renderEmployees, payroll: renderPayroll };

  async function checkHealth() {
    const el = document.getElementById("api-status");
    try {
      const h = await api("/health");
      el.innerHTML = `<span class="status-dot ok"></span>API v${h.version}`;
    } catch (e) {
      el.innerHTML = `<span class="status-dot err"></span>${e.message}`;
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
    base.placeholder = location.origin;
    const persist = () => {
      saveConfig({ tenantId: tenant.value.trim(), orgId: org.value.trim(), apiBase: base.value.trim() });
      checkHealth();
    };
    tenant.onchange = persist;
    org.onchange = persist;
    base.onchange = persist;
  }

  async function navigate(name) {
    document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("active", b.dataset.page === name));
    const main = document.getElementById("page-content");
    try {
      await pages[name](main);
    } catch (e) {
      main.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
    }
  }

  async function doLogin(form) {
    const cfg = getConfig();
    const base = cfg.apiBase.replace(/\/$/, "");
    const res = await fetch(`${base}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        tenant_id: form.tenant.value.trim(),
        organization_id: form.org.value.trim() || null,
        user_id: form.user.value.trim() || "ui-user",
        api_key: form.apikey.value,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login fallido");
    setJwt(data.access_token);
    saveConfig({ tenantId: form.tenant.value.trim(), orgId: form.org.value.trim(), apiBase: cfg.apiBase });
    document.getElementById("login-modal").classList.add("hidden");
    checkHealth();
    navigate("dashboard");
  }

  function bindLogin() {
    const modal = document.getElementById("login-modal");
    const form = document.getElementById("login-form");
    if (!form) return;
    form.tenant.value = getConfig().tenantId;
    form.org.value = getConfig().orgId;
    form.onsubmit = async (e) => {
      e.preventDefault();
      const err = document.getElementById("login-error");
      err.textContent = "";
      try {
        await doLogin(form);
      } catch (ex) {
        err.textContent = ex.message;
      }
    };
    loadSsoConfig().then((ssoCfg) => {
      const btn = document.getElementById("btn-sso-en1");
      if (!btn || !ssoCfg.enabled) return;
      btn.classList.remove("hidden");
      btn.onclick = () => startEn1Sso(ssoCfg);
    });
    document.getElementById("btn-logout")?.addEventListener("click", () => {
      setJwt("");
      setRefreshToken("");
      modal.classList.remove("hidden");
    });
    document.getElementById("btn-login-open")?.addEventListener("click", () => {
      modal.classList.remove("hidden");
    });
  }

  async function boot() {
    try {
      if (await handleSsoCallback()) {
        await checkHealth();
        navigate("dashboard");
        return;
      }
    } catch (e) {
      document.getElementById("login-error")?.classList.remove("hidden");
      const err = document.getElementById("login-error");
      if (err) err.textContent = e.message;
    }
    bindConfig();
    bindLogin();
    checkHealth();
    navigate("dashboard");
  }

  document.querySelectorAll("nav button").forEach((btn) => {
    btn.onclick = () => navigate(btn.dataset.page);
  });

  boot();
})();
