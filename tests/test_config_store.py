from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
from backend.app.services import config_store


@pytest.fixture()
def temp_config(monkeypatch, tmp_path: Path):
    path = tmp_path / "config" / "config_ui.json"
    monkeypatch.setattr(config, "UI_CONFIG_PATHS", [path])
    # перезавантажуємо внутрішній кеш
    config.UI = config.load_ui_config()
    monkeypatch.setattr(config_store, "CONFIG_PATH", path)
    yield path


def test_write_and_read_config(temp_config: Path):
    payload = {"MAX_ACTIVE_TRADES": 3, "DRY_RUN": True}
    result = config_store.write_config(payload)
    assert result == payload

    loaded = config_store.read_config()
    assert loaded["MAX_ACTIVE_TRADES"] == 3
    assert loaded["DRY_RUN"] is True

    on_disk = json.loads(temp_config.read_text(encoding="utf-8"))
    assert on_disk == payload
