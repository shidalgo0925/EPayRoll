from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from epayroll.integration.odoo import build_journal_entry


@dataclass(frozen=True)
class OdooPushConfig:
    url: str
    api_key: str
    database: str | None = None


class OdooPushError(Exception):
    pass


def load_push_config() -> OdooPushConfig:
    url = (os.environ.get("ODOO_PUSH_URL") or "").strip()
    api_key = (os.environ.get("ODOO_API_KEY") or "").strip()
    database = (os.environ.get("ODOO_DATABASE") or "").strip() or None
    if not url:
        raise OdooPushError("ODOO_PUSH_URL no configurada")
    if not api_key:
        raise OdooPushError("ODOO_API_KEY no configurada")
    return OdooPushConfig(url=url, api_key=api_key, database=database)


def push_journal_entry(entry: dict[str, Any], config: OdooPushConfig | None = None) -> dict[str, Any]:
    """Envía asiento JSON a Odoo (webhook/API REST configurable)."""
    cfg = config or load_push_config()
    payload = {
        "database": cfg.database,
        "entry": entry,
    }
    headers = {
        "Authorization": f"Bearer {cfg.api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(cfg.url, json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise OdooPushError(f"Error de conexión Odoo: {e}") from e

    if resp.status_code >= 400:
        raise OdooPushError(f"Odoo respondió HTTP {resp.status_code}: {resp.text[:500]}")

    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text}

    return {
        "status": "ok",
        "http_status": resp.status_code,
        "odoo_response": body,
        "run_id": entry.get("run_id"),
        "balanced": entry.get("balanced"),
    }


def prepare_and_push(bundle, config: OdooPushConfig | None = None) -> dict[str, Any]:
    entry = build_journal_entry(bundle)
    if not entry.get("balanced"):
        raise OdooPushError("Asiento no balanceado — push abortado")
    result = push_journal_entry(entry, config=config)
    result["journal"] = entry
    return result
