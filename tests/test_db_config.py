from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from epayroll.db.config_loader import load_config
from epayroll.engine.config import load_config_from_seed


def test_load_config_fallback_to_seed_when_no_db():
    with patch("epayroll.db.config_loader.load_config_from_db", side_effect=ConnectionError("no db")):
        cfg = load_config(prefer_db=True)
    seed_cfg = load_config_from_seed()
    assert len(cfg.rules) == len(seed_cfg.rules)
    assert "SALARIO_BASE" in cfg.concepts


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Requiere PostgreSQL con seed aplicado",
)
def test_load_config_from_db_integration():
    cfg = load_config(prefer_db=True)
    assert len(cfg.rules) >= 10
    assert cfg.concepts["CSS_EMPLEADO"].tipo == "DESCUENTO"
