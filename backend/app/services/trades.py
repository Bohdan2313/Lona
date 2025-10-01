"""Read-only helpers for exposing trades to the API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

from utils.logger import get_active_trades

MOCK_TRADES_PATH = Path("data/active_trades.json")


def _normalise_trade(record: Dict[str, Any]) -> Dict[str, Any]:
    # гарантуємо наявність ключових полів для фронтенду
    defaults = {
        "trade_id": record.get("trade_id") or record.get("symbol", "unknown"),
        "symbol": record.get("symbol", "UNKNOWN"),
        "side": record.get("side", "LONG").upper(),
        "entry_price": float(record.get("entry_price", 0.0) or 0.0),
        "quantity": float(record.get("quantity", 0.0) or 0.0),
        "leverage": record.get("leverage"),
        "opened_at": record.get("opened_at"),
        "pnl_percent": record.get("pnl_percent"),
        "status": record.get("status", "open"),
    }
    return defaults


def load_open_trades() -> List[Dict[str, Any]]:
    trades = get_active_trades()
    if isinstance(trades, dict):
        values = list(trades.values())
    elif isinstance(trades, list):
        values = trades
    else:
        values = []

    if not values and MOCK_TRADES_PATH.exists():
        try:
            with MOCK_TRADES_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                values = list(data.values())
            elif isinstance(data, list):
                values = data
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail=f"Не вдалося прочитати trades: {exc}") from exc

    return [_normalise_trade(t) for t in values if isinstance(t, dict)]
