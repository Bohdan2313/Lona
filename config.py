# config.py

import os
import json
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

try:
    from pybit.unified_trading import HTTP  # type: ignore
except Exception:  # pragma: no cover - pybit може бути відсутній у тестовому середовищі
    HTTP = None  # type: ignore

# ============================ 🔐 КЛЮЧІ/КЛІЄНТ ============================
load_dotenv()
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

EXCHANGE = "bybit"


class MockHTTP:
    """Примітивний мок-клієнт Bybit для офлайн-режиму."""

    def __init__(self):
        self.is_mock = True

    def __getattr__(self, name):  # pragma: no cover - простий мок
        def _call(*args, **kwargs):
            return {
                "retCode": 0,
                "retMsg": f"mocked:{name}",
                "result": {"list": []},
                "time": 0,
            }

        return _call


if HTTP and BYBIT_API_KEY and BYBIT_API_SECRET:
    bybit = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
else:
    bybit = MockHTTP()

client = bybit  # універсальний псевдонім

# ============================ ⚙️ ЗАВАНТАЖЕННЯ UI-КОНФІГУ ============================
UI_CONFIG_PATHS = [
    Path("config/config_ui.json"),
    Path("config_ui.json"),
]


def _resolve_ui_config_path() -> Path:
    """Повертає перший існуючий шлях для UI-конфігурації або стандартний."""
    for candidate in UI_CONFIG_PATHS:
        if candidate.exists():
            return candidate
    # Якщо файл відсутній — створюємо у стандартному місці
    default_path = UI_CONFIG_PATHS[0]
    default_path.parent.mkdir(parents=True, exist_ok=True)
    default_path.write_text(json.dumps({}, indent=2, ensure_ascii=False))
    return default_path


def load_ui_config() -> Dict[str, Any]:
    path = _resolve_ui_config_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Не вдалося завантажити UI-конфіг ({path}): {e}")
        return {}


def save_ui_config(data: Dict[str, Any]) -> None:
    path = _resolve_ui_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


UI = load_ui_config()

# ============================ 🧹 ФІЛЬТРИ/ЗАГАЛЬНЕ ============================
SKIP_1000_TOKENS = False
ACTIVE_TRADES_FILE = "data/active_trades.json"
ENABLE_LOGGING = True
TRADING_CYCLE_PAUSE = 60

DESIRED_ACTIVE_TRADES = UI.get("DESIRED_ACTIVE_TRADES", 5)
MAX_LONG_TRADES = UI.get("MAX_LONG_TRADES", 4)
MAX_SHORT_TRADES = UI.get("MAX_SHORT_TRADES", 1)

ACCOUNT_SAFETY_BUFFER_PCT = UI.get("ACCOUNT_SAFETY_BUFFER_PCT", 0.001)
ACCOUNT_MIN_FREE_USDT = UI.get("ACCOUNT_MIN_FREE_USDT", 0.0)

USE_DYNAMIC_SYMBOLS = UI.get("USE_DYNAMIC_SYMBOLS", True)
GET_TOP_SYMBOLS_CONFIG = UI.get("GET_TOP_SYMBOLS_CONFIG", {
    "min_volume": 2_000_000,
    "limit": 20
})

MAX_ACTIVE_TRADES = UI.get("MAX_ACTIVE_TRADES", 5)
DRY_RUN = UI.get("DRY_RUN", False)
if isinstance(bybit, MockHTTP):
    DRY_RUN = True

# ============================ 💰 МАНУАЛЬНІ ПАРАМЕТРИ ============================
USE_MANUAL_BALANCE = UI.get("USE_MANUAL_BALANCE", True)
MANUAL_BALANCE = UI.get("MANUAL_BALANCE", 32.0)

USE_MANUAL_LEVERAGE = UI.get("USE_MANUAL_LEVERAGE", True)
MANUAL_LEVERAGE = UI.get("MANUAL_LEVERAGE", 5)

USE_EXCHANGE_TP = UI.get("USE_EXCHANGE_TP", False)
TP_USE_IOC = UI.get("TP_USE_IOC", True)
TP_EPSILON = UI.get("TP_EPSILON", 0.0007)

# ============================ 🤖 SMART AVERAGING / DCA ============================
SMART_AVG = UI.get("SMART_AVG", {
    "enabled": True,
    "leverage": 5,
    "base_margin": 32,
    "max_adds": 30,
    "dca_step_pct": 0.025,
    "dca_mode": "equal",
    "dca_factor": 1.3,
    "tp_from_avg_pct": 0.012,
    "alt_tp_from_avg_pct": 0.012,
    "max_margin_per_trade": 1800.0,
    "min_liq_buffer": 0.0,
    "atr_pause_pct": 999,
    "trend_flip_cut_pct": 0.010,
    "cooldown_min": 25,
    "anchor": "ladder"
})

# ============================ Innovation / High-Volatility guards ============================
BLOCK_INNOVATION = True
INNOVATION_MIN_LISTING_DAYS = 14
INNOVATION_MIN_24H_TURNOVER = 5_000_000
INNOVATION_CACHE_FILE = "data/innovation_cache.json"
