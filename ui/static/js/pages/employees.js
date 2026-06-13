import { api, getConfig, DEMO_ORG } from "../api.js";

export async function renderEmployees(container) {
  container.innerHTML = `<p class="loading">Cargando empleados…</p>`;
  const cfg = getConfig();

  try {
    const rows = await api(`/api/v1/organizations/${cfg.orgId || DEMO_ORG}/employees`);

    container.innerHTML = `
      <div class="page-header">
        <h1>Empleados</h1>
        <p>${rows.length} activo(s) en la organización</p>
      </div>

      <div class="panel">
        <table>
          <thead>
            <tr>
              <th>Cédula</th>
              <th>Nombre</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            ${
              rows.length
                ? rows
                    .map(
                      (e) =>
                        `<tr>
                          <td>${e.cedula}</td>
                          <td>${e.nombres} ${e.apellidos}</td>
                          <td><code style="font-size:0.7rem;color:var(--muted)">${e.id}</code></td>
                        </tr>`
                    )
                    .join("")
                : `<tr><td colspan="3" class="loading">Sin empleados — usa Planilla → Setup demo</td></tr>`
            }
          </tbody>
        </table>
      </div>
    `;
  } catch (e) {
    container.innerHTML = `
      <div class="page-header"><h1>Empleados</h1></div>
      <div class="alert alert-error">${e.message}</div>
    `;
  }
}
