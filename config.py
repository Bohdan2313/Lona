# config.py

import os
import json
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# ============================ 🔐 КЛЮЧІ/КЛІЄНТ ============================
load_dotenv()
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

EXCHANGE = "bybit"
bybit = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
client = bybit  # універсальний псевдонім

# ============================ ⚙️ ЗАВАНТАЖЕННЯ UI-КОНФІГУ ============================
UI_CONFIG_PATH = "config/config_ui.json"

def load_ui_config():
    try:
        if os.path.exists(UI_CONFIG_PATH):
            with open(UI_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"❌ Не вдалося завантажити UI-конфіг: {e}")
    return {}

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
