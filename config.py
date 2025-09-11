# config.py

import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

# ============================ 🔐 КЛЮЧІ/КЛІЄНТ ============================
load_dotenv()
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

EXCHANGE = "bybit"
bybit = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)
client = bybit  # універсальний псевдонім

# ============================ 🧹 ФІЛЬТРИ/ЗАГАЛЬНЕ ============================
SKIP_1000_TOKENS = False
ACTIVE_TRADES_FILE = "data/active_trades.json"
ENABLE_LOGGING = True
TRADING_CYCLE_PAUSE = 60   

# config.py
DESIRED_ACTIVE_TRADES = 7             # скільки ХОЧЕМО одночасних угод
ACCOUNT_SAFETY_BUFFER_PCT = 0.05      # 5% балансу тримаємо «на чорний день»
ACCOUNT_MIN_FREE_USDT = 0.0           # додаткова фіксована подушка


MAX_ACTIVE_TRADES = 7
DRY_RUN = False

# ============================ 📈 АНАЛІТИКА ============================
VOLUME_THRESHOLDS = {
    "very_high_ratio": 1.8,
    "high_ratio": 1.1,
    "very_low_ratio": 0.15,
    "low_ratio": 0.5,
    "min_bybit_volume": {
        "low": 50_000,
        "normal": 200_000,
        "high": 500_000
    }
}

# ============================ 💰 МАНУАЛЬНІ ПАРАМЕТРИ ============================
# Якщо хочеш завжди стартувати $100 і плече 5× — тримай True і ці значення
USE_MANUAL_BALANCE = False
MANUAL_BALANCE = 7.0  # $ старт на угоду (маржа першої сходинки)

USE_MANUAL_LEVERAGE = True
MANUAL_LEVERAGE = 5     # базове плече (узгоджене зі SMART_AVG)

USE_EXCHANGE_TP = False

TP_USE_IOC = True  # якщо True → TP ордер буде IOC (миттєвий), а не PostOnly

TP_EPSILON       = 0.0007 # 0.07% м'який допуск для софт TP у manage_open_trade
# (TP_USE_IOC можеш залишити, але він ігноруватиметься коли USE_EXCHANGE_TP=False)


# ============================ 🤖 SMART AVERAGING / DCA ============================
SMART_AVG = {
    "enabled": True,

    # ці два параметри тут радше довідкові; фактичні беруться з MANUAL_* якщо прапори True
    "leverage": 5,
    "base_margin": 6,          # стартова маржа на угоду (1-а сходинка)

    "max_adds": 5,                 # кількість докупок максимум
    "dca_step_pct": 0.020,         # крок між рівнями (від середньої), 4.5% ~ sweet spot на 15m
    "dca_mode": "progressive",           # "equal" або "progressive"
    "dca_factor": 1.3,             # якщо progressive — помірний мультиплікатор

    # TP від середньої ціни (1% ≈ +5% до депозиту при 5×; 2% ≈ +10%)
    "tp_from_avg_pct": 0.015,
    "alt_tp_from_avg_pct": 0.015,

    # ліміти/гварди
    "max_margin_per_trade": 3900.0, # 100 старт + до 5 докупок по 100 = 600
    "min_liq_buffer": 0.10,        # мін. буфер до ліквідації після кожної докупки (40%)
    "atr_pause_pct": 0.12,         # якщо ATR%(15m) > 10% — пауза докупок
    "trend_flip_cut_pct": 0.30,    # при фліпі глобального тренду проти нас — скорочуємо 40%
    "cooldown_min": 25,             # пауза між новими сесіями того ж символу

    # анкер докупок (ОСНОВНЕ!)
    "anchor": "ladder"
}


# === Innovation / High-Volatility guards ===
BLOCK_INNOVATION            = True       # якщо True — символи Innovation/молоді/тонкі ми просто скіпаємо
INNOVATION_MIN_LISTING_DAYS = 14         # мін. вік лістингу (днів)
INNOVATION_MIN_24H_TURNOVER = 5_000_000  # мін. 24h оборот у $
INNOVATION_CACHE_FILE       = "data/innovation_cache.json"
