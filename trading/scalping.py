# scalping.py

from trading.executor import round_qty_bybit
import time
from analysis.indicators import get_volatility,analyze_support_resistance
import traceback
from utils.tools import check_position_with_retry
from datetime import datetime, timedelta
from trading.executor import get_current_futures_price
from utils.logger import log_message, log_error, log_debug
from trading.executor import OrderExecutor
from trading.risk import calculate_amount_to_use
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
import random
import numpy as np
from utils.signal_logger import log_final_trade_result
from uuid import uuid4
from utils.logger import mark_trade_closed, remove_active_trade, prune_inactive_trades, _at_safe_load



# ---- OpenTrades helpers (рахуємо лише незакриті) ----------------------------
def get_open_trades_count() -> int:
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            return sum(1 for t in trades.values() if not t.get("closed"))
        elif isinstance(trades, list):
            return sum(1 for t in trades if isinstance(t, dict) and not t.get("closed"))
    except Exception as e:
        log_error(f"[get_open_trades_count] {e}")
    return 0

def has_open_trade_for(symbol: str) -> bool:
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            for rec in trades.values():
                if rec.get("symbol") == symbol and not rec.get("closed"):
                    return True
        elif isinstance(trades, list):
            for rec in trades:
                if isinstance(rec, dict) and rec.get("symbol") == symbol and not rec.get("closed"):
                    return True
    except Exception as e:
        log_error(f"[has_open_trade_for] {e}")
    return False



ACTIVE_TRADES_FILE_SIMPLE = "data/ActiveTradesSimple.json"

# === реєстри потоків ===
active_threads = {}   # потоки конкретних угод (ключ = trade_id)
bg_threads = {}       # фонові демони: monitor_all_open_trades, monitor_watchlist_candidate



SIDE_BUY = "Buy"
SIDE_SELL = "Sell"
# 🔒 Набір символів, які прямо зараз відкриваються (антидубль)
opening_symbols = set()


RECENT_SCALPING_FILE = "data/recent_scalping.json"

# ===================== COMPAT / ADAPTER LAYER =====================
# Все нижче — безпечні адаптери під твій OrderExecutor + Bybit клієнт.
# Вони знімають помилки "is not defined" і працюють з твоїм API.

# -- helpers
def _symbol_clean(s: str) -> str:
    return str(s).split("_")[0]

# ---- ActiveTrades accessors -------------------------------------------------
def get_active_trade(trade_id: str):
    """
    Повертає один трейд з load_active_trades() (який у тебе вже є).
    """
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            return trades.get(trade_id)
        elif isinstance(trades, list):
            for t in trades:
                if isinstance(t, dict) and t.get("trade_id") == trade_id:
                    return t
    except Exception as e:
        log_error(f"[compat] get_active_trade error: {e}")
    return None

def update_active_trade(trade_id: str, patch: dict):
    """
    Акуратно оновлює запис у ActiveTrades: якщо є утиліти mark/remove/append — користуємось ними.
    Інакше — робимо ручний фолбек (видалити + додати назад).
    """
    try:
        current = get_active_trade(trade_id)
        if not current:
            log_message(f"[compat] update_active_trade: {trade_id} not found (noop)")
            return False
        current.update(patch or {})
        # якщо є прямий апдейтер у utils.logger — спробуємо ним
        try:
            from utils.logger import update_active_trade as _real_upd  # type: ignore
            _real_upd(trade_id, current)
            return True
        except Exception:
            pass
        # фолбек: remove -> append
        if 'remove_active_trade' in globals():
            try: remove_active_trade(trade_id)
            except Exception: pass
        if 'append_active_trade' in globals():
            try: append_active_trade(current)
            except Exception: pass
        return True
    except Exception as e:
        log_error(f"[compat] update_active_trade fallback error: {e}")
        return False

def place_or_update_tp(symbol: str, side: str, quantity: float, avg_entry: float, tp_from_avg_pct: float):
    """
    Якщо USE_EXCHANGE_TP=False — нічого не робимо (bot-only).
    Якщо True — ставимо ReduceOnly Limit (IOC/PostOnly) з підгонкою qty.
    """
    try:
        from config import USE_EXCHANGE_TP, TP_USE_IOC
    except Exception:
        USE_EXCHANGE_TP, TP_USE_IOC = False, False

    if not USE_EXCHANGE_TP:
        return None  # bot-only режим

    # --- далі код якщо колись увімкнеш біржовий TP ---
    symbol_clean = symbol.split("_")[0]
    side_u = side.upper()
    is_long = side_u in ("LONG","BUY")
    tp_price = float(avg_entry) * (1.0 + tp_from_avg_pct if is_long else 1.0 - tp_from_avg_pct)
    close_side = "Sell" if is_long else "Buy"
    pos_side   = "LONG" if is_long else "SHORT"

    rounded_qty = round_qty_bybit(symbol_clean, float(quantity))
    tif = "IOC" if TP_USE_IOC else "PostOnly"

    resp = bybit.place_order(
        category="linear",
        symbol=symbol_clean,
        side=close_side,
        positionSide=pos_side,
        orderType="Limit",
        qty=str(rounded_qty),
        price=str(tp_price),
        reduceOnly=True,
        timeInForce=tif
    )
    if resp.get("retCode") == 0:
        oid = resp.get("result", {}).get("orderId")
        log_message(f"🎯 [TP] {symbol_clean} {side_u} qty={rounded_qty} @ {tp_price:.6f} (orderId={oid})")
        return oid
    else:
        log_error(f"⚠️ [TP] Bybit error: {resp}")
        return None


