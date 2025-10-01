"""Analytics helpers exposed via API endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from backend.app.services.bot_runner import runner

MOCK_PNL_PATH = Path("data/mock/pnl_series.json")


def load_pnl_series() -> List[dict]:
    if MOCK_PNL_PATH.exists():
        with MOCK_PNL_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    # якщо у mock-режимі — беремо генератор з runner
    series = runner.pnl_series()
    if series:
        return series
    # fallback — порожній список
    return []
