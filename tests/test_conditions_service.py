from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services import conditions


@pytest.fixture()
def temp_conditions(monkeypatch, tmp_path: Path):
    path = tmp_path / "config" / "custom_conditions.json"
    monkeypatch.setattr(conditions, "CONDITIONS_PATHS", [path])
    yield path


def test_save_and_load_conditions(temp_conditions: Path):
    payload = {
        "mode": "CUSTOM",
        "long": {"core": [["rsi_trend", "up"]]},
        "short": {"core": [["rsi_trend", "down"]]},
    }
    saved = conditions.save_conditions(payload)
    assert saved["mode"] == "CUSTOM"

    loaded = conditions.load_conditions()
    assert loaded["long"]["core"][0] == ["rsi_trend", "up"]

    disk = json.loads(temp_conditions.read_text(encoding="utf-8"))
    assert disk["short"]["core"][0][1] == "down"
