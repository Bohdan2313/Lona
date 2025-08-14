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


# === Реєстри потоків ===
# Потоки конкретних угод (ключ = trade_id)
active_threads: dict[str, threading.Thread] = {}
# Фонові демони (монітор біржі, вочліст тощо)
bg_threads: dict[str, threading.Thread] = {}

def run_llama_trading_pipeline():
    """
    🚀 Головна функція запуску з підтримкою багатьох угод:
    Відбір монет → Моніторинг → Торгівля
    """
    log_message("🚦 [DEBUG] Старт LLaMA Trading Pipeline")

    # 🧵 Запускаємо моніторинг відкритих угод у фоновому потоці (один раз)
    if "monitor_all_open_trades" not in bg_threads:
        t = threading.Thread(target=monitor_all_open_trades, daemon=True)
        t.start()
        bg_threads["monitor_all_open_trades"] = t
        log_message("🧵 [DEBUG] monitor_all_open_trades запущено у фоні")
    else:
        log_message("🧵 [DEBUG] monitor_all_open_trades вже працює — пропускаємо старт")

    # 👁 Запуск моніторингу монет біля підтримки з Watchlist (один раз)
    if "monitor_watchlist_candidate" not in bg_threads:
        log_message("👁 [DEBUG] Старт monitor_watchlist_candidate у фоні")
        t = threading.Thread(target=monitor_watchlist_candidate, daemon=True)
        t.start()
        bg_threads["monitor_watchlist_candidate"] = t
    else:
        log_message("👁 [DEBUG] monitor_watchlist_candidate вже працює — пропускаємо старт")

    log_message("🔄 [DEBUG] Вхід у головний цикл while True")
    while True:
        try:
            active_trades = get_active_trades()
            active_count = len(active_trades)
            log_message(f"📦 [DEBUG] Завантажено активних угод: {active_count}")

            if active_count >= MAX_ACTIVE_TRADES:
                log_message(f"🛑 Вже відкрито {active_count} угод (макс={MAX_ACTIVE_TRADES})")
                time.sleep(TRADING_CYCLE_PAUSE)
                continue

            log_message("🔍 [DEBUG] Запускаємо find_best_scalping_targets()")
            find_best_scalping_targets()
            log_message("🔁 [DEBUG] Повернення з find_best_scalping_targets()")

        except Exception as e:
            log_error(f"❌ Виняток у run_llama_trading_pipeline: {e}\n{traceback.format_exc()}")

        log_message(f"⏳ [DEBUG] Пауза перед новим циклом: {TRADING_CYCLE_PAUSE} сек")
        time.sleep(TRADING_CYCLE_PAUSE)

# Стартуємо пайплайн тільки якщо файл запускається напряму (не при імпорті)
if __name__ == "__main__":
    log_message("✅ MAIN ЗАПУЩЕНО")
    run_llama_trading_pipeline()
