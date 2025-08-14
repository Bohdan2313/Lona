# 📁 Файл: run_llama_trading.py

import time
from datetime import datetime
from trading.scalping import find_best_scalping_targets

from utils.logger import log_message, log_error
import json
import os
from config import bybit
from config import MAX_ACTIVE_TRADES
from trading.scalping import execute_scalping_trade
from config import TRADING_CYCLE_PAUSE, MANUAL_BALANCE
from utils.tools import get_current_futures_price
from config import ACTIVE_TRADES_FILE
from utils.logger import get_active_trades
import threading
from trading.scalping import monitor_all_open_trades
from analysis.signal_analysis import analyze_signal_stats 
from utils.logger import sanitize_signals
from trading.scalping import monitor_watchlist_candidate
import traceback
import threading

# 🔁 Контроль активних потоків, щоб не дублювати
active_threads = {}

def run_llama_trading_pipeline():
    """
    🚀 Головна функція запуску з підтримкою багатьох угод:
    Відбір монет → Моніторинг → Торгівля
    """
    log_message("🚦 [DEBUG] Старт LLaMA Trading Pipeline")

    # 🧵 Запускаємо моніторинг відкритих угод у фоновому потоці
    threading.Thread(target=monitor_all_open_trades, daemon=True).start()
    log_message("🧵 [DEBUG] monitor_all_open_trades запущено у фоні")

    # 👁 Запуск моніторингу монет біля підтримки з Watchlist
    if "monitor_watchlist" not in active_threads:
        log_message("👁 [DEBUG] Старт monitor_watchlist_candidate у фоні")
        t = threading.Thread(target=monitor_watchlist_candidate, daemon=True)
        t.start()
        active_threads["monitor_watchlist"] = t

    log_message("🔄 [DEBUG] Вхід у головний цикл while True")
    while True:
        try:
            active_trades = get_active_trades()
            log_message(f"📦 [DEBUG] Завантажено активних угод: {len(active_trades)}")
            active_count = len(active_trades)

            if active_count >= MAX_ACTIVE_TRADES:
                log_message(f"🛑 Вже відкрито {active_count} угод (макс={MAX_ACTIVE_TRADES})")
                time.sleep(TRADING_CYCLE_PAUSE)
                continue

            # ⏬ Тут виклик без повернення
            log_message("🔍 [DEBUG] Запускаємо find_best_scalping_targets()")
            find_best_scalping_targets()
            log_message("🔁 [DEBUG] Повернення з find_best_scalping_targets()")

        except Exception as e:
            log_error(f"❌ Виняток у run_llama_trading_pipeline: {e}\n{traceback.format_exc()}")

        log_message(f"⏳ [DEBUG] Пауза перед новим циклом: {TRADING_CYCLE_PAUSE} сек")
        time.sleep(TRADING_CYCLE_PAUSE)

# ⏯ Старт
log_message("✅ MAIN ЗАПУЩЕНО")
run_llama_trading_pipeline()
