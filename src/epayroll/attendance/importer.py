"""Importador CSV de asistencia estándar."""

from __future__ import annotations

import csv
import io
from typing import Any


def parse_attendance_csv(content: str | bytes) -> list[dict[str, Any]]:
    if isinstance(content, bytes):
        content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content.strip()))
    rows: list[dict[str, Any]] = []
    for line_num, row in enumerate(reader, start=2):
        if not any(v and str(v).strip() for v in row.values()):
            continue
        item = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        item["_line"] = line_num
        rows.append(item)
    return rows
