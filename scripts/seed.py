#!/usr/bin/env python3
"""
Carga seed legal desde docs/seed/*.json hacia PostgreSQL.
Uso: python scripts/seed.py [--database-url postgresql://...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Instalar dependencias: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / "docs" / "seed"


def load_json(name: str) -> dict:
    path = SEED_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def seed_contract_types(cur) -> None:
    data = load_json("contract_types.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    for item in data["items"]:
        cur.execute(
            """
            INSERT INTO contract_types (
                codigo, descripcion, genera_prima_antiguedad, genera_vacaciones,
                genera_decimo_tercer, proporcional_prestaciones, genera_fondo_cesantia,
                activo, vigencia_desde, vigencia_hasta
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,true,%s,%s)
            ON CONFLICT (codigo, vigencia_desde) DO UPDATE SET
                descripcion = EXCLUDED.descripcion,
                genera_prima_antiguedad = EXCLUDED.genera_prima_antiguedad,
                genera_vacaciones = EXCLUDED.genera_vacaciones,
                genera_decimo_tercer = EXCLUDED.genera_decimo_tercer,
                proporcional_prestaciones = EXCLUDED.proporcional_prestaciones,
                genera_fondo_cesantia = EXCLUDED.genera_fondo_cesantia
            """,
            (
                item["codigo"],
                item["descripcion"],
                item["genera_prima_antiguedad"],
                item["genera_vacaciones"],
                item["genera_decimo_tercer"],
                item["proporcional_prestaciones"],
                item.get("genera_fondo_cesantia", False),
                vd,
                vh,
            ),
        )


def seed_payroll_concepts(cur) -> dict[str, str]:
    data = load_json("payroll_concepts.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    concept_ids: dict[str, str] = {}
    for item in data["items"]:
        cur.execute(
            """
            INSERT INTO payroll_concepts (
                codigo, descripcion, tipo, naturaleza, imprime_recibo,
                acumulable_aguinaldo, acumulable_vacaciones,
                cotizable_css, cotizable_se, gravable_isr,
                orden_visual, activo, vigencia_desde, vigencia_hasta
            ) VALUES (%s,%s,%s::payroll_concept_type,%s::concept_nature,%s,%s,%s,%s,%s,%s,%s,true,%s,%s)
            ON CONFLICT (codigo, vigencia_desde) DO UPDATE SET
                descripcion = EXCLUDED.descripcion,
                tipo = EXCLUDED.tipo,
                orden_visual = EXCLUDED.orden_visual
            RETURNING id, codigo
            """,
            (
                item["codigo"],
                item["descripcion"],
                item["tipo"],
                item["naturaleza"],
                item.get("imprime_recibo", True),
                item.get("acumulable_aguinaldo", False),
                item.get("acumulable_vacaciones", False),
                item.get("cotizable_css", False),
                item.get("cotizable_se", False),
                item.get("gravable_isr", False),
                item.get("orden_visual", 0),
                vd,
                vh,
            ),
        )
        row = cur.fetchone()
        concept_ids[row[1]] = str(row[0])
    return concept_ids


def seed_calculation_rules(cur, concept_ids: dict[str, str]) -> None:
    data = load_json("calculation_rules.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    for item in data["items"]:
        concept_id = concept_ids.get(item["codigo_concepto"])
        if not concept_id:
            print(f"  WARN: concepto no encontrado {item['codigo_concepto']}")
            continue
        cur.execute(
            """
            INSERT INTO calculation_rules (
                concept_id, condicion_aplicacion, base_calculo, unidad,
                aplica_contratos, prioridad_calculo, redondeo,
                referencia_legal, nota, activo, vigencia_desde, vigencia_hasta
            )
            SELECT %s::uuid, %s, %s, %s::calculation_unit, %s, %s, %s::rounding_mode, %s, %s, true, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM calculation_rules cr
                WHERE cr.concept_id = %s::uuid
                  AND cr.vigencia_desde = %s
                  AND cr.base_calculo = %s
            )
            """,
            (
                concept_id,
                item["condicion_aplicacion"],
                item["base_calculo"],
                item["unidad"],
                item.get("aplica_contratos", []),
                item["prioridad_calculo"],
                item.get("redondeo", "CENTESIMO"),
                item.get("referencia_legal"),
                item.get("nota"),
                vd,
                vh,
                concept_id,
                vd,
                item["base_calculo"],
            ),
        )


def seed_shift_types(cur) -> None:
    data = load_json("shift_types.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    for item in data["items"]:
        cur.execute(
            """
            INSERT INTO shift_types (
                codigo, descripcion, hora_inicio, hora_fin, tipo_jornada,
                horas_max_dia, horas_max_semana, recargo_domingo, recargo_feriado,
                maximo_extras_diarias, maximo_extras_semanales,
                activo, vigencia_desde, vigencia_hasta
            ) VALUES (%s,%s,%s,%s,%s::jornada_type,%s,%s,%s,%s,%s,%s,true,%s,%s)
            ON CONFLICT (codigo, vigencia_desde) DO UPDATE SET descripcion = EXCLUDED.descripcion
            """,
            (
                item["codigo"],
                item["descripcion"],
                item["hora_inicio"],
                item["hora_fin"],
                item["tipo_jornada"],
                item["horas_max_dia"],
                item["horas_max_semana"],
                item["recargo_domingo"],
                item["recargo_feriado"],
                item["maximo_extras_diarias"],
                item["maximo_extras_semanales"],
                vd,
                vh,
            ),
        )


def seed_holidays(cur) -> None:
    data = load_json("holidays_2026.json")
    for item in data["items"]:
        cur.execute(
            """
            INSERT INTO holidays (fecha, descripcion, tipo, recargo_trabajar, es_recuperable, anio)
            VALUES (%s,%s,%s::holiday_type,%s,%s,%s)
            ON CONFLICT (fecha, descripcion) DO NOTHING
            """,
            (
                item["fecha"],
                item["descripcion"],
                item.get("tipo", "FERIADO_NACIONAL"),
                item.get("recargo_trabajar", 1.50),
                item.get("es_recuperable", False),
                data.get("anio", 2026),
            ),
        )


def seed_css_rates(cur) -> None:
    data = load_json("css_rates.json")
    for item in data["items"]:
        vd = parse_date(item.get("vigencia_desde", data["vigencia_desde"]))
        vh = parse_date(item.get("vigencia_hasta", data.get("vigencia_hasta")))
        cur.execute(
            """
            INSERT INTO css_rates (
                concepto, porcentaje_empleado, porcentaje_empleador,
                sobre_base, tope_mensual, referencia_legal, nota,
                vigencia_desde, vigencia_hasta
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (concepto, vigencia_desde) DO UPDATE SET
                porcentaje_empleado = EXCLUDED.porcentaje_empleado,
                porcentaje_empleador = EXCLUDED.porcentaje_empleador
            """,
            (
                item["concepto"],
                item.get("porcentaje_empleado", 0),
                item.get("porcentaje_empleador", 0),
                item.get("sobre_base", "bruto_cotizable"),
                data.get("tope_mensual"),
                item.get("referencia_legal", data.get("nota")),
                item.get("nota"),
                vd,
                vh,
            ),
        )


def seed_se_rates(cur) -> None:
    data = load_json("se_rates.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    mapping = {"SE_EMPLEADO": "EMPLEADO", "SE_EMPLEADOR": "EMPLEADOR"}
    for item in data["items"]:
        parte = mapping.get(item["concepto"], "EMPLEADO")
        cur.execute(
            """
            INSERT INTO se_rates (concepto, porcentaje, parte, sobre_base, referencia_legal, vigencia_desde, vigencia_hasta)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                item["concepto"],
                item["porcentaje"],
                parte,
                item.get("sobre_base", "bruto_cotizable_se"),
                data.get("referencia_legal"),
                vd,
                vh,
            ),
        )