# ---- Liq buffer check (консервативно) --------------------------------------
def has_liq_buffer_after_add(symbol: str, side: str, extra_qty: float, min_buffer: float, leverage: int):
    """
    Оцінює запас до ліквідації ПОТОЧНОЇ позиції і порівнює з порогом.
    Якщо Bybit віддає liqPrice — використовуємо її; якщо ні, робимо м'який True.
    """
    try:
        symbol_clean = _symbol_clean(symbol)
        resp = bybit.get_positions(category="linear", symbol=symbol_clean)
        lst = resp.get("result", {}).get("list", [])
        if not lst:
            log_message("[compat] has_liq_buffer_after_add: no positions → True")
            return True

        mark_price = float(get_current_futures_price(symbol_clean) or 0.0)
        if mark_price <= 0:
            return True

        side_u = side.upper()
        # беремо першу релевантну позицію
        for pos in lst:
            size = float(pos.get("size", 0) or 0)
            if size <= 0: 
                continue
            pos_side = str(pos.get("side", "")).upper()  # BUY / SELL
            if (side_u in ("LONG","BUY") and pos_side != "BUY") or (side_u in ("SHORT","SELL") and pos_side != "SELL"):
                continue
            liq = pos.get("liqPrice") or pos.get("liq_price") or pos.get("liqPrice_e")
            if liq is None:
                # нема точного ліквіда, не блочимо
                log_message("[compat] liqPrice not available → allow add (permissive)")
                return True
            liq = float(liq)
            if side_u in ("LONG","BUY"):
                buf = (mark_price - liq) / mark_price
            else:
                buf = (liq - mark_price) / mark_price
            ok = (buf >= float(min_buffer))
            log_message(f"[compat] has_liq_buffer_after_add: buf={buf:.3f} vs min={min_buffer:.3f} → {ok}")
            return ok

        return True
    except Exception as e:
        log_error(f"[compat] has_liq_buffer_after_add error: {e}")
        return True


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

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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

        if "monitor_all_open_trades" not in bg_threads:
            t = threading.Thread(target=monitor_all_open_trades, daemon=True)
            t.start()
            bg_threads["monitor_all_open_trades"] = t
            log_debug("monitor_all_open_trades запущено")

        if "monitor_watchlist_candidate" not in bg_threads:
            t = threading.Thread(target=monitor_watchlist_candidate, daemon=True)
            t.start()
            bg_threads["monitor_watchlist_candidate"] = t
            log_debug("monitor_watchlist_candidate запущено")


        symbols = get_top_symbols(limit=20)
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
    🚀 Відкрити реальну угоду та ініціалізувати Smart Averaging (DCA)
    - НІЯКИХ дублюючих біржових функцій у цьому файлі
    - Всі біржові дії — тільки через executor.OrderExecutor
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
            # 🔁 фолбек балансу
            if balance is None:
                balance = get_usdt_balance()

            # 🛡 ліміт активних угод (рахуємо лише незакриті)
            if get_open_trades_count() >= MAX_ACTIVE_TRADES:
                log_message(f"🛑 [SAFEGUARD] Ліміт досягнуто: {get_open_trades_count()} ≥ {MAX_ACTIVE_TRADES}")
                return

            # 🛡 антидубль по символу (якщо вже є активна угода по цьому символу)
            if has_open_trade_for(symbol):
                log_message(f"⏳ [SAFEGUARD] Вже є відкрита угода по {symbol} → пропуск")
                return


            # 🧭 напрямок
            side_norm = (position_side or "").upper()
            if side_norm == "LONG":
                side = "Buy"
            elif side_norm == "SHORT":
                side = "Sell"
            else:
                log_error(f"❌ Невідомий напрямок position_side={position_side} → пропуск")
                return

            # 🧱 signals/conditions
            conditions = None
            if isinstance(behavior_summary, dict):
                maybe_signals = behavior_summary.get("signals")
                if isinstance(maybe_signals, dict) and maybe_signals:
                    conditions = maybe_signals

            if not conditions:
                snapshot = build_monitor_snapshot(symbol)
                if not snapshot:
                    log_error(f"❌ Snapshot для {symbol} не створено → пропуск")
                    return
                conditions = convert_snapshot_to_conditions(snapshot)
                if not conditions:
                    log_error(f"❌ Conditions для {symbol} не створені → пропуск")
                    return

            # 🎯 SCORE → тільки для sizing
            score = 0.0
            if isinstance(behavior_summary, dict):
                try:
                    score = float(behavior_summary.get("score", 0.0) or 0.0)
                except Exception:
                    score = 0.0
            if score == 0.0:
                score = 6.0  # нейтральний дефолт

            # ⚙️ плечe/сума
            try:
                from config import SMART_AVG
            except Exception:
                SMART_AVG = {}

            leverage = (
                manual_leverage
                if manual_leverage is not None
                else (MANUAL_LEVERAGE if USE_MANUAL_LEVERAGE else SMART_AVG.get("leverage", 5))
            )
            amount = (
                manual_amount
                if manual_amount is not None
                else (MANUAL_BALANCE if USE_MANUAL_BALANCE else calculate_amount_to_use(score, balance, leverage))
            )
            if amount < 5:
                log_message(f"⚠️ Сума {amount} < $5 → встановлено $5")
                amount = 5

            # 🎯 Цільова ціна
            target_price = target.get("target_price")
            if target_price is None:
                target_price = (
                    conditions.get("price")
                    or conditions.get("current_price")
                    or get_current_futures_price(symbol)
                )

            log_message(
                f"📤 Відправка ордера: {symbol} | Сума(маржа): {amount} | "
                f"Плече: {leverage} | Side: {side} | PositionSide: {side_norm}"
            )

            # ❗ Всі біржові дії — через OrderExecutor
            executor = OrderExecutor(
                symbol=symbol,
                side=side,
                amount_to_use=amount,
                target_price=target_price,
                position_side=side_norm,
                leverage=leverage,
                bypass_price_check=True
            )
            result = executor.execute()
            if not result or "entry_price" not in result:
                log_error(f"❌ Ордер не відкрився для {symbol}")
                return

            entry_price = float(result["entry_price"])
            # Якщо executor не повертає qty — оцінюємо (для внутр. стейту DCA)
            filled_qty = float(result.get("quantity") or 0.0)
            if filled_qty <= 0:
                filled_qty = amount * leverage / entry_price

            send_telegram_message(
                f"🚀 <b>Угода відкрита:</b> {symbol}\n"
                f"➡️ Напрямок: {side_norm}\n"
                f"💸 Сума (маржа): {amount}\n"
                f"⚡ Плече: {leverage}x\n"
                f"🎯 Ціна входу: {entry_price}\n"
                f"📈 SCORE: {round(score, 2)}"
            )
            log_message(f"✅ Ордер відкрито для {symbol} @ {entry_price}")

            # 🗃️ trade_id
            ts = datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')
            trade_id = f"{symbol}_{ts}_{uuid4().hex[:6]}"

            decision_summary = {
                "score": float(score),
                "source": ("watchlist" if isinstance(behavior_summary, dict) and str(behavior_summary.get("entry_reason", "")).startswith("WATCHLIST") else "finbest"),
                "note": "No TradeScore; amount derived from decision score/default",
            }

            # ====================== SMART AVERAGING (DCA) INIT ======================
            dca_enabled = bool(SMART_AVG.get("enabled", True))
            max_adds = int(SMART_AVG.get("max_adds", 5))
            dca_step_pct = float(SMART_AVG.get("dca_step_pct", 0.045))
            dca_mode = str(SMART_AVG.get("dca_mode", "equal"))
            dca_factor = float(SMART_AVG.get("dca_factor", 1.2))
            tp_from_avg_pct = float(SMART_AVG.get("tp_from_avg_pct", 0.01))
            alt_tp_from_avg_pct = float(SMART_AVG.get("alt_tp_from_avg_pct", 0.02))
            max_margin_per_trade = float(SMART_AVG.get("max_margin_per_trade", 600.0))
            min_liq_buffer = float(SMART_AVG.get("min_liq_buffer", 0.40))
            atr_pause_pct = float(SMART_AVG.get("atr_pause_pct", 0.10))
            trend_flip_cut_pct = float(SMART_AVG.get("trend_flip_cut_pct", 0.40))
            cooldown_min = int(SMART_AVG.get("cooldown_min", 20))

            avg_entry = entry_price
            adds_done = 0
            total_margin_used = float(amount)
            total_qty = filled_qty

            # Перший TP (для логіки; біржу не чіпаємо)
            tp_price = avg_entry * (1.0 + tp_from_avg_pct) if side_norm == "LONG" else avg_entry * (1.0 - tp_from_avg_pct)

            trade_record = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side_norm,
                "entry_price": entry_price,
                "amount": amount,                 # стартова маржа
                "leverage": leverage,
                "opened": datetime.utcnow().isoformat(),
                "closed": False,
                "signals": make_json_safe(decision_summary),
                "conditions": make_json_safe(conditions),
                "behavior_summary": make_json_safe(behavior_summary),
                "result_percent": None,
                "peak_pnl_percent": None,
                "worst_pnl_percent": None,
                "exit_reason": None,
                "duration": None,

                # >>> DCA state <<<
                "smart_avg": {
                    "enabled": dca_enabled,
                    "avg_entry": avg_entry,
                    "adds_done": adds_done,
                    "max_adds": max_adds,
                    "dca_step_pct": dca_step_pct,
                    "dca_mode": dca_mode,
                    "dca_factor": dca_factor,
                    "tp_from_avg_pct": tp_from_avg_pct,
                    "alt_tp_from_avg_pct": alt_tp_from_avg_pct,
                    "tp_price": tp_price,
                    "tp_order_id": None,  # біржовий TP не ставимо (bot-only)
                    "total_margin_used": total_margin_used,
                    "total_qty": total_qty,
                    "max_margin_per_trade": max_margin_per_trade,
                    "min_liq_buffer": min_liq_buffer,
                    "atr_pause_pct": atr_pause_pct,
                    "trend_flip_cut_pct": trend_flip_cut_pct,
                    "cooldown_min": cooldown_min
                }
            }

            # ✅ активні трейди + лог
            from utils.logger import append_active_trade
            append_active_trade(trade_record)

            from utils.signal_logger import append_signal_record
            append_signal_record(trade_record)

            try:
                if 'update_active_trade' in globals():
                    update_active_trade(trade_id, trade_record)
            except Exception:
                pass

        finally:
            opening_symbols.discard(symbol)

    except Exception as e:
        log_error(f"❌ [execute_scalping_trade] Помилка: {e}\n{traceback.format_exc()}")


