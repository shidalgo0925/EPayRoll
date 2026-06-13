# EPAYROLL_MASTER_PLAN.md

**Versión:** 1.0  
**Estado:** Diseño Estratégico  
**Propietario:** Easy Technology Services  
**Producto:** EPayRoll  
**Fecha:** Junio 2026

---

## 1. VISIÓN

EPayRoll será una plataforma SaaS de gestión laboral, planilla, cumplimiento legal y administración del talento humano para Panamá, construida sobre la arquitectura multiempresa y multitenant de EasyNodeOne (EN1).

El objetivo **no** es desarrollar una calculadora de planilla.

El objetivo es construir una **plataforma de cumplimiento laboral** que permita a una empresa administrar integralmente:

- Empleados
- Contratos
- Asistencia
- Planilla
- Vacaciones
- Décimo Tercer Mes
- Prima de Antigüedad
- Liquidaciones
- Fondo de Cesantía
- CSS
- ISR
- Seguro Educativo
- Riesgos Profesionales
- Cumplimiento MITRADEL
- Cumplimiento DGI
- Cumplimiento CSS
- Indicadores de RRHH

Todo mediante **reglas configurables y auditables**.

---

## 2. PROPUESTA DE VALOR

EPayRoll se diferenciará de otros sistemas porque:

1. No tendrá reglas laborales quemadas en código.
2. Será configurable mediante tablas maestras.
3. Mantendrá histórico legal por vigencia.
4. Tendrá planificación obligatoria de vacaciones.
5. Gestionará pasivos laborales en tiempo real.
6. Estará preparado para auditorías.
7. Será multiempresa y multitenant.
8. Permitirá integración con ERP y bancos.
9. Estará construido específicamente para Panamá.

---

## 3. DOCUMENTOS MAESTROS

| Documento | Propósito |
|-----------|-----------|
| [EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md](./EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md) | Fuente oficial de reglas legales (9 dominios) |
| [EPAYROLL_DATA_MODEL.md](./EPAYROLL_DATA_MODEL.md) | Entidades, relaciones, catálogos, históricos |
| [EPAYROLL_TECH_ARCHITECTURE.md](./EPAYROLL_TECH_ARCHITECTURE.md) | Stack, APIs, motor de fórmulas, EN1, integraciones |
| [EPAYROLL_ROADMAP.md](./EPAYROLL_ROADMAP.md) | Fases, sprints, entregables, dependencias |

Este documento (`EPAYROLL_MASTER_PLAN.md`) es el **documento rector**; los cuatro anteriores son documentos hijos.

---

## 4. PILARES DEL PRODUCTO

### Pilar 1 — Gestión de Empleados

- Expediente digital
- Datos personales
- Dependientes
- Documentos
- Historial laboral
- Organigrama

### Pilar 2 — Gestión Contractual

- Contratos (tipos configurables)
- Adendas
- Cambios salariales
- Suspensiones
- Reingresos
- Terminaciones

### Pilar 3 — Asistencia y Tiempo

- Horarios
- Turnos
- Marcaciones
- Horas extras (diurnas, nocturnas, mixtas)
- Tardanzas
- Ausencias
- Incapacidades (fondo licencia + CSS)

### Pilar 4 — Motor de Planilla

- Salario base
- Extras y recargos (domingo, feriado)
- Deducciones legales y voluntarias
- ISR (proyección anual, YTD)
- CSS (empleado y empleador)
- Seguro Educativo
- Riesgos profesionales
- Validación salario mínimo

Basado en **reglas configurables** — ver [Compliance Blueprint](./EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md).

### Pilar 5 — Vacaciones Inteligentes *(diferenciador)*

- Acumulación (30 días / 11 meses — Art. 54 CT)
- Programación obligatoria (2 meses anticipación — Art. 57 CT)
- Alertas de acumulación excesiva
- Sustituciones y cobertura operativa
- Proyección financiera de pasivo
- Control de pasivos en tiempo real

> Ningún colaborador debe permanecer años acumulando vacaciones sin planificación.

### Pilar 6 — Prestaciones Laborales

- **Décimo tercer mes** (motor propio — Decreto 19/1973)
- **Prima de antigüedad** (Art. 224 CT)
- **Vacaciones** (pago y proporcional)
- **Liquidaciones** (vacaciones + décimo + prima + preaviso/indemnización según causa)
- **Fondo de cesantía** (Arts. 229 A–D CT)

### Pilar 7 — Cumplimiento Legal

- MITRADEL (contratos, registros)
- CSS / SIPE (planilla preelaborada)
- DGI (retenciones ISR, Formulario 03)
- Histórico y trazabilidad por vigencia

### Pilar 8 — Analítica y Gestión

- Rotación
- Ausentismo
- Horas extras
- Vacaciones acumuladas
- Pasivos laborales (vacaciones, décimo, prima, cesantía)
- Costos laborales y proyección

---

## 5. PRINCIPIO DE DISEÑO

### Configuración sobre código

Toda regla legal y de negocio debe vivir en **tablas maestras** con vigencia (`fecha_desde`, `fecha_hasta`).

El motor únicamente **interpreta** reglas: condiciones, fórmulas, prioridades, redondeo.

**Prohibido en código fuente:**

- Tasas legales (CSS, SE, ISR, riesgo profesional)
- Tramos ISR y montos fijos
- Topes de cotización CSS
- Recargos de horas extras, domingo y feriado
- Feriados nacionales
- Montos de salario mínimo por categoría

