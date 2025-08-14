# scalping.py

import time
from analysis.indicators import get_volatility,analyze_support_resistance
import traceback
from utils.tools import check_position_with_retry
from datetime import datetime, timedelta
from trading.executor import get_current_futures_price
from utils.logger import log_message, log_error, log_debug
from trading.executor import OrderExecutor
from trading.risk import calculate_amount_to_use
from ai.decision import calculate_trade_score
from config import bybit
is_trade_open = False
import pandas as pd
from analysis.market import analyze_volume
from utils.get_klines_bybit import get_klines_clean_bybit
import json
import re
from datetime import datetime
from analysis.monitor_coin_behavior import build_monitor_snapshot 
import os
from utils.telegram_bot import send_telegram_message
import random  
from config import MAX_ACTIVE_TRADES
from config import ACTIVE_TRADES_FILE
from utils.logger import append_active_trade
import threading
from config import USE_MANUAL_BALANCE, MANUAL_BALANCE, USE_MANUAL_LEVERAGE, MANUAL_LEVERAGE
from utils.tools import get_usdt_balance
from analysis.market import get_top_symbols
from decimal import Decimal, getcontext
getcontext().prec = 10  # для точного порівняння без округлень
from analysis.monitor_coin_behavior import convert_snapshot_to_conditions
from utils.signal_logger import update_signal_record
from trading.executor import OrderExecutor
from ai.decision import check_trade_conditions_long, check_trade_conditions_short
from config import (PARTIAL_CLOSE_PERCENT, PARTIAL_CLOSE_TRIGGER,
                        TRAILING_STOP_OFFSET, MANAGE_TP_PERCENT, MANAGE_SL_PERCENT)
import random
import numpy as np
from utils.signal_logger import log_final_trade_result



SIDE_BUY = "Buy"
SIDE_SELL = "Sell"
# 🔒 Набір символів, які прямо зараз відкриваються (антидубль)
opening_symbols = set()


RECENT_SCALPING_FILE = "data/recent_scalping.json"

