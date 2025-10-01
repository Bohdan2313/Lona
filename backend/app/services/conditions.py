"""Helpers for working with custom trade conditions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import HTTPException

CONDITIONS_PATHS = [
    Path("config/custom_conditions.json"),
    Path("Custom Conditions.json"),
]


def _resolve_conditions_path() -> Path:
    for path in CONDITIONS_PATHS:
        if path.exists():
            return path
    default = CONDITIONS_PATHS[0]
    default.parent.mkdir(parents=True, exist_ok=True)
    default.write_text(json.dumps({}, indent=2, ensure_ascii=False))
    return default


def load_conditions() -> Dict[str, Any]:
    path = _resolve_conditions_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Не вдалося прочитати умови: {exc}") from exc


def save_conditions(data: Dict[str, Any]) -> Dict[str, Any]:
    path = _resolve_conditions_path()
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Не вдалося зберегти умови: {exc}") from exc
