# config.py

import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
# Фільтрація токенів з префіксом "1000"
SKIP_1000_TOKENS = True


ACTIVE_TRADES_FILE = "data/active_trades.json"


# 📥 Завантаження ключів із .env
load_dotenv()
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

EXCHANGE = "bybit"



bybit = HTTP(
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)


# 🧠 Універсальний обʼєкт для клієнта (щоб у коді завжди використовувати "client")
client = bybit
# ============================ 📈 АНАЛІТИКА ============================

VOLUME_THRESHOLDS = {
    "very_high_ratio": 1.8,
    "high_ratio": 1.1,
    "very_low_ratio": 0.15,
    "low_ratio": 0.5,
    "min_binance_volume": {
        "low": 50_000,
        "normal": 200_000,
        "high": 500_000
    }
}


# ============================ ⚙️ СИСТЕМНІ НАЛАШТУВАННЯ ============================

# 💰 Баланс та плече
USE_MANUAL_BALANCE = True
MANUAL_BALANCE = 6  # USDT

USE_MANUAL_LEVERAGE = True
MANUAL_LEVERAGE = 10  

MAX_ACTIVE_TRADES = 2


# === ManageOpenTrade Settings ===
PARTIAL_CLOSE_PERCENT = 60        # 📊 Частково закрити % від обсягу
PARTIAL_CLOSE_TRIGGER = 0.8       # 🚀 Триггер часткового закриття (80% від TP)
TRAILING_STOP_OFFSET = 0.02       # 📉 Відкат ціни для трейлінг-стопа (1%)
MANAGE_TP_PERCENT = 0.20          # 🎯 Тейкпрофіт (12%)
MANAGE_SL_PERCENT = 0.10          # ⛔ Стоп-лосс (4%)

 
# 📉 Мінімальний SCORE для входу
TRADE_SCORE_SHORT_THRESHOLD = -10
TRADE_SCORE_LONG_THRESHOLD = 40


# 🔁 Повторюваність торгового циклу
TRADING_CYCLE_PAUSE = 60                 # Пауза між торговими циклами (секунди)

# 🔊 Журналювання
ENABLE_LOGGING = True

# ============================ 📈 АНАЛІТИКА ============================

VOLUME_THRESHOLDS = {
    "very_high_ratio": 1.8,
    "high_ratio": 1.1,
    "very_low_ratio": 0.15,
    "min_bybit_volume": {  # 👈 адаптовано
        "low": 50_000,
        "normal": 200_000,
        "high": 500_000
    }
}

# ============================ 🧪 РЕЖИМИ ============================

# 🤖 Режим тестування (не відкриває реальні ордери)
DRY_RUN = False

# 📉 Мінімальний SCORE для входу