def manage_open_trade(symbol, entry_price, side, amount, leverage, behavior_summary,
                      trade_id=None, sessions=None, check_interval=1, entry_time=None, signals=None):
    """
    👁 Smart Averaging (DCA) моніторинг відкритої угоди — BOT-ONLY TP:
    - Без SL.
    - TP рахується від СЕРЕДНЬОЇ (avg_entry) на +tp_from_avg_pct (LONG) / -tp_from_avg_pct (SHORT)
    - Докупки по кроку dca_step_pct від avg_entry з перерахунком середньої та пересуванням TP
    - Ніяких прямых bybit-викликів у цьому файлі — лише OrderExecutor з executor.py
    """
    log_message(f"👁 [DCA] Старт manage_open_trade для {symbol} ({side}) @ {entry_price}")

    symbol_clean = str(symbol).split("_")[0]
    if entry_time is None:
        entry_time = datetime.now()

    is_long = side.upper() in ["LONG", "BUY"]
    entry_price = Decimal(str(entry_price))

    # ===== Конфіг =====
    try:
        from config import SMART_AVG, TP_EPSILON,USE_EXCHANGE_TP
    except Exception:
        SMART_AVG = {}
        TP_EPSILON = 0.0007
        USE_EXCHANGE_TP = False  # за замовчуванням — BOT-only

    dca_enabled           = bool(SMART_AVG.get("enabled", True))
    base_margin           = float(SMART_AVG.get("base_margin", float(amount or 0.0) or 100.0))
    max_adds              = int(SMART_AVG.get("max_adds", 5))
    dca_step_pct          = float(SMART_AVG.get("dca_step_pct", 0.045))
    dca_mode              = str(SMART_AVG.get("dca_mode", "equal"))
    dca_factor            = float(SMART_AVG.get("dca_factor", 1.2))
    tp_from_avg_pct       = float(SMART_AVG.get("tp_from_avg_pct", 0.01))
    alt_tp_from_avg_pct   = float(SMART_AVG.get("alt_tp_from_avg_pct", 0.02))
    max_margin_per_trade  = float(SMART_AVG.get("max_margin_per_trade", (float(amount or 0.0) + 500.0)))
    min_liq_buffer        = float(SMART_AVG.get("min_liq_buffer", 0.40))
    atr_pause_pct         = float(SMART_AVG.get("atr_pause_pct", 0.10))
    trend_flip_cut_pct    = float(SMART_AVG.get("trend_flip_cut_pct", 0.0))
    cooldown_min          = int(SMART_AVG.get("cooldown_min", 20))

    # ===== Стан DCA з ActiveTrades (якщо є) =====
    smart = None
    try:
        if trade_id and 'get_active_trade' in globals():
            tr = get_active_trade(trade_id)
            if tr and isinstance(tr, dict):
                smart = tr.get("smart_avg")
    except Exception as e:
        log_error(f"⚠️ Не вдалося отримати active_trade для {trade_id}: {e}")

    if not smart:
        try:
            init_qty = (float(amount) * float(leverage)) / float(entry_price)
        except Exception:
            init_qty = 0.0
        smart = {
            "enabled": dca_enabled,
            "avg_entry": float(entry_price),
            "adds_done": 0,
            "max_adds": max_adds,
            "dca_step_pct": dca_step_pct,
            "dca_mode": dca_mode,
            "dca_factor": dca_factor,
            "tp_from_avg_pct": tp_from_avg_pct,
            "alt_tp_from_avg_pct": alt_tp_from_avg_pct,
            "tp_price": float(entry_price * (Decimal("1")+Decimal(str(tp_from_avg_pct)) if is_long else Decimal("1")-Decimal(str(tp_from_avg_pct)))),
            "tp_order_id": None,  # біржовий TP не використовуємо (якщо USE_EXCHANGE_TP=False)
            "total_margin_used": float(amount or 0.0),
            "total_qty": init_qty,
            "max_margin_per_trade": max_margin_per_trade,
            "min_liq_buffer": min_liq_buffer,
            "atr_pause_pct": atr_pause_pct,
            "trend_flip_cut_pct": trend_flip_cut_pct,
            "cooldown_min": cooldown_min
        }

    # Локальні змінні
    avg_entry = Decimal(str(smart.get("avg_entry", float(entry_price))))
    adds_done = int(smart.get("adds_done", 0))
    total_margin_used = float(smart.get("total_margin_used", float(amount or 0.0)))
    total_qty = float(smart.get("total_qty", 0.0))
    tp_price = Decimal(str(smart.get("tp_price", float(avg_entry * (Decimal("1")+Decimal(str(tp_from_avg_pct)) if is_long else Decimal("1")-Decimal(str(tp_from_avg_pct)))))))
    tp_order_id = smart.get("tp_order_id")

    # --- анти-спам між докупками (сек) ---
    MIN_SECONDS_BETWEEN_ADDS = int(SMART_AVG.get("min_seconds_between_adds", 45))
    _last_add_ts = 0.0


    peak_pnl_percent = -9999.0
    worst_pnl_percent =  9999.0
    trade_closed = False

    def save_state():
        if not trade_id:
            return
        smart["avg_entry"] = float(avg_entry)
        smart["adds_done"] = int(adds_done)
        smart["total_margin_used"] = float(total_margin_used)
        smart["total_qty"] = float(total_qty)
        smart["tp_price"] = float(tp_price)
        smart["tp_order_id"] = tp_order_id
        try:
            if 'update_active_trade' in globals():
                update_active_trade(trade_id, {"smart_avg": smart})
        except Exception as e:
            log_error(f"⚠️ update_active_trade failed для {trade_id}: {e}")

    def calc_tp_from_avg():
        return avg_entry * (Decimal("1")+Decimal(str(tp_from_avg_pct)) if is_long else Decimal("1")-Decimal(str(tp_from_avg_pct)))

    def next_dca_price():
        step = Decimal(str(dca_step_pct))
        return avg_entry * (Decimal("1")-step if is_long else Decimal("1")+step)

    def price_ok_for_dca(cur):
        return (cur <= next_dca_price()) if is_long else (cur >= next_dca_price())

    def finalize_trade(reason, final_price):
        nonlocal peak_pnl_percent, worst_pnl_percent, trade_closed, total_qty

        if trade_closed:
            log_debug(f"⏭ finalize_trade вже викликано раніше для {symbol_clean} → скіп")
            return

        pnl = ((final_price - avg_entry) / avg_entry)
        if not is_long:
            pnl *= -1
        pnl_percent = float(pnl * Decimal(str(leverage)) * Decimal("100"))
        duration_seconds = (datetime.now() - entry_time).total_seconds()
        duration_str = str(timedelta(seconds=int(duration_seconds)))
        result = "WIN" if pnl_percent > 0 else "LOSS" if pnl_percent < 0 else "BREAKEVEN"

        # Закриття ВСІЄЇ позиції через OrderExecutor (market reduceOnly)
        executor = OrderExecutor(
            symbol=symbol_clean,
            side=("Sell" if is_long else "Buy"),
            position_side=side,
            leverage=leverage,
            amount_to_use=0.0,          # ← обов’язково
            bypass_price_check=True 
        )
        closed_ok = False
        try:
            closed_ok = bool(executor.close_position())
        except Exception as e:
            log_error(f"❌ close_position exception для {symbol_clean}: {e}")
            closed_ok = False

        if not closed_ok:
            log_error(f"❌ НЕ ВДАЛОСЯ закрити {symbol_clean} ({reason}) → залишаємо моніторинг")
            return

        trade_closed = True
        total_qty = 0.0

        try:
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
        except Exception:
            pass

        try:
            if signals:
                log_final_trade_result(
                    symbol=symbol_clean,
                    trade_id=trade_id,
                    entry_price=float(avg_entry),
                    exit_price=float(final_price),
                    result=result,
                    peak_pnl=round(peak_pnl_percent, 2),
                    worst_pnl=round(worst_pnl_percent, 2),
                    duration=duration_str,
                    exit_reason=reason,
                    snapshot=signals
                )
        except Exception as e:
            log_message(f"📊 Запис трейду {trade_id} завершено у signal_stats.json (fallback ok)")
            log_error(f"⚠️ Не вдалося записати у signal_stats: {e}")

        send_telegram_message(
            f"📴 <b>Угода завершена:</b> {symbol_clean}\n"
            f"Причина: {reason}\n"
            f"Плече: {leverage}x\n"
            f"Результат: {result} | PnL: {round(pnl_percent, 2)}%"
        )

        try:
            if trade_id:
                mark_trade_closed(trade_id, {
                    "exit_reason": reason,
                    "result_percent": round(pnl_percent, 2),
                    "closed": True,
                    "close_time": datetime.utcnow().isoformat()
                })
                remove_active_trade(trade_id)
        except Exception as e:
            log_error(f"⚠️ Не вдалося оновити ActiveTrades для {trade_id}: {e}")

    # ===== Початковий TP — ТІЛЬКИ лог (на біржу не штовхаємо, якщо USE_EXCHANGE_TP=False) =====
    if not tp_order_id:
        try:
            tp_price = calc_tp_from_avg()
            if USE_EXCHANGE_TP and 'place_or_update_tp' in globals() and float(total_qty) > 0:
                # якщо колись захочеш — можна увімкнути прапорець у config.py
                tp_order_id = place_or_update_tp(
                    symbol=symbol_clean,
                    side=side,
                    quantity=total_qty,
                    avg_entry=float(avg_entry),
                    tp_from_avg_pct=float(tp_from_avg_pct)
                )
                log_message(f"🎯 [DCA] Біржовий TP встановлено {symbol_clean} {side}: {float(tp_price):.6f} (qty≈{total_qty:.6f})")
            else:
                log_message(f"ℹ️ [DCA] Плановий TP (bot-only) {symbol_clean} {side}: {float(tp_price):.6f} (qty≈{total_qty:.6f})")
        except Exception as _tp_err:
            log_message(f"⚠️ Не вдалося поставити TP: {type(_tp_err).__name__}: {_tp_err}")
    save_state()

    # ===== Основний цикл =====
    try:
        while True:
            current_price = Decimal(str(get_current_futures_price(symbol_clean)))

            # якщо позиція зникла на біржі → фіналізація
            if not check_position_with_retry(symbol_clean, side, retries=3, delay=2):
                log_message(f"⚠️ Позиція {symbol_clean} закрита вручну на біржі → завершую моніторинг")
                finalize_trade("Manual Close", current_price)
                break

            # PnL від середньої
            pnl = ((current_price - avg_entry) / avg_entry)
            if not is_long:
                pnl *= -1
            pnl_percent = float(pnl * Decimal(str(leverage)) * Decimal("100"))

            if pnl_percent > peak_pnl_percent:
                peak_pnl_percent = pnl_percent
            if pnl_percent < worst_pnl_percent:
                worst_pnl_percent = pnl_percent

            log_message(
                f"📡 [DCA] {symbol_clean} Ціна: {current_price}, PnL(avg): {round(pnl_percent, 2)}% "
                f"(Peak: {round(peak_pnl_percent, 2)}%, Worst: {round(worst_pnl_percent, 2)}%) "
                f"| avg={float(avg_entry):.6f}, adds={adds_done}/{max_adds}"
            )

            # ====== BOT-ONLY TP з ε-допуском ======
            tp_price = calc_tp_from_avg()
            eps = Decimal(str(TP_EPSILON))
            hit_tp = (
                (is_long  and current_price >= (tp_price * (Decimal("1") - eps))) or
                ((not is_long) and current_price <= (tp_price * (Decimal("1") + eps)))
            )
            if hit_tp:
                log_message(f"⚑ [HIT_TP] {symbol_clean} {side}: {float(current_price):.6f} vs TP {float(tp_price):.6f}")
                finalize_trade("Take Profit (soft)", current_price)
                break

            # ====== DCA: докупка ======
            if dca_enabled and adds_done < max_adds and price_ok_for_dca(current_price):
                # пауза між докупками (анти-спам)
                now_ts = time.time()
                if now_ts - _last_add_ts < MIN_SECONDS_BETWEEN_ADDS:
                    log_debug(f"[DCA] skip add: {now_ts - _last_add_ts:.1f}s < {MIN_SECONDS_BETWEEN_ADDS}s")
                    time.sleep(check_interval)
                    continue

                if atr_pause_pct > 0:
                    try:
                        snapshot = build_monitor_snapshot(symbol_clean)
                        cond = convert_snapshot_to_conditions(snapshot) if snapshot else {}
                        atrp = float(cond.get("atr_percent") or 0.0)
                        if atrp and atrp >= (atr_pause_pct * 100.0):
                            log_message(f"⏸ [DCA] ATR%={atrp:.2f} вище порогу ({atr_pause_pct*100:.0f}%) → пауза докупки")
                            time.sleep(check_interval)
                            continue
                    except Exception:
                        pass

                # Розмір додатку в маржі
                add_margin = base_margin * (dca_factor ** adds_done) if dca_mode == "progressive" else base_margin

                # Ліміт маржі
                if (total_margin_used + add_margin) > max_margin_per_trade:
                    log_message(f"🛑 [DCA] max_margin_per_trade досягнуто ({total_margin_used + add_margin:.2f} > {max_margin_per_trade:.2f}) → докупка скасована")
                    time.sleep(check_interval)
                    continue

                # Буфер до ліквідації (якщо є util)
                can_add = True
                if min_liq_buffer > 0 and 'has_liq_buffer_after_add' in globals():
                    try:
                        approx_qty = float(add_margin) * float(leverage) / float(current_price)
                        can_add = bool(has_liq_buffer_after_add(symbol_clean, side, approx_qty, min_liq_buffer, leverage))
                    except Exception:
                        can_add = True
                if not can_add:
                    log_message(f"🛑 [DCA] Недостатній буфер до ліквідації → докупка скасована")
                    time.sleep(check_interval)
                    continue

                # Надсилаємо докупку через OrderExecutor
                executor = OrderExecutor(
                    symbol=symbol_clean,
                    side=("Buy" if is_long else "Sell"),
                    position_side=side,
                    amount_to_use=float(add_margin),
                    leverage=leverage,
                    target_price=float(current_price)
                )
                ok = False
                fill_price = float(current_price)
                filled_qty = 0.0
                try:
                    res = executor.execute()
                    ok = bool(res and res.get("entry_price"))
                    if ok:
                        fill_price = float(res["entry_price"])
                        filled_qty = float(res.get("quantity") or (add_margin * leverage / fill_price))
                except Exception as e:
                    log_error(f"❌ [DCA] execute() помилка для {symbol_clean}: {e}")

                if not ok:
                    log_message(f"⚠️ [DCA] Докупка не пройшла для {symbol_clean}")
                    time.sleep(check_interval)
                    continue

                # Перерахунок середньої
                prev_qty = total_qty
                prev_avg = float(avg_entry)
                total_qty = prev_qty + filled_qty
                if total_qty <= 0:
                    log_error(f"❌ [DCA] Аномалія total_qty <= 0 після докупки")
                    time.sleep(check_interval)
                    continue
                avg_entry = Decimal(str((prev_avg * prev_qty + fill_price * filled_qty) / total_qty))
                total_margin_used += float(add_margin)
                adds_done += 1
                _last_add_ts = now_ts

                # Оновлене планове TP (на біржу — лише за бажанням прапорця)
                tp_price = calc_tp_from_avg()
                if USE_EXCHANGE_TP and 'place_or_update_tp' in globals():
                    try:
                        tp_order_id = place_or_update_tp(
                            symbol=symbol_clean,
                            side=side,
                            quantity=total_qty,
                            avg_entry=float(avg_entry),
                            tp_from_avg_pct=float(tp_from_avg_pct)
                        )
                        log_message(f"🎯 [DCA] Біржовий TP оновлено {symbol_clean} {side}: {float(tp_price):.6f} (qty≈{total_qty:.6f})")
                    except Exception as _tp_err:
                        log_message(f"⚠️ [DCA] Не вдалося оновити TP: {type(_tp_err).__name__}: {_tp_err}")
                else:
                    log_message(f"ℹ️ [DCA] Новий плановий TP (bot-only): {float(tp_price):.6f}")

                save_state()

                send_telegram_message(
                    f"➕ <b>DCA додано</b> {symbol_clean}\n"
                    f"Сходинка: {adds_done}/{max_adds}\n"
                    f"Fill: {fill_price}\n"
                    f"Нова середня: {float(avg_entry):.6f}\n"
                    f"Новий TP: {float(tp_price):.6f}"
                )

            # ===== Опційний cut при розвороті тренду (частковий) =====
            if trend_flip_cut_pct > 0:
                try:
                    snapshot = build_monitor_snapshot(symbol_clean)
                    cond = convert_snapshot_to_conditions(snapshot) if snapshot else {}
                    gtrend = str(cond.get("global_trend", "")).lower()
                    flip_bad = (is_long and gtrend in {"bearish", "strong_bearish"}) or ((not is_long) and gtrend in {"bullish", "strong_bullish"})
                    if flip_bad and total_qty > 0:
                        cut_qty = total_qty * float(trend_flip_cut_pct)
                        try:
                            ex = OrderExecutor(
                                symbol=symbol_clean,
                                side=("Sell" if is_long else "Buy"),
                                position_side=side,
                                leverage=leverage,
                                amount_to_use=0.0,
                                bypass_price_check=True
                            )
                            # часткове закриття лише якщо така функція є в executor.py
                            if hasattr(ex, "close_position_qty"):
                                ok_cut = bool(ex.close_position_qty(cut_qty))
                                if ok_cut:
                                    total_qty -= cut_qty
                                    if USE_EXCHANGE_TP and 'place_or_update_tp' in globals():
                                        tp_order_id = place_or_update_tp(
                                            symbol=symbol_clean,
                                            side=side,
                                            quantity=total_qty,
                                            avg_entry=float(avg_entry),
                                            tp_from_avg_pct=float(tp_from_avg_pct)
                                        )
                                    save_state()
                                    log_message(f"✂️ [DCA] Trend-flip cut: скорочено {cut_qty:.6f} {symbol_clean}. Залишок qty={total_qty:.6f}")
                            else:
                                log_message("ℹ️ close_position_qty відсутня в executor.py → пропускаю частковий cut")
                        except Exception as e:
                            log_error(f"⚠️ [DCA] Trend-flip cut помилка: {e}")
                except Exception:
                    pass

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
    📥 Повертає dict активних угод із ActiveTrades.json (ключ = trade_id).
    """
    try:
        data = _at_safe_load()  # потокобезпечне читання з utils.logger
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            # Рідкісний кейс: якщо раптом список — конвертуємо
            return {t.get("trade_id", f"trade_{i}"): t for i, t in enumerate(data) if isinstance(t, dict)}
        return {}
    except Exception as e:
        log_error(f"❌ load_active_trades: помилка завантаження → {e}")
        return {}


def resolve_trade_id(symbol: str, side: str) -> str | None:
    """
    Підхоплює наш локальний trade_id (той самий, що записали у signal_stats/ActiveTrades)
    для пари symbol+side. Якщо не знайдено — повертає None.
    """
    try:
        local_active = load_active_trades()  # очікуємо dict {trade_id: rec}
        if isinstance(local_active, dict):
            side_u = (side or "").upper()
            for tid, rec in local_active.items():
                if rec.get("symbol") == symbol and str(rec.get("side", "")).upper() == side_u:
                    return tid
    except Exception as e:
        log_error(f"resolve_trade_id: {e}")
    return None


def monitor_all_open_trades():
    """
    🔄 Безперервно моніторить всі відкриті угоди напряму з біржі (Bybit API).
    ⚠️ Не перетирає повний ActiveTrades.json; спрощений стан пише в ACTIVE_TRADES_FILE_SIMPLE.
    """
    log_message("🚦 [DEBUG] Старт monitor_all_open_trades() (LIVE API)")

    def monitor_trade_thread(trade_id, trade):
        try:
            symbol = trade.get("symbol")
            entry_price = trade.get("entry_price")
            side = trade.get("side", "LONG")
            amount = trade.get("amount", 0.0)
            leverage = trade.get("leverage", 10)
            summary = trade.get("behavior_summary", {})
            sessions = trade.get("monitoring_sessions", [])

            log_message(f"👁 [DEBUG] Старт моніторингу угоди {trade_id} ({symbol})")

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
            # 🛡️ Отримуємо всі відкриті позиції з біржі
            response = bybit.get_positions(category="linear", settleCoin="USDT")
            positions = response.get("result", {}).get("list", []) or []

            # ⏳ Якщо пусто — кілька ретраїв
            if not positions:
                for attempt in range(1, 4):
                    time.sleep(2)
                    response = bybit.get_positions(category="linear", settleCoin="USDT")
                    positions = response.get("result", {}).get("list", []) or []
                    if positions:
                        log_debug(f"Позиції знайдено на спробі {attempt}")
                        break

            live_trades = {}
            simple_trades = {}
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

            for pos in positions:
                try:
                    size = float(pos.get("size", 0) or 0)
                except Exception:
                    size = 0.0
                if size <= 0:
                    continue

                symbol = pos.get("symbol")
                # Сторона: з positionSide або з side
                raw_ps = str(pos.get("positionSide", "")).upper()
                if raw_ps in ("LONG", "SHORT"):
                    side = raw_ps
                else:
                    side = "LONG" if str(pos.get("side", "")).upper() == "BUY" else "SHORT"

                # Ціна входу: використовуємо avgEntryPrice, фолбек на avgPrice
                try:
                    entry_price = float(pos.get("avgEntryPrice") or pos.get("avgPrice") or 0.0)
                except Exception:
                    entry_price = 0.0

                # Плече
                try:
                    leverage = int(float(pos.get("leverage", 1)))
                except Exception:
                    leverage = 1

                # 🔑 Спробувати підхопити наш локальний trade_id
                trade_id = resolve_trade_id(symbol, side)
                if not trade_id:
                    # Резервний біржовий ідентифікатор (НЕ використовується для оновлення stats, тільки для ключа потоку)

                    local_id = resolve_trade_id(symbol, side)     # 👈 спробує знайти наш trade_id у ActiveTrades
                    trade_id = local_id or f"{symbol}_{pos.get('positionIdx', '0')}"

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

                # 📝 Спрощений запис (окремий файл, не чіпає повний ActiveTrades.json)
                simple_trades[trade_id] = {
                    "symbol": symbol,
                    "side": side,
                    "opened_at": current_time
                }

            # 🔹 Пишемо спрощений файл окремо, щоб не зносити повні записи
            try:
                with open(ACTIVE_TRADES_FILE_SIMPLE, "w", encoding="utf-8") as f:
                    json.dump(simple_trades, f, indent=2, ensure_ascii=False)
                    prune_inactive_trades(set(live_trades.keys()))

                log_debug(f"ActiveTradesSimple.json оновлено ({len(simple_trades)} угод)")
            except Exception as e:
                log_error(f"❌ [monitor_all_open_trades] Помилка при записі ActiveTradesSimple.json: {e}")

            # 🚀 Стартуємо моніторинг для кожної угоди (по нашому або резервному trade_id)
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
                    # вже моніториться — пропускаємо
                    pass

        except Exception as e:
            log_error(f"❌ monitor_all_open_trades (API): {e}")

        time.sleep(2)



