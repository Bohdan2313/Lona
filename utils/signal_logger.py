import os
import json
from datetime import datetime
from utils.logger import log_error, log_message
from utils.logger import sanitize_signals
import pandas as pd
import numpy as np

STATS_PATH = "data/signal_stats.json"


def safe_float(value, default=0.0):
    """
    📦 Безпечне конвертування в float. Якщо value не число — повертає default.
    """
    try:
        if isinstance(value, (list, dict)):
            return default  # dict/list не конвертуємо
        return float(value)
    except (TypeError, ValueError):
        return default


def categorize_signals(signals: dict) -> str:
    """
    🧠 Формує деталізований ключ для signal_stats.json
    """
    import json

    if not isinstance(signals, dict):
        log_error(f"❌ categorize_signals отримав {type(signals)} → {signals}")
        return json.dumps({"fallback": True, "raw": str(signals)}, sort_keys=True, ensure_ascii=False)
    else:
        for k, v in signals.items():
            if isinstance(v, (pd.Series, pd.DataFrame, np.ndarray)):
                log_error(f"⚠️ Found NON-JSON SAFE value in signals: {k} → {type(v)}")

    def rsi_category(rsi):
        rsi = safe_float(rsi, 50)
        if rsi < 30:
            return "oversold"
        if rsi < 45:
            return "low"
        if rsi <= 55:
            return "neutral"
        if rsi <= 70:
            return "high"
        return "overbought"

    def whale_category(score):
        score = safe_float(score, 0)
        if score < 30:
            return "weak"
        if score < 70:
            return "medium"
        if score < 90:
            return "strong"
        return "ultra"

    def delta_category(delta):
        delta = safe_float(delta, 0)
        if delta > 2:
            return "surge"
        if delta > 0.5:
            return "up"
        if delta < -2:
            return "crash"
        if delta < -0.5:
            return "down"
        return "flat"

    try:
        # Перетворюємо всі вкладені структури в string
        for k, v in signals.items():
            if isinstance(v, (dict, list)):
                signals[k] = json.dumps(v, ensure_ascii=False, sort_keys=True)

        signal_key = {
            "trend": signals.get("trend", "unknown"),
            "global_trend": signals.get("global_trend", "neutral"),
            "macd": signals.get("macd_trend", "neutral"),
            "macd_cross": signals.get("macd_crossed", "none"),
            "macd_hist": signals.get("macd_hist_direction", "flat"),
            "rsi": rsi_category(signals.get("rsi", 50)),
            "rsi_div": signals.get("rsi_divergence", "none"),
            "whale": whale_category(signals.get("whale_score", 0)),
            "volume": signals.get("volume", "normal"),
            "volatility": signals.get("volatility_level", "unknown"),
            "pattern": "yes" if safe_float(signals.get("pattern_score", 0)) > 0 else "none",
            "bollinger": signals.get("bollinger_signal", "neutral"),
            "side": signals.get("position_side", "LONG"),
            "lstm": "bullish" if safe_float(signals.get("lstm_score", 0)) > 0 else "bearish",
            "atr": safe_float(signals.get("atr_score", 0)),
            "microtrend_1m": signals.get("microtrend_1m", "NEUTRAL"),
            "microtrend_5m": signals.get("microtrend_5m", "flat"),
            "stoch": signals.get("stoch_signal", "neutral"),
            "cci": signals.get("cci_signal", "neutral"),
            "support": signals.get("support_position", "unknown"),
            "confidence": signals.get("confidence_tag", "weak"),
            "delta": delta_category(signals.get("delta_1m", 0)),
            "health": "ok" if signals.get("health_ok", True) else "bad"
        }
        return json.dumps(signal_key, sort_keys=True)

    except Exception as e:
        import traceback
        log_error(f"❌ categorize_signals помилка: {e}\n{traceback.format_exc()}")
        return json.dumps({"error": "fallback", "signals": str(signals)}, sort_keys=True)


