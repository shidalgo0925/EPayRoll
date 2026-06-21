"""Validación de filas de asistencia estándar (hechos, no montos)."""

from __future__ import annotations

from datetime import date, time
from typing import Any


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


def normalize_fact_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normaliza claves CSV/API a formato interno."""
    return {
        "cedula": (raw.get("cedula") or raw.get("identificacion") or "").strip() or None,
        "employee_id": (raw.get("employee_id") or "").strip() or None,
        "fecha": raw.get("fecha"),
        "turno": (raw.get("turno") or raw.get("shift") or "DIURNO").strip(),
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
        if not data["hora_entrada"]:
            errors.append("hora_entrada requerida si no es ausencia/vacaciones/incapacidad")
        if not data["hora_salida"]:
            errors.append("hora_salida requerida si no es ausencia/vacaciones/incapacidad")
        elif data["hora_entrada"] and data["hora_salida"] and data["hora_salida"] <= data["hora_entrada"]:
            errors.append("hora_salida debe ser posterior a hora_entrada")

    return data, errors
