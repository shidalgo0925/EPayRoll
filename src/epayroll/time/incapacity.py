from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "docs" / "seed" / "incapacity_config.json"


def _q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@lru_cache
def load_incapacity_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@dataclass(frozen=True)
class IncapacityPaymentSplit:
    dias_total: int
    dias_empleador: int
    dias_css: int
    monto_empleador: Decimal
    monto_css_subsidio: Decimal
    salario_diario: Decimal
    fondo_licencia_usado_horas: Decimal


@dataclass(frozen=True)
class LicenseFundBalance:
    jornadas_acumuladas: Decimal
    horas_acumuladas: Decimal
    horas_usadas: Decimal
    horas_disponibles: Decimal
    tope_anual: Decimal


def count_calendar_days(fecha_inicio: date, fecha_fin: date) -> int:
    if fecha_fin < fecha_inicio:
        return 0
    return (fecha_fin - fecha_inicio).days + 1


def iter_dates(fecha_inicio: date, fecha_fin: date):
    d = fecha_inicio
    while d <= fecha_fin:
        yield d
        d += timedelta(days=1)


def accrue_license_fund_hours(
    jornadas_trabajadas: Decimal,
    config: dict | None = None,
) -> Decimal:
    """Art. 200 — 12 horas por cada 26 jornadas, tope 144h/año (sin acumulación multi-año aquí)."""
    cfg = config or load_incapacity_config()
    fl = cfg["fondo_licencia"]
    horas_por_bloque = Decimal(str(fl["horas_por_26_jornadas"]))
    max_anual = Decimal(str(fl["max_horas_anuales"]))
    bloques = jornadas_trabajadas // Decimal("26")
    return min(bloques * horas_por_bloque, max_anual)


def license_fund_balance(
    jornadas_trabajadas: Decimal,
    horas_usadas: Decimal,
    config: dict | None = None,
) -> LicenseFundBalance:
    cfg = config or load_incapacity_config()
    fl = cfg["fondo_licencia"]
    max_anual = Decimal(str(fl["max_horas_anuales"]))
    max_acum = max_anual * Decimal(str(fl["max_acumulacion_anios"]))
    horas_acum = accrue_license_fund_hours(jornadas_trabajadas, cfg)
    horas_acum = min(horas_acum, max_acum)
    disponible = max(Decimal("0"), horas_acum - horas_usadas)
    return LicenseFundBalance(
        jornadas_acumuladas=jornadas_trabajadas,
        horas_acumuladas=horas_acum,
        horas_usadas=horas_usadas,
        horas_disponibles=disponible,
        tope_anual=max_anual,
    )


def calculate_incapacity_payment(
    dias_incapacidad: int,
    salario_diario: Decimal,
    fondo_agotado: bool = False,
    config: dict | None = None,
) -> IncapacityPaymentSplit:
    """
    GT-10 — días 1-2 empleador (fondo licencia), días 3+ subsidio CSS.
    Si fondo agotado, días 1-2 siguen siendo cargo empleador (100% salario).
    """
    cfg = config or load_incapacity_config()
    pago = cfg["pago_incapacidad"]
    dias_emp = int(pago["dias_empleador_fondo"])
    pct_emp = Decimal(str(pago["pct_empleador"]))
    pct_css = Decimal(str(pago["pct_css_default"]))
    fl = cfg["fondo_licencia"]
    horas_jornada = Decimal(str(fl["horas_jornada_referencia"]))

    dias_emp_actual = min(dias_incapacidad, dias_emp)
    dias_css = max(0, dias_incapacidad - dias_emp_actual)

    monto_emp = _q2(salario_diario * pct_emp * Decimal(dias_emp_actual))
    monto_css = _q2(salario_diario * pct_css * Decimal(dias_css))
    fondo_horas = horas_jornada * Decimal(dias_emp_actual)
    if fondo_agotado:
        fondo_horas = Decimal("0")

    return IncapacityPaymentSplit(
        dias_total=dias_incapacidad,
        dias_empleador=dias_emp_actual,
        dias_css=dias_css,
        monto_empleador=monto_emp,
        monto_css_subsidio=monto_css,
        salario_diario=salario_diario,
        fondo_licencia_usado_horas=fondo_horas,
    )


def dias_incapacidad_en_periodo(
    fecha_inicio: date,
    fecha_fin: date,
    incapacities: list[tuple[date, date]],
) -> int:
    """Cuenta días calendario de incapacidad dentro del período (sin doble conteo)."""
    dias: set[date] = set()
    for inc_ini, inc_fin in incapacities:
        for d in iter_dates(inc_ini, inc_fin):
            if fecha_inicio <= d <= fecha_fin:
                dias.add(d)
    return len(dias)
