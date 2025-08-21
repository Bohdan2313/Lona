import datetime
from utils.logger import log_error
from analysis.indicators import (
    analyze_macd_atr,
    analyze_rsi,
    analyze_stochastic,
    analyze_bollinger_bands,
    analyze_support_resistance,
    get_volatility,
    detect_candlestick_patterns
)
from analysis.whales import get_whale_score
from analysis.sentiment import get_news_sentiment
from utils.tools import get_price_change
import time
from utils.tools import get_current_futures_price
from utils.logger import log_message, log_error
import os
import json


import pandas as pd

from analysis.indicators import get_micro_trend_5m


from predict_lstm import predict_lstm
from analysis.indicators import analyze_cci
from analysis.indicators import detect_rsi_divergence
from analysis.market import analyze_global_trend,analyze_market

from utils.get_klines_bybit import get_klines_clean_bybit
from analysis.indicators import get_micro_trend_1m
from analysis.market import analyze_volume, get_news_trend_summary

def safe_analyze(func, symbol, default=None):
    """
    🛡️ Безпечний виклик аналізатора. Якщо помилка або None → повертає default або {}.
    """
    try:
        result = func(symbol)
        if result is None:
            log_message(f"⚠️ {func.__name__} повернув None для {symbol}, fallback на default.")
            return default or {}
        return result
    except Exception as e:
        log_error(f"❌ {func.__name__} помилка для {symbol}: {e}")
        return default or {}