def quick_scan_coin(symbol: str) -> dict | None:
    """
    ⚡ Fast screening монети для pre-фільтру
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="1h", limit=150)
        if df is None or df.empty or len(df) < 50:
            return None

        df["close"] = df["close"].astype(float)
        close_mean = df["close"].mean()
        close_std = df["close"].std()
        volatility = round((close_std / max(close_mean, 1e-8)) * 100, 2)

        volume_category = analyze_volume(symbol)
        if isinstance(volume_category, dict):
            volume_category = volume_category.get("level", "low")

        volume_score = {
            "very_low": 0,
            "low": 1,
            "normal": 2,
            "high": 3,
            "very_high": 4
        }.get(volume_category, 0)

        return {
            "volume_score": volume_score,
            "volatility": volatility
        }

    except Exception as e:
        log_error(f"❌ quick_scan_coin помилка для {symbol}: {e}")
        return None


WATCHLIST_LOG_PATH = "logs/watchlist_debug.json"
WATCHLIST_PATH = "data/watchlist.json"
MONITOR_INTERVAL = 5  # секунд

def load_watchlist() -> list:
    try:
        if not os.path.exists(WATCHLIST_PATH):
            with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
                json.dump([], f)
            return []

        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                log_error("❌ Watchlist JSON не є списком! Скидаю файл.")
                return []
            return data

    except Exception as e:
        log_error(f"❌ Не вдалося прочитати watchlist.json: {e}")
        return []

def save_watchlist(watchlist):
    try:
        os.makedirs(os.path.dirname(WATCHLIST_PATH), exist_ok=True)
        log_message(f"📋 [WATCHLIST] Збереження {len(watchlist)} монет у {WATCHLIST_PATH}")
        with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(watchlist, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log_error(f"❌ Помилка запису Watchlist: {e}")

def add_to_watchlist(symbol, support_position, current_price,side="LONG"):
    try:
        watchlist = load_watchlist()

        # Перевіряємо, чи монета вже в списку
        if any(item["symbol"] == symbol for item in watchlist):
            log_message(f"ℹ️ [WATCHLIST] {symbol} вже у списку — пропуск")
            return

        watchlist.append({
            "symbol": symbol,
            "support_position": support_position,
            "current_price": current_price,
            "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "side": side
        })

        save_watchlist(watchlist)
        log_message(f"📥 [WATCHLIST] {symbol} збережено в watchlist.json")

    except Exception as e:
        log_error(f"❌ [WATCHLIST] Помилка при додаванні {symbol}: {e}")


def _canonicalize_patterns_for_log(patterns):
    """
    Канонізація під твої fast-lane патерни:
    bullish_engulfing / bearish_engulfing / hammer / shooting_star / evening_star / morning_star / doji
    """
    out = []
    if isinstance(patterns, list):
        for p in patterns:
            if isinstance(p, dict):
                t = str(p.get("type", "")).lower()
                d = str(p.get("direction", "")).lower()
                if t == "engulfing" and d in ("bullish", "bearish"):
                    out.append(f"{d}_engulfing")
                elif t in ("hammer", "shooting_star", "evening_star", "morning_star", "doji"):
                    out.append(t)
            elif isinstance(p, str):
                out.append(p.lower())
    return sorted(set(out))


def log_watchlist_reason(symbol, side, reason, conditions=None):
    """
    Логує рівно ті ключі, які використовують нові check_trade_conditions_long/short,
    і додає list 'blockers' з конкретними причинами, чому ще НЕ відкрито.
    """
    try:
        import os, json
        from datetime import datetime

        os.makedirs("logs", exist_ok=True)
        filepath = "logs/watchlist_debug.json"
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        def safe(val):
            if isinstance(val, (int, float, str, bool)) or val is None:
                return val
            if isinstance(val, list):
                return [safe(v) for v in val]
            if isinstance(val, dict):
                return {str(k): safe(v) for k, v in val.items()}
            return str(val)

        minimal = {}
        blockers = []

        if isinstance(conditions, dict):
            # === поля, які реально читають твої check_* ===
            keys = [
                "support_position", "global_trend", "volume_category",
                "macd_trend", "macd_hist_direction", "macd_crossed",
                "rsi_value", "rsi_trend", "rsi_signal",
                "stoch_signal", "stoch_k", "stoch_d",
                "bollinger_position", "bollinger_signal",
                "cci_signal", "cci_value",
                "microtrend_1m", "microtrend_5m", "delta_1m",
                "patterns"
            ]
            for k in keys:
                minimal[k] = safe(conditions.get(k))

            # канонізовані патерни для fast-lane
            minimal["patterns_canon"] = _canonicalize_patterns_for_log(conditions.get("patterns", []))

            # === формуємо blockers відповідно до ТОЧНИХ правил у check_* ===
            side = str(side or "").upper()

            sp = str(minimal.get("support_position", "")).lower()
            gt = str(minimal.get("global_trend", "unknown")).lower()
            vol = str(minimal.get("volume_category", "unknown")).lower()

            macd_trend = minimal.get("macd_trend", "neutral")
            macd_hist  = minimal.get("macd_hist_direction", "flat")
            macd_cross = minimal.get("macd_crossed", "none")

            try:
                rsi_val = float(minimal.get("rsi_value", 0) or 0)
            except Exception:
                rsi_val = 0.0
            rsi_trend  = str(minimal.get("rsi_trend", "flat")).lower()
            rsi_signal = minimal.get("rsi_signal", "neutral")

            stoch_signal = minimal.get("stoch_signal", "neutral")
            try:
                k_val = float(minimal.get("stoch_k")) if minimal.get("stoch_k") is not None else None
            except Exception:
                k_val = None
            try:
                d_val = float(minimal.get("stoch_d")) if minimal.get("stoch_d") is not None else None
            except Exception:
                d_val = None

            try:
                bb_pos = float(minimal.get("bollinger_position", 50) or 50)
            except Exception:
                bb_pos = 50.0
            bb_sig = minimal.get("bollinger_signal", "neutral")

            cci_sig = minimal.get("cci_signal", "neutral")
            try:
                cci_val = float(minimal.get("cci_value", 0) or 0)
            except Exception:
                cci_val = 0.0

            micro1m = str(minimal.get("microtrend_1m", "neutral")).lower()
            try:
                delta_1m = float(minimal.get("delta_1m", 0) or 0)
            except Exception:
                delta_1m = 0.0

            # --- загальні блокери ---
            if vol == "very_low":
                blockers.append("volume_category=very_low")

            if side == "LONG":
                # support/global
                if sp not in ("near_support", "between"):
                    blockers.append(f"support_position={sp} (need near_support/between)")
                if gt not in ("bullish", "strong_bullish", "flat"):
                    blockers.append(f"global_trend={gt} (need bullish/strong_bullish/flat)")

                # MACD
                if not ((macd_trend == "bullish") or (macd_hist == "up")):
                    blockers.append("MACD: need trend=bullish or hist=up")
                if macd_cross not in ("none", "bullish"):
                    blockers.append(f"macd_crossed={macd_cross} (need none/bullish)")

                # RSI
                if not (30 <= rsi_val <= 62):
                    blockers.append(f"RSI out of 30..62 ({rsi_val})")
                if rsi_trend not in ("up", "neutral"):
                    blockers.append(f"rsi_trend={rsi_trend} (need up/neutral)")
                if rsi_signal not in ("oversold", "neutral", "bullish_momentum"):
                    blockers.append(f"rsi_signal={rsi_signal} (need oversold/neutral/bullish_momentum)")

                # Stoch
                if stoch_signal not in ("oversold", "oversold_cross_up", "neutral"):
                    blockers.append(f"stoch_signal={stoch_signal} (need oversold/oversold_cross_up/neutral)")
                if k_val is not None and d_val is not None:
                    if not (k_val <= 40 or d_val <= 40):
                        blockers.append(f"stoch too high (K={k_val}, D={d_val}, need any≤40)")

                # Bollinger
                if not (bb_pos <= 60):
                    blockers.append(f"bollinger_position={bb_pos} (need ≤60)")
                if bb_sig not in ("neutral", "bullish_momentum"):
                    blockers.append(f"bollinger_signal={bb_sig} (need neutral/bullish_momentum)")

                # Micro
                if micro1m == "bearish" and delta_1m < 0:
                    blockers.append(f"microtrend_1m=bearish with delta_1m={delta_1m}")

            elif side == "SHORT":
                # support/global
                if sp not in ("near_resistance", "between"):
                    blockers.append(f"support_position={sp} (need near_resistance/between)")
                if gt not in ("bullish", "strong_bullish", "flat", "bearish"):
                    blockers.append(f"global_trend={gt} (need bullish/strong_bullish/flat/bearish)")

                # MACD
                if not ((macd_trend == "bearish") or (macd_hist == "down")):
                    blockers.append("MACD: need trend=bearish or hist=down")
                if macd_cross not in ("none", "bearish"):
                    blockers.append(f"macd_crossed={macd_cross} (need none/bearish)")

                # RSI
                if not (55 <= rsi_val <= 78):
                    blockers.append(f"RSI out of 55..78 ({rsi_val})")
                if rsi_trend not in ("down", "neutral", "up"):
                    blockers.append(f"rsi_trend={rsi_trend} (invalid)")
                if rsi_signal not in ("neutral", "bullish_momentum", "overbought"):
                    blockers.append(f"rsi_signal={rsi_signal} (need neutral/bullish_momentum/overbought)")

                # Stoch
                if stoch_signal not in ("overbought", "neutral"):
                    blockers.append(f"stoch_signal={stoch_signal} (need overbought/neutral)")
                if k_val is not None and d_val is not None:
                    if not (k_val >= 70 or d_val >= 70):
                        blockers.append(f"stoch too low (K={k_val}, D={d_val}, need any≥70)")

                # CCI
                if not ((cci_sig in ("overbought", "neutral")) and (cci_val >= 60)):
                    blockers.append(f"CCI weak: {cci_sig} {cci_val} (need sig overbought/neutral and value≥60)")

                # Bollinger
                if not (bb_pos >= 65):
                    blockers.append(f"bollinger_position={bb_pos} (need ≥65)")
                if bb_sig not in ("neutral", "bearish_momentum", "bullish_momentum"):
                    blockers.append(f"bollinger_signal={bb_sig} (invalid)")

                # Micro
                if micro1m == "bullish" and delta_1m > 0:
                    blockers.append(f"microtrend_1m=bullish with delta_1m={delta_1m}")

            # Якщо blockers порожній, а угоди нема — значить або ще не всі дані стабільні,
            # або fast-lane патерн не з’явився — це теж корисно бачити в логах.
            if not blockers:
                blockers.append("no hard blockers; waiting for confirmation/fast-lane")

        # формуємо запис
        entry = {
            "timestamp": timestamp,
            "symbol": symbol,
            "side": (str(side).upper() if side else side),
            "reason": safe(reason),
            "blockers": blockers,
            "conditions": minimal
        }

        # безпечне читання існуючого логу
        try:
            existing = []
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
        except Exception:
            existing = []

        existing.append(entry)

        # атомарний запис
        tmp = filepath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        os.replace(tmp, filepath)

    except Exception as e:
        log_error(f"❌ log_watchlist_reason (new) помилка: {e}")



def monitor_watchlist_candidate():
    import concurrent.futures

    log_debug("Старт моніторингу Watchlist Candidates")

    def is_open_signal(res: dict) -> bool:
        return isinstance(res, dict) and res.get("open_trade") in ("LONG", "SHORT")

    def process_candidate(item):
        try:
            symbol = item["symbol"]
            side = item["side"]

            snapshot = build_monitor_snapshot(symbol)
            if not snapshot:
                log_watchlist_reason(symbol, side, "❌ snapshot is None", {})
                return None

            conditions = convert_snapshot_to_conditions(snapshot)
            if not conditions:
                log_watchlist_reason(symbol, side, "❌ conditions is None", {})
                return None

            # Виклик фільтра за напрямком
            if side == "LONG":
                result = check_trade_conditions_long(conditions)
            elif side == "SHORT":
                result = check_trade_conditions_short(conditions)
            else:
                result = None

            # Немає сигналу — чекаємо далі
            if not is_open_signal(result):
                log_debug(f"{symbol}: ще немає сигналу {side}")
                log_watchlist_reason(symbol, side, "still waiting for full signal confirmation", conditions)
                return None

            # Перевірка узгодженості напрямку
            detected_side = result["open_trade"]
            if detected_side != side:
                log_debug(f"{symbol}: напрямок не збігається → {detected_side} ≠ {side}")
                log_watchlist_reason(symbol, side, "side mismatch", conditions)
                return None

            # Відкриваємо угоду
            log_message(f"🎯 Watchlist: умови виконані для {symbol} → відкриваємо {side}")
            balance = get_usdt_balance()

            behavior_summary = {
                "entry_reason": f"WATCHLIST_TRIGGER_{side}",
                "signals": conditions,
                "volume": conditions.get("volume")  # може бути None — ок
            }

            # Обираємо актуальну ціну
            price = (
                conditions.get("price")
                or conditions.get("current_price")
                or snapshot.get("price")
                or snapshot.get("current_price")
            )

            target_data = {
                "symbol": symbol,
                "target_price": price,  # важливо саме target_price
                "price": price,
                "volume": conditions.get("volume"),
                "recommended_leverage": None,
                "source": "watchlist"
            }

            execute_scalping_trade(
                target=target_data,
                balance=balance,
                position_side=side,
                behavior_summary=behavior_summary
            )

            log_debug(f"Видалення {symbol} з Watchlist")
            return symbol  # повертаємо символ для видалення

        except Exception as e:
            log_error(f"❌ [monitor_watchlist_candidates] помилка для {item}: {e}")
            log_watchlist_reason(item.get("symbol", "UNKNOWN"), item.get("side", "UNKNOWN"), f"Помилка: {e}", {})
            return None

    # === Основний цикл моніторингу ===
    while True:
        watchlist = load_watchlist() or []
        if not watchlist:
            time.sleep(MONITOR_INTERVAL)
            continue

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_candidate, item) for item in watchlist]
            results = [f.result() for f in futures]
            to_remove = [sym for sym in results if sym]

        if to_remove:
            updated_watchlist = [item for item in watchlist if item["symbol"] not in to_remove]
            save_watchlist(updated_watchlist)

        time.sleep(MONITOR_INTERVAL)


def find_best_scalping_targets():
    """
    🚀 Бойовий режим:
    - Відбір монет біля підтримки/опору, а також у стані between (маршрутизація за глобальним трендом).
    - Якщо пройшла check_trade_conditions() → відкриття угоди.
    - Якщо не пройшла → додаємо в watchlist.json для моніторингу.
    - monitor_watchlist_candidate пише в logs/watchlist_debug.json кожні 5 сек.
    """
    try:
        log_message("🚦 Старт find_best_scalping_targets()")

        # 🔄 Запуск фонових моніторів
        if "monitor_all_open_trades" not in active_threads:
            t = threading.Thread(target=monitor_all_open_trades, daemon=True)
            t.start()
            active_threads["monitor_all_open_trades"] = t
            log_debug("monitor_all_open_trades запущено")

        if "monitor_watchlist_candidate" not in active_threads:
            t = threading.Thread(target=monitor_watchlist_candidate, daemon=True)
            t.start()
            active_threads["monitor_watchlist_candidate"] = t
            log_debug("monitor_watchlist_candidate запущено")

        symbols = get_top_symbols(limit=50)
        random.shuffle(symbols)
        log_debug(f"Монети для аналізу: {symbols}")

        watchlist_data = load_watchlist() or []

        for symbol in symbols:
            log_message(f"🎯 Аналіз {symbol}")
            snapshot = build_monitor_snapshot(symbol)
            if not snapshot:
                log_message(f"⚠️ [SKIP] {symbol} → snapshot None")
                continue

            log_debug(f"Snapshot OK для {symbol}")
            conditions = convert_snapshot_to_conditions(snapshot)
            if not conditions:
                log_message(f"⚠️ [SKIP] {symbol} → conditions None")
                continue

            log_debug(f"Conditions OK для {symbol}")

            # ✅ Нормалізація support_position
            support_position = str(conditions.get("support_position", "unknown")).lower()
            if support_position in {"null", "unknown", ""}:
                support_position = "between"

            global_trend = str(conditions.get("global_trend", "unknown")).lower()

            # ✅ Обробляємо near_support / near_resistance / between
            result = None
            side = None

            if support_position == "near_support":
                side = "LONG"
                result = check_trade_conditions_long(conditions)

            elif support_position == "near_resistance":
                side = "SHORT"
                result = check_trade_conditions_short(conditions)

            elif support_position == "between":
                # Маршрутизація за глобальним трендом — м’яко, як домовлялись
                if global_trend in ("bullish", "strong_bullish", "flat"):
                    side = "LONG"
                    result = check_trade_conditions_long(conditions)
                elif global_trend == "bearish":
                    side = "SHORT"
                    result = check_trade_conditions_short(conditions)
                else:
                    log_message(f"⛔ [SKIP] {symbol} → BETWEEN, але global_trend={global_trend}")
                    side = "LONG"  # дефолт, щоб віддати у watchlist з напрямком
                    result = {"add_to_watchlist": True, "watch_reason": f"between + unknown global_trend"}

            else:
                log_message(f"⛔ [SKIP] {symbol} → support_position={support_position}")
                continue

            log_message(f"[TRACE] check_trade_conditions({side}) → {result}")

            if isinstance(result, dict) and result.get("open_trade") in ["LONG", "SHORT"]:
                # ✅ Всі умови виконані — відкриваємо угоду
                position_side = result.get("open_trade")
                price = conditions.get("price") or conditions.get("current_price") or snapshot.get("price")
                balance = get_usdt_balance()
                execute_scalping_trade(
                    target={
                        "symbol": symbol,
                        "target_price": price,  # 👈 ключ саме target_price
                        "price": price
                    },
                    balance=balance,
                    position_side=position_side,
                    behavior_summary=None
                )
                log_message(f"🚀 [TRADE] Відкрито угоду по {symbol} ({position_side})")

            else:
                # ⏳ Умови не пройдені — додаємо у watchlist з причиною
                reason = ""
                if isinstance(result, dict) and result.get("add_to_watchlist"):
                    reason = result.get("watch_reason", "")
                    log_message(f"ℹ️ [WATCH] {symbol} → {reason}")

                already_exists = any((item.get("symbol") == symbol) for item in watchlist_data)
                if not already_exists:
                    direction = side if side in ("LONG", "SHORT") else ("LONG" if support_position == "near_support" else "SHORT")
                    add_to_watchlist(
                        symbol=symbol,
                        support_position=support_position,
                        current_price=conditions.get("current_price"),
                        side=direction
                    )
                    # 🔄 одразу оновимо локальний список, щоб не перетерти файл старими даними
                    watchlist_data.append({
                        "symbol": symbol,
                        "support_position": support_position,
                        "current_price": conditions.get("current_price"),
                        "side": direction
                    })
                    log_message(f"📥 [WATCHLIST] {symbol} додано ({support_position}/{direction})")
                else:
                    log_message(f"ℹ️ [WATCHLIST] {symbol} вже у списку → пропуск")

    except Exception as e:
        log_error(f"❌ [find_best_scalping_targets] Фатальна помилка: {e}")
        traceback.print_exc()


def execute_scalping_trade(target, balance, position_side, behavior_summary, manual_amount=None, manual_leverage=None):
    """
    🚀 Виконує реальну угоду, записує сигнал при відкритті та віддає monitor_all_open_trades у контроль
    """
    try:
        symbol = target["symbol"]
        log_debug(f"Старт execute_scalping_trade для {symbol}")

        # ⛔ антидубль: якщо інший потік вже відкриває цей символ — виходимо
        if symbol in opening_symbols:
            log_message(f"⏳ {symbol} вже відкривається іншим потоком → пропуск")
            return
        opening_symbols.add(symbol)

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

        try:
            # 🔁 фолбек балансу (на випадок, якщо викликали з balance=None)
            if balance is None:
                balance = get_usdt_balance()

            # ✅ Перевірка чи монета вже моніториться (можеш лишити як додатковий запобіжник)
            if symbol in active_threads:
                log_message(f"⚠️ {symbol} вже моніториться → пропуск")
                return

            # 🛡 Фінальна перевірка MAX_ACTIVE_TRADES перед відправкою ордера
            active_trades = load_active_trades()
            if len(active_trades) >= MAX_ACTIVE_TRADES:
                log_message(f"🛑 [SAFEGUARD] Перед відправкою ордера → вже відкрито {len(active_trades)} угод")
                return

            snapshot = build_monitor_snapshot(symbol)
            if not snapshot:
                log_error(f"❌ Snapshot для {symbol} не створено → пропуск")
                return

            conditions = convert_snapshot_to_conditions(snapshot)
            if not conditions:
                log_error(f"❌ Conditions для {symbol} не створені → пропуск")
                return

            score_data = calculate_trade_score(conditions, position_side=position_side)
            score = score_data.get("score", 0)
            signals = score_data.get("signals", {})

            log_message(f"🎯 Score={score} → відкриваємо реальну угоду")

            leverage = manual_leverage if manual_leverage is not None else (MANUAL_LEVERAGE if USE_MANUAL_LEVERAGE else 5)

            amount = (
                manual_amount
                if manual_amount is not None
                else (MANUAL_BALANCE if USE_MANUAL_BALANCE else calculate_amount_to_use(score, balance, leverage))
            )
            if amount < 5:
                log_message(f"⚠️ Сума {amount} < $5 → встановлено $5")
                amount = 5

            # 🧭 Визначення напрямку угоди
            if position_side.upper() == "LONG":
                side = "Buy"
            elif position_side.upper() == "SHORT":
                side = "Sell"
            else:
                log_error(f"❌ Невідомий напрямок position_side={position_side} → пропуск")
                return

            log_message(
                f"📤 Відправка ордера: {symbol} | Сума: {amount} | "
                f"Плече: {leverage} | Side: {side} | PositionSide: {position_side.upper()}"
            )

            executor = OrderExecutor(
                symbol=symbol,
                side=side,
                amount_to_use=amount,
                target_price=target.get("target_price"),
                position_side=position_side.upper(),
                leverage=leverage,
                bypass_price_check=True
            )
            result = executor.execute()
            if not result or "entry_price" not in result:
                log_error(f"❌ Ордер не відкрився для {symbol}")
                return

            entry_price = result["entry_price"]
            send_telegram_message(
                f"🚀 <b>Угода відкрита:</b> {symbol}\n"
                f"➡️ Напрямок: {position_side.upper()}\n"
                f"💸 Сума: {amount}\n"
                f"⚡ Плече: {leverage}x\n"
                f"🎯 Ціна входу: {entry_price}\n"
                f"📈 SCORE: {score}"
            )

            log_message(f"✅ Ордер відкрито для {symbol} @ {entry_price}")

            trade_id = f"{symbol}_{datetime.utcnow().strftime('%H%M%S')}"
            trade_record = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": position_side.upper(),
                "entry_price": entry_price,
                "amount": amount,
                "leverage": leverage,
                "opened": datetime.utcnow().isoformat(),
                "closed": False,
                "signals": make_json_safe(signals),
                "conditions": make_json_safe(conditions),
                "behavior_summary": make_json_safe(behavior_summary),
                "result_percent": None,
                "peak_pnl_percent": None,
                "worst_pnl_percent": None,
                "exit_reason": None,
                "duration": None
            }

            log_debug(f"Trade Record для {trade_id}: {json.dumps(trade_record, indent=2, ensure_ascii=False)}")
            append_active_trade(trade_record)  # ✅ Запис у ActiveTrades (файл)

            # ✅ Запис сигналу у signal_stats.json
            from utils.signal_logger import append_signal_record  # локальний імпорт, щоб не чіпати верх
            append_signal_record(trade_record)

        finally:
            # знімемо блокування символу у будь-якому випадку
            opening_symbols.discard(symbol)

    except Exception as e:
        log_error(f"❌ [execute_scalping_trade] Помилка: {e}\n{traceback.format_exc()}")



def manage_open_trade(symbol, entry_price, side, amount, leverage, behavior_summary,
                      trade_id=None, sessions=None, check_interval=1, entry_time=None, signals=None):

    """
    👁 Розширений моніторинг відкритої угоди:
    - Стандартний TP/SL
    - Часткове закриття на піку
    - Трейлінг-стоп для залишку
    """
    
    log_message(f"👁 [DEBUG] Старт manage_open_trade для {symbol} ({side}) @ {entry_price}")

    symbol_clean = symbol.split("_")[0]
    if entry_time is None:
        entry_time = datetime.now()

    is_long = side.upper() in ["LONG", "BUY"]
    entry_price = Decimal(str(entry_price))
    tp_target = Decimal(str(MANAGE_TP_PERCENT))
    sl_target = Decimal(str(MANAGE_SL_PERCENT))

    if is_long:
        take_profit = entry_price * (Decimal("1") + tp_target / Decimal(leverage))
        stop_loss = entry_price * (Decimal("1") - sl_target / Decimal(leverage))
    else:
        take_profit = entry_price * (Decimal("1") - tp_target / Decimal(leverage))
        stop_loss = entry_price * (Decimal("1") + sl_target / Decimal(leverage))

    log_message(f"🎯 TP={take_profit:.4f}, SL={stop_loss:.4f}")

    partial_closed = False
    trailing_stop_active = False
    trailing_stop_price = None
    remaining_amount = amount

    peak_pnl_percent = -9999.0
    worst_pnl_percent = 9999.0

    def finalize_trade(reason, final_price, close_amount,signals=None):
        nonlocal peak_pnl_percent, worst_pnl_percent, remaining_amount
        pnl = ((final_price - entry_price) / entry_price)
        if not is_long:
            pnl *= -1
        pnl_percent = float(pnl * leverage * 100)
        duration_seconds = (datetime.now() - entry_time).total_seconds()
        duration_str = str(timedelta(seconds=int(duration_seconds)))
        result = "WIN" if pnl_percent > 0 else "LOSS" if pnl_percent < 0 else "BREAKEVEN"

        executor = OrderExecutor(
            symbol=symbol_clean,
            side="Sell" if is_long else "Buy",
            position_side=side,
            amount_to_use=close_amount,
            leverage=leverage
        )
        if executor.close_position():
            log_message(f"✅ Часткове закриття {symbol_clean} ({reason}) на біржі")
        else:
            log_error(f"❌ НЕ ВДАЛОСЯ закрити {symbol_clean} ({reason}) на біржі")

        remaining_amount -= close_amount 

        if remaining_amount <= 0:
            update_signal_record(trade_id, {
                "closed": True,
                "close_time": datetime.utcnow().isoformat(),
                "exit_reason": reason,
                "result_percent": round(pnl_percent, 2),
                "peak_pnl_percent": round(peak_pnl_percent, 2),
                "worst_pnl_percent": round(worst_pnl_percent, 2),
                "duration": duration_str,
                "result": result
            })

            if signals:
                try:
                    log_final_trade_result(
                        symbol=symbol_clean,
                        trade_id=trade_id,
                        entry_price=float(entry_price),
                        exit_price=float(final_price),
                        result=result,
                        peak_pnl=round(peak_pnl_percent, 2),
                        worst_pnl=round(worst_pnl_percent, 2),
                        duration=duration_str,
                        exit_reason=reason,
                        snapshot=signals  # signals — це повний snapshot з conditions
                    )
                except Exception as e:
                    log_message(f"📊 Запис трейду {trade_id} завершено у signal_stats.json")

                    log_error(f"⚠️ Не вдалося записати у signal_stats: {e}")

            send_telegram_message(
                f"📴 <b>Угода завершена:</b> {symbol_clean}\n"
                f"Причина: {reason}\n"
                f"Плече: {leverage}x\n"
                f"Сума: {close_amount}\n"
                f"Результат: {result} | PnL: {round(pnl_percent, 2)}%"
            )

    try:
        while True:
            current_price = Decimal(str(get_current_futures_price(symbol_clean)))
            if not check_position_with_retry(symbol_clean, side, retries=3, delay=2):
                log_message(f"⚠️ Позиція {symbol_clean} закрита вручну на біржі → завершую моніторинг")
                finalize_trade("Manual Close", current_price, remaining_amount,signals=signals)
                break

            pnl = ((current_price - entry_price) / entry_price)
            if not is_long:
                pnl *= -1
            pnl_percent = float(pnl * leverage * 100)

            if pnl_percent > peak_pnl_percent:
                peak_pnl_percent = pnl_percent
            if pnl_percent < worst_pnl_percent:
                worst_pnl_percent = pnl_percent

            log_message(f"📡 {symbol_clean} Ціна: {current_price}, PnL: {round(pnl_percent, 2)}% "
                        f"(Peak: {round(peak_pnl_percent, 2)}%, Worst: {round(worst_pnl_percent, 2)}%)")

            # 🎯 Часткове закриття
            if not partial_closed and pnl_percent >= PARTIAL_CLOSE_TRIGGER * MANAGE_TP_PERCENT * 100:
                partial_close_amount = amount * (PARTIAL_CLOSE_PERCENT / 100)
                finalize_trade("Partial Take Profit", current_price, partial_close_amount,signals=signals)

                trailing_stop_price = current_price * (1 - TRAILING_STOP_OFFSET if is_long else 1 + TRAILING_STOP_OFFSET)
                trailing_stop_active = True
                partial_closed = True
                log_message(f"🔒 Часткове закриття {PARTIAL_CLOSE_PERCENT}% @ {current_price}, "
                            f"Трейлінг-стоп активовано @ {trailing_stop_price}")

            # 🏁 Трейлінг-стоп
            if trailing_stop_active:
                if (is_long and current_price <= trailing_stop_price) or (not is_long and current_price >= trailing_stop_price):
                    finalize_trade("Trailing Stop", current_price, remaining_amount,signals=signals)
                    break
                if (is_long and current_price > trailing_stop_price) or (not is_long and current_price < trailing_stop_price):
                    trailing_stop_price = current_price * (1 - TRAILING_STOP_OFFSET if is_long else 1 + TRAILING_STOP_OFFSET)
                    log_message(f"📈 Трейлінг-стоп оновлено @ {trailing_stop_price}")

            # 🎯 Take Profit
            if (is_long and current_price >= take_profit) or (not is_long and current_price <= take_profit):
                finalize_trade("Take Profit", current_price, remaining_amount,signals=signals)
                break

            # ⛔ Stop Loss
            if (is_long and current_price <= stop_loss) or (not is_long and current_price >= stop_loss):
                finalize_trade("Stop Loss", current_price, remaining_amount,signals=signals)
                break

            time.sleep(check_interval)

    except Exception as e:
        log_error(f"❌ [manage_open_trade] Помилка: {e}")


def adjust_risk_by_volatility(symbol, base_leverage=50):
    """
    🛡️ Адаптивне плече на основі волатильності:
    - Низька волатильність → більше плече
    - Висока волатильність → менше плече
    """
    try:
        volatility = get_volatility(symbol)

        if volatility == "very_low":
            adjusted_leverage = min(base_leverage + 20, 75)  # Додаємо плече на тихому ринку
        elif volatility == "high":
            adjusted_leverage = max(base_leverage - 20, 10)  # Зменшуємо плече на високій волатильності
        else:
            adjusted_leverage = base_leverage  # Нормальне плече

        log_message(f"⚙️ Адаптивне плече для {symbol}: {adjusted_leverage}x (волатильність: {volatility})")
        return adjusted_leverage

    except Exception as e:
        log_error(f"❌ Помилка у adjust_risk_by_volatility для {symbol}: {e}")
        return base_leverage


def load_active_trades():
    """
    📥 Завантажує ActiveTrades з JSON у форматі dict (ключ trade_id).
    Якщо файл відсутній, пустий або пошкоджений — повертає {}
    """
    try:
        if not os.path.exists(ACTIVE_TRADES_FILE):
            log_message("📂 ActiveTrades файл відсутній — створюю новий.")
            return {}

        with open(ACTIVE_TRADES_FILE, "r", encoding="utf-8") as f:
            active_trades = json.load(f)

        if isinstance(active_trades, list):
            log_error("❌ ActiveTrades у форматі list — конвертую у dict за trade_id.")
            dict_trades = {}
            for trade in active_trades:
                trade_id = trade.get("trade_id") or f"{trade.get('symbol', 'UNKNOWN')}_{datetime.utcnow().timestamp()}"
                dict_trades[trade_id] = trade
            return dict_trades

        if not isinstance(active_trades, dict):
            log_error("❌ ActiveTrades має некоректний формат (очікується dict). Скидання.")
            return {}

        return active_trades

    except Exception as e:
        log_error(f"❌ load_active_trades: помилка завантаження → {e}")
        return {}


# Список активних потоків по символах
active_threads = {}

def monitor_all_open_trades():
    """
    🔄 Безперервно моніторить всі відкриті угоди напряму з біржі (Bybit API).
    Синхронізує ActiveTrades.json у спрощеному форматі: symbol, side, opened_at.
    """
    log_message("🚦 [DEBUG] Старт monitor_all_open_trades() (LIVE API)")

    def monitor_trade_thread(trade_id, trade):
        try:
            symbol = trade.get("symbol")
            entry_price = trade.get("entry_price")
            side = trade.get("side", "LONG")
            amount = trade.get("amount", 0)
            leverage = trade.get("leverage", 10)
            summary = trade.get("behavior_summary", {})
            sessions = trade.get("monitoring_sessions", [])

            log_message(f"👁 [DEBUG] Старт моніторингу угоди {symbol}")

            manage_open_trade(
            symbol, entry_price, side, amount, leverage, summary, trade_id, sessions
        )

        except Exception as e:
            log_error(f"❌ monitor_trade_thread({trade_id}): {e}")
        finally:
            active_threads.pop(trade_id, None)
            log_message(f"🧹 Потік моніторингу {trade_id} завершено та видалено з active_threads")

    while True:
        try:
            # 🛡️ Отримуємо всі відкриті позиції напряму з біржі
            response = bybit.get_positions(category="linear", settleCoin="USDT")
            positions = response.get("result", {}).get("list", [])
            
            # ⏳ Якщо API вернуло пусто, робимо ще 3 спроби перед оновленням ActiveTrades
            retry_attempts = 3
            if len(positions) == 0:
                for attempt in range(1, retry_attempts + 1):
                    time.sleep(2)
                    response = bybit.get_positions(category="linear", settleCoin="USDT")
                    positions = response.get("result", {}).get("list", [])
                    if len(positions) > 0:
                        log_debug(f"Позиції знайдено на спробі {attempt}")
                        break

            live_trades = {}
            simple_trades = {}
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            for pos in positions:
                size = float(pos.get("size", 0))
                if size > 0:
                    symbol = pos.get("symbol")
                    trade_id = f"{symbol}_{pos.get('positionIdx', '0')}"
                    entry_price = float(pos.get("avgPrice", 0))
                    leverage = int(pos.get("leverage", 1))
                    side = pos.get("positionSide", "").upper()
                    if not side:
                        side = "LONG" if pos.get("side", "").upper() == "BUY" else "SHORT"


                    live_trades[trade_id] = {
                        "symbol": symbol,
                        "entry_price": entry_price,
                        "side": side,
                        "amount": size,
                        "leverage": leverage,
                        "behavior_summary": {
                            "entry_reason": "LIVE_MONITOR",
                            "score": 0,
                            "signals": {}
                        },
                        "monitoring_sessions": []
                    }

                    # 📝 Спрощений запис для ActiveTrades.json
                    simple_trades[trade_id] = {
                        "symbol": symbol,
                        "side": side,
                        "opened_at": current_time
                    }

            # 📦 Оновлюємо ActiveTrades.json (спрощений формат)
            try:
                with open(ACTIVE_TRADES_FILE, "w", encoding="utf-8") as f:
                    json.dump(simple_trades, f, indent=2, ensure_ascii=False)
                log_debug(f"ActiveTrades.json оновлено ({len(simple_trades)} угод)")
            except Exception as e:
                log_error(f"❌ [monitor_all_open_trades] Помилка при записі ActiveTrades.json: {e}")

            # 🚀 Стартуємо моніторинг для кожної угоди
            for trade_id, trade in live_trades.items():
                if trade_id not in active_threads:
                    log_debug(f"Запуск моніторингу для {trade_id} (API)")
                    t = threading.Thread(
                        target=monitor_trade_thread,
                        args=(trade_id, trade),
                        daemon=True
                    )
                    t.start()
                    active_threads[trade_id] = t
                else:
                    log_debug(f"{trade_id} вже моніториться")

        except Exception as e:
            log_error(f"❌ monitor_all_open_trades (API): {e}")

        time.sleep(2)
