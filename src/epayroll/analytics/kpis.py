from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from epayroll.engine.rounding import RoundingMode, round_amount


@dataclass
class TurnoverMetrics:
    terminaciones: int
    plantilla_inicio: int
    plantilla_fin: int
    promedio_plantilla: Decimal
    tasa_rotacion_pct: Decimal


@dataclass
class AbsenteeismMetrics:
    dias_ausencia: Decimal
    dias_programados: Decimal
    tasa_ausentismo_pct: Decimal


@dataclass
class OvertimeMetrics:
    horas_extra_total: Decimal
    horas_extra_promedio_empleado: Decimal
    empleados_con_extras: int
    empleados_activos: int
    horas_extra_diurna: Decimal
    horas_extra_nocturna: Decimal
    horas_domingo_feriado: Decimal


def calc_turnover(
    terminaciones: int,
    plantilla_inicio: int,
    plantilla_fin: int,
) -> TurnoverMetrics:
    promedio = Decimal(str(max(plantilla_inicio + plantilla_fin, 1))) / Decimal("2")
    tasa = round_amount(
        Decimal(str(terminaciones)) / promedio * Decimal("100"),
        RoundingMode.CENTESIMO,
    )
    return TurnoverMetrics(
        terminaciones=terminaciones,
        plantilla_inicio=plantilla_inicio,
        plantilla_fin=plantilla_fin,
        promedio_plantilla=round_amount(promedio, RoundingMode.CENTESIMO),
        tasa_rotacion_pct=tasa,
    )


def calc_absenteeism(
    dias_ausencia: Decimal,
    dias_programados: Decimal,
) -> AbsenteeismMetrics:
    if dias_programados <= 0:
        tasa = Decimal("0")
    else:
        tasa = round_amount(
            dias_ausencia / dias_programados * Decimal("100"),
            RoundingMode.CENTESIMO,
        )
    return AbsenteeismMetrics(
        dias_ausencia=round_amount(dias_ausencia, RoundingMode.CENTESIMO),
        dias_programados=round_amount(dias_programados, RoundingMode.CENTESIMO),
        tasa_ausentismo_pct=tasa,
    )


def calc_overtime(
    attendance_rows: list[dict[str, Decimal]],
    empleados_activos: int,
) -> OvertimeMetrics:
    diurna = Decimal("0")
    nocturna = Decimal("0")
    domingo_feriado = Decimal("0")
    con_extras = 0

    for row in attendance_rows:
        h_ed = row.get("horas_extra_diurna", Decimal("0"))
        h_en = row.get("horas_extra_nocturna", Decimal("0")) + row.get(
            "horas_extra_mixta_noct", Decimal("0")
        )
        h_df = row.get("horas_domingo", Decimal("0")) + row.get("horas_feriado", Decimal("0"))
        total_row = h_ed + h_en + h_df
        diurna += h_ed
        nocturna += h_en
        domingo_feriado += h_df
        if total_row > 0:
            con_extras += 1

    total = diurna + nocturna + domingo_feriado
    promedio = (
        round_amount(total / Decimal(str(max(empleados_activos, 1))), RoundingMode.CENTESIMO)
        if empleados_activos
        else Decimal("0")
    )
    return OvertimeMetrics(
        horas_extra_total=round_amount(total, RoundingMode.CENTESIMO),
        horas_extra_promedio_empleado=promedio,
        empleados_con_extras=con_extras,
        empleados_activos=empleados_activos,
        horas_extra_diurna=round_amount(diurna, RoundingMode.CENTESIMO),
        horas_extra_nocturna=round_amount(nocturna, RoundingMode.CENTESIMO),
        horas_domingo_feriado=round_amount(domingo_feriado, RoundingMode.CENTESIMO),
    )
