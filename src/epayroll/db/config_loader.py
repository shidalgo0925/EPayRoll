from __future__ import annotations

from datetime import date
from decimal import Decimal

from epayroll.engine.config import ConceptDef, EngineConfig, RuleDef, load_config_from_seed

from epayroll.engine.isr import IsrBracket, IsrConfig

from .connection import get_connection


def _vigencia_clause(as_of: date, alias: str = "") -> tuple[str, tuple]:
    prefix = f"{alias}." if alias else ""
    return (
        f"({prefix}vigencia_desde <= %s AND ({prefix}vigencia_hasta IS NULL OR {prefix}vigencia_hasta >= %s))",
        (as_of, as_of),
    )


def load_config_from_db(as_of: date | None = None, database_url: str | None = None) -> EngineConfig:
    as_of = as_of or date.today()

    with get_connection(database_url) as conn:
        with conn.cursor() as cur:
            concepts: dict[str, ConceptDef] = {}
            vig_sql, vig_params = _vigencia_clause(as_of)
            cur.execute(
                f"""
                SELECT codigo, descripcion, tipo, orden_visual
                FROM payroll_concepts
                WHERE activo = true AND {vig_sql}
                """,
                vig_params,
            )
            for row in cur.fetchall():
                concepts[row[0]] = ConceptDef(
                    codigo=row[0],
                    descripcion=row[1],
                    tipo=row[2],
                    orden_visual=row[3] or 0,
                )

            cur.execute(
                """
                SELECT pc.codigo, cr.condicion_aplicacion, cr.base_calculo, cr.unidad,
                       cr.aplica_contratos, cr.prioridad_calculo, cr.redondeo::text, cr.referencia_legal
                FROM calculation_rules cr
                JOIN payroll_concepts pc ON pc.id = cr.concept_id
                WHERE cr.activo = true
                  AND cr.vigencia_desde <= %s
                  AND (cr.vigencia_hasta IS NULL OR cr.vigencia_hasta >= %s)
                ORDER BY cr.prioridad_calculo, pc.codigo
                """,
                (as_of, as_of),
            )
            rules: list[RuleDef] = []
            for row in cur.fetchall():
                rules.append(
                    RuleDef(
                        codigo_concepto=row[0],
                        condicion_aplicacion=row[1],
                        base_calculo=row[2],
                        unidad=row[3],
                        aplica_contratos=list(row[4] or []),
                        prioridad_calculo=row[5],
                        redondeo=row[6],
                        referencia_legal=row[7],
                    )
                )

            cur.execute(
                """
                SELECT id, metodo, factor_anualizacion, deduccion_previa
                FROM isr_config
                WHERE vigencia_desde <= %s AND (vigencia_hasta IS NULL OR vigencia_hasta >= %s)
                ORDER BY vigencia_desde DESC LIMIT 1
                """,
                (as_of, as_of),
            )
            isr_row = cur.fetchone()
            if not isr_row:
                raise ValueError("No hay isr_config vigente en BD")
            config_id = isr_row[0]
            cur.execute(
                """
                SELECT rango_desde, rango_hasta, porcentaje, excedente_desde, impuesto_fijo_acumulado
                FROM isr_brackets WHERE config_id = %s ORDER BY orden
                """,
                (config_id,),
            )
            brackets = [
                IsrBracket(
                    rango_desde=Decimal(str(r[0])),
                    rango_hasta=Decimal(str(r[1])) if r[1] is not None else None,
                    porcentaje=Decimal(str(r[2])),
                    excedente_desde=Decimal(str(r[3])),
                    impuesto_fijo_acumulado=Decimal(str(r[4])),
                )
                for r in cur.fetchall()
            ]
            isr = IsrConfig(
                factor_anualizacion=isr_row[2],
                deduccion_previa=isr_row[3],
                brackets=brackets,
            )

            tasa_css_patronal = Decimal("0.1325")
            tasa_prima = Decimal("0.0192")
            cur.execute(
                """
                SELECT concepto, porcentaje_empleador
                FROM css_rates
                WHERE vigencia_desde <= %s AND (vigencia_hasta IS NULL OR vigencia_hasta >= %s)
                """,
                (as_of, as_of),
            )
            for concepto, pct in cur.fetchall():
                if concepto == "CUOTA_CSS_EMPLEADOR":
                    tasa_css_patronal = Decimal(str(pct))
                if concepto == "PRIMA_ANTIGUEDAD_PATRONAL":
                    tasa_prima = Decimal(str(pct))

    if not concepts or not rules:
        raise ValueError("Config legal incompleta en BD — ejecutar scripts/seed.py")

    return EngineConfig(
        as_of=as_of,
        concepts=concepts,
        rules=rules,
        isr=isr,
        tasa_css_patronal=tasa_css_patronal,
        tasa_prima_antiguedad_patronal=tasa_prima,
    )


def load_config(
    as_of: date | None = None,
    database_url: str | None = None,
    prefer_db: bool = True,
) -> EngineConfig:
    """Carga config desde BD; fallback a JSON seed si BD no disponible."""
    if prefer_db:
        try:
            return load_config_from_db(as_of=as_of, database_url=database_url)
        except Exception:
            pass
    return load_config_from_seed(as_of=as_of)
