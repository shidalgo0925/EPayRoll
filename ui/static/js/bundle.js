/* EPayRoll UI — bundle único (sin ES modules, evita caché rota) */
(function () {
  "use strict";

  const DEMO_TENANT = "00000000-0000-0000-0000-000000000001";
  const DEMO_ORG = "00000000-0000-0000-0000-000000000010";
  const FETCH_TIMEOUT_MS = 15000;
  const SIDEBAR_KEY = "epayroll_sidebar_collapsed";

  const PAGE_TITLES = {
    dashboard: "Dashboard",
    employees: "Empleados",
    payroll: "Planilla",
    attendance: "Asistencia",
    vacations: "Vacaciones",
    incapacities: "Incapacidades",
    liquidations: "Liquidaciones",
    settings: "Configuración",
  };

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
      headers["X-Roles"] = "payroll_admin,rrhh,contador";
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

  function escHtml(v) {
    return String(v ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function rowKey(row) {
    return row.id || row.request_id || row.case_id || "";
  }

  function crudActions(id, { edit = true, del = true, extra = "" } = {}) {
    if (!id) return "<td></td>";
    return `<td class="crud-actions">${extra}${
      edit
        ? `<button type="button" class="btn-icon" data-crud-edit="${escHtml(id)}" title="Editar"><svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg></button>`
        : ""
    }${
      del
        ? `<button type="button" class="btn-icon btn-icon-danger" data-crud-del="${escHtml(id)}" title="Eliminar"><svg viewBox="0 0 24 24" width="14" height="14"><path fill="currentColor" d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12M19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg></button>`
        : ""
    }</td>`;
  }

  function bindCrud(container, handlers) {
    if (handlers.onEdit) {
      container.querySelectorAll("[data-crud-edit]").forEach((btn) => {
        btn.onclick = () => handlers.onEdit(btn.dataset.crudEdit);
      });
    }
    if (handlers.onDelete) {
      container.querySelectorAll("[data-crud-del]").forEach((btn) => {
        btn.onclick = () => handlers.onDelete(btn.dataset.crudDel);
      });
    }
    if (handlers.onView) {
      container.querySelectorAll("[data-crud-view]").forEach((btn) => {
        btn.onclick = () => handlers.onView(btn.dataset.crudView);
      });
    }
  }

  function flashMsg(elId, text, ok = true) {
    const el = document.getElementById(elId);
    if (!el) return;
    el.innerHTML = text
      ? `<div class="alert alert-${ok ? "success" : "error"}">${escHtml(text)}</div>`
      : "";
  }

  async function apiDelete(path) {
    return api(path, { method: "DELETE" });
  }

  async function apiPatch(path, body) {
    return api(path, { method: "PATCH", body: JSON.stringify(body) });
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
      <div class="page-header page-header-sub dash-header">
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

      <div class="grid-kpi">
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
      </div>

      <div class="grid-metric">
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
        <div class="page-header page-header-sub"><h1>Dashboard ejecutivo</h1></div>
        <div class="alert alert-error">${e.message}</div>
        <p class="loading">Verifica tenant/org en Configuración. Tenant demo: ${DEMO_TENANT}</p>`;
    }
  }

  async function renderEmployees(container) {
    container.innerHTML = `<p class="loading">Cargando empleados…</p>`;
    const cfg = getConfig();
    const orgId = cfg.orgId || DEMO_ORG;
    try {
      const rows = await api(`/api/v1/organizations/${orgId}/employees`);
      container.innerHTML = `
        <div class="page-header page-header-sub"><h1>Empleados</h1><p>Expediente completo para planilla — columnas A–D del modelo Excel + contrato</p></div>
        <div class="panel">
          <div class="crud-form-title" id="emp-form-title">Nuevo empleado</div>
          <form id="emp-form" class="inline-form">
            <input type="hidden" name="employee_id" value="" />
            <fieldset class="form-section"><legend>Identificación planilla</legend>
              <label>Ficha<input name="ficha" placeholder="Nº ficha" /></label>
              <label>Cédula<input name="cedula" required /></label>
              <label>Nombres<input name="nombres" required /></label>
              <label>Apellidos<input name="apellidos" required /></label>
              <label>Celular<input name="telefono" placeholder="6207-5181" /></label>
            </fieldset>
            <fieldset class="form-section"><legend>Expediente</legend>
              <label>Email<input name="email" type="email" placeholder="Opcional" /></label>
              <label>Fecha nacimiento<input name="fecha_nacimiento" type="date" /></label>
              <label>Estado civil<select name="estado_civil"><option value="">—</option><option>SOLTERO</option><option>CASADO</option><option>UNIDO</option><option>VIUDO</option><option>DIVORCIADO</option></select></label>
              <label>Dirección<input name="direccion" placeholder="Opcional" /></label>
            </fieldset>
            <fieldset class="form-section"><legend>Contrato (planilla)</legend>
              <label>Salario mensual<input name="salario_base" type="number" step="0.01" min="0" placeholder="850.00" /></label>
              <label>Inicio contrato<input name="fecha_inicio_contrato" type="date" /></label>
              <label>Forma pago<select name="forma_pago"><option value="QUINCENAL">Quincenal</option><option value="MENSUAL">Mensual</option></select></label>
              <label>Banco<select name="banco"><option value="">—</option><option value="BANCO_GENERAL">Banco General</option><option value="BANISTMO">Banistmo</option><option value="BAC">BAC</option></select></label>
              <label>Cuenta bancaria<input name="cuenta_bancaria" placeholder="Para ACH" /></label>
            </fieldset>
            <button type="submit" class="btn" id="emp-submit">Crear</button>
            <button type="button" class="btn btn-secondary hidden" id="emp-cancel">Cancelar</button>
          </form>
          <div id="emp-msg"></div>
        </div>
        <div class="panel hidden" id="emp-contract-panel">
          <div class="crud-form-title">Asignar contrato</div>
          <form id="emp-contract-form" class="inline-form">
            <input type="hidden" name="employee_id" value="" />
            <label>Salario base<input name="salario_base" type="number" step="0.01" min="0" required /></label>
            <label>Inicio<input name="fecha_inicio" type="date" required /></label>
            <label>Forma pago<select name="forma_pago"><option value="QUINCENAL">Quincenal</option><option value="MENSUAL">Mensual</option></select></label>
            <button type="submit" class="btn">Guardar contrato</button>
            <button type="button" class="btn btn-secondary" id="emp-contract-cancel">Cancelar</button>
          </form>
          <div id="emp-contract-msg"></div>
        </div>
        <div class="panel">
          <h2>Expediente (${rows.length} activo(s))</h2>
          <div class="planilla-scroll">
          <table class="table-crud planilla-grid"><thead><tr>
            <th>Ficha</th><th>Nombre</th><th>Celular</th><th>Cédula</th>
            <th>Sal. mensual</th><th>Sal. quincenal</th><th>Forma pago</th><th>Ingreso</th><th>Banco</th><th>Cuenta</th><th></th>
          </tr></thead><tbody>
            ${rows.length ? rows.map((e) => `<tr data-id="${escHtml(e.id)}">
              <td>${escHtml(e.ficha || "—")}</td>
              <td>${escHtml(e.nombres)} ${escHtml(e.apellidos)}</td>
              <td>${escHtml(e.telefono || "—")}</td>
              <td>${escHtml(e.cedula)}</td>
              <td>${e.salario_base != null ? fmtMoney(e.salario_base) : "—"}</td>
              <td>${e.salario_quincenal != null ? fmtMoney(e.salario_quincenal) : "—"}</td>
              <td>${escHtml(e.forma_pago || "—")}</td>
              <td>${escHtml(e.fecha_inicio_contrato || "—")}</td>
              <td>${escHtml(e.banco || "—")}</td>
              <td>${escHtml(e.cuenta_bancaria || "—")}</td>
              ${crudActions(e.id, { extra: `<button type="button" class="btn btn-secondary btn-sm" data-emp-contract="${escHtml(e.id)}">Contrato</button>` })}
            </tr>`).join("") : `<tr><td colspan="11">Sin empleados — crea uno o Planilla → Setup demo</td></tr>`}
          </tbody></table>
          </div>
        </div>`;

      const form = document.getElementById("emp-form");
      const title = document.getElementById("emp-form-title");
      const submit = document.getElementById("emp-submit");
      const cancel = document.getElementById("emp-cancel");

      const resetForm = () => {
        form.reset();
        form.employee_id.value = "";
        title.textContent = "Nuevo empleado";
        submit.textContent = "Crear";
        cancel.classList.add("hidden");
      };

      cancel.onclick = resetForm;

      form.onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const id = fd.get("employee_id");
        const payload = {
          cedula: fd.get("cedula").trim(),
          nombres: fd.get("nombres").trim(),
          apellidos: fd.get("apellidos").trim(),
          email: fd.get("email").trim() || null,
          ficha: fd.get("ficha").trim() || null,
          telefono: fd.get("telefono").trim() || null,
          fecha_nacimiento: fd.get("fecha_nacimiento") || null,
          estado_civil: fd.get("estado_civil") || null,
          direccion: fd.get("direccion").trim() || null,
        };
        const banco = fd.get("banco");
        const cuenta = fd.get("cuenta_bancaria")?.trim();
        try {
          if (id) {
            await apiPatch(`/api/v1/employees/${id}`, payload);
            if (banco && cuenta) {
              await api(`/api/v1/employees/${id}/bank-account`, {
                method: "POST",
                body: JSON.stringify({ banco, numero_cuenta: cuenta, tipo_cuenta: "AHORROS" }),
              });
            }
            flashMsg("emp-msg", "Empleado actualizado");
          } else {
            const created = await api(`/api/v1/organizations/${orgId}/employees`, {
              method: "POST",
              body: JSON.stringify(payload),
            });
            const salario = fd.get("salario_base");
            if (salario) {
              const fechaContrato = fd.get("fecha_inicio_contrato") || todayIso();
              await createEmployeeContract(created.id, salario, fechaContrato, fd.get("forma_pago"));
              flashMsg("emp-msg", "Empleado y contrato creados");
            } else {
              flashMsg("emp-msg", "Empleado creado (sin contrato — asigna uno para planilla)");
            }
            if (banco && cuenta) {
              await api(`/api/v1/employees/${created.id}/bank-account`, {
                method: "POST",
                body: JSON.stringify({ banco, numero_cuenta: cuenta, tipo_cuenta: "AHORROS" }),
              });
            }
          }
          resetForm();
          await renderEmployees(container);
        } catch (err) {
          flashMsg("emp-msg", err.message, false);
        }
      };

      const contractPanel = document.getElementById("emp-contract-panel");
      const contractForm = document.getElementById("emp-contract-form");
      document.getElementById("emp-contract-cancel").onclick = () => contractPanel.classList.add("hidden");
      contractForm.onsubmit = async (e) => {
        e.preventDefault();
        const fd = new FormData(contractForm);
        try {
          await createEmployeeContract(
            fd.get("employee_id"),
            fd.get("salario_base"),
            fd.get("fecha_inicio"),
            fd.get("forma_pago")
          );
          flashMsg("emp-contract-msg", "Contrato guardado");
          contractPanel.classList.add("hidden");
          await renderEmployees(container);
        } catch (err) {
          flashMsg("emp-contract-msg", err.message, false);
        }
      };
      container.querySelectorAll("[data-emp-contract]").forEach((btn) => {
        btn.onclick = () => {
          contractForm.employee_id.value = btn.dataset.empContract;
          contractForm.fecha_inicio.value = todayIso();
          contractPanel.classList.remove("hidden");
          contractPanel.scrollIntoView({ behavior: "smooth", block: "start" });
        };
      });

      bindCrud(container, {
        onEdit: async (id) => {
          try {
            const emp = await api(`/api/v1/employees/${id}`);
            form.employee_id.value = emp.id;
            form.cedula.value = emp.cedula;
            form.nombres.value = emp.nombres;
            form.apellidos.value = emp.apellidos;
            form.email.value = emp.email || "";
            form.ficha.value = emp.ficha || "";
            form.telefono.value = emp.telefono || "";
            form.fecha_nacimiento.value = emp.fecha_nacimiento || "";
            form.estado_civil.value = emp.estado_civil || "";
            form.direccion.value = emp.direccion || "";
            if (form.banco) form.banco.value = emp.banco || "";
            if (form.cuenta_bancaria) form.cuenta_bancaria.value = emp.cuenta_bancaria || "";
            title.textContent = "Editar empleado";
            submit.textContent = "Guardar";
            cancel.classList.remove("hidden");
            form.scrollIntoView({ behavior: "smooth", block: "start" });
          } catch (err) {
            flashMsg("emp-msg", err.message, false);
          }
        },
        onDelete: async (id) => {
          if (!confirm("¿Dar de baja este empleado?")) return;
          try {
            await apiDelete(`/api/v1/employees/${id}`);
            flashMsg("emp-msg", "Empleado dado de baja");
            await renderEmployees(container);
          } catch (err) {
            flashMsg("emp-msg", err.message, false);
          }
        },
      });
    } catch (e) {
      container.innerHTML = `<div class="page-header page-header-sub"><h1>Empleados</h1></div><div class="alert alert-error">${escHtml(e.message)}</div>`;
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

  async function renderPayroll(container) {
    const cfg = getConfig();
    const orgId = cfg.orgId || DEMO_ORG;
    container.innerHTML = `<p class="loading">Cargando planilla…</p>`;
    let periods = [];
    let employees = [];
    try {
      [periods, employees] = await Promise.all([
        api(`/api/v1/organizations/${orgId}/payroll-periods`),
        fetchOrgEmployees(),
      ]);
    } catch {
      periods = [];
      employees = [];
    }
    const nameMap = employeeNameMap(employees);

    container.innerHTML = `
      <div class="page-header page-header-sub"><h1>Planilla</h1><p>Multi-empleado · períodos, corrida batch, cierre y exportaciones</p></div>
      <div class="panel">
        <h2>Empleados — datos planilla (${employees.length})</h2>
        <p class="loading" style="margin-bottom:0.75rem">Ficha, nombre, celular, cédula, salarios y contrato (modelo Excel cols A–G).</p>
        <div class="planilla-scroll">
        <table class="table-crud planilla-grid"><thead><tr>
          <th>Ficha</th><th>Nombre</th><th>Celular</th><th>Cédula</th>
          <th>Sal. mensual</th><th>Sal. quincenal</th><th>Forma pago</th><th>Ingreso</th>
        </tr></thead><tbody>
          ${employees.length ? employees.map((e) => `<tr>
            <td>${escHtml(e.ficha || "—")}</td>
            <td>${escHtml(e.nombres)} ${escHtml(e.apellidos)}</td>
            <td>${escHtml(e.telefono || "—")}</td>
            <td>${escHtml(e.cedula)}</td>
            <td>${e.salario_base != null ? fmtMoney(e.salario_base) : "—"}</td>
            <td>${e.salario_quincenal != null ? fmtMoney(e.salario_quincenal) : "—"}</td>
            <td>${escHtml(e.forma_pago || "—")}</td>
            <td>${escHtml(e.fecha_inicio_contrato || "—")}</td>
          </tr>`).join("") : `<tr><td colspan="8">Sin empleados — alta en Empleados</td></tr>`}
        </tbody></table>
        </div>
      </div>
      <div class="panel">
        <div class="crud-form-title">Nuevo período</div>
        <form id="period-form" class="inline-form">
          <label>Inicio<input type="date" name="fecha_inicio" required /></label>
          <label>Fin<input type="date" name="fecha_fin" required /></label>
          <label>Pago<input type="date" name="fecha_pago" required /></label>
          <label>Tipo<select name="tipo"><option value="QUINCENAL">Quincenal</option><option value="MENSUAL">Mensual</option></select></label>
          <button type="submit" class="btn">Crear período</button>
        </form>
        <div id="period-msg"></div>
      </div>
      <div class="panel">
        <h2>Períodos</h2>
        <table class="table-crud"><thead><tr><th>Inicio</th><th>Fin</th><th>Pago</th><th>Estado</th><th></th></tr></thead><tbody>
          ${periods.length ? periods.map((p) => `<tr>
            <td>${escHtml(p.fecha_inicio)}</td><td>${escHtml(p.fecha_fin)}</td><td>${escHtml(p.fecha_pago)}</td>
            <td>${escHtml(p.estado)}</td>
            <td class="crud-actions"><button type="button" class="btn btn-secondary btn-sm" data-select-period="${escHtml(p.id)}">Usar</button></td>
          </tr>`).join("") : `<tr><td colspan="5">Sin períodos — crea uno o Setup demo</td></tr>`}
        </tbody></table>
      </div>
      <div class="panel"><h2>Estado</h2><table><tbody>
        <tr><td>Organización</td><td><code>${orgId}</code></td></tr>
        <tr><td>Período activo</td><td><code id="st-period">${payrollState.periodId || "—"}</code></td></tr>
        <tr><td>Corrida</td><td><code id="st-run">${payrollState.runId || "—"}</code></td></tr>
        <tr><td>Empleado (demo)</td><td><code id="st-employee">${payrollState.employeeId || "—"}</code></td></tr>
      </tbody></table></div>
      <div class="panel" id="batch-results-panel">
        <h2>Resultado corrida</h2>
        <div id="batch-results"><p class="loading">Ejecuta corrida quincenal o carga una corrida guardada</p></div>
      </div>
      <div class="panel">
        <h2>Verificación planilla (operador)</h2>
        <p class="loading" style="margin-bottom:0.75rem">Todas las columnas según Planilla_modelo.xlsx — revisar antes de cerrar período.</p>
        <div class="btn-row" style="margin-bottom:0.75rem">
          <button type="button" class="btn btn-secondary btn-sm" id="btn-planilla-refresh">Actualizar vista</button>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-planilla-xlsx">Exportar Excel</button>
        </div>
        <div id="planilla-verify"><p class="loading">—</p></div>
      </div>
      <div class="panel"><h2>Acciones</h2>
        <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem">
          <input type="checkbox" id="chk-use-attendance" />
          Usar asistencia del período (tabla estándar)
        </label>
        <div class="btn-row">
          <button class="btn" id="btn-setup">Setup demo</button>
          <button class="btn" id="btn-run">Corrida quincenal</button>
          <button class="btn" id="btn-close">Cerrar período</button>
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
    const showBatchResults = (data) => {
      const el = document.getElementById("batch-results");
      if (el) el.innerHTML = renderBatchResultsHtml(data, nameMap);
    };
    const loadRun = async (runId) => {
      if (!runId) return;
      try {
        const data = await api(`/api/v1/payroll/runs/${runId}`);
        showBatchResults(data);
      } catch {
        /* corrida aún no consultable */
      }
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

    document.getElementById("period-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        const r = await api(`/api/v1/organizations/${orgId}/payroll-periods`, {
          method: "POST",
          body: JSON.stringify({
            fecha_inicio: fd.get("fecha_inicio"),
            fecha_fin: fd.get("fecha_fin"),
            fecha_pago: fd.get("fecha_pago"),
            tipo: fd.get("tipo"),
          }),
        });
        payrollState.periodId = r.payroll_period_id;
        savePayrollState();
        flashMsg("period-msg", "Período creado");
        await renderPayroll(container);
      } catch (err) {
        flashMsg("period-msg", err.message, false);
      }
    };

    container.querySelectorAll("[data-select-period]").forEach((btn) => {
      btn.onclick = () => {
        payrollState.periodId = btn.dataset.selectPeriod;
        savePayrollState();
        sync();
        flashMsg("period-msg", "Período seleccionado");
      };
    });

    document.getElementById("btn-setup").onclick = async () => {
      const r = await act("Setup demo", () => api("/api/v1/demo/setup"));
      payrollState.periodId = r.payroll_period_id || payrollState.periodId;
      payrollState.employeeId = r.employee_id || payrollState.employeeId;
      savePayrollState();
      sync();
    };
    document.getElementById("btn-run").onclick = async () => {
      if (!payrollState.periodId) return out("Primero: selecciona o crea un período", true);
      if (!employees.length) return out("Sin empleados activos — alta en Empleados", true);
      out(`⏳ Corrida batch (${employees.length} empleado(s))…`);
      try {
        const useAtt = document.getElementById("chk-use-attendance")?.checked || false;
        const r = await api(`/api/v1/payroll/periods/${payrollState.periodId}/run`, {
          method: "POST",
          body: JSON.stringify({ use_attendance: useAtt, dias_trabajados: 15 }),
        });
        payrollState.runId = r.run_id;
        savePayrollState();
        sync();
        showBatchResults(r);
        out(`✅ Corrida batch — ${r.employee_count} empleado(s) · neto total ${fmtMoney(r.totales?.neto)}`);
        await loadPlanillaView(payrollState.runId, container);
      } catch (e) {
        out(`❌ Corrida batch: ${e.message}`, true);
      }
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

    document.getElementById("btn-planilla-refresh").onclick = () =>
      loadPlanillaView(payrollState.runId, container);
    document.getElementById("btn-planilla-xlsx").onclick = async () => {
      if (!payrollState.runId) return out("Sin corrida activa", true);
      try {
        await api(`/api/v1/exports/planilla-modelo/${payrollState.runId}`, { method: "POST", body: "{}" });
        window.open(`/api/v1/exports/planilla-modelo/${payrollState.runId}/download`, "_blank");
      } catch (e) {
        out(`❌ Excel: ${e.message}`, true);
      }
    };

    if (payrollState.runId) {
      loadRun(payrollState.runId);
      loadPlanillaView(payrollState.runId, container);
    }
  }

  async function fetchOrgEmployees() {
    const cfg = getConfig();
    return api(`/api/v1/organizations/${cfg.orgId || DEMO_ORG}/employees`);
  }

  function employeeOptions(employees, selectedId) {
    if (!employees.length) return `<option value="">— Sin empleados (Planilla → Setup demo) —</option>`;
    return employees
      .map(
        (e) =>
          `<option value="${e.id}"${e.id === selectedId ? " selected" : ""}>${e.apellidos}, ${e.nombres}</option>`
      )
      .join("");
  }

  function employeeNameMap(employees) {
    const map = {};
    employees.forEach((e) => {
      map[e.id] = `${e.apellidos}, ${e.nombres}`;
    });
    return map;
  }

  function renderBatchResultsHtml(data, nameMap) {
    const rows = data.employees || [];
    const tot = data.totales || {};
    const runId = data.run_id || "";
    return `
      <p class="settings-kv" style="margin-bottom:0.75rem">
        <strong>Corrida:</strong> <code>${escHtml(runId)}</code> ·
        <strong>Empleados:</strong> ${data.employee_count ?? rows.length}
      </p>
      <table class="table-crud"><thead><tr><th>Empleado</th><th>Bruto</th><th>Deducciones</th><th>Neto</th><th></th></tr></thead><tbody>
        ${rows.length ? rows.map((r) => `<tr>
          <td>${escHtml(nameMap[r.employee_id] || r.employee_id)}</td>
          <td>${fmtMoney(r.bruto)}</td>
          <td>${fmtMoney(r.deducciones)}</td>
          <td>${fmtMoney(r.neto)}</td>
          <td>${runId ? `<a class="btn btn-secondary btn-sm" href="/api/v1/payroll/runs/${escHtml(runId)}/payslips/${escHtml(r.employee_id)}" target="_blank" rel="noopener">PDF</a>` : ""}</td>
        </tr>`).join("") : `<tr><td colspan="5">Sin líneas en la corrida</td></tr>`}
        <tr><td><strong>Total</strong></td><td><strong>${fmtMoney(tot.bruto)}</strong></td><td><strong>${fmtMoney(tot.deducciones)}</strong></td><td><strong>${fmtMoney(tot.neto)}</strong></td><td></td></tr>
      </tbody></table>`;
  }

  async function createEmployeeContract(employeeId, salario, fechaInicio, formaPago) {
    return api(`/api/v1/employees/${employeeId}/contracts`, {
      method: "POST",
      body: JSON.stringify({
        salario_base: Number(salario),
        fecha_inicio: fechaInicio,
        forma_pago: formaPago || "QUINCENAL",
        contract_type_codigo: "INDEFINIDO",
      }),
    });
  }

  function renderPlanillaGrid(data) {
    const cols = data.columnas || [];
    const rows = data.rows || [];
    const tot = data.totales || {};
    const thead = cols.map((c) => `<th title="${escHtml(c.key)}">${escHtml(c.titulo)}</th>`).join("");
    const tbody = rows.length
      ? rows
          .map(
            (r) => `<tr data-emp="${escHtml(r.employee_id)}">${cols
              .map((c) => {
                const v = r[c.key];
                const isMoney = c.tipo === "moneda";
                return `<td>${isMoney ? fmtMoney(v) : escHtml(v ?? "—")}</td>`;
              })
              .join("")}</tr>`
          )
          .join("")
      : `<tr><td colspan="${cols.length}">Sin datos — ejecuta corrida batch</td></tr>`;
    const tfoot =
      `<td><strong>TOTAL</strong></td>` +
      cols
        .slice(1)
        .map((c) =>
          tot[c.key] != null ? `<td><strong>${fmtMoney(tot[c.key])}</strong></td>` : `<td></td>`
        )
        .join("");
    return `
      <p class="settings-kv" style="margin-bottom:0.75rem">
        <strong>${escHtml(data.razon_social || "")}</strong> ·
        ${escHtml(data.periodo?.fecha_inicio)} → ${escHtml(data.periodo?.fecha_fin)} ·
        ${rows.length} empleado(s) · ${cols.length} columnas
      </p>
      <div class="planilla-scroll">
        <table class="table-crud planilla-grid"><thead><tr>${thead}</tr></thead>
        <tbody>${tbody}</tbody>
        <tfoot><tr>${tfoot}</tr></tfoot>
        </table>
      </div>`;
  }

  async function loadPlanillaView(runId, container) {
    const el = document.getElementById("planilla-verify");
    if (!el || !runId) return;
    el.innerHTML = `<p class="loading">Cargando planilla completa…</p>`;
    try {
      const data = await api(`/api/v1/payroll/runs/${runId}/planilla`);
      el.innerHTML = renderPlanillaGrid(data);
    } catch (e) {
      el.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
    }
  }

  async function renderVacations(container) {
    container.innerHTML = `<p class="loading">Cargando vacaciones…</p>`;
    const cfg = getConfig();
    const orgId = cfg.orgId || DEMO_ORG;
    let empId = payrollState.employeeId;
    try {
      const [employees, dash, coverage] = await Promise.all([
        fetchOrgEmployees(),
        api(`/api/v1/organizations/${orgId}/vacation/dashboard`),
        api(`/api/v1/organizations/${orgId}/vacation/coverage`),
      ]);
      if (!empId && employees.length) empId = employees[0].id;

      let balance = null;
      let requests = [];
      if (empId) {
        [balance, requests] = await Promise.all([
          api(`/api/v1/employees/${empId}/vacation/balance`),
          api(`/api/v1/employees/${empId}/vacation/requests`),
        ]);
      }

      const alerts = dash.alertas || [];
      const scheduled = coverage.programadas || coverage.items || [];

      container.innerHTML = `
        <div class="page-header page-header-sub"><h1>Vacaciones</h1><p>Arts. 52–59 · pasivo org · cobertura sustitutos</p></div>
        <div class="grid">
          <div class="card"><div class="label">Pasivo vacaciones (org)</div><div class="value">${fmtMoney(dash.pasivo_total || dash.total_pasivo)}</div></div>
          <div class="card"><div class="label">Empleados con alerta</div><div class="value">${(dash.empleados_alerta || alerts).length || alerts.length}</div></div>
          <div class="card"><div class="label">Programadas sin sustituto</div><div class="value">${coverage.sin_sustituto ?? scheduled.filter((s) => !s.substitute_employee_id).length ?? "—"}</div></div>
        </div>
        <div class="panel">
          <h2>Empleado</h2>
          <select id="vac-emp" class="emp-select">${employeeOptions(employees, empId)}</select>
          <div id="vac-balance" class="loading" style="margin-top:0.75rem">${balance ? `Pendientes: <strong>${balance.dias_pendientes ?? balance.dias_pendiente ?? "—"}</strong> días · ganados ${balance.dias_ganados ?? "—"}` : "Selecciona empleado"}</div>
        </div>
        <div class="panel">
          <div class="crud-form-title" id="vac-form-title">Nueva solicitud</div>
          <form id="vac-form" class="inline-form">
            <input type="hidden" name="request_id" value="" />
            <label>Inicio<input type="date" name="inicio" required /></label>
            <label>Fin<input type="date" name="fin" required /></label>
            <label>Días<input type="number" name="dias" step="0.5" min="0.5" value="5" required /></label>
            <button type="submit" class="btn" id="vac-submit">Solicitar</button>
            <button type="button" class="btn btn-secondary" id="vac-accrue">Acumular saldo</button>
            <button type="button" class="btn btn-secondary hidden" id="vac-cancel">Cancelar edición</button>
          </form>
          <div id="vac-msg"></div>
        </div>
        <div class="panel">
          <h2>Solicitudes</h2>
          <table class="table-crud"><thead><tr><th>Período</th><th>Días</th><th>Estado</th><th>Sustituto</th><th></th></tr></thead>
          <tbody id="vac-requests">${requests.length ? requests.map((r) => {
            const rid = rowKey(r);
            const editable = r.estado === "SOLICITADO";
            const approveBtn = editable ? `<button class="btn btn-secondary btn-sm" data-approve="${escHtml(rid)}">Aprobar</button>` : "";
            return `<tr>
            <td>${escHtml(r.fecha_inicio)} → ${escHtml(r.fecha_fin)}</td><td>${escHtml(r.dias_solicitados)}</td><td>${escHtml(r.estado)}</td>
            <td><code style="font-size:0.65rem">${escHtml(r.substitute_employee_id || "—")}</code></td>
            ${crudActions(rid, { edit: editable, del: editable, extra: approveBtn })}
          </tr>`;
          }).join("") : `<tr><td colspan="5">Sin solicitudes</td></tr>`}</tbody></table>
        </div>
        <div class="panel"><h2>Cobertura próxima</h2>
          <table><thead><tr><th>Empleado</th><th>Desde</th><th>Hasta</th><th>Sustituto</th></tr></thead><tbody>
            ${scheduled.length ? scheduled.slice(0, 10).map((s) => `<tr>
              <td>${s.empleado_nombre || s.employee_id || "—"}</td>
              <td>${s.fecha_inicio}</td><td>${s.fecha_fin}</td>
              <td>${s.substitute_employee_id ? "✓" : "⚠ sin asignar"}</td>
            </tr>`).join("") : `<tr><td colspan="4">Sin vacaciones programadas</td></tr>`}
          </tbody></table>
        </div>`;

      const reloadEmp = async (id) => {
        payrollState.employeeId = id;
        savePayrollState();
        await renderVacations(container);
      };

      document.getElementById("vac-emp").onchange = (e) => reloadEmp(e.target.value);

      const vacForm = document.getElementById("vac-form");
      const vacTitle = document.getElementById("vac-form-title");
      const vacSubmit = document.getElementById("vac-submit");
      const vacCancel = document.getElementById("vac-cancel");

      const resetVacForm = () => {
        vacForm.request_id.value = "";
        vacForm.inicio.value = "";
        vacForm.fin.value = "";
        vacForm.dias.value = "5";
        vacTitle.textContent = "Nueva solicitud";
        vacSubmit.textContent = "Solicitar";
        vacCancel.classList.add("hidden");
      };

      vacCancel.onclick = resetVacForm;

      document.getElementById("vac-accrue").onclick = async () => {
        const id = document.getElementById("vac-emp").value;
        if (!id) return;
        try {
          await api(`/api/v1/employees/${id}/vacation/accrue`, { method: "POST", body: "{}" });
          document.getElementById("vac-msg").innerHTML = `<div class="alert alert-success">Saldo acumulado</div>`;
          reloadEmp(id);
        } catch (e) {
          document.getElementById("vac-msg").innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
      };

      document.getElementById("vac-form").onsubmit = async (e) => {
        e.preventDefault();
        const id = document.getElementById("vac-emp").value;
        if (!id) return;
        const fd = new FormData(e.target);
        const requestId = fd.get("request_id");
        const payload = {
          fecha_inicio: fd.get("inicio"),
          fecha_fin: fd.get("fin"),
          dias_solicitados: Number(fd.get("dias")),
        };
        try {
          if (requestId) {
            await apiPatch(`/api/v1/vacation/requests/${requestId}`, payload);
            flashMsg("vac-msg", "Solicitud actualizada");
          } else {
            await api(`/api/v1/employees/${id}/vacation/requests`, {
              method: "POST",
              body: JSON.stringify(payload),
            });
            flashMsg("vac-msg", "Solicitud creada");
          }
          resetVacForm();
          reloadEmp(id);
        } catch (err) {
          flashMsg("vac-msg", err.message, false);
        }
      };

      bindCrud(container, {
        onEdit: (requestId) => {
          const row = requests.find((r) => rowKey(r) === requestId);
          if (!row || row.estado !== "SOLICITADO") return;
          vacForm.request_id.value = requestId;
          vacForm.inicio.value = row.fecha_inicio;
          vacForm.fin.value = row.fecha_fin;
          vacForm.dias.value = row.dias_solicitados;
          vacTitle.textContent = "Editar solicitud";
          vacSubmit.textContent = "Guardar";
          vacCancel.classList.remove("hidden");
          vacForm.scrollIntoView({ behavior: "smooth", block: "start" });
        },
        onDelete: async (requestId) => {
          if (!confirm("¿Cancelar esta solicitud?")) return;
          try {
            await apiDelete(`/api/v1/vacation/requests/${requestId}`);
            flashMsg("vac-msg", "Solicitud cancelada");
            reloadEmp(document.getElementById("vac-emp").value);
          } catch (err) {
            flashMsg("vac-msg", err.message, false);
          }
        },
      });

      container.querySelectorAll("[data-approve]").forEach((btn) => {
        btn.onclick = async () => {
          try {
            await api(`/api/v1/vacation/requests/${btn.dataset.approve}/approve`, {
              method: "POST",
              body: "{}",
            });
            reloadEmp(document.getElementById("vac-emp").value);
          } catch (err) {
            document.getElementById("vac-msg").innerHTML = `<div class="alert alert-error">${err.message}</div>`;
          }
        };
      });
    } catch (e) {
      container.innerHTML = `<div class="page-header page-header-sub"><h1>Vacaciones</h1></div><div class="alert alert-error">${e.message}</div>`;
    }
  }

  async function renderAttendance(container) {
    const cfg = getConfig();
    const orgId = cfg.orgId || DEMO_ORG;
    container.innerHTML = `<p class="loading">Cargando asistencia…</p>`;

    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const defaultIni = `${y}-${m}-01`;
    const defaultFin = `${y}-${m}-15`;

    container.innerHTML = `
      <div class="page-header page-header-sub">
        <h1>Asistencia</h1>
        <p>Tabla estándar de hechos — CSV, API o carga manual. El motor de planilla no depende del reloj.</p>
      </div>
      <div class="panel">
        <h2>Importar CSV</h2>
        <p class="loading" style="margin-bottom:0.75rem">Columnas: cedula, fecha, turno, hora_entrada, hora_salida, descanso_minutos, tipo_dia, ausencia, incapacidad, vacaciones, observacion</p>
        <form id="att-import-form">
          <div class="inline-form" style="margin-bottom:0.75rem">
            <label>Desde<input type="date" name="fecha_inicio" value="${defaultIni}" required /></label>
            <label>Hasta<input type="date" name="fecha_fin" value="${defaultFin}" required /></label>
            <label>Archivo<input type="text" name="nombre" placeholder="asistencia-junio.csv" /></label>
          </div>
          <label>Contenido CSV<textarea name="csv" rows="8" placeholder="cedula,fecha,turno,hora_entrada,hora_salida,..."></textarea></label>
          <div class="btn-row" style="margin-top:0.75rem">
            <button type="submit" class="btn">Importar</button>
            <button type="button" class="btn btn-secondary" id="att-validate">Validar período</button>
            <button type="button" class="btn btn-secondary" id="att-process">Procesar → resumen quincenal</button>
          </div>
        </form>
        <div id="att-msg"></div>
        <pre class="output" id="att-output">Listo.</pre>
      </div>
      <div class="panel">
        <h2>Hechos del período</h2>
        <div class="btn-row" style="margin-bottom:0.75rem">
          <button type="button" class="btn btn-secondary btn-sm" id="att-refresh">Actualizar</button>
        </div>
        <div id="att-facts"><p class="loading">—</p></div>
      </div>
      <div class="panel">
        <h2>Resumen quincenal</h2>
        <div id="att-summary"><p class="loading">Procese el período para ver resumen por empleado</p></div>
      </div>`;

    const out = (text, err) => {
      const el = document.getElementById("att-output");
      el.className = err ? "alert alert-error" : "alert alert-success";
      el.textContent = text;
    };

    const getRange = () => {
      const form = document.getElementById("att-import-form");
      return {
        fecha_inicio: form.fecha_inicio.value,
        fecha_fin: form.fecha_fin.value,
      };
    };

    const loadFacts = async () => {
      const { fecha_inicio, fecha_fin } = getRange();
      const el = document.getElementById("att-facts");
      try {
        const data = await api(
          `/api/v1/organizations/${orgId}/attendance/facts?fecha_inicio=${fecha_inicio}&fecha_fin=${fecha_fin}`
        );
        const facts = data.facts || [];
        el.innerHTML = facts.length
          ? `<table class="table-crud"><thead><tr>
              <th>Cédula</th><th>Fecha</th><th>Entrada</th><th>Salida</th><th>Tipo</th><th>Estado</th><th>Obs.</th>
            </tr></thead><tbody>${facts
              .map(
                (f) => `<tr>
                <td>${escHtml(f.cedula)}</td>
                <td>${escHtml(f.fecha)}</td>
                <td>${escHtml(f.hora_entrada || (f.ausencia ? "ausencia" : "—"))}</td>
                <td>${escHtml(f.hora_salida || "—")}</td>
                <td>${escHtml(f.tipo_dia)}</td>
                <td>${f.estado_validacion === "VALIDO" ? "✓" : "✗"} ${escHtml(f.estado_validacion)}</td>
                <td>${escHtml(f.observacion || "")}</td>
              </tr>`
              )
              .join("")}</tbody></table>`
          : `<p class="loading">Sin hechos en el rango seleccionado</p>`;
      } catch (e) {
        el.innerHTML = `<p class="alert alert-error">${escHtml(e.message)}</p>`;
      }
    };

    const loadSummary = async () => {
      const { fecha_inicio, fecha_fin } = getRange();
      const el = document.getElementById("att-summary");
      try {
        const data = await api(
          `/api/v1/organizations/${orgId}/attendance/summary?fecha_inicio=${fecha_inicio}&fecha_fin=${fecha_fin}`
        );
        const emps = data.employees || [];
        el.innerHTML = emps.length
          ? `<table class="table-crud"><thead><tr>
              <th>Cédula</th><th>Nombre</th><th>Días</th><th>Extra D</th><th>Extra N</th><th>Dom.</th><th>Feriado</th><th>Aus.</th><th>Tard.</th>
            </tr></thead><tbody>${emps
              .map(
                (e) => `<tr>
                <td>${escHtml(e.cedula)}</td><td>${escHtml(e.nombre)}</td>
                <td>${escHtml(e.dias_trabajados)}</td><td>${escHtml(e.horas_extra_diurnas)}</td>
                <td>${escHtml(e.horas_extra_nocturnas)}</td><td>${escHtml(e.horas_domingo)}</td>
                <td>${escHtml(e.horas_feriado)}</td><td>${e.ausencias}</td><td>${e.tardanzas}</td>
              </tr>`
              )
              .join("")}</tbody></table>`
          : `<p class="loading">Sin resumen — importe y procese hechos válidos</p>`;
      } catch (e) {
        el.innerHTML = `<p class="alert alert-error">${escHtml(e.message)}</p>`;
      }
    };

    document.getElementById("att-import-form").onsubmit = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      try {
        const r = await api(`/api/v1/organizations/${orgId}/attendance/import/csv`, {
          method: "POST",
          body: JSON.stringify({
            csv_content: fd.get("csv"),
            fuente: "CSV",
            nombre_archivo: fd.get("nombre") || null,
            fecha_inicio: fd.get("fecha_inicio"),
            fecha_fin: fd.get("fecha_fin"),
          }),
        });
        flashMsg("att-msg", `Importado: ${r.validos} válidos, ${r.errores} errores`);
        out(JSON.stringify(r, null, 2));
        await loadFacts();
      } catch (err) {
        flashMsg("att-msg", err.message, false);
        out(err.message, true);
      }
    };

    document.getElementById("att-validate").onclick = async () => {
      const { fecha_inicio, fecha_fin } = getRange();
      try {
        const r = await api(`/api/v1/organizations/${orgId}/attendance/validate`, {
          method: "POST",
          body: JSON.stringify({ fecha_inicio, fecha_fin }),
        });
        out(JSON.stringify(r, null, 2), !r.listo_para_planilla);
        flashMsg("att-msg", r.listo_para_planilla ? "Listo para planilla" : "Hay errores pendientes", r.listo_para_planilla);
      } catch (err) {
        out(err.message, true);
      }
    };

    document.getElementById("att-process").onclick = async () => {
      const { fecha_inicio, fecha_fin } = getRange();
      try {
        const r = await api(`/api/v1/organizations/${orgId}/attendance/process`, {
          method: "POST",
          body: JSON.stringify({ fecha_inicio, fecha_fin }),
        });
        out(JSON.stringify(r, null, 2));
        await loadSummary();
        await loadFacts();
      } catch (err) {
        out(err.message, true);
      }
    };

    document.getElementById("att-refresh").onclick = () => {
      loadFacts();
      loadSummary();
    };

    await loadFacts();
  }

  async function renderIncapacities(container) {
    container.innerHTML = `<p class="loading">Cargando incapacidades…</p>`;
    let empId = payrollState.employeeId;
    try {
      const employees = await fetchOrgEmployees();
      if (!empId && employees.length) empId = employees[0].id;

      let rows = [];
      let fund = null;
      if (empId) {
        [rows, fund] = await Promise.all([
          api(`/api/v1/employees/${empId}/incapacities`),
          api(`/api/v1/employees/${empId}/license-fund/balance`),
        ]);
      }

      container.innerHTML = `
        <div class="page-header page-header-sub"><h1>Incapacidades</h1><p>Art. 200 · fondo licencia · GT-10</p></div>
        <div class="panel">
          <h2>Empleado</h2>
          <select id="inc-emp" class="emp-select">${employeeOptions(employees, empId)}</select>
          <p class="loading" style="margin-top:0.75rem">Fondo licencia ${fund?.anio || new Date().getFullYear()}: <strong>${fund?.horas_disponibles ?? fund?.saldo_horas ?? "—"}</strong> h disponibles</p>
        </div>
        <div class="panel">
          <div class="crud-form-title" id="inc-form-title">Registrar incapacidad</div>
          <form id="inc-form" class="inline-form">
            <input type="hidden" name="incapacity_id" value="" />
            <label>Inicio<input type="date" name="inicio" required /></label>
            <label>Fin<input type="date" name="fin" required /></label>
            <label>Tipo<select name="tipo"><option value="CSS">CSS</option><option value="MATERNIDAD">Maternidad</option><option value="OTRO">Otro</option></select></label>
            <label>Certificado<input type="text" name="cert" placeholder="Ref. CSS" /></label>
            <button type="submit" class="btn" id="inc-submit">Registrar</button>
            <button type="button" class="btn btn-secondary hidden" id="inc-cancel">Cancelar</button>
          </form>
          <div id="inc-msg"></div>
        </div>
        <div class="panel">
          <h2>Impacto en período</h2>
          <form id="inc-impact-form" class="inline-form">
            <label>Desde<input type="date" name="desde" required /></label>
            <label>Hasta<input type="date" name="hasta" required /></label>
            <button type="submit" class="btn btn-secondary">Calcular GT-10</button>
          </form>
          <pre class="output" id="inc-impact-out">—</pre>
        </div>
        <div class="panel">
          <h2>Historial</h2>
          <table class="table-crud"><thead><tr><th>Inicio</th><th>Fin</th><th>Tipo</th><th>Certificado</th><th></th></tr></thead><tbody>
            ${rows.length ? rows.map((r) => `<tr>
              <td>${escHtml(r.fecha_inicio)}</td><td>${escHtml(r.fecha_fin)}</td><td>${escHtml(r.tipo)}</td><td>${escHtml(r.certificado_ref || "—")}</td>
              ${crudActions(r.id)}
            </tr>`).join("") : `<tr><td colspan="5">Sin registros</td></tr>`}
          </tbody></table>
        </div>`;

      const incForm = document.getElementById("inc-form");
      const incTitle = document.getElementById("inc-form-title");
      const incSubmit = document.getElementById("inc-submit");
      const incCancel = document.getElementById("inc-cancel");

      const resetIncForm = () => {
        incForm.incapacity_id.value = "";
        incForm.reset();
        incTitle.textContent = "Registrar incapacidad";
        incSubmit.textContent = "Registrar";
        incCancel.classList.add("hidden");
      };

      incCancel.onclick = resetIncForm;

      const reloadEmp = async (id) => {
        payrollState.employeeId = id;
        savePayrollState();
        await renderIncapacities(container);
      };

      document.getElementById("inc-emp").onchange = (e) => reloadEmp(e.target.value);

      document.getElementById("inc-form").onsubmit = async (e) => {
        e.preventDefault();
        const id = document.getElementById("inc-emp").value;
        if (!id) return;
        const fd = new FormData(e.target);
        const incId = fd.get("incapacity_id");
        const payload = {
          fecha_inicio: fd.get("inicio"),
          fecha_fin: fd.get("fin"),
          tipo: fd.get("tipo"),
          certificado_ref: fd.get("cert") || null,
        };
        try {
          if (incId) {
            await apiPatch(`/api/v1/incapacities/${incId}`, payload);
            flashMsg("inc-msg", "Incapacidad actualizada");
          } else {
            await api(`/api/v1/employees/${id}/incapacities`, {
              method: "POST",
              body: JSON.stringify(payload),
            });
            flashMsg("inc-msg", "Incapacidad registrada");
          }
          resetIncForm();
          reloadEmp(id);
        } catch (err) {
          flashMsg("inc-msg", err.message, false);
        }
      };

      bindCrud(container, {
        onEdit: async (incId) => {
          try {
            const row = await api(`/api/v1/incapacities/${incId}`);
            incForm.incapacity_id.value = incId;
            incForm.inicio.value = row.fecha_inicio;
            incForm.fin.value = row.fecha_fin;
            incForm.tipo.value = row.tipo;
            incForm.cert.value = row.certificado_ref || "";
            incTitle.textContent = "Editar incapacidad";
            incSubmit.textContent = "Guardar";
            incCancel.classList.remove("hidden");
            incForm.scrollIntoView({ behavior: "smooth", block: "start" });
          } catch (err) {
            flashMsg("inc-msg", err.message, false);
          }
        },
        onDelete: async (incId) => {
          if (!confirm("¿Eliminar este registro de incapacidad?")) return;
          try {
            await apiDelete(`/api/v1/incapacities/${incId}`);
            flashMsg("inc-msg", "Incapacidad eliminada");
            reloadEmp(document.getElementById("inc-emp").value);
          } catch (err) {
            flashMsg("inc-msg", err.message, false);
          }
        },
      });

      document.getElementById("inc-impact-form").onsubmit = async (e) => {
        e.preventDefault();
        const id = document.getElementById("inc-emp").value;
        if (!id) return;
        const fd = new FormData(e.target);
        const out = document.getElementById("inc-impact-out");
        out.textContent = "Calculando…";
        try {
          const r = await api(`/api/v1/employees/${id}/incapacities/period-impact`, {
            method: "POST",
            body: JSON.stringify({ fecha_inicio: fd.get("desde"), fecha_fin: fd.get("hasta") }),
          });
          out.textContent = JSON.stringify(r, null, 2);
        } catch (err) {
          out.textContent = err.message;
        }
      };
    } catch (e) {
      container.innerHTML = `<div class="page-header page-header-sub"><h1>Incapacidades</h1></div><div class="alert alert-error">${e.message}</div>`;
    }
  }

  const CAUSAS = [
    { value: "RENUNCIA", label: "Renuncia" },
    { value: "DESPIDO_JUSTIFICADO", label: "Despido justificado" },
    { value: "DESPIDO_INJUSTIFICADO", label: "Despido injustificado" },
  ];

  function todayIso() {
    return new Date().toISOString().slice(0, 10);
  }

  async function renderLiquidations(container) {
    container.innerHTML = `<p class="loading">Cargando liquidaciones…</p>`;
    const cfg = getConfig();
    const orgId = cfg.orgId || DEMO_ORG;
    let empId = payrollState.employeeId;
    try {
      const [employees, cases] = await Promise.all([
        fetchOrgEmployees(),
        api(`/api/v1/organizations/${orgId}/terminations`).catch(() => []),
      ]);
      if (!empId && employees.length) empId = employees[0].id;

      let balance = null;
      if (empId) {
        try {
          balance = await api(`/api/v1/employees/${empId}/vacation/balance`);
        } catch {
          balance = null;
        }
      }

      const diasVac = balance?.dias_pendientes ?? balance?.dias_pendiente ?? "0";

      container.innerHTML = `
        <div class="page-header page-header-sub"><h1>Liquidaciones</h1><p>GT-05 / GT-06 · cálculo y registro de casos</p></div>
        <div class="panel">
          <h2>Casos guardados</h2>
          <table class="table-crud"><thead><tr><th>Empleado</th><th>Causa</th><th>Terminación</th><th>Total</th><th></th></tr></thead><tbody>
            ${cases.length ? cases.map((c) => `<tr>
              <td>${escHtml(c.nombres)} ${escHtml(c.apellidos)}</td>
              <td>${escHtml(c.causa)}</td>
              <td>${escHtml(c.fecha_terminacion)}</td>
              <td>${fmtMoney(c.total)}</td>
              <td class="crud-actions"><button type="button" class="btn btn-secondary btn-sm" data-crud-view="${escHtml(c.case_id)}">Ver</button></td>
            </tr>`).join("") : `<tr><td colspan="5">Sin casos guardados</td></tr>`}
          </tbody></table>
        </div>
        <div class="panel">
          <div class="crud-form-title">Nuevo cálculo</div>
          <form id="liq-form" class="inline-form">
            <label>Empleado
              <select id="liq-emp" name="employee" class="emp-select">${employeeOptions(employees, empId)}</select>
            </label>
            <label>Causa
              <select name="causa">${CAUSAS.map((c) => `<option value="${c.value}">${c.label}</option>`).join("")}</select>
            </label>
            <label>Terminación<input type="date" name="fecha_terminacion" value="${todayIso()}" required /></label>
            <label>Cumplió preaviso<input type="checkbox" name="cumplio_preaviso" checked style="width:auto;margin-top:0.35rem" /></label>
          </form>
        </div>
        <div class="panel">
          <h2>Parámetros</h2>
          <form id="liq-params" class="inline-form">
            <label>Días vac. pend.<input type="number" name="dias_vacaciones" step="0.5" min="0" value="${diasVac}" /></label>
            <label>Salario prima<input type="number" name="salario_prima" step="0.01" min="0" placeholder="Auto contrato" /></label>
            <label>Salario diario vac.<input type="number" name="salario_diario_vac" step="0.01" min="0" placeholder="Opcional" /></label>
            <label>Salarios acum. año<input type="number" name="salarios_anio" step="0.01" min="0" value="0" /></label>
            <label>Salario indem.<input type="number" name="salario_indem" step="0.01" min="0" placeholder="Opcional" /></label>
          </form>
          <div class="btn-row" style="margin-top:0.75rem;margin-bottom:0">
            <button type="button" class="btn" id="liq-calc">Calcular</button>
            <button type="button" class="btn btn-secondary" id="liq-persist" disabled>Guardar caso</button>
          </div>
          <div id="liq-msg"></div>
        </div>
        <div class="panel">
          <h2>Resultado</h2>
          <div id="liq-result"><p class="loading">Selecciona empleado y calcula</p></div>
        </div>`;

      let lastPayload = null;

      const reloadEmp = async (id) => {
        payrollState.employeeId = id;
        savePayrollState();
        await renderLiquidations(container);
      };

      document.getElementById("liq-emp").onchange = (e) => reloadEmp(e.target.value);

      const renderCaseDetail = (data) => {
        document.getElementById("liq-result").innerHTML = `
          <p class="settings-kv" style="margin-bottom:0.75rem">
            <strong>Caso:</strong> <code>${escHtml(data.case_id)}</code> ·
            <strong>Causa:</strong> ${escHtml(data.causa || "—")} ·
            <strong>Terminación:</strong> ${escHtml(data.fecha_terminacion || "—")}
          </p>
          <table><thead><tr><th>Concepto</th><th>Monto</th></tr></thead><tbody>
            <tr><td>Vacaciones</td><td>${fmtMoney(data.monto_vacaciones)}</td></tr>
            <tr><td>Décimo</td><td>${fmtMoney(data.monto_decimo)}</td></tr>
            <tr><td>Prima antigüedad</td><td>${fmtMoney(data.monto_prima)}</td></tr>
            <tr><td>Preaviso</td><td>${fmtMoney(data.monto_preaviso)}</td></tr>
            <tr><td>Indemnización</td><td>${fmtMoney(data.monto_indemnizacion)}</td></tr>
            <tr><td><strong>Total</strong></td><td><strong>${fmtMoney(data.total)}</strong></td></tr>
          </tbody></table>`;
      };

      const buildBody = (persist) => {
        const emp = document.getElementById("liq-emp").value;
        if (!emp) throw new Error("Selecciona un empleado");
        const f = document.getElementById("liq-form");
        const p = document.getElementById("liq-params");
        const fd = new FormData(f);
        const pd = new FormData(p);
        const body = {
          causa: fd.get("causa"),
          fecha_terminacion: fd.get("fecha_terminacion"),
          cumplio_preaviso: fd.get("cumplio_preaviso") === "on",
          dias_vacaciones_pendientes: Number(pd.get("dias_vacaciones") || 0),
          salarios_acumulados_anio: Number(pd.get("salarios_anio") || 0),
          persist,
        };
        const salPrima = pd.get("salario_prima");
        const salDiario = pd.get("salario_diario_vac");
        const salIndem = pd.get("salario_indem");
        if (salPrima) body.salario_promedio_prima = Number(salPrima);
        if (salDiario) body.salario_diario_vacaciones = Number(salDiario);
        if (salIndem) body.salario_promedio_indemnizacion = Number(salIndem);
        return { emp, body };
      };

      const renderResult = (data) => {
        const lines = data.lines || [];
        document.getElementById("liq-result").innerHTML = `
          <p class="settings-kv" style="margin-bottom:0.75rem">
            <strong>Bruto:</strong> ${fmtMoney(data.bruto)} ·
            <strong>Deducciones:</strong> ${fmtMoney(data.deducciones)} ·
            <strong>Neto:</strong> ${fmtMoney(data.neto)}
            ${data.case_id ? ` · <strong>Caso:</strong> <code>${data.case_id}</code>` : ""}
          </p>
          <table><thead><tr><th>Concepto</th><th>Tipo</th><th>Monto</th></tr></thead><tbody>
            ${lines.length ? lines.map((l) => `<tr><td>${l.concepto}</td><td>${l.tipo}</td><td>${fmtMoney(l.monto)}</td></tr>`).join("") : `<tr><td colspan="3">Sin líneas</td></tr>`}
          </tbody></table>`;
      };

      document.getElementById("liq-calc").onclick = async () => {
        flashMsg("liq-msg", "");
        document.getElementById("liq-result").innerHTML = `<p class="loading">Calculando…</p>`;
        try {
          const { emp, body } = buildBody(false);
          lastPayload = { emp, body: { ...body, persist: true } };
          const data = await api(`/api/v1/employees/${emp}/termination/calculate`, {
            method: "POST",
            body: JSON.stringify(body),
          });
          renderResult(data);
          document.getElementById("liq-persist").disabled = false;
        } catch (e) {
          document.getElementById("liq-result").innerHTML = `<p class="loading">—</p>`;
          flashMsg("liq-msg", e.message, false);
        }
      };

      document.getElementById("liq-persist").onclick = async () => {
        try {
          const { emp, body } = lastPayload || buildBody(true);
          const data = await api(`/api/v1/employees/${emp}/termination/calculate`, {
            method: "POST",
            body: JSON.stringify({ ...body, persist: true }),
          });
          renderResult(data);
          flashMsg("liq-msg", "Caso guardado — empleado marcado inactivo");
          document.getElementById("liq-persist").disabled = true;
          await renderLiquidations(container);
        } catch (e) {
          flashMsg("liq-msg", e.message, false);
        }
      };

      bindCrud(container, {
        onView: async (caseId) => {
          try {
            const data = await api(`/api/v1/termination/${caseId}`);
            renderCaseDetail(data);
            document.getElementById("liq-result").scrollIntoView({ behavior: "smooth" });
          } catch (e) {
            flashMsg("liq-msg", e.message, false);
          }
        },
      });
    } catch (e) {
      container.innerHTML = `<div class="page-header page-header-sub"><h1>Liquidaciones</h1></div><div class="alert alert-error">${escHtml(e.message)}</div>`;
    }
  }

  const pages = {
    dashboard: renderDashboard,
    employees: renderEmployees,
    payroll: renderPayroll,
    attendance: renderAttendance,
    vacations: renderVacations,
    incapacities: renderIncapacities,
    liquidations: renderLiquidations,
    settings: renderSettings,
  };

  function sessionLabel() {
    return getJwt() ? "Sesión JWT activa" : "Modo headers (stub)";
  }

  async function renderSettings(container) {
    const cfg = getConfig();
    let healthHtml = `<span class="loading">Verificando…</span>`;
    try {
      const h = await api("/health");
      healthHtml = `<span class="status-dot ok"></span> Conectado — API v${h.version}`;
    } catch (e) {
      healthHtml = `<span class="status-dot err"></span> ${e.message}`;
    }

    container.innerHTML = `
      <div class="page-header page-header-sub">
        <h1>Configuración</h1>
        <p>Conexión API, organización y sesión</p>
      </div>
      <div class="settings-grid">
        <div class="panel settings-section">
          <h2>Conexión API</h2>
          <div class="field">
            <label for="cfg-base">API base</label>
            <input id="cfg-base" type="url" spellcheck="false" value="${cfg.apiBase.replace(/"/g, "&quot;")}" placeholder="${location.origin}" />
            <p class="settings-hint">Vacío = mismo origen (<code>${location.origin}</code>)</p>
          </div>
          <p id="cfg-health" class="settings-kv">${healthHtml}</p>
          <div class="settings-actions">
            <button type="button" class="btn btn-secondary" id="cfg-test">Probar conexión</button>
          </div>
        </div>
        <div class="panel settings-section">
          <h2>Organización</h2>
          <div class="field">
            <label for="cfg-tenant">Tenant ID</label>
            <input id="cfg-tenant" type="text" spellcheck="false" value="${cfg.tenantId.replace(/"/g, "&quot;")}" />
          </div>
          <div class="field">
            <label for="cfg-org">Organización ID</label>
            <input id="cfg-org" type="text" spellcheck="false" value="${cfg.orgId.replace(/"/g, "&quot;")}" />
          </div>
          <p class="settings-hint">Demo seed: tenant <code>${DEMO_TENANT}</code> · org <code>${DEMO_ORG}</code></p>
          <div class="settings-actions">
            <button type="button" class="btn" id="cfg-save">Guardar</button>
            <button type="button" class="btn btn-secondary" id="cfg-reset-demo">Restaurar demo</button>
          </div>
          <div id="cfg-save-msg"></div>
        </div>
        <div class="panel settings-section">
          <h2>Sesión</h2>
          <div id="session-badge" class="session-badge ${getJwt() ? "ok" : "guest"}">${sessionLabel()}</div>
          <p class="settings-kv">
            <strong>Tenant:</strong> ${cfg.tenantId}<br />
            <strong>Organización:</strong> ${cfg.orgId || "—"}
          </p>
          <div class="settings-actions">
            <button type="button" class="btn" id="btn-login-open">Iniciar sesión</button>
            <button type="button" class="btn btn-secondary" id="btn-logout">Cerrar sesión</button>
          </div>
        </div>
        <div class="panel settings-section" style="grid-column:1/-1">
          <h2>Configuración legal (por organización)</h2>
          <p class="settings-hint">Tasas CSS/SE/Riesgo y cuentas contables — editables por compañía.</p>
          <div class="btn-row" style="margin-bottom:0.75rem">
            <button type="button" class="btn btn-secondary btn-sm" id="cfg-legal-load">Cargar config</button>
            <button type="button" class="btn btn-secondary btn-sm" id="cfg-legal-seed">Cargar defaults modelo</button>
          </div>
          <div id="cfg-legal-content"><p class="loading">Pulse «Cargar config»</p></div>
        </div>
      </div>`;

    const persist = (msg) => {
      const tenant = document.getElementById("cfg-tenant").value.trim();
      const org = document.getElementById("cfg-org").value.trim();
      const apiBase = document.getElementById("cfg-base").value.trim();
      saveConfig({ tenantId: tenant, orgId: org, apiBase });
      checkHealth();
      if (msg) {
        const el = document.getElementById("cfg-save-msg");
        el.innerHTML = `<div class="alert alert-success" style="margin-top:0.75rem">${msg}</div>`;
        setTimeout(() => { el.innerHTML = ""; }, 2500);
      }
    };

    document.getElementById("cfg-save").onclick = () => persist("Configuración guardada");
    document.getElementById("cfg-reset-demo").onclick = () => {
      document.getElementById("cfg-tenant").value = DEMO_TENANT;
      document.getElementById("cfg-org").value = DEMO_ORG;
      document.getElementById("cfg-base").value = "";
      persist("Valores demo restaurados");
    };
    document.getElementById("cfg-test").onclick = async () => {
      const el = document.getElementById("cfg-health");
      el.innerHTML = `<span class="loading">Verificando…</span>`;
      persist();
      try {
        const h = await api("/health");
        el.innerHTML = `<span class="status-dot ok"></span> Conectado — API v${h.version}`;
      } catch (e) {
        el.innerHTML = `<span class="status-dot err"></span> ${e.message}`;
      }
    };

    document.getElementById("btn-login-open").onclick = () => {
      const modal = document.getElementById("login-modal");
      const form = document.getElementById("login-form");
      form.tenant.value = getConfig().tenantId;
      form.org.value = getConfig().orgId;
      modal.classList.remove("hidden");
    };
    document.getElementById("btn-logout").onclick = () => {
      setJwt("");
      setRefreshToken("");
      document.getElementById("session-badge").className = "session-badge guest";
      document.getElementById("session-badge").textContent = sessionLabel();
      document.getElementById("login-modal").classList.remove("hidden");
    };

    const renderLegal = async () => {
      const orgId = document.getElementById("cfg-org").value.trim() || DEMO_ORG;
      const box = document.getElementById("cfg-legal-content");
      box.innerHTML = `<p class="loading">Cargando…</p>`;
      try {
        const [rates, accounts] = await Promise.all([
          api(`/api/v1/organizations/${orgId}/legal/rates`),
          api(`/api/v1/organizations/${orgId}/legal/account-codes`),
        ]);
        box.innerHTML = `
          <h3 style="margin:0.75rem 0 0.35rem">Tasas</h3>
          <table class="table-crud"><thead><tr><th>Código</th><th>% Empleado</th><th>% Patronal</th><th>Vigencia</th></tr></thead>
          <tbody>${rates.length ? rates.map((r) => `<tr><td>${escHtml(r.codigo)}</td><td>${r.porcentaje_empleado || "—"}</td><td>${r.porcentaje_empleador || "—"}</td><td>${escHtml(r.vigencia_desde)}</td></tr>`).join("") : `<tr><td colspan="4">Sin tasas — use defaults modelo</td></tr>`}</tbody></table>
          <h3 style="margin:0.75rem 0 0.35rem">Cuentas contables</h3>
          <table class="table-crud"><thead><tr><th>Concepto</th><th>Cuenta</th><th>Etiqueta</th></tr></thead>
          <tbody>${accounts.length ? accounts.map((a) => `<tr><td>${escHtml(a.concepto_codigo)}</td><td>${escHtml(a.cuenta_codigo)}</td><td>${escHtml(a.etiqueta || "—")}</td></tr>`).join("") : `<tr><td colspan="3">Sin cuentas</td></tr>`}</tbody></table>`;
      } catch (e) {
        box.innerHTML = `<div class="alert alert-error">${escHtml(e.message)}</div>`;
      }
    };
    document.getElementById("cfg-legal-load").onclick = renderLegal;
    document.getElementById("cfg-legal-seed").onclick = async () => {
      const orgId = document.getElementById("cfg-org").value.trim() || DEMO_ORG;
      try {
        await api(`/api/v1/organizations/${orgId}/legal/seed-defaults`, { method: "POST", body: "{}" });
        await renderLegal();
      } catch (e) {
        flashMsg("cfg-save-msg", e.message, false);
      }
    };
  }

  async function checkHealth() {
    const el = document.getElementById("api-status");
    if (!el) return;
    el.classList.add("loading");
    try {
      const h = await api("/health");
      el.classList.remove("loading");
      el.innerHTML = `<span class="status-dot ok"></span>API v${h.version}`;
    } catch (e) {
      el.classList.remove("loading");
      el.innerHTML = `<span class="status-dot err"></span>${e.message}`;
    }
  }

  function pageContainer() {
    const inner = document.querySelector("#page-content .page-inner");
    if (inner) return inner;
    const main = document.getElementById("page-content");
    if (!main) return null;
    const wrap = document.createElement("div");
    wrap.className = "page-inner";
    main.innerHTML = "";
    main.appendChild(wrap);
    return wrap;
  }

  function setPageTitle(name) {
    const el = document.getElementById("page-title");
    if (el) el.textContent = PAGE_TITLES[name] || name;
  }

  function initSidebar() {
    const layout = document.getElementById("app-layout");
    const toggle = document.getElementById("sidebar-toggle");
    if (!layout || !toggle) return;
    if (localStorage.getItem(SIDEBAR_KEY) === "1") {
      layout.classList.add("sidebar-collapsed");
      const label = toggle.querySelector(".collapse-label");
      if (label) label.textContent = "Expandir";
    }
    toggle.onclick = () => {
      const collapsed = layout.classList.toggle("sidebar-collapsed");
      localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
      const label = toggle.querySelector(".collapse-label");
      if (label) label.textContent = collapsed ? "Expandir" : "Contraer";
    };
  }

  async function navigate(name) {
    document.querySelectorAll("[data-page]").forEach((b) => {
      b.classList.toggle("active", b.dataset.page === name);
    });
    setPageTitle(name);
    const container = pageContainer();
    if (!container) return;
    try {
      await pages[name](container);
    } catch (e) {
      container.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
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
    navigate("settings");
  }

  function bindLogin() {
    const form = document.getElementById("login-form");
    if (!form) return;
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
    bindLogin();
    initSidebar();
    document.querySelectorAll("[data-page]").forEach((btn) => {
      btn.onclick = () => navigate(btn.dataset.page);
    });
    checkHealth();
    navigate("dashboard");
  }

  boot();
})();
