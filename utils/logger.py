import os
from datetime import datetime

import json
import os
import copy
import numpy as np
import pandas as pd
from config import bybit
from config import ACTIVE_TRADES_FILE,MAX_ACTIVE_TRADES
SIDE_BUY = "Buy"
SIDE_SELL = "Sell"


BLACKLIST_PATH = "data/loss_blacklist.json"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DATA_DIR = os.path.join(BASE_DIR, "data")

# Шляхи
TRADES_LOG_PATH = os.path.join(DATA_DIR, "trades.log")
ANALYTICS_LOG_PATH = os.path.join(DATA_DIR, "analytics.log")
SCALPING_LOG_PATH = os.path.join(DATA_DIR, "scalping_trades.log")
SCALPING_ANALYSIS_PATH = os.path.join(DATA_DIR, "scalping_analysis.log")
LONA_MIND_LOG_PATH = os.path.join(LOGS_DIR, "lona_mind.log")
GPT_QUERIES_LOG_PATH = os.path.join(LOGS_DIR, "gpt_queries.log")

# Створюємо директорії, якщо їх нема
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def deep_sanitize(data):
    """
    🧹 Рекурсивно приводить всі дані до Python стандартних типів.
    """
    try:
        if isinstance(data, dict):
            return {str(k): deep_sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [deep_sanitize(v) for v in data]
        elif isinstance(data, (pd.Series, np.ndarray)):
            return data.tolist()
        elif isinstance(data, (np.integer, np.floating)):
            return float(data)
        elif isinstance(data, (int, float, str, bool)):
            return data
        elif isinstance(data, (datetime, pd.Timestamp)):
            return data.isoformat()
        else:
            log_message(f"⚠️ deep_sanitize: невідомий тип {type(data)}, замінюємо на None")
            return None  # 🔥 краще None, ніж str(data)
    except Exception as e:
        log_error(f"❌ deep_sanitize помилка: {e}")
        return {}


def sanitize_signals(signals: dict) -> dict:
    """
    🧹 Приводить всі значення в signals до JSON-safe стандартних типів.
    """
    def make_safe(value):
        if isinstance(value, dict):
            return {str(k): make_safe(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [make_safe(v) for v in value]
        elif isinstance(value, (np.integer, np.floating)):
            return float(value)
        elif isinstance(value, (datetime, pd.Timestamp)):
            return value.isoformat()
        elif isinstance(value, (pd.Series, np.ndarray)):
            return value.tolist()
        elif isinstance(value, (int, float, str, bool)):
            return value
        else:
            log_message(f"⚠️ sanitize_signals: невідомий тип {type(value)}, замінюємо на None")
            return None

    try:
        return {str(k): make_safe(v) for k, v in signals.items()}
    except Exception as e:
        log_error(f"❌ sanitize_signals помилка: {e}")
        return {}


DEBUG_LOG_PATH = os.path.join(LOGS_DIR, "debug.log")
DEBUG_KEYWORDS = ["[DEBUG]", "[TRACE]", "[WATCHLIST]", "[SKIP]"]


def _write_log(path: str, message: str):
    with open(path, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def log_debug(msg: str):
    """Записує службові повідомлення у debug.log без виводу в термінал."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"{timestamp} | {msg}"
    try:
        _write_log(DEBUG_LOG_PATH, full_msg)
    except Exception as e:
        print(f"❌ [log_debug] Помилка: {e}")


def log_message(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"{timestamp} | {msg}"
    try:
        if any(tag in msg for tag in DEBUG_KEYWORDS):
            _write_log(DEBUG_LOG_PATH, full_msg)
            return
        _write_log(TRADES_LOG_PATH, full_msg)
        print(f"📘 {full_msg}")
    except Exception as e:
        print(f"❌ [log_message] Помилка: {e}")

def log_error(error_msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"{timestamp} | ❌ ERROR: {error_msg}"
    try:
        with open(ANALYTICS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
        print(f"🚨 {full_msg}")
    except Exception as e:
        print(f"❌ [log_error] Помилка: {e}")

def log_trade_result(symbol, side, entry_price, exit_price, quantity, result_type="TP", leverage=1):
    try:
        pnl = (exit_price - entry_price) * quantity
        if side == SIDE_SELL:
            pnl = -pnl
        pnl_percent = (pnl / (entry_price * quantity)) * 100 * leverage
        status = "✅ Take Profit" if result_type == "TP" else "🛑 Stop Loss"

        log_line = (
            f"{datetime.now():%Y-%m-%d %H:%M:%S} | {symbol} | {status} | {side} | "
            f"Entry: {entry_price} → Exit: {exit_price} | Qty: {quantity} | "
            f"PnL: {pnl:.2f} USDT ({pnl_percent:.2f}%) | Leverage: {leverage}"
        )

        with open(ANALYTICS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
        log_message(f"📊 {log_line}")

    except Exception as e:
        log_error(f"❌ [log_trade_result] Помилка: {e}")

def log_lona_thought(symbol, thought):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LONA_MIND_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{symbol}] {thought}\n\n")
        log_message(f"🧠 [{symbol}] {thought}")
    except Exception as e:
        log_error(f"❌ [log_lona_thought] Помилка: {e}")

def log_scalping_trade(symbol, entry_price, exit_price, side, pnl, reason):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            f"[{now}] {symbol} | {side} | Вхід: {entry_price} | Вихід: {exit_price} | "
            f"PnL: {round(pnl, 2)}% | Причина закриття: {reason}"
        )
        with open(SCALPING_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(message + "\n")
        log_message(f"📄 {message}")

        # Якщо збиток — додаємо до blacklist
        if pnl < 0:
            blacklist = {}
            if os.path.exists(BLACKLIST_PATH):
                with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
                    blacklist = json.load(f)

            blacklist[symbol] = datetime.now().timestamp()

            with open(BLACKLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(blacklist, f, indent=2)
            log_message(f"⚠️ {symbol} додано до blacklist через збиток")

    except Exception as e:
        log_error(f"❌ [log_scalping_trade] Помилка: {e}")

def save_scalping_analysis(message):
    try:
        with open(SCALPING_ANALYSIS_PATH, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")
        log_message("📋 Scalping Analysis записано.")
    except Exception as e:
        log_error(f"❌ [save_scalping_analysis] Помилка: {e}")

def log_gpt_query(prompt, response):
    try:
        with open(GPT_QUERIES_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"=== PROMPT ===\n{prompt}\n=== RESPONSE ===\n{response}\n\n")
        log_message("📄 GPT запит записано.")
    except Exception as e:
        log_error(f"❌ [log_gpt_query] Помилка: {e}")



def log_erx_decision(symbol, reason, blocked=True):
    try:
        entry = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "blocked": blocked,
            "reason": reason
        }
        log_path = "logs/erx_decisions.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log_error(f"❌ Не вдалося записати рішення ERX: {e}")


from threading import Lock

active_trades_lock = Lock()

def append_active_trade(trade_record: dict):
    """
    📝 Логгер: записує trade_record в ActiveTrades.json
    """
    try:
        symbol = trade_record.get("symbol", "UNKNOWN")

        # Завантажуємо існуючі трейди
        if os.path.exists(ACTIVE_TRADES_FILE):
            with open(ACTIVE_TRADES_FILE, "r", encoding="utf-8") as f:
                trades = json.load(f)
        else:
            trades = {}

        trades[symbol] = trade_record  # Повний запис

        with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)

        log_message(f"📥 Записано трейд {symbol} до ActiveTrades.json")
    except Exception as e:
        log_error(f"❌ append_active_trade: {e}")


def remove_active_trade(symbol: str):
    """
    🧹 Видаляє угоду за символом або trade_id із ActiveTrades (DICT формат)
    """
    try:
        with active_trades_lock:
            log_message("🔒 [DEBUG] ActiveTrades LOCK отримано для видалення")

            if not os.path.exists(ACTIVE_TRADES_FILE):
                log_message("⚠️ ActiveTrades файл відсутній — нічого видаляти.")
                return

            # 📂 Читаємо файл
            try:
                with open(ACTIVE_TRADES_FILE, "r", encoding="utf-8") as f:
                    active_trades = json.load(f)
            except json.JSONDecodeError:
                log_error("❌ remove_active_trade: ActiveTrades файл пошкоджений — створюю новий")
                active_trades = {}

            if isinstance(active_trades, list):
                log_error("❌ ActiveTrades у форматі list — конвертую у dict.")
                active_trades = {
                    t.get("trade_id", f"trade_{i}"): t
                    for i, t in enumerate(active_trades)
                }

            # 🧹 Знаходимо trade_id по symbol
            to_remove = None
            for tid, data in active_trades.items():
                if data.get("symbol") == symbol or tid == symbol:
                    to_remove = tid
                    break

            if to_remove:
                removed = active_trades.pop(to_remove, None)
                log_message(f"🧹 Угода {to_remove} видалена з ActiveTrades")
            else:
                log_message(f"⚠️ remove_active_trade: угода {symbol} не знайдена у ActiveTrades")

            # 💾 Перезапис файлу
            with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as f:
                json.dump(active_trades, f, indent=2, ensure_ascii=False)

            log_message(f"📦 [DEBUG] ActiveTrades оновлено після видалення: {len(active_trades)} угод")

    except Exception as e:
        log_error(f"❌ remove_active_trade({symbol}): {e}")


# 📦 Логування завершених угод
CLOSED_TRADES_FILE = "data/closed_trades.json"

def append_closed_trade(trade_data: dict):
    """
    📁 Додає закриту угоду в CLOSED_TRADES_FILE (max 500 записів)
    та логує фінальний результат у signal_stats.json
    """
    try:
        from utils.signal_logger import log_final_trade_result  # 🆕 нова функція

        def make_json_safe(obj):
            if isinstance(obj, dict):
                return {str(k): make_json_safe(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_safe(v) for v in obj]
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            elif isinstance(obj, (np.ndarray, pd.Series, pd.DataFrame)):
                return obj.tolist()
            elif isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            elif isinstance(obj, (int, float, str, bool)) or obj is None:
                return obj
            else:
                return str(obj)

        trade_data = make_json_safe(trade_data)

        # 📂 Додаємо угоду до CLOSED_TRADES_FILE
        if not os.path.exists(CLOSED_TRADES_FILE):
            with open(CLOSED_TRADES_FILE, "w") as f:
                json.dump([], f)

        with open(CLOSED_TRADES_FILE, "r") as f:
            try:
                trades = json.load(f)
            except json.JSONDecodeError:
                log_error("❌ CLOSED_TRADES_FILE пошкоджений — скидаю у [].")
                trades = []

        if not isinstance(trades, list):
            log_error("❌ CLOSED_TRADES_FILE має некоректний формат. Скидаю у [].")
            trades = []

        trades.append(trade_data)
        trades = trades[-500:]  # 🧹 Тримаємо лише останні 500 угод

        with open(CLOSED_TRADES_FILE, "w") as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)

        pnl = round(trade_data.get('pnl_percent', 0.0), 2)
        peak_pnl = round(trade_data.get('peak_pnl_percent', pnl), 2)
        worst_pnl = round(trade_data.get('worst_pnl_percent', pnl), 2)

        log_message(
            f"📁 Закрита угода: {trade_data.get('symbol')} → PnL: {pnl}% "
            f"(📈 Пік: {peak_pnl}% | 📉 Мін: {worst_pnl}%)"
        )

        # 🆕 Логування фінального результату у signal_stats.json
        log_final_trade_result(
            symbol=trade_data.get("symbol"),
            trade_id=trade_data.get("trade_id"),
            entry_price=trade_data.get("entry_price"),
            exit_price=trade_data.get("exit_price"),
            result=trade_data.get("result", "UNKNOWN"),
            peak_pnl=peak_pnl,
            worst_pnl=worst_pnl,
            duration=trade_data.get("duration_minutes", 0),
            exit_reason=trade_data.get("exit_reason", "UNKNOWN"),
            snapshot={
                "behavior_summary": trade_data.get("behavior_summary", {}),
                "conditions": trade_data.get("conditions", {}),
                "symbol": trade_data.get("symbol", "UNKNOWN"),
                "entry_price": trade_data.get("entry_price"),
                "exit_price": trade_data.get("exit_price"),
                "peak_pnl_percent": peak_pnl,
                "worst_pnl_percent": worst_pnl,
                "duration_minutes": trade_data.get("duration_minutes", 0),
                "exit_reason": trade_data.get("exit_reason", "UNKNOWN"),
                "result": trade_data.get("result", "UNKNOWN"),
                "active": False,
                "trade_id": trade_data.get("trade_id")
            }
        )

    except Exception as e:
        log_error(f"❌ append_closed_trade() — помилка: {e}")


def get_active_trades():
    """
    📂 Отримує активні угоди з файлу або підтягуючи з біржі, якщо файл порожній.
    Зберігає у ActiveTrades.json лише symbol: timestamp.
    """
    try:
        if not os.path.exists(ACTIVE_TRADES_FILE):
            log_message("📂 ActiveTrades файл відсутній — створюю новий.")
            with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)
            return {}

        with open(ACTIVE_TRADES_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                log_error("❌ ActiveTrades файл пошкоджений — скидаю у {}")
                data = {}
                with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as fw:
                    json.dump(data, fw, indent=2)

        if isinstance(data, dict) and data:
            log_message(f"📦 Завантажено {len(data)} активних угод із файлу.")
            return data

        log_message("⚠️ ActiveTrades порожній — підтягую з біржі...")

        response = bybit.get_positions(category="linear", settleCoin="USDT")
        positions = response.get("result", {}).get("list", [])
        active_trades = {}
        for pos in positions:
            size = float(pos.get("size", 0))
            if size > 0:
                symbol = pos.get("symbol")
                active_trades[symbol] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(active_trades, f, indent=2, ensure_ascii=False)

        log_message(f"✅ Синхронізовано {len(active_trades)} активних угод із біржі.")
        return active_trades

    except Exception as e:
        log_error(f"❌ get_active_trades помилка: {e}")
        return {}


CANDIDATES_LOG_PATH = "logs/scalping_candidates.log"

def log_candidate_simple(symbol, score):
    """
    📦 Логування простим форматом: час, токен, скор
    """
    try:
        if not os.path.exists("logs"):
            os.makedirs("logs")
        with open(CANDIDATES_LOG_PATH, "a", encoding="utf-8") as f:
            time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{time_str} | {symbol} → Score: {score}\n")
    except Exception as e:
        log_message(f"❌ log_candidate_simple error: {e}")