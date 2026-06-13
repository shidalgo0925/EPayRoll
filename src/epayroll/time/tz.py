"""Zona horaria Panamá (UTC-5, sin DST)."""
from __future__ import annotations

from datetime import timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("America/Panama")
except Exception:
    # Windows sin paquete tzdata
    TZ = timezone(timedelta(hours=-5), name="America/Panama")
