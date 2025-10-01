"""Utilities for reading/writing UI configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

from config import load_ui_config, save_ui_config

CONFIG_PATH = Path("config/config_ui.json")


def get_config_path() -> Path:
    """Return the concrete config path, creating parents if required."""
    path = CONFIG_PATH
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # ініціалізуємо файлом з поточного стану у config.py
        data = load_ui_config()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def read_config() -> Dict[str, Any]:
    try:
        return load_ui_config()
    except Exception as exc:  # pragma: no cover - захисний блок
        raise HTTPException(status_code=500, detail=f"Не вдалося прочитати конфіг: {exc}") from exc


def write_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not isinstance(payload, dict):
            raise TypeError("Config payload must be a dict")
        save_ui_config(payload)
        return payload
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Не вдалося зберегти конфіг: {exc}") from exc


def update_config(patch: Dict[str, Any]) -> Dict[str, Any]:
    config = read_config()
    config.update(patch)
    return write_config(config)
