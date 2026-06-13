"""Push automático asiento Odoo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from epayroll.engine.context import PayrollInput
from epayroll.engine.orchestrator import PayrollEngine
from epayroll.export.models import PayrollExportBundle, PayrollExportEmployee, PayrollExportPeriod
from epayroll.integration.odoo_push import OdooPushConfig, OdooPushError, push_journal_entry


def _bundle():
    engine = PayrollEngine()
    result = engine.run(
        PayrollInput(
            salario_mensual=Decimal("1800"),
            dias_trabajados=Decimal("15"),
            es_quincena=True,
            mes=6,
        )
    )
    conceptos = {line.codigo_concepto: line.monto for line in result.lines}
    return PayrollExportBundle(
        run_id="run-push-1",
        period=PayrollExportPeriod(
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 6, 15),
            fecha_pago=date(2026, 6, 16),
        ),
        employees=[
            PayrollExportEmployee(
                employee_id="e1",
                cedula="8-1",
                nombres="A",
                apellidos="B",
                bruto=result.bruto,
                neto=result.neto,
                aportes_patronales=result.aportes_patronales,
                conceptos=conceptos,
            )
        ],
    )


def test_push_missing_url(monkeypatch):
    monkeypatch.delenv("ODOO_PUSH_URL", raising=False)
    monkeypatch.delenv("ODOO_API_KEY", raising=False)
    with pytest.raises(OdooPushError, match="ODOO_PUSH_URL"):
        from epayroll.integration.odoo_push import load_push_config

        load_push_config()


@patch("epayroll.integration.odoo_push.httpx.Client")
def test_push_journal_success(mock_client_cls):
    from epayroll.integration.odoo import build_journal_entry

    entry = build_journal_entry(_bundle())
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 99, "name": "MOVE/2026/001"}
    mock_resp.text = '{"id": 99}'
    mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

    cfg = OdooPushConfig(url="https://odoo.example/hook", api_key="secret", database="demo")
    result = push_journal_entry(entry, config=cfg)
    assert result["status"] == "ok"
    assert result["odoo_response"]["id"] == 99