def log_signal_result(signals: dict, result: float, full_snapshot: dict = None):
    """
    📦 Логування сигналів та результатів у STATS_PATH
    ✅ Зберігає повний snapshot та результат угоди.
    """
    try:
        result = safe_float(result, 0.0)
    except Exception as e:
        log_error(f"❌ log_signal_result: неможливо привести result до float → {e}")
        return

    # 📂 Перевірка та завантаження файлу
    if not os.path.exists(STATS_PATH):
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
        stats = []
        log_message("📄 STATS_PATH створено")
    else:
        try:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                stats = json.load(f)
        except Exception as e:
            log_error(f"⚠️ STATS_PATH пошкоджений, створюю новий → {e}")
            stats = []

    if not isinstance(stats, list):
        log_error("❌ STATS не є списком! Скидаю до порожнього списку.")
        stats = []

    # 🩹 Fallback для signals
    if not signals and full_snapshot and "conditions" in full_snapshot:
        signals = full_snapshot.get("conditions", {})
        log_message("⚠️ signals пусті → fallback на full_snapshot.conditions")

    signals = sanitize_signals(signals)

    # 🗝️ Тимчасовий match_key
    match_key = "N/A"

    # 📈 Додаткові PnL
    peak_pnl = safe_float(full_snapshot.get("peak_pnl_percent"), result)
    worst_pnl = safe_float(full_snapshot.get("worst_pnl_percent"), result)

    # 📌 Основні дані
    symbol = signals.get("symbol") or full_snapshot.get("symbol", "UNKNOWN")
    trade_id = (full_snapshot or {}).get("trade_id")
    entry_price = (signals.get("entry_price") or full_snapshot.get("entry_price") or 0.0)
    exit_price = (signals.get("exit_price") or full_snapshot.get("exit_price") or None)
    duration = (signals.get("duration_minutes") or full_snapshot.get("duration_minutes", 0))
    exit_reason = full_snapshot.get("exit_reason", "OPEN")
    trade_result = full_snapshot.get("result", "OPEN")
    active = True if trade_result == "OPEN" else False

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # 🆕 Створюємо новий запис
    entry = {
        "key": match_key,
        "numeric_key": {},
        "signals": signals,
        "full_snapshot": {**(full_snapshot or {}), "active": active, "trade_id": trade_id},
        "pnl_percent": result,
        "peak_pnl_percent": peak_pnl,
        "worst_pnl_percent": worst_pnl,
        "symbol": symbol,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "timestamp": timestamp,
        "duration": duration,
        "exit_reason": exit_reason,
        "result": trade_result,
        "active": active
    }

    # 📝 Деактивація старих активних записів
    for s in stats:
        if s.get("symbol", "").upper() == symbol.upper() \
           and s.get("active", False) \
           and (not trade_id or s.get("full_snapshot", {}).get("trade_id") == trade_id):
            s["active"] = False
            s["full_snapshot"]["active"] = False
            log_message(f"🟠 Деактивовано старий запис для {symbol} (trade_id={trade_id})")

    # ➕ Додаємо новий запис
    stats.append(entry)
    log_message(f"✅ Додано новий запис для {symbol} у signal_stats.json (trade_id={trade_id})")

    # 💾 Запис у файл
    try:
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(stats[-500:], f, indent=2, ensure_ascii=False)
        log_message(
            f"📦 Passport оновлено → PnL={result:.2f}% | 📈 Пік={peak_pnl:.2f}% | 📉 Мін={worst_pnl:.2f}% | 🏁 {trade_result}"
        )
    except Exception as e:
        log_error(f"❌ Помилка при записі в STATS_PATH → {e}")