def seed_isr(cur) -> None:
    data = load_json("isr_brackets.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    cur.execute(
        """
        INSERT INTO isr_config (metodo, factor_anualizacion, deduccion_previa, referencia_legal, vigencia_desde, vigencia_hasta)
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            data.get("metodo", "ANUAL_PROYECTADO"),
            data.get("factor_anualizacion", 13),
            data.get("deduccion_previa", "css_empleado"),
            data.get("referencia_legal"),
            vd,
            vh,
        ),
    )
    config_id = cur.fetchone()[0]
    for i, item in enumerate(data["items"], start=1):
        cur.execute(
            """
            INSERT INTO isr_brackets (
                config_id, rango_desde, rango_hasta, porcentaje,
                excedente_desde, impuesto_fijo_acumulado, orden
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                config_id,
                item["rango_desde"],
                item.get("rango_hasta"),
                item["porcentaje"],
                item.get("excedente_desde", 0),
                item.get("impuesto_fijo_acumulado", 0),
                i,
            ),
        )


def seed_decimo(cur) -> None:
    data = load_json("decimo_config.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    cur.execute(
        """
        INSERT INTO decimo_config (
            fechas_pago, meses_acumulacion, formula,
            cotiza_css, tasa_css_decimo, cotiza_se, gravable_isr,
            proporcional_liquidacion, referencia_legal, vigencia_desde, vigencia_hasta
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            json.dumps(data["fechas_pago"]),
            json.dumps(data["meses_acumulacion_por_partida"]),
            data.get("formula"),
            data.get("cotiza_css", True),
            data.get("tasa_css_decimo", 0.0725),
            data.get("cotiza_se", False),
            data.get("gravable_isr", False),
            data.get("proporcional_en_liquidacion", True),
            data.get("referencia_legal"),
            vd,
            vh,
        ),
    )


def seed_professional_risk(cur) -> None:
    data = load_json("professional_risk_rates.json")
    vd = parse_date(data["vigencia_desde"])
    vh = parse_date(data.get("vigencia_hasta"))
    for item in data["items"]:
        cur.execute(
            """
            INSERT INTO professional_risk_rates (codigo_actividad, descripcion, porcentaje_riesgo, vigencia_desde, vigencia_hasta)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (codigo_actividad, vigencia_desde) DO UPDATE SET
                porcentaje_riesgo = EXCLUDED.porcentaje_riesgo
            """,
            (
                item["codigo_actividad"],
                item["descripcion"],
                item["porcentaje_riesgo"],
                vd,
                vh,
            ),
        )


def seed_demo_tenant(cur) -> None:
    """Tenant y organización principal — Easy Technology Services."""
    cur.execute(
        """
        INSERT INTO tenants (id, nombre, slug)
        VALUES ('00000000-0000-0000-0000-000000000001', 'Easy Technology Services', 'demo-easytech')
        ON CONFLICT (slug) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            updated_at = now()
        """
    )
    cur.execute(
        """
        INSERT INTO sm_activities (codigo, descripcion)
        VALUES ('ADMIN_OFICINA', 'Actividades administrativas')
        ON CONFLICT (codigo) DO NOTHING
        """
    )
    cur.execute(
        """
        INSERT INTO sm_regions (codigo, descripcion)
        VALUES ('PANAMA_CIUDAD', 'Ciudad de Panamá')
        ON CONFLICT (codigo) DO NOTHING
        """
    )
    cur.execute(
        """
        INSERT INTO organizations (id, tenant_id, razon_social, ruc, codigo_css_actividad)
        SELECT
            '00000000-0000-0000-0000-000000000010',
            t.id,
            'Easy Technology Services S.A.',
            '0000000000000',
            'ADMIN_OFICINA'
        FROM tenants t WHERE t.slug = 'demo-easytech'
        ON CONFLICT (id) DO UPDATE SET
            razon_social = EXCLUDED.razon_social,
            updated_at = now()
        """
    )
    cur.execute(
        """
        INSERT INTO organization_settings (organization_id, periodo_pago)
        SELECT o.id, 'QUINCENAL'::payment_frequency
        FROM organizations o
        JOIN tenants t ON t.id = o.tenant_id
        WHERE t.slug = 'demo-easytech'
        ON CONFLICT (organization_id) DO NOTHING
        """
    )
    cur.execute(
        """
        INSERT INTO organization_risk_classification (organization_id, codigo_actividad, porcentaje_riesgo, vigencia_desde)
        SELECT o.id, 'ADMIN_OFICINA', 0.0105, CURRENT_DATE
        FROM organizations o
        JOIN tenants t ON t.id = o.tenant_id
        WHERE t.slug = 'demo-easytech'
        AND NOT EXISTS (
            SELECT 1 FROM organization_risk_classification orc
            WHERE orc.organization_id = o.id AND orc.vigencia_hasta IS NULL
        )
        """
        )


def seed_demo_users(cur) -> None:
    """Usuarios de aplicación con acceso por empresa."""
    sys.path.insert(0, str(ROOT / "src"))
    from epayroll.auth.passwords import hash_password

    demo_password = os.environ.get("EPAYROLL_DEMO_PASSWORD", "EasyTech2026!")
    tenant_id = "00000000-0000-0000-0000-000000000001"
    org_ets = "00000000-0000-0000-0000-000000000010"

    users = [
        (
            "shidalgo@eastech.services",
            "Seul Hidalgo",
            [org_ets],
            ["payroll_admin", "rrhh", "contador", "tenant_admin"],
            os.environ.get("EPAYROLL_SHIDALGO_PASSWORD", demo_password),
        ),
        (
            "admin@easytech.services",
            "Administrador Demo",
            [org_ets],
            ["payroll_admin", "contador", "tenant_admin"],
            demo_password,
        ),
    ]
    for email, nombres, org_ids, roles, password in users:
        pwd_hash = hash_password(password)
        cur.execute(
            """
            INSERT INTO app_users (tenant_id, email, password_hash, nombres)
            VALUES (%s::uuid, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                nombres = EXCLUDED.nombres,
                activo = true,
                updated_at = now()
            RETURNING id
            """,
            (tenant_id, email, pwd_hash, nombres),
        )
        user_id = cur.fetchone()[0]
        for org_id in org_ids:
            cur.execute(
                """
                INSERT INTO user_organization_memberships (user_id, organization_id, roles)
                VALUES (%s::uuid, %s::uuid, %s::text[])
                ON CONFLICT (user_id, organization_id) DO UPDATE SET
                    roles = EXCLUDED.roles,
                    activo = true,
                    updated_at = now()
                """,
                (user_id, org_id, roles),
            )
    cur.execute(
        """
        UPDATE app_users SET activo = false, updated_at = now()
        WHERE email = 'shidalgo@easytech.services'
        """
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed legal EPayRoll")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://epayroll:epayroll@localhost:5432/epayroll",
        ),
    )
    parser.add_argument("--skip-demo", action="store_true")
    args = parser.parse_args()

    print(f"Conectando a {args.database_url.split('@')[-1]}...")
    conn = psycopg2.connect(args.database_url)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("→ contract_types")
            seed_contract_types(cur)
            print("→ payroll_concepts")
            concept_ids = seed_payroll_concepts(cur)
            print("→ calculation_rules")
            seed_calculation_rules(cur, concept_ids)
            print("→ shift_types")
            seed_shift_types(cur)
            print("→ holidays")
            seed_holidays(cur)
            print("→ css_rates")
            seed_css_rates(cur)
            print("→ se_rates")
            seed_se_rates(cur)
            print("→ isr")
            seed_isr(cur)
            print("→ decimo_config")
            seed_decimo(cur)
            print("→ professional_risk_rates")
            seed_professional_risk(cur)
            if not args.skip_demo:
                print("→ demo tenant")
                seed_demo_tenant(cur)
                print("→ demo users")
                seed_demo_users(cur)
        conn.commit()
        print("Seed completado.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
