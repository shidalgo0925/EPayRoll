"""Configuración legal por organización y vista planilla operador."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from epayroll.attendance.payroll_descuento import descuento_horas_decimal
from epayroll.db.connection import get_connection

ROOT = Path(__file__).resolve().parents[3]
PLANILLA_COLUMNS = ROOT / "docs" / "seed" / "planilla_modelo_columns.json"


def _load_planilla_meta() -> dict[str, Any]:
    with open(PLANILLA_COLUMNS, encoding="utf-8") as f:
        return json.load(f)


class LegalConfigRepository:
    def list_rates(self, organization_id: str, database_url: str | None = None) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, codigo, descripcion, porcentaje_empleado, porcentaje_empleador,
                           vigencia_desde, vigencia_hasta, activo
                    FROM organization_legal_rates
                    WHERE organization_id = %s::uuid AND activo = true
                    ORDER BY codigo, vigencia_desde DESC
                    """,
                    (organization_id,),
                )
                rows = cur.fetchall()
        return [self._rate_row(r) for r in rows]

    def upsert_rate(
        self,
        organization_id: str,
        *,
        codigo: str,
        descripcion: str | None = None,
        porcentaje_empleado: Decimal | None = None,
        porcentaje_empleador: Decimal | None = None,
        vigencia_desde: date | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        vd = vigencia_desde or date.today()
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO organization_legal_rates (
                        organization_id, codigo, descripcion,
                        porcentaje_empleado, porcentaje_empleador, vigencia_desde
                    ) VALUES (%s::uuid, %s, %s, %s, %s, %s)
                    ON CONFLICT (organization_id, codigo, vigencia_desde) DO UPDATE SET
                        descripcion = COALESCE(EXCLUDED.descripcion, organization_legal_rates.descripcion),
                        porcentaje_empleado = COALESCE(EXCLUDED.porcentaje_empleado, organization_legal_rates.porcentaje_empleado),
                        porcentaje_empleador = COALESCE(EXCLUDED.porcentaje_empleador, organization_legal_rates.porcentaje_empleador),
                        activo = true,
                        updated_at = now()
                    RETURNING id, codigo, descripcion, porcentaje_empleado, porcentaje_empleador,
                              vigencia_desde, vigencia_hasta, activo
                    """,
                    (
                        organization_id,
                        codigo,
                        descripcion,
                        porcentaje_empleado,
                        porcentaje_empleador,
                        vd,
                    ),
                )
                row = cur.fetchone()
        return self._rate_row(row)

    def list_account_codes(
        self, organization_id: str, database_url: str | None = None
    ) -> list[dict[str, Any]]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, concepto_codigo, cuenta_codigo, etiqueta, activo
                    FROM organization_account_codes
                    WHERE organization_id = %s::uuid AND activo = true
                    ORDER BY concepto_codigo
                    """,
                    (organization_id,),
                )
                rows = cur.fetchall()
        return [self._account_row(r) for r in rows]

    def upsert_account_code(
        self,
        organization_id: str,
        *,
        concepto_codigo: str,
        cuenta_codigo: str,
        etiqueta: str | None = None,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO organization_account_codes (
                        organization_id, concepto_codigo, cuenta_codigo, etiqueta
                    ) VALUES (%s::uuid, %s, %s, %s)
                    ON CONFLICT (organization_id, concepto_codigo) DO UPDATE SET
                        cuenta_codigo = EXCLUDED.cuenta_codigo,
                        etiqueta = COALESCE(EXCLUDED.etiqueta, organization_account_codes.etiqueta),
                        activo = true,
                        updated_at = now()
                    RETURNING id, concepto_codigo, cuenta_codigo, etiqueta, activo
                    """,
                    (organization_id, concepto_codigo, cuenta_codigo, etiqueta),
                )
                row = cur.fetchone()
        return self._account_row(row)

    def resolve_rates_for_payroll(
        self, organization_id: str, as_of: date | None = None, database_url: str | None = None
    ) -> dict[str, Decimal]:
        """Defaults globales + override organization_legal_rates por compañía."""
        _ = as_of
        rates: dict[str, Decimal] = {
            "tasa_css_empleado": Decimal("0.0975"),
            "tasa_css_patronal": Decimal("0.1325"),
            "tasa_se_empleado": Decimal("0.0125"),
            "tasa_se_patronal": Decimal("0.0150"),
            "tasa_riesgo_empresa": Decimal("0.0098"),
        }
        for row in self.list_rates(organization_id, database_url=database_url):
            codigo = row["codigo"]
            if row.get("porcentaje_empleado") is not None:
                pct = Decimal(str(row["porcentaje_empleado"]))
                if codigo == "CSS_EMPLEADO":
                    rates["tasa_css_empleado"] = pct
                elif codigo == "SE_EMPLEADO":
                    rates["tasa_se_empleado"] = pct
            if row.get("porcentaje_empleador") is not None:
                pct = Decimal(str(row["porcentaje_empleador"]))
                if codigo == "CSS_EMPLEADOR":
                    rates["tasa_css_patronal"] = pct
                elif codigo == "SE_EMPLEADOR":
                    rates["tasa_se_patronal"] = pct
                elif codigo == "RIESGO_PROFESIONAL":
                    rates["tasa_riesgo_empresa"] = pct
        return rates

    def seed_org_defaults(self, organization_id: str, database_url: str | None = None) -> None:
        meta = _load_planilla_meta()
        for item in meta.get("tasas_default_org", []):
            self.upsert_rate(
                organization_id,
                codigo=item["codigo"],
                descripcion=item.get("descripcion"),
                porcentaje_empleado=Decimal(str(item["porcentaje_empleado"]))
                if item.get("porcentaje_empleado") is not None
                else None,
                porcentaje_empleador=Decimal(str(item["porcentaje_empleador"]))
                if item.get("porcentaje_empleador") is not None
                else None,
                database_url=database_url,
            )
        for item in meta.get("cuentas_default", []):
            self.upsert_account_code(
                organization_id,
                concepto_codigo=item["concepto_codigo"],
                cuenta_codigo=item["cuenta_codigo"],
                etiqueta=item.get("etiqueta"),
                database_url=database_url,
            )

    @staticmethod
    def _rate_row(row) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "codigo": row[1],
            "descripcion": row[2],
            "porcentaje_empleado": str(row[3]) if row[3] is not None else None,
            "porcentaje_empleador": str(row[4]) if row[4] is not None else None,
            "vigencia_desde": row[5].isoformat(),
            "vigencia_hasta": row[6].isoformat() if row[6] else None,
            "activo": row[7],
        }

    @staticmethod
    def _account_row(row) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "concepto_codigo": row[1],
            "cuenta_codigo": row[2],
            "etiqueta": row[3],
            "activo": row[4],
        }


class PlanillaViewRepository:
    def get_run_planilla(
        self, run_id: str, database_url: str | None = None
    ) -> dict[str, Any]:
        meta = _load_planilla_meta()
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT pp.organization_id, pp.fecha_inicio, pp.fecha_fin, pp.fecha_pago,
                           pp.tipo, o.razon_social
                    FROM payroll_runs pr
                    JOIN payroll_periods pp ON pp.id = pr.payroll_period_id
                    JOIN organizations o ON o.id = pp.organization_id
                    WHERE pr.id = %s::uuid
                    """,
                    (run_id,),
                )
                header = cur.fetchone()
                if not header:
                    raise ValueError("Corrida no encontrada")

                org_id = str(header[0])
                period_tipo = header[4]
                es_quincena = period_tipo == "QUINCENAL"
                dias_pago_nominal = Decimal("15") if es_quincena else Decimal("30")
                cur.execute(
                    """
                    SELECT pes.employee_id, e.ficha, e.nombres, e.apellidos, e.telefono, e.cedula,
                           pes.bruto, pes.total_deducciones, pes.neto, pes.aportes_patronales,
                           c.salario_base, c.forma_pago::text
                    FROM payroll_employee_summary pes
                    JOIN employees e ON e.id = pes.employee_id
                    LEFT JOIN LATERAL (
                        SELECT salario_base, forma_pago FROM contracts
                        WHERE employee_id = pes.employee_id AND estado = 'ACTIVO'
                        ORDER BY fecha_inicio DESC LIMIT 1
                    ) c ON true
                    WHERE pes.payroll_run_id = %s::uuid
                    ORDER BY COALESCE(e.ficha, ''), e.apellidos, e.nombres
                    """,
                    (run_id,),
                )
                emp_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT pl.employee_id, pc.codigo, pl.monto
                    FROM payroll_lines pl
                    JOIN payroll_concepts pc ON pc.id = pl.concept_id
                    WHERE pl.payroll_run_id = %s::uuid
                    """,
                    (run_id,),
                )
                line_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT employee_id, dias_trabajados, dias_descuento, monto_desc_dias,
                           dev_isr, prestamo_empleado, desc_prestamo, descuento_banco,
                           saldo_prestamo, notas, descuento_minutos, monto_desc_tiempo
                    FROM payroll_run_adjustments
                    WHERE payroll_run_id = %s::uuid
                    """,
                    (run_id,),
                )
                adj_rows = {str(r[0]): r for r in cur.fetchall()}

        from epayroll.db.attendance_facts_repository import AttendanceFactsRepository

        att_repo = AttendanceFactsRepository()
        fecha_ini = header[1]
        fecha_fin = header[2]

        concepts: dict[str, dict[str, Decimal]] = {}
        for emp_id, codigo, monto in line_rows:
            eid = str(emp_id)
            concepts.setdefault(eid, {})[codigo] = Decimal(str(monto))

        rows: list[dict[str, Any]] = []
        tot_keys = [
            "salario_mensual", "salario_quincenal", "dias_pago", "descuento_minutos", "descuento_horas",
            "monto_desc_tiempo", "monto_desc_dias", "dev_isr",
            "salario_cotizable", "css_empleado", "se_empleado", "isr", "cpp_prestaciones",
            "prestamo_empleado", "desc_prestamo", "descuento_banco", "total_descuentos",
            "cancelacion", "css_patronal", "se_patronal", "riesgo_profesional",
            "gastos_empresa", "total_cpp_prest",
        ]
        totales = {k: Decimal("0") for k in tot_keys}

        for idx, row in enumerate(emp_rows, start=1):
            eid = str(row[0])
            sal_mensual = Decimal(str(row[10] or row[6]))
            es_quincenal = (row[11] or "QUINCENAL") == "QUINCENAL"
            sal_quincenal = sal_mensual / Decimal("2") if es_quincenal else sal_mensual
            lines = concepts.get(eid, {})
            adj = adj_rows.get(eid)
            dias_trab = Decimal(str(adj[1])) if adj and adj[1] is not None else dias_pago_nominal
            dias_desc = Decimal(str(adj[2])) if adj else Decimal("0")
            monto_desc_dias = Decimal(str(adj[3])) if adj else Decimal("0")
            dev_isr = Decimal(str(adj[4])) if adj else Decimal("0")
            prestamo = Decimal(str(adj[5])) if adj else Decimal("0")
            desc_prest = Decimal(str(adj[6])) if adj else Decimal("0")
            desc_banco = Decimal(str(adj[7])) if adj else Decimal("0")
            saldo_prest = Decimal(str(adj[8])) if adj else Decimal("0")
            desc_min = int(adj[10]) if adj and adj[10] is not None else 0
            monto_desc_tiempo = Decimal(str(adj[11])) if adj and adj[11] is not None else Decimal("0")

            if desc_min == 0 and monto_desc_tiempo == 0:
                att_sum = att_repo.summarize_employee_for_payroll(
                    org_id, eid, fecha_ini, fecha_fin, es_quincena=es_quincena
                )
                desc_min = int(att_sum.get("descuento_minutos") or 0)
                if desc_min > 0:
                    from epayroll.attendance.payroll_descuento import monto_descuento_tiempo

                    monto_desc_tiempo = monto_descuento_tiempo(sal_mensual, desc_min)

            desc_horas = descuento_horas_decimal(desc_min)

            sal_cot = lines.get("SALARIO_BASE", Decimal(str(row[6])))
            sal_diario = sal_mensual / Decimal("30")
            if monto_desc_dias == 0 and dias_desc > 0:
                monto_desc_dias = (sal_diario * dias_desc).quantize(Decimal("0.01"))
            descuento_ya_en_bruto = dias_desc > 0 and dias_trab < dias_pago_nominal
            css_emp = lines.get("CSS_EMPLEADO", Decimal("0"))
            se_emp = lines.get("SE_EMPLEADO", Decimal("0"))
            isr = lines.get("ISR", Decimal("0"))
            cpp = css_emp + se_emp + isr
            css_pat = lines.get("CSS_EMPLEADOR", Decimal("0"))
            se_pat = lines.get("SE_EMPLEADOR", Decimal("0"))
            riesgo = lines.get("RIESGO_PROFESIONAL", Decimal("0"))
            prima = lines.get("PRIMA_ANTIGUEDAD_PATRONAL", Decimal("0"))
            # Gastos empresa = aportes patronales visibles en planilla (sin prima antigüedad).
            gastos = css_pat + se_pat + riesgo
            monto_desc_en_total = Decimal("0") if descuento_ya_en_bruto else monto_desc_dias
            total_desc = cpp + desc_prest + desc_banco + monto_desc_en_total + monto_desc_tiempo - dev_isr
            cancelacion = sal_cot - total_desc
            total_cpp = gastos + prima + cpp

            dias_pago = dias_pago_nominal
            item = {
                "employee_id": eid,
                "ficha": row[1] or str(idx),
                "nombre_completo": f"{row[2]} {row[3]}".strip(),
                "telefono": row[4] or "",
                "cedula": row[5],
                "salario_mensual": str(sal_mensual),
                "salario_quincenal": str(sal_quincenal),
                "dias_pago": str(dias_pago),
                "dias_trabajados": str(dias_trab),
                "dias_descuento": str(dias_desc),
                "descuento_minutos": str(desc_min),
                "descuento_horas": str(desc_horas),
                "monto_desc_tiempo": str(monto_desc_tiempo),
                "monto_desc_dias": str(monto_desc_dias),
                "descuento_ya_en_salario": descuento_ya_en_bruto,
                "dev_isr": str(dev_isr),
                "salario_cotizable": str(sal_cot),
                "css_empleado": str(css_emp),
                "se_empleado": str(se_emp),
                "isr": str(isr),
                "cpp_prestaciones": str(cpp),
                "prestamo_empleado": str(prestamo),
                "desc_prestamo": str(desc_prest),
                "descuento_banco": str(desc_banco),
                "saldo_prestamo": str(saldo_prest),
                "total_descuentos": str(total_desc),
                "cancelacion": str(cancelacion),
                "css_patronal": str(css_pat),
                "se_patronal": str(se_pat),
                "riesgo_profesional": str(riesgo),
                "prima_antiguedad_patronal": str(prima),
                "gastos_empresa": str(gastos),
                "total_cpp_prest": str(total_cpp),
                "notas": adj[9] if adj else None,
                "lines": [
                    {"concepto": k, "monto": str(v)} for k, v in sorted(lines.items())
                ],
            }
            rows.append(item)
            for k in tot_keys:
                if k in item:
                    totales[k] += Decimal(item[k])

        return {
            "run_id": run_id,
            "organization_id": org_id,
            "razon_social": header[5],
            "periodo": {
                "fecha_inicio": header[1].isoformat(),
                "fecha_fin": header[2].isoformat(),
                "fecha_pago": header[3].isoformat(),
                "tipo": header[4],
            },
            "columnas": meta["columnas"],
            "rows": rows,
            "totales": {k: str(v) for k, v in totales.items()},
        }

    def upsert_adjustment(
        self,
        run_id: str,
        employee_id: str,
        data: dict[str, Any],
        database_url: str | None = None,
    ) -> dict[str, Any]:
        with get_connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO payroll_run_adjustments (
                        payroll_run_id, employee_id, dias_trabajados, dias_descuento,
                        monto_desc_dias, dev_isr, prestamo_empleado, desc_prestamo,
                        descuento_banco, saldo_prestamo, notas
                    ) VALUES (
                        %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (payroll_run_id, employee_id) DO UPDATE SET
                        dias_trabajados = EXCLUDED.dias_trabajados,
                        dias_descuento = EXCLUDED.dias_descuento,
                        monto_desc_dias = EXCLUDED.monto_desc_dias,
                        dev_isr = EXCLUDED.dev_isr,
                        prestamo_empleado = EXCLUDED.prestamo_empleado,
                        desc_prestamo = EXCLUDED.desc_prestamo,
                        descuento_banco = EXCLUDED.descuento_banco,
                        saldo_prestamo = EXCLUDED.saldo_prestamo,
                        notas = EXCLUDED.notas,
                        updated_at = now()
                    RETURNING employee_id
                    """,
                    (
                        run_id,
                        employee_id,
                        data.get("dias_trabajados"),
                        data.get("dias_descuento", 0),
                        data.get("monto_desc_dias", 0),
                        data.get("dev_isr", 0),
                        data.get("prestamo_empleado", 0),
                        data.get("desc_prestamo", 0),
                        data.get("descuento_banco", 0),
                        data.get("saldo_prestamo", 0),
                        data.get("notas"),
                    ),
                )
        return self.get_run_planilla(run_id, database_url=database_url)