**Permitido en código:**

- Operadores y estructura del motor (prioridad, dependencias, redondeo)
- Lógica de anualización ISR (mecanismo, no los tramos)
- Flujo de corrida de planilla
- Validaciones estructurales (integridad referencial, estados)

---

## 6. MULTITENANT (EN1)

EPayRoll utilizará la arquitectura **EasyNodeOne (EN1)**.

Características:

- Multiempresa
- Multiorganización
- Catálogo central
- Configuración por tenant
- Aislamiento de datos

### Prerrequisitos EN1 (checklist)

Antes de Fase 2, EN1 debe proveer:

- [ ] Modelo de tenant / organización estable
- [ ] Autenticación y autorización (RBAC)
- [ ] Aislamiento de datos por tenant
- [ ] Catálogos compartidos vs. configurables por tenant
- [ ] APIs o eventos para integración con módulos EPayRoll

> **Riesgo:** Si EN1 no está listo, Fase 1.5 puede implementarse con tenant stub documentado en Tech Architecture.

---

## 7. CAPAS TRANSVERSALES

Aplican desde Fase 2 en adelante:

| Capa | Alcance |
|------|---------|
| **Auditoría** | Quién creó/modificó regla, concepto, tasa; vigencia; corrida de planilla inmutable |
| **Seguridad / RBAC** | Contador, RRHH, gerente, empleado — permisos por módulo |
| **Golden tests legales** | Casos validados por contador panameño; regresión automática |
| **Versionado** | Toda tabla maestra con historial; nunca borrar, desactivar con vigencia |

---

## 8. INTEGRACIONES OBJETIVO

### ERP

- Odoo *(prioridad Fase 7)*
- SAP
- QuickBooks
- Sistemas propietarios

### Bancos

- ACH
- Banco General
- Banistmo
- BAC
- Caja de Ahorros

### Gobierno

- CSS / SIPE (planilla preelaborada)
- DGI / e-Tax (Formulario 03)

---

## 9. DIFERENCIADORES COMPETITIVOS

### Nivel operativo

- Planilla Panamá completa (9 dominios legales)
- Cumplimiento legal con histórico
- Integraciones ERP y bancos

### Nivel gerencial

- Pasivos laborales en tiempo real
- Riesgo laboral (vacaciones acumuladas, horas extras)
- Proyección financiera

### Nivel estratégico

- Vacaciones inteligentes (planificación preventiva)
- Planeación de reemplazos
- Cumplimiento preventivo ante auditorías MITRADEL/CSS/DGI

---

## 10. ROADMAP GENERAL

| Fase | Nombre | Entregable principal |
|------|--------|----------------------|
| **0** | Marco Legal Panamá | [Compliance Blueprint](./EPAYROLL_PANAMA_COMPLIANCE_BLUEPRINT.md) |
| **1** | Modelo de Datos | [Data Model](./EPAYROLL_DATA_MODEL.md) |
| **1.5** | Core operativo | Empleados, contratos, catálogos mínimos, períodos |
| **2** | Motor de Reglas | Motor configurable + seed legal inicial |
| **3** | Asistencia y Tiempo | Turnos, marcaciones, cálculo de extras |
| **4** | Planilla | Nómina completa (ISR, CSS, SE, décimo, validación SM) |
| **5** | Vacaciones Inteligentes | Planificación obligatoria + pasivos |
| **6** | Exportación CSS / DGI | SIPE, Form 03, conciliación |
| **7** | Integraciones ERP y Bancos | Conectores Odoo, ACH |
| **8** | Analítica Gerencial | Dashboards ejecutivos |

Detalle de sprints: [EPAYROLL_ROADMAP.md](./EPAYROLL_ROADMAP.md).

### Nota MVP

Fase 4 puede iniciar con **entrada manual** de días trabajados y horas extras antes de Fase 3 completa (asistencia automatizada).

---

## 11. CRITERIO DE ÉXITO

EPayRoll será exitoso cuando una empresa pueda:

- [ ] Cumplir con la normativa laboral, CSS y DGI de Panamá
- [ ] Calcular planillas correctamente en corrida reproducible
- [ ] Reducir riesgos laborales (vacaciones, pasivos, horas extras)
- [ ] Controlar vacaciones con planificación obligatoria
- [ ] Visualizar pasivos laborales en tiempo real
- [ ] Prepararse para auditorías con trazabilidad completa
- [ ] Integrarse con ERP y bancos existentes
- [ ] **Actualizar reglas legales sin modificar código** (solo tablas maestras)
- [ ] Pasar **casos golden** validados por contador panameño
- [ ] Conciliar planilla interna vs. exportación SIPE/DGI en ambiente de prueba

---

## 12. FUENTES LEGALES OFICIALES

| Dominio | Referencia |
|---------|------------|
| Código de Trabajo | [MITRADEL](https://www.mitradel.gob.pa/trabajadores/codigo-detrabajo/) |
| CSS | Ley 51 de 2005 + reformas (Ley 462/2025) |
| Seguro Educativo | Ley 13 de 1987 |
| ISR | Código Fiscal Arts. 699–700 |
| Décimo | Decreto 19 de 1973 |
| Salario mínimo | Decretos ejecutivos vigentes (ej. Decreto 13/2025) |

**Validador requerido:** contador / abogado laboral panameño para seed legal y golden tests.

---

*Documento rector EPayRoll — Easy Technology Services*
