"""Validación de filas de asistencia estándar (hechos, no montos)."""

from __future__ import annotations

import json
import re
from datetime import date, time
from typing import Any

ATT_SPLIT_PREFIX = "EPAYROLL_ATT_SPLIT:"
ATT_DESCUENTO_PREFIX = "EPAYROLL_DESCUENTO:"
_ATT_SPLIT_RE = re.compile(r"^EPAYROLL_ATT_SPLIT:(\{[^}]+\})")
_ATT_DESCUENTO_RE = re.compile(r"^EPAYROLL_DESCUENTO:(\{[^}]+\})")

DEFAULT_SCHEDULE = {
    "amIn": time(8, 0),
    "amOut": time(12, 0),
    "pmIn": time(13, 0),
    "pmOut": time(17, 0),
}


def _parse_bool(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "si", "sí", "y")


def _parse_time(value: Any) -> time | None:
    if value is None or value == "":
        return None
    if isinstance(value, time):
        return value
    s = str(value).strip()
    parts = s.split(":")
    if len(parts) >= 2:
        return time(int(parts[0]), int(parts[1]))
    return None


def _parse_split_obs(observacion: str | None) -> dict[str, Any] | None:
    if not observacion:
        return None
    m = _ATT_SPLIT_RE.match(str(observacion).strip())
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _minutes_between(from_time: time | None, to_time: time | None) -> int | None:
    if not from_time or not to_time:
        return None
    diff = (to_time.hour * 60 + to_time.minute) - (from_time.hour * 60 + from_time.minute)
    return diff if diff >= 0 else None


def _descanso_from_split_obs(observacion: str | None) -> int | None:
    split = _parse_split_obs(observacion)
    if not split:
        return None
    return _minutes_between(_parse_time(split.get("amOut")), _parse_time(split.get("pmIn")))


def _parse_descuento_obs(observacion: str | None) -> int | None:
    if not observacion:
        return None
    for line in str(observacion).splitlines():
        m = _ATT_DESCUENTO_RE.match(line.strip())
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("minutos") is not None:
            return max(0, int(data["minutos"]))
    return None


def compute_descuento_minutos(
    hora_entrada: time | None,
    hora_salida: time | None,
    observacion: str | None,
    *,
    schedule: dict[str, time] | None = None,
) -> int:
    """Minutos descontables vs horario programado (tardanza / salida anticipada)."""
    sched = schedule or DEFAULT_SCHEDULE
    split = _parse_split_obs(observacion)
    am_in = _parse_time(hora_entrada) or sched["amIn"]
    pm_out = _parse_time(hora_salida) or sched["pmOut"]
    am_out = _parse_time(split.get("amOut") if split else None) or sched["amOut"]
    pm_in = _parse_time(split.get("pmIn") if split else None) or sched["pmIn"]

    total = 0
    for actual, expected in (
        (am_in, sched["amIn"]),
        (pm_in, sched["pmIn"]),
    ):
        late = _minutes_between(expected, actual)
        if late:
            total += late
    for actual, expected in (
        (am_out, sched["amOut"]),
        (pm_out, sched["pmOut"]),
    ):
        early = _minutes_between(actual, expected)
        if early:
            total += early
    return total


def normalize_fact_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normaliza claves CSV/API a formato interno."""
    turno_val = (raw.get("turno") or raw.get("shift") or "").strip()
    if not turno_val:
        he = raw.get("hora_entrada")
        hs = raw.get("hora_salida")
        turno_val = "DIURNO" if (he or hs) else None
    data = {
        "cedula": (raw.get("cedula") or raw.get("identificacion") or "").strip() or None,
        "employee_id": (raw.get("employee_id") or "").strip() or None,
        "fecha": raw.get("fecha"),
        "turno": turno_val,
        "hora_entrada": _parse_time(raw.get("hora_entrada")),
        "hora_salida": _parse_time(raw.get("hora_salida")),
        "descanso_minutos": int(raw.get("descanso_minutos") or 0),
        "tipo_dia": str(raw.get("tipo_dia") or "NORMAL").strip().upper(),
        "ausencia": _parse_bool(raw.get("ausencia")),
        "incapacidad": _parse_bool(raw.get("incapacidad")),
        "vacaciones": _parse_bool(raw.get("vacaciones")),
        "observacion": (raw.get("observacion") or raw.get("observación") or "").strip() or None,
        "fuente": (raw.get("fuente") or "MANUAL").strip().upper(),
    }
    no_trabajo = bool(data["ausencia"] or data["incapacidad"] or data["vacaciones"])
    if not no_trabajo:
        split_descanso = _descanso_from_split_obs(data["observacion"])
        if split_descanso is not None:
            data["descanso_minutos"] = split_descanso
    return data


def validate_fact_row(
    row: dict[str, Any],
    *,
    employee_id: str | None = None,
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Valida hecho de asistencia. Retorna (normalizado, errores)."""
    data = normalize_fact_row(row)
    errors: list[str] = []

    if employee_id:
        data["employee_id"] = employee_id
    elif not data["cedula"] and not data["employee_id"]:
        errors.append("cedula o employee_id requerido")

    fecha = data["fecha"]
    if fecha is None or fecha == "":
        errors.append("fecha requerida")
    elif isinstance(fecha, str):
        try:
            data["fecha"] = date.fromisoformat(fecha.strip())
        except ValueError:
            errors.append(f"fecha inválida: {fecha}")
    if isinstance(data.get("fecha"), date):
        if fecha_inicio and data["fecha"] < fecha_inicio:
            errors.append("fecha antes del período")
        if fecha_fin and data["fecha"] > fecha_fin:
            errors.append("fecha después del período")

    tipo = data["tipo_dia"]
    if tipo not in ("NORMAL", "DOMINGO", "FERIADO"):
        errors.append(f"tipo_dia inválido: {tipo}")

    if data["descanso_minutos"] < 0:
        errors.append("descanso_minutos no puede ser negativo")

    no_trabajo = data["ausencia"] or data["vacaciones"] or data["incapacidad"]
    if not no_trabajo:
        vacio = not data["hora_entrada"] and not data["hora_salida"]
        if vacio:
            pass
        elif not data["hora_entrada"]:
            errors.append("hora_entrada requerida si no es ausencia/vacaciones/incapacidad")
        elif not data["hora_salida"]:
            errors.append("hora_salida requerida si no es ausencia/vacaciones/incapacidad")
        elif data["hora_entrada"] and data["hora_salida"] and data["hora_salida"] <= data["hora_entrada"]:
            errors.append("hora_salida debe ser posterior a hora_entrada")

    return data, errors
