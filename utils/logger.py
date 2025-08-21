import os
from datetime import datetime

import json
import os
import copy
import numpy as np
import pandas as pd
from config import bybit
from config import ACTIVE_TRADES_FILE,MAX_ACTIVE_TRADES
import tempfile
from threading import Lock


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


# --- ActiveTrades: thread-safe & atomic, key = trade_id ---



_AT_LOCK = Lock()  # глобальний лок на ActiveTrades
# використовуємо існуючий ACTIVE_TRADES_FILE з config

def _at_safe_load() -> dict:
    """Потокобезпечне читання ActiveTrades.json. Завжди повертає dict{trade_id: rec}."""
    if not os.path.exists(ACTIVE_TRADES_FILE):
        return {}
    try:
        with open(ACTIVE_TRADES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            # страхувальний ап: конвертація зі списку у dict
            return {t.get("trade_id", f"trade_{i}"): t for i, t in enumerate(data) if isinstance(t, dict)}
        return {}
    except Exception:
        return {}

def _at_atomic_save(data: dict) -> None:
    """Атомарний запис ActiveTrades.json через tempfile + os.replace."""
    content = json.dumps(data, indent=2, ensure_ascii=False)
    dirn = os.path.dirname(ACTIVE_TRADES_FILE) or "."
    with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8",
                                     dir=dirn, prefix=".swap_", suffix=".json") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, ACTIVE_TRADES_FILE)

def append_active_trade(trade_record: dict) -> None:
    """Додає/оновлює запис у ActiveTrades за trade_id."""
    trade_id = trade_record.get("trade_id")
    if not trade_id:
        log_error("❌ append_active_trade: відсутній trade_id")
        return
    with _AT_LOCK:
        trades = _at_safe_load()
        trades[trade_id] = deep_sanitize(trade_record)
        _at_atomic_save(trades)
    log_message(f"📥 Записано трейд {trade_id} до ActiveTrades.json")

def mark_trade_closed(trade_id: str, updates: dict | None = None) -> None:
    """Позначає угоду закритою та оновлює поля."""
    with _AT_LOCK:
        trades = _at_safe_load()
        if trade_id in trades:
            trades[trade_id]["closed"] = True
            if isinstance(updates, dict):
                trades[trade_id].update(deep_sanitize(updates))
            _at_atomic_save(trades)
            log_message(f"🔒 Позначено closed у ActiveTrades для {trade_id}")
        else:
            log_message(f"⚠️ mark_trade_closed: {trade_id} не знайдено")

def remove_active_trade(trade_id: str) -> None:
    """Видаляє угоду з ActiveTrades.json за trade_id."""
    with _AT_LOCK:
        trades = _at_safe_load()
        if trade_id in trades:
            trades.pop(trade_id, None)
            _at_atomic_save(trades)
            log_message(f"🧹 Угода {trade_id} видалена з ActiveTrades")
        else:
            log_message(f"⚠️ remove_active_trade: {trade_id} не знайдено")

def prune_inactive_trades(live_ids: set[str]) -> None:
    """
    Видаляє записи, яких немає серед live_ids або які мають closed=True.
    ⚠️ РЕКОМЕНДАЦІЯ: викликати лише для угод із джерелом LIVE_MONITOR.
    """
    with _AT_LOCK:
        trades = _at_safe_load()
        removed = False
        for tid in list(trades.keys()):
            rec = trades[tid]
            is_live_mon = (rec.get("behavior_summary", {}) or {}).get("entry_reason") == "LIVE_MONITOR"
            if rec.get("closed") or (is_live_mon and tid not in live_ids):
                trades.pop(tid, None)
                removed = True
        if removed:
            _at_atomic_save(trades)
            log_message("🧹 ActiveTrades прунінг виконано")

def get_active_trades() -> dict:
    """
    Повертає dict{trade_id: rec} з ActiveTrades.json.
    (Без автосинху з біржі — за це відповідає monitor_all_open_trades.)
    """
    with _AT_LOCK:
        return _at_safe_load()


def reconcile_active_trades_with_exchange():
    """
    Звіряє ActiveTrades.json з біржею:
    - будує live-множину як (symbol, SIDE)
    - видаляє локальні записи, яких немає на біржі, або які вже closed=True
    """
    try:
        # 1) забираємо живі пози з біржі
        resp = bybit.get_positions(category="linear", settleCoin="USDT") or {}
        items = (resp.get("result", {}) or {}).get("list", []) or []

        live = set()
        for pos in items:
            size = float(pos.get("size", 0) or 0.0)
            if size <= 0:
                continue
            symbol = pos.get("symbol")
            side = str(pos.get("positionSide", "")).upper()
            if not side:
                side = "LONG" if str(pos.get("side","")).upper()=="BUY" else "SHORT"
            live.add((symbol, side))

        # 2) вантажимо локальні трейди та чистимо
        with _AT_LOCK:
            trades = _at_safe_load()  # dict {trade_id: record}
            if not isinstance(trades, dict):
                trades = {}

            before = len(trades)
            removed_any = False

            for tid in list(trades.keys()):
                rec = trades.get(tid) or {}
                if rec.get("closed"):
                    trades.pop(tid, None)
                    removed_any = True
                    continue
                sym = rec.get("symbol")
                sd  = str(rec.get("side", "")).upper()
                if (sym, sd) not in live:
                    trades.pop(tid, None)
                    removed_any = True

            if removed_any:
                _at_atomic_save(trades)

            log_message(f"🧼 Reconcile: live={len(live)}, before={before}, after={len(trades)}")

    except Exception as e:
        log_error(f"reconcile_active_trades_with_exchange: {e}")