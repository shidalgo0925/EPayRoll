from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from epayroll.time.tz import TZ

# Art. 30 CT — períodos de trabajo
DIURNO_START = time(6, 0)
DIURNO_END = time(18, 0)


@dataclass(frozen=True)
class ShiftConfig:
    codigo: str
    tipo_jornada: str  # DIURNA, NOCTURNA, MIXTA
    horas_max_dia: Decimal = Decimal("8")
    maximo_extras_diarias: Decimal = Decimal("3")


@dataclass
class DailyAttendance:
    fecha: date
    horas_ordinarias: Decimal = Decimal("0")
    horas_extra_diurna: Decimal = Decimal("0")
    horas_extra_nocturna: Decimal = Decimal("0")
    horas_extra_mixta_noct: Decimal = Decimal("0")
    horas_domingo: Decimal = Decimal("0")
    horas_feriado: Decimal = Decimal("0")
    es_feriado: bool = False
    es_domingo: bool = False
    dias_trabajados: Decimal = Decimal("0")


@dataclass
class PeriodSummary:
    dias_trabajados: Decimal
    horas_extra_diurnas: Decimal
    horas_extra_nocturnas: Decimal
    horas_extra_mixta_nocturnas: Decimal
    horas_domingo: Decimal
    horas_feriado: Decimal
    days: list[DailyAttendance]


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _is_diurno_hour(t: time) -> bool:
    return DIURNO_START <= t < DIURNO_END


def _hours_between(start: datetime, end: datetime) -> Decimal:
    if end <= start:
        return Decimal("0")
    seconds = (end - start).total_seconds()
    return _q2(Decimal(str(seconds)) / Decimal("3600"))


def _split_diurno_nocturno(start: datetime, end: datetime) -> tuple[Decimal, Decimal]:
    """Retorna (horas_diurnas, horas_nocturnas) entre dos timestamps."""
    if end <= start:
        return Decimal("0"), Decimal("0")
    diurno = Decimal("0")
    nocturno = Decimal("0")
    cursor = start
    while cursor < end:
        nxt = min(end, cursor + timedelta(hours=1))
        frac = _hours_between(cursor, nxt)
        if _is_diurno_hour(cursor.time()):
            diurno += frac
        else:
            nocturno += frac
        cursor = nxt
    return _q2(diurno), _q2(nocturno)


def calculate_day(
    fecha: date,
    entrada: datetime,
    salida: datetime,
    shift: ShiftConfig,
    es_feriado: bool = False,
    es_incapacidad: bool = False,
) -> DailyAttendance:
    """
    Calcula asistencia diaria desde marcación entrada/salida.
    Arts. 31, 33 CT — jornada máxima y clasificación de extras.
    """
    if es_incapacidad:
        return DailyAttendance(fecha=fecha)

    entrada = entrada.astimezone(TZ) if entrada.tzinfo else entrada.replace(tzinfo=TZ)
    salida = salida.astimezone(TZ) if salida.tzinfo else salida.replace(tzinfo=TZ)

    total = _hours_between(entrada, salida)
    if total <= 0:
        return DailyAttendance(fecha=fecha)

    es_domingo = fecha.weekday() == 6
    diurno, nocturno = _split_diurno_nocturno(entrada, salida)
    max_ord = shift.horas_max_dia

    result = DailyAttendance(
        fecha=fecha,
        es_feriado=es_feriado,
        es_domingo=es_domingo,
        dias_trabajados=Decimal("1") if total > 0 else Decimal("0"),
    )

    # Feriado / domingo: horas ordinarias del día generan recargo (Art. 48-49)
    if es_feriado:
        ord_hours = min(total, max_ord)
        result.horas_feriado = ord_hours
        extra = max(Decimal("0"), total - max_ord)
        if extra > 0:
            result.horas_extra_diurna = _classify_extra(shift, diurno, nocturno, extra)[0]
            result.horas_extra_nocturna = _classify_extra(shift, diurno, nocturno, extra)[1]
            result.horas_extra_mixta_noct = _classify_extra(shift, diurno, nocturno, extra)[2]
        return result

    if es_domingo:
        ord_hours = min(total, max_ord)
        result.horas_domingo = ord_hours
        extra = max(Decimal("0"), total - max_ord)
        if extra > 0:
            ex_d, ex_n, ex_m = _classify_extra(shift, diurno, nocturno, extra)
            result.horas_extra_diurna = ex_d
            result.horas_extra_nocturna = ex_n
            result.horas_extra_mixta_noct = ex_m
        return result

    # Día laboral normal
    ord_hours = min(total, max_ord)
    result.horas_ordinarias = ord_hours
    extra = max(Decimal("0"), total - max_ord)
    if extra > shift.maximo_extras_diarias:
        extra = shift.maximo_extras_diarias  # Art. 36 — tope 3h/día (advertencia en UI)

    ex_d, ex_n, ex_m = _classify_extra(shift, diurno, nocturno, extra, ordinarias=ord_hours)
    result.horas_extra_diurna = ex_d
    result.horas_extra_nocturna = ex_n
    result.horas_extra_mixta_noct = ex_m
    return result


def _classify_extra(
    shift: ShiftConfig,
    diurno: Decimal,
    nocturno: Decimal,
    extra: Decimal,
    ordinarias: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal, Decimal]:
    """Distribuye horas extra según tipo de jornada — Art. 33 CT."""
    if extra <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")

    if shift.tipo_jornada == "NOCTURNA":
        return Decimal("0"), extra, Decimal("0")
    if shift.tipo_jornada == "MIXTA":
        # Extras en prolongación nocturna mixta → 75% (Art. 33 ord. 3)
        if nocturno > ordinarias:
            mixta_noct = min(extra, nocturno - ordinarias)
            rest = extra - mixta_noct
            return rest, Decimal("0"), mixta_noct
        return extra, Decimal("0"), Decimal("0")

    # DIURNA — extras diurnas 25%; si caen en nocturno → 50%
    if nocturno <= 0:
        return extra, Decimal("0"), Decimal("0")
    ratio = nocturno / (diurno + nocturno) if (diurno + nocturno) > 0 else Decimal("0")
    ex_n = _q2(extra * ratio)
    ex_d = _q2(extra - ex_n)
    return ex_d, ex_n, Decimal("0")


def summarize_period(days: list[DailyAttendance]) -> PeriodSummary:
    return PeriodSummary(
        dias_trabajados=_q2(sum((d.dias_trabajados for d in days), Decimal("0"))),
        horas_extra_diurnas=_q2(sum((d.horas_extra_diurna for d in days), Decimal("0"))),
        horas_extra_nocturnas=_q2(sum((d.horas_extra_nocturna for d in days), Decimal("0"))),
        horas_extra_mixta_nocturnas=_q2(sum((d.horas_extra_mixta_noct for d in days), Decimal("0"))),
        horas_domingo=_q2(sum((d.horas_domingo for d in days), Decimal("0"))),
        horas_feriado=_q2(sum((d.horas_feriado for d in days), Decimal("0"))),
        days=days,
    )