def build_monitor_snapshot(symbol):
    log_message(f"🛠 [DEBUG] ВХІД у build_monitor_snapshot для {symbol}")

    """
    📦 Створює повний snapshot для монети, використовуючи всі аналітичні модулі.
    """
    try:
        log_message(f"🔍 [DEBUG] Старт build_monitor_snapshot для {symbol}")

        # === Отримання даних з аналізаторів ===
        market_trend_data   = safe_analyze(analyze_market, symbol) or {}
        macd_data           = safe_analyze(analyze_macd_atr, symbol) or {}
        rsi_data            = safe_analyze(analyze_rsi, symbol) or {}
        stoch_data          = safe_analyze(analyze_stochastic, symbol) or {}
        bollinger_data      = safe_analyze(analyze_bollinger_bands, symbol) or {}
        support_data        = safe_analyze(analyze_support_resistance, symbol) or {}
        cci_data            = safe_analyze(analyze_cci, symbol) or {}
        volatility_data     = safe_analyze(get_volatility, symbol) or {}
        candle_patterns     = safe_analyze(detect_candlestick_patterns, symbol, []) or {}
        rsi_divergence      = safe_analyze(detect_rsi_divergence, symbol) or {}
        microtrend_1m_data  = safe_analyze(get_micro_trend_1m, symbol) or {}
        microtrend_5m_data  = safe_analyze(get_micro_trend_5m, symbol) or {}
        volume_data         = safe_analyze(analyze_volume, symbol) or {}
        whale_score_data    = safe_analyze(get_whale_score, symbol, 50) or {}
        global_trend_data   = analyze_global_trend() or {}
        news_data           = get_news_trend_summary() or {"news_summary": "UNKNOWN"}

        # --- дістаємо внутрішні об’єкти один раз (правильні шляхи)
        _macd      = macd_data.get("macd", {})                  # trend, hist_direction, crossed, score
        _atr       = macd_data.get("atr", {})                   # level, score
        _rsi       = rsi_data.get("rsi", {})                    # signal, value, trend, score
        _stoch     = stoch_data.get("stochastic", {})           # signal, k, d, score
        _boll      = bollinger_data.get("bollinger", {})        # signal, position, width, score
        _cci       = cci_data.get("cci", {})                    # signal, value, score
        _vol       = volatility_data.get("volatility", {})      # level, percentage, score
        _sr        = support_data.get("support_resistance", {}) # position, score, ...
        _patterns  = candle_patterns.get("candlestick", {})     # patterns, score
        _mt1m_dir  = microtrend_1m_data.get("microtrend_direction", "flat")
        _mt5m_dir  = microtrend_5m_data.get("microtrend_direction", "flat")
        _global_tr = global_trend_data.get("global_trend", {}).get("direction", "neutral")

        # === Лог ключових індикаторів (тепер з реальних полів)
        macd_trend   = _macd.get("trend", "neutral")
        rsi_signal   = _rsi.get("signal", "neutral")
        trend_dir    = market_trend_data.get("trend", "neutral")
        whale_score  = whale_score_data.get("whale_score", {}).get("score", 0.0)
        volume_level = volume_data.get("volume_analysis", {}).get("level", "unknown")

        log_message(
            f"🔎 {symbol} | Trend: {trend_dir} | MACD: {macd_trend} | "
            f"RSI: {rsi_signal} | Whale: {whale_score} | Volume: {volume_level}"
        )

        # === Додаткові дані ===
        price       = get_current_futures_price(symbol) or 0.0
        log_message(f"🧪 [DEBUG] Отримано ціну для {symbol}: {price}")
        delta_1m    = round(get_price_change(symbol, 1) or 0.0, 2)
        delta_5m    = round(get_price_change(symbol, 5) or 0.0, 2)
        sentiment   = get_news_sentiment(symbol) or "neutral"
        lstm_pred   = predict_lstm(symbol) or "neutral"
        price_trail = get_recent_price_trail(symbol, minutes=3) or []

        # === bars_in_state з price_trail (без нових залежностей)
        # рахуємо скільки останніх 1m кроків йшли в одному напрямку
        bars_in_state = 1
        try:
            trail = list(price_trail or [])
            if len(trail) >= 2:
                # перетворимо на різниці (дельти барів)
                diffs = []
                for i in range(1, len(trail)):
                    d = (trail[i] or 0.0) - (trail[i-1] or 0.0)
                    diffs.append(d)

                # поточний напрямок за останнім кроком
                last_dir = 1 if diffs[-1] > 0 else (-1 if diffs[-1] < 0 else 0)

                # рахуємо послідовні бари в тому ж напрямку від кінця
                cnt = 1
                for d in reversed(diffs[:-1]):
                    dir_ = 1 if d > 0 else (-1 if d < 0 else 0)
                    if dir_ == last_dir and dir_ != 0:
                        cnt += 1
                    else:
                        break
                bars_in_state = max(1, cnt)
        except Exception as e:
            log_message(f"⚠️ [DEBUG] bars_in_state calc fail: {e}")
            bars_in_state = 1


        # === Micro snapshots (локальні)
        micro_1m = {
            "trend": _mt1m_dir,
            "change_pct": delta_1m,
            "pattern": detect_candlestick_patterns(symbol, interval="1m").get("candlestick", {}).get("patterns", [])
        }

        micro_5m = {
            "trend": _mt5m_dir,
            "change_pct": delta_5m,
            "pattern": detect_candlestick_patterns(symbol, interval="5m").get("candlestick", {}).get("patterns", [])
        }

        # === Нормалізація RSI divergence до dict у indicators
        _rsi_div_obj = rsi_divergence.get("rsi_divergence", {})
        if isinstance(_rsi_div_obj, dict):
            rsi_divergence_norm = {
                "state": _rsi_div_obj.get("state", _rsi_div_obj.get("type", "none")),
                "score": float(_rsi_div_obj.get("score", 0.0) or 0.0)
            }
        elif isinstance(_rsi_div_obj, str):
            rsi_divergence_norm = {"state": _rsi_div_obj, "score": 0.0}
        else:
            rsi_divergence_norm = {"state": "none", "score": 0.0}

        # === Основний snapshot ===
        snapshot = {
            "symbol": symbol,
            "timestamp": int(datetime.datetime.utcnow().timestamp() * 1000),
            "price": price,
            "support_position": _sr.get("position", "unknown"),
            "whale_score": whale_score,
            "sentiment": sentiment,
            "trend": trend_dir,
            "volume_category": volume_level,
            "news_summary": news_data.get("news_summary", "UNKNOWN") if isinstance(news_data, dict) else news_data,
            "delta_1m": delta_1m,
            "delta_5m": delta_5m,
            "lstm_prediction": lstm_pred,

            "indicators": {
                # сигналові значення з детальних індикаторів
                "bars_in_state": int(bars_in_state),  # 👈 ДОДАТИ
                "macd": _macd.get("trend", "neutral"),
                "rsi": _rsi.get("signal", "neutral"),
                "stochastic": _stoch.get("signal", "neutral"),
                "bollinger": _boll.get("signal", "neutral"),
                "support_resistance": _sr.get("position", "unknown"),
                "cci": _cci.get("signal", "neutral"),
                "volatility": _vol.get("level", "low"),

                # оглядові/глобальні
                "local_trend": market_trend_data.get("trend", "neutral"),
                "macd_trend": market_trend_data.get("macd_trend", "neutral"),
                "cci_signal": market_trend_data.get("cci_signal", "neutral"),
                "atr_level": market_trend_data.get("atr_level", 0.0),
                "volume_category": market_trend_data.get("volume_category", "unknown"),
                "patterns": _patterns.get("patterns", []),
                "rsi_divergence": rsi_divergence_norm,  # завжди dict
                "global_trend": _global_tr,

                # мікротренди
                "microtrend_1m": _mt1m_dir,
                "microtrend_5m": _mt5m_dir,

                "scores": {
                    "macd_score": _macd.get("score", 0.0),
                    "rsi_score": _rsi.get("score", 0.0),
                    "stoch_score": _stoch.get("score", 0.0),
                    "bollinger_score": _boll.get("score", 0.0),
                    "support_resistance_score": _sr.get("score", 0.0),
                    "cci_score": _cci.get("score", 0.0),
                    "volatility_score": _vol.get("score", 0.0),
                    "pattern_score": _patterns.get("score", 0.0),
                    "microtrend_1m_score": microtrend_1m_data.get("microtrend_score", 0.0),
                    "microtrend_5m_score": microtrend_5m_data.get("microtrend_score", 0.0)
                }
            },

            # === raw_values у форматі, який чекає convert_snapshot_to_conditions
            "raw_values": {
                "macd": {
                    "macd": {
                        "trend": _macd.get("trend", "neutral"),
                        "score": _macd.get("score", 0.0),
                        "hist_direction": _macd.get("hist_direction", "flat"),
                        "crossed": _macd.get("crossed", "none"),
                    },
                    "atr": {
                        "level": _atr.get("level", 0.0),
                        "score": _atr.get("score", 0.0),
                    }
                },
                "market_trend": market_trend_data,
                "rsi": {"rsi": _rsi},
                "stochastic": {"stochastic": _stoch},
                "bollinger": {"bollinger": _boll},
                "support_resistance": {"support_resistance": _sr},
                "cci": {"cci": _cci},
                "volatility": {"volatility": _vol},
                "candle_patterns": {"candlestick": _patterns},
                "rsi_divergence": rsi_divergence,  # сирі дані як є — для дебагу
                "microtrend_1m": microtrend_1m_data,
                "microtrend_5m": microtrend_5m_data,
                "volume_analysis": volume_data,
                "whale_score": whale_score_data,
                "global_trend": global_trend_data,
                "news_summary": news_data
            },

            "micro": {
                "1m": micro_1m,
                "5m": micro_5m
            },

            "sparkline_price": price_trail[-10:] if price_trail else []
        }

        # === Proximity to local high ===
        try:
            df_1m = get_klines_clean_bybit(symbol, interval="1m", limit=20)
            if df_1m is not None and not df_1m.empty:
                df_1m["close"] = pd.to_numeric(df_1m["close"], errors="coerce")
                local_high = df_1m["close"].max()
                snapshot["proximity_to_high"] = round(price / local_high, 4) if local_high else 0.0
            else:
                snapshot["proximity_to_high"] = 0.0
            log_message(f"📊 [DEBUG] Proximity to High для {symbol}: {snapshot['proximity_to_high']}")
        except Exception as e:
            log_error(f"❌ proximity_to_high помилка: {e}")
            snapshot["proximity_to_high"] = 0.0

        snapshot["current_price"] = price  # 👈 для сумісності
        log_message(f"✅ [DEBUG] Готовий snapshot для {symbol}")

        # === 15m bar_closed (без дергання біржі зайвий раз)
        now_ms = int(datetime.datetime.utcnow().timestamp() * 1000)
        # відкриття поточної 15m свічки (UTC)
        open_15m_ms = (now_ms // (15*60*1000)) * (15*60*1000)
        # вважаємо "закритою", якщо пройшло > 15m - 2s (safety)
        bar_closed_15m = (now_ms - open_15m_ms) >= (15*60*1000 - 2000)

        # === Останні дві свічки (для перевірки розвороту)
        try:
            df = get_klines_clean_bybit(symbol, interval="1m", limit=2)
            if df is not None and len(df) >= 2:
                last_candle = df.iloc[-1].to_dict()
                prev_candle = df.iloc[-2].to_dict() 
                snapshot["last_candle"] = last_candle
                snapshot["prev_candle"] = prev_candle
                snapshot["last_candle"]["closed"] = bool(bar_closed_15m)
        except Exception as e:
            log_error(f"❌ Неможливо отримати останні свічки для {symbol}: {e}")

        return snapshot

    except Exception as e:
        log_error(f"❌ build_monitor_snapshot помилка для {symbol}: {e}")
        return None



def convert_snapshot_to_conditions(snapshot):
    """
    🔄 Конвертує снапшот у conditions для торгової логіки.
    - Безпечна розпаковка news_summary (dict | str)
    - Правильний витяг патернів (raw_values.candle_patterns або indicators.patterns)
    - Гнучкий шлях до microtrend_5m
    - Нормалізація bollinger_position (якщо 0..1 -> 0..100)
    """
    try:
        indicators = snapshot.get("indicators", {}) or {}
        raw_values = snapshot.get("raw_values", {}) or {}
        market_trend_data = raw_values.get("market_trend", {}) or {}

        # === MACD + ATR ===
        macd_root = raw_values.get("macd", {}) or {}
        macd_data = macd_root.get("macd", {}) or {}
        atr_data = macd_root.get("atr", {}) or {}

        # === RSI ===
        rsi_root = raw_values.get("rsi", {}) or {}
        rsi_data = rsi_root.get("rsi", {}) or {}

        # === Stochastic ===
        stoch_root = raw_values.get("stochastic", {}) or {}
        stoch_data = stoch_root.get("stochastic", {}) or {}

        # === Bollinger ===
        boll_root = raw_values.get("bollinger", {}) or {}
        bollinger_data = boll_root.get("bollinger", {}) or {}

        # === Support/Resistance ===
        sr_root = raw_values.get("support_resistance", {}) or {}
        sr_data = sr_root.get("support_resistance", {}) or {}

        # === Patterns ===
        cp = raw_values.get("candle_patterns", {}) or {}
        if isinstance(cp, dict) and "candlestick" in cp:
            patt_obj = cp.get("candlestick", {}) or {}
            patt_list = patt_obj.get("patterns", []) or []
            patt_score = patt_obj.get("score", 0.0) or 0.0
        else:
            patt_list = cp.get("patterns", []) if isinstance(cp, dict) else []
            patt_score = cp.get("pattern_score", 0.0) if isinstance(cp, dict) else 0.0
        # Fallback на snapshot.indicators.patterns, якщо в raw порожньо
        if not patt_list:
            patt_list = indicators.get("patterns", []) or []

        # === Volatility ===
        vol_root = raw_values.get("volatility", {}) or {}
        volatility_data = vol_root.get("volatility", {}) or {}

        # === CCI ===
        cci_root = raw_values.get("cci", {}) or {}
        cci_data = cci_root.get("cci", {}) or {}

        # === News sentiment (type-safe) ===
        ns = snapshot.get("news_summary", "UNKNOWN")
        news_sentiment = ns.get("trend", "neutral") if isinstance(ns, dict) else "neutral"

        # === Microtrends ===
        micro1m = indicators.get("microtrend_1m", "neutral")
        micro5m = indicators.get("microtrend_5m", None)
        if micro5m is None:
            mt5 = raw_values.get("microtrend_5m", {}) or {}
            micro5m = mt5.get("microtrend_direction",
                              mt5.get("micro_trend_5m", {}).get("direction", "neutral"))

        # === Bollinger position нормалізація (якщо раптом у 0..1)
        bp = bollinger_data.get("position", 50)
        try:
            bp = float(bp)
            if 0.0 <= bp <= 1.0:
                bp = round(bp * 100.0, 2)
        except Exception:
            bp = 50.0

        # === Stoch K/D безпечні float-и
        try:
            stoch_k = float(stoch_data.get("k")) if stoch_data.get("k") is not None else None
        except Exception:
            stoch_k = None
        try:
            stoch_d = float(stoch_data.get("d")) if stoch_data.get("d") is not None else None
        except Exception:
            stoch_d = None

        # === RSI value безпечний float
        try:
            rsi_value = float(rsi_data.get("value", market_trend_data.get("rsi", 0.0)) or 0.0)
        except Exception:
            rsi_value = 0.0

        # === RSI divergence: безпечний парсер з нормалізацією
        _rsi_div = indicators.get("rsi_divergence", {})
        if isinstance(_rsi_div, dict):
            _rsi_div_score = float(_rsi_div.get("score", 0.0) or 0.0)
        else:
            _rsi_div = {"state": str(_rsi_div), "score": 0.0}
            _rsi_div_score = 0.0

        # === Збір conditions (ключі залишаються тими ж)
        conditions = {
            "symbol": snapshot.get("symbol"),
            "trend": market_trend_data.get("trend", "unknown"),

            # MACD з технічного блоку
            "macd_trend": macd_data.get("trend", "neutral"),
            "macd_score": macd_data.get("score", 0.0),
            "macd_hist_direction": macd_data.get("hist_direction", "flat"),
            "macd_crossed": macd_data.get("crossed", "none"),

            # ATR
            "atr_level": atr_data.get("level", market_trend_data.get("atr_level", 0.0)),
            "atr_score": atr_data.get("score", 0.0),

            # RSI
            "rsi_signal": rsi_data.get("signal", "neutral"),
            "rsi_value": rsi_value,
            "rsi_trend": rsi_data.get("trend", "flat"),
            "rsi_score": rsi_data.get("score", 0.0),

            # RSI divergence (вже нормалізовано)
            "rsi_divergence": _rsi_div,
            "rsi_divergence_score": _rsi_div_score,

            # CCI
            "cci_signal": cci_data.get("signal", "neutral"),
            "cci_value": cci_data.get("value", 0.0),
            "cci_score": cci_data.get("score", 0.0),

            # Stochastic
            "stoch_signal": stoch_data.get("signal", "neutral"),
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "stoch_score": stoch_data.get("score", 0.0),

            # Bollinger
            "bollinger_signal": bollinger_data.get("signal", "neutral"),
            "bollinger_position": bp,
            "bollinger_width": bollinger_data.get("width", 0.0),
            "bollinger_score": bollinger_data.get("score", 0.0),

            # SR
            "support": sr_data.get("support"),
            "resistance": sr_data.get("resistance"),
            "support_position": snapshot.get("support_position", "unknown"),
            "support_resistance_score": sr_data.get("score", 0.0),

            # Обсяг/волатильність/глобалка
            "volume_category": market_trend_data.get("volume_category", "unknown"),
            "global_trend": indicators.get("global_trend", "unknown"),
            "lstm_prediction": snapshot.get("lstm_prediction", 0.0),
            "proximity_to_high": snapshot.get("proximity_to_high", 0.0),
            "whale_score": snapshot.get("whale_score", 0),
            "news_sentiment": news_sentiment,
            "volatility_pct": volatility_data.get("percentage", 0.0),
            "volatility_level": volatility_data.get("level", "unknown"),
            "volatility_score": volatility_data.get("score", 0.0),
            "volatility": market_trend_data.get("volatility", 0.0),

            # Мікротренди
            "microtrend_1m": micro1m,
            "microtrend_1m_score": indicators.get("scores", {}).get("microtrend_1m_score", 0.0),
            "microtrend_5m": micro5m,
            "microtrend_5m_score": indicators.get("scores", {}).get("microtrend_5m_score", 0.0),

            # Патерни
            "patterns": patt_list,
            "pattern_score": patt_score,

            # Дельти, стейти, ціна
            "delta_1m": snapshot.get("delta_1m", 0.0),
            "delta_5m": snapshot.get("delta_5m", 0.0),
            "health_ok": snapshot.get("health_ok", True),
            "health_reason": snapshot.get("health_reason", "ok"),
            "current_price": snapshot.get("current_price", 0.0),
            "price": snapshot.get("price") or snapshot.get("current_price", 0.0),

            # Свічи для локальних розворотів
            "last_candle": snapshot.get("last_candle", {}),
            "prev_candle": snapshot.get("prev_candle", {}),
        }
               
               
         # === Добудова службових полів для анти-фільтрів ===

        # 1) bar_closed (беремо з last_candle.closed; якщо немає — True)
        lc = snapshot.get("last_candle", {}) or {}
        bar_closed = bool(lc.get("closed", True))

        # 2) bars_in_state (те, що ми порахували у build_monitor_snapshot)
        bis = indicators.get("bars_in_state")
        try:
            bars_in_state = int(bis) if bis is not None else 1
        except Exception:
            bars_in_state = 1

        # 3) atr_percent (%). Якщо ATR і price валідні — рахуємо; інакше — fallback на volatility percentage
        price_val = snapshot.get("price") or snapshot.get("current_price", 0.0)
        try:
            price_val = float(price_val) if price_val is not None else 0.0
        except Exception:
            price_val = 0.0

        atr_level = atr_data.get("level", market_trend_data.get("atr_level", 0.0)) or 0.0
        try:
            atr_level = float(atr_level)
        except Exception:
            atr_level = 0.0

        if price_val > 0.0 and atr_level > 0.0:
            atr_percent = (atr_level / price_val) * 100.0
        else:
            vp = volatility_data.get("percentage", 0.0)
            try:
                atr_percent = float(vp) if vp is not None else 0.0
            except Exception:
                atr_percent = 0.0

        # 4) normalize support_position до стабільного домену
        sp = snapshot.get("support_position", "unknown")
        sp = (str(sp).lower().strip() if isinstance(sp, str) else "unknown")
        if sp not in {"near_support","between","near_resistance"}:
            sup = sr_data.get("support")
            res = sr_data.get("resistance")
            try:
                sup = float(sup) if sup is not None else None
                res = float(res) if res is not None else None
            except Exception:
                sup = res = None

            if sup is not None and res is not None and price_val:
                dist_s = abs(price_val - sup)
                dist_r = abs(price_val - res)
                sp = "near_support" if dist_s < dist_r else "near_resistance"
            else:
                sp = "between"
        support_position = sp

        # 5) volume_category → нормальний домен (підтягнемо з snapshot, якщо є)
        vc_raw = snapshot.get("volume_category", market_trend_data.get("volume_category", "unknown"))

        if isinstance(vc_raw, dict):
            # спроби витягнути рівень з можливих форматів
            vc = (
                vc_raw.get("level") or
                (vc_raw.get("volume_analysis", {}) or {}).get("level") or
                "normal"
            )
        else:
            vc = str(vc_raw).lower().strip()

        if vc not in {"very_low", "low", "normal", "high", "very_high"}:
            vc = "normal"


        # 6) покласти в conditions
        conditions.update({
            "bar_closed": bar_closed,
            "bars_in_state": bars_in_state,
            "atr_percent": atr_percent,
            "support_position": support_position,
            "volume_category": vc,
        })

        return conditions

    except Exception as e:
        log_error(f"❌ convert_snapshot_to_conditions помилка: {e}")
        return {}


SNAPSHOT_PATH = "data/monitor_snapshots"


def get_recent_price_trail(symbol: str, minutes: int = 3, interval: str = "1m") -> list:
    """
    📉 Отримує список останніх цін монети за вказану кількість хвилин.
    Повертає масив цін [float] для побудови спарклайну.
    """
    try:
        interval_clean = interval.replace("m", "")
        df = get_klines_clean_bybit(symbol, interval=interval_clean, limit=minutes)
        
        if df is None or df.empty:
            log_error(f"❌ [get_recent_price_trail] Порожні Klines для {symbol}")
            return []

        if len(df) < minutes:
            log_message(f"⚠️ [get_recent_price_trail] Мало свічок для {symbol}: {len(df)} (очікувалось {minutes})")

        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])

        return df["close"].tolist()

    except Exception as e:
        log_error(f"❌ [get_recent_price_trail] Помилка: {e}")
        return []