def log_final_trade_result(symbol, trade_id, entry_price, exit_price, result,
                           peak_pnl, worst_pnl, duration, exit_reason, snapshot):
    """
    📦 Додає фінальний запис угоди у signal_stats.json (append-only).
    Формат → повний signals при відкритті + фінальний результат.
    """
    try:
        if not os.path.exists(STATS_PATH):
            log_message("📄 STATS_PATH не знайдено, створюю новий файл.")
            stats = []
        else:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                try:
                    stats = json.load(f)
                except json.JSONDecodeError:
                    log_error("❌ STATS_PATH пошкоджений — скидаю у [].")
                    stats = []

        if not isinstance(stats, list):
            log_error("❌ STATS_PATH має некоректний формат. Скидаю у [].")
            stats = []

        # 🗝 Отримуємо signals при вході
        entry_signals = snapshot.get("conditions") or snapshot.get("behavior_summary", {}).get("signals") or {}

        # 📋 Створюємо фінальний запис
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        final_entry = {
            "key": snapshot.get("key", "N/A"),
            "numeric_key": snapshot.get("numeric_key", {}),
            "signals": sanitize_signals(entry_signals),
            "full_snapshot": {
                **snapshot,
                "symbol": symbol,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "peak_pnl_percent": peak_pnl,
                "worst_pnl_percent": worst_pnl,
                "duration_minutes": duration,
                "result": result,
                "exit_reason": exit_reason,
                "active": False,
                "trade_id": trade_id,
                "timestamp": timestamp
            },
            # 📌 Основні метрики угоди
            "pnl_percent": round(peak_pnl if result == "WIN" else worst_pnl, 2),
            "peak_pnl_percent": round(peak_pnl, 2),
            "worst_pnl_percent": round(worst_pnl, 2),
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "timestamp": timestamp,
            "duration": duration,
            "exit_reason": exit_reason,
            "result": result,
            "active": False
        }

        stats.append(final_entry)

        # 💾 Зберігаємо лише останні 500 записів
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(stats[-500:], f, indent=2, ensure_ascii=False)

        log_message(
            f"✅ Додано фінальний запис для {symbol} у signal_stats.json → "
            f"PNL={final_entry['pnl_percent']}% | 🏁 {result}"
        )

    except Exception as e:
        log_error(f"❌ log_final_trade_result() — помилка: {e}")


def log_clean_open_signal(symbol, trade_id, entry_price, snapshot):
    """
    📥 Додає новий запис у signal_stats.json при відкритті угоди (без PnL та результатів).
    """
    try:
        if not os.path.exists(STATS_PATH):
            log_message("📄 STATS_PATH не знайдено, створюю новий файл.")
            stats = []
        else:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                try:
                    stats = json.load(f)
                except json.JSONDecodeError:
                    log_error("❌ STATS_PATH пошкоджений — скидаю у [].")
                    stats = []

        # Створюємо початковий запис
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        open_entry = {
            "symbol": symbol,
            "trade_id": trade_id,
            "entry_price": entry_price,
            "signals": snapshot.get("conditions", {}),
            "timestamp": timestamp
        }

        stats.append(open_entry)

        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(stats[-500:], f, indent=2, ensure_ascii=False)

        log_message(f"✅ Додано сигнал для {symbol} у signal_stats.json")

    except Exception as e:
        log_error(f"❌ log_clean_open_signal() — помилка: {e}")



def append_signal_record(trade_record):
    """
    📝 Додає новий запис у signal_stats.json при відкритті угоди.
    """
    try:
        if not os.path.exists(STATS_PATH):
            with open(STATS_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)

        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)

        stats.append(trade_record)

        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        log_message(f"✅ [signal_logger] Новий запис додано у signal_stats.json (trade_id={trade_record.get('trade_id')})")

    except Exception as e:
        log_error(f"❌ [signal_logger] append_signal_record: помилка → {e}")

def update_signal_record(trade_id, updates):
    """
    🔄 Оновлює існуючий запис у signal_stats.json за trade_id або symbol+opened
    """
    try:
        if not os.path.exists(STATS_PATH):
            log_error("❌ [signal_logger] signal_stats.json не знайдено.")
            return

        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)

        updated = False
        for trade in stats:
            # Спочатку шукаємо за trade_id
            if trade.get("trade_id") == trade_id:
                trade.update(updates)
                updated = True
                break
            # Якщо trade_id не збігся → fallback на symbol+opened
            elif (trade.get("symbol") in trade_id and not trade.get("closed", False)):
                log_message(f"⚠️ [signal_logger] Збіг за symbol={trade.get('symbol')} (без trade_id)")
                trade.update(updates)
                updated = True
                break

        if updated:
            with open(STATS_PATH, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            log_message(f"✅ [signal_logger] Запис оновлено для trade_id={trade_id}")
        else:
            log_error(f"❌ [signal_logger] trade_id={trade_id} не знайдено для оновлення.")

    except Exception as e:
        log_error(f"❌ [signal_logger] update_signal_record: помилка → {e}")
