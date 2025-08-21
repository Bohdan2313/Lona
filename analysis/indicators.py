import pandas as pd
import numpy as np
import talib
from utils.logger import log_message
from utils.tools import get_current_futures_price
from utils.logger import log_error
import ta
from utils.tools import get_historical_data
from utils.tools import get_klines
from utils.get_klines_bybit import get_klines_clean_bybit
import json


def analyze_macd_atr(symbol):
    """
    📈 MACD + ATR (15m), підвищена чутливість:
    - Тренд за rolling-вікном гістограми (5 барів)
    - Напрям за дельтою гістограми на останніх 3 барах
    - "Теплий" перетин: якщо стався протягом останніх 3 барів — вважаємо активним
    - ATR-фільтр м’якший (нейтралізуємо тільки при дуже тихому ринку)
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="15m", limit=200)
        if df is None or df.empty or len(df) < 60:
            return default_macd_atr()

        df = df.dropna(subset=["close", "high", "low"])
        close, high, low = df["close"].astype(float), df["high"].astype(float), df["low"].astype(float)

        macd_raw, signal_raw, hist_raw = talib.MACD(close)
        atr_raw = talib.ATR(high, low, close, timeperiod=14)

        if pd.isna(macd_raw).all() or pd.isna(signal_raw).all() or pd.isna(hist_raw).all() or pd.isna(atr_raw).all():
            return default_macd_atr()

        macd = pd.Series(macd_raw).fillna(0.0)
        signal = pd.Series(signal_raw).fillna(0.0)
        hist = pd.Series(hist_raw).fillna(0.0)
        atr = pd.Series(atr_raw).fillna(0.0)

        macd_now, signal_now, hist_now = macd.iloc[-1], signal.iloc[-1], hist.iloc[-1]
        atr_now = atr.iloc[-1]
        price_now = float(close.iloc[-1])

        # --- Тренд за rolling-вікном гістограми (середнє за 5 барів)
        hist_ma5 = hist.tail(5).mean()
        if hist_ma5 > 0:
            macd_trend = "bullish"
        elif hist_ma5 < 0:
            macd_trend = "bearish"
        else:
            macd_trend = "neutral"

        # --- Напрям гістограми: дивимось дельту за 3 останні бари
        dh = hist.diff().tail(3).sum()
        if dh > 0:
            hist_direction = "up"
        elif dh < 0:
            hist_direction = "down"
        else:
            hist_direction = "flat"

        # --- "Теплий" перетин: шукаємо перетин за останні 3 бари
        crossed = "none"
        last3 = min(3, len(macd) - 1)
        for i in range(1, last3 + 1):
            m_prev, s_prev = macd.iloc[-1 - i], signal.iloc[-1 - i]
            m_cur, s_cur = macd.iloc[-i], signal.iloc[-i]
            if m_prev < s_prev and m_cur > s_cur:
                crossed = "bullish_cross"
                break
            if m_prev > s_prev and m_cur < s_cur:
                crossed = "bearish_cross"
                break

        # --- ATR як % від ціни: нейтралізуємо лише при дуже низькій волатильності
        atr_pct = (atr_now / max(price_now, 1e-8)) * 100
        if atr_pct < 0.2:
            macd_trend = "neutral"
            hist_direction = "flat"
            crossed = "none"

        # --- Оцінка "сили" за гістограмою + інерцією
        score = float(hist_ma5) * 10  # масштабуємо, щоб не було мікро-оцінок
        score = round(max(min(score, 10.0), -10.0), 2)

        macd_result = {
            "trend": macd_trend,
            "hist_direction": hist_direction,
            "crossed": crossed,
            "score": score,
            "raw_values": {
                "macd_now": round(float(macd_now), 6),
                "signal_now": round(float(signal_now), 6),
                "hist_now": round(float(hist_now), 6),
                "hist_ma5": round(float(hist_ma5), 6)
            },
            "last_5_values": hist.tail(5).round(4).tolist()
        }

        atr_result = {
            "level": round(float(atr_now), 4),
            "score": round(float(atr_pct), 2),  # ATR як відсоток від ціни
            "raw_values": {
                "atr_now": round(float(atr_now), 6),
                "atr_pct": round(float(atr_pct), 4)
            },
            "last_5_values": atr.tail(5).round(4).tolist()
        }

        return {
            "macd": macd_result,
            "atr": atr_result
        }

    except Exception as e:
        log_error(f"❌ [MACD+ATR] analyze_macd_atr помилка: {e}")
        return default_macd_atr()


def default_macd_atr():
    """Повертає дефолтні значення."""
    return {
        "macd": {
            "trend": "neutral",
            "hist_direction": "flat",
            "crossed": "none",
            "score": 0.0,
            "raw_values": {},
            "last_5_values": []
        },
        "atr": {
            "level": 0,
            "score": 0.0,
            "raw_values": {},
            "last_5_values": []
        }
    }


def analyze_cci(symbol):
    """
    📊 Розширений CCI аналіз (15-хв) з momentum сигналами для скальпінгу.
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="15m", limit=150)
        if df is None or df.empty or len(df) < 40:
            return {
                "cci": {
                    "signal": "neutral",
                    "value": None,
                    "score": 0.0,
                    "last_5": [],
                    "slope": "flat"
                }
            }

        df.dropna(subset=["high", "low", "close"], inplace=True)
        high, low, close = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
        cci_series = talib.CCI(high, low, close, timeperiod=20)
        cci = pd.Series(cci_series).dropna()

        if cci.empty:
            return {
                "cci": {
                    "signal": "neutral",
                    "value": None,
                    "score": 0.0,
                    "last_5": [],
                    "slope": "flat"
                }
            }

        cci_now = cci.iloc[-1]
        cci_last_5 = cci.tail(5).round(2).tolist()

        # === Класичні сигнали
        signal = "neutral"
        score = 0.0

        if cci_now > 200:
            signal, score = "strong_overbought", -6.0
        elif cci_now > 100:
            signal, score = "overbought", -3.0
        elif cci_now < -200:
            signal, score = "strong_oversold", +6.0
        elif cci_now < -100:
            signal, score = "oversold", +3.0

        # === Momentum сигнали для [-100..100]
        if -100 < cci_now < 100:
            slope_check = cci.diff().tail(3).tolist()
            if all(s > 0 for s in slope_check):
                signal, score = "bullish_momentum", +1.5
            elif all(s < 0 for s in slope_check):
                signal, score = "bearish_momentum", -1.5

        # === Визначення slope
        slope = "flat"
        if len(cci_last_5) >= 2:
            if cci_last_5[-1] > cci_last_5[-2]:
                slope = "up"
            elif cci_last_5[-1] < cci_last_5[-2]:
                slope = "down"

        log_message(f"📊 CCI {symbol}: {cci_now:.2f} → {signal} | Score: {score} | Slope: {slope}")

        return {
            "cci": {
                "signal": signal,
                "value": round(cci_now, 2),
                "score": round(score, 2),
                "last_5": cci_last_5,
                "slope": slope
            }
        }

    except Exception as e:
        return {
            "cci": {
                "signal": "neutral",
                "value": None,
                "score": 0.0,
                "last_5": [],
                "slope": "flat"
            }
        }


def analyze_stochastic(symbol):
    """
    📉 STOCH (15m) — більш чутливий:
    - "Теплий" крос (за останні 2 бари)
    - Моментум у середині діапазону (20..80) за схилом K і D (3 бари)
    - Пороги перекуп/перепродані залишені 80/20, але сигналів стане більше
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="15m", limit=150)
        if df is None or df.empty or len(df) < 40:
            return {
                "stochastic": {
                    "signal": "neutral",
                    "k": None,
                    "d": None,
                    "score": 0.0,
                    "raw_values": {},
                    "last_5_values": {}
                }
            }

        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)

        slowk, slowd = talib.STOCH(
            df['high'], df['low'], df['close'],
            fastk_period=14, slowk_period=3, slowk_matype=0,
            slowd_period=3, slowd_matype=0
        )

        if slowk.isna().all() or slowd.isna().all():
            return {
                "stochastic": {
                    "signal": "neutral",
                    "k": None,
                    "d": None,
                    "score": 0.0,
                    "raw_values": {},
                    "last_5_values": {}
                }
            }

        k, d = float(slowk.iloc[-1]), float(slowd.iloc[-1])
        k_prev, d_prev = float(slowk.iloc[-2]), float(slowd.iloc[-2])

        k_last_5 = slowk.tail(5).round(2).tolist()
        d_last_5 = slowd.tail(5).round(2).tolist()

        signal, score = "neutral", 0.0

        # Теплий крос за останні 2 бари
        crossed_up = False
        crossed_down = False
        for i in range(1, min(2, len(slowk) - 1) + 1):
            kp, dp = float(slowk.iloc[-1 - i]), float(slowd.iloc[-1 - i])
            kc, dc = float(slowk.iloc[-i]), float(slowd.iloc[-i])
            if kp < dp and kc > dc:
                crossed_up = True
                break
            if kp > dp and kc < dc:
                crossed_down = True
                break

        if k < 20 and (crossed_up or (k_prev < d_prev and k > d)):
            signal, score = "oversold_cross_up", +8.0
        elif k > 80 and (crossed_down or (k_prev > d_prev and k < d)):
            signal, score = "overbought_cross_down", -8.0
        elif k < 20:
            signal, score = "oversold", +3.0
        elif k > 80:
            signal, score = "overbought", -3.0
        else:
            # Momentum у середині діапазону
            slope_k = pd.Series(slowk).diff().tail(3).sum()
            slope_d = pd.Series(slowd).diff().tail(3).sum()
            if slope_k > 0 and slope_d > 0:
                signal, score = "bullish_momentum", +1.5
            elif slope_k < 0 and slope_d < 0:
                signal, score = "bearish_momentum", -1.5

        return {
            "stochastic": {
                "signal": signal,
                "k": round(k, 2),
                "d": round(d, 2),
                "score": round(score, 2),
                "raw_values": {
                    "k_current": round(k, 4),
                    "d_current": round(d, 4),
                    "k_previous": round(k_prev, 4),
                    "d_previous": round(d_prev, 4),
                    "crossed_up_last2": crossed_up,
                    "crossed_down_last2": crossed_down
                },
                "last_5_values": {
                    "k": k_last_5,
                    "d": d_last_5
                }
            }
        }

    except Exception as e:
        log_message(f"❌ [STOCH] analyze_stochastic помилка: {e}")
        return {
            "stochastic": {
                "signal": "neutral",
                "k": None,
                "d": None,
                "score": 0.0,
                "raw_values": {},
                "last_5_values": {}
            }
        }


def analyze_bollinger_bands(symbol):
    """
    📊 Bollinger Bands (15m, 20 періодів, 2σ) — стабільніша версія:
    - Позиція в каналі завжди 0..100 (кламп)
    - Squeeze: ширина нижче 25-го перцентилю за останні 40 барів
    - Momentum за позицією: >=65 → bullish_momentum, <=35 → bearish_momentum
    - Breakout-детект: price > upper / price < lower
    Повертає ту ж структуру, що й раніше (drop-in).
    """
    try:
        import pandas as pd
        import numpy as np
        import talib

        df = get_klines_clean_bybit(symbol, interval="15m", limit=300)
        if df is None or df.empty or len(df) < 40:
            return {
                "bollinger": {
                    "signal": "neutral",
                    "position": 50,
                    "width": 0.0,
                    "status": "neutral",
                    "score": 0.0,
                    "raw_values": {},
                    "last_5_widths": []
                }
            }

        close = pd.to_numeric(df["close"], errors="coerce").astype(float)
        close = close.dropna()
        if close.empty or len(close) < 40:
            return {
                "bollinger": {
                    "signal": "neutral",
                    "position": 50,
                    "width": 0.0,
                    "status": "neutral",
                    "score": 0.0,
                    "raw_values": {},
                    "last_5_widths": []
                }
            }

        arr = close.values
        # Класичні параметри: 20 періодів, 2σ
        upper, middle, lower = talib.BBANDS(arr, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)

        last_close = float(arr[-1])
        up = float(upper[-1]) if np.isfinite(upper[-1]) else last_close
        lo = float(lower[-1]) if np.isfinite(lower[-1]) else last_close
        mid = float(middle[-1]) if np.isfinite(middle[-1]) else last_close

        width_now = up - lo
        if not np.isfinite(width_now) or width_now <= 0:
            width_now = 1e-9  # захист від нульової ширини

        # Позиція в каналі (клампимо 0..100)
        pos_raw = ((last_close - lo) / width_now) * 100.0
        position = round(max(0.0, min(100.0, pos_raw)), 2)

        # Динамічний squeeze: порівнюємо поточну ширину з Q25 за 40 барів
        widths_series = pd.Series(upper - lower)
        widths_series = widths_series.replace([np.inf, -np.inf], np.nan).ffill().bfill()
        widths_last40 = widths_series.tail(40)
        q25 = float(widths_last40.quantile(0.25)) if not widths_last40.isna().all() else width_now
        is_squeeze = width_now <= max(q25, 1e-9)

        # Ширина у відсотках до середньої смуги — зручно для діагностики
        width_pct = float(width_now / mid) if mid > 0 else 0.0

        # Сигнали
        signal, score = "neutral", 0.0
        if last_close > up:
            signal, score = "breakout_up", +10.0
        elif last_close < lo:
            signal, score = "breakout_down", -10.0
        elif is_squeeze:
            signal, score = "squeeze", +3.0
        elif position >= 65.0:
            signal, score = "bullish_momentum", +1.5
        elif position <= 35.0:
            signal, score = "bearish_momentum", -1.5

        last_5_widths = widths_series.tail(5).round(4).fillna(0.0).tolist()

        return {
            "bollinger": {
                "signal": signal,
                "position": position,                    # 0..100
                "width": round(float(width_now), 4),     # абсолютна ширина
                "status": signal,
                "score": round(float(score), 2),
                "raw_values": {
                    "last_close": round(last_close, 6),
                    "upper_val": round(up, 6),
                    "lower_val": round(lo, 6),
                    "q25_width": round(float(q25), 6),
                    "width_pct": round(float(width_pct), 6)
                },
                "last_5_widths": last_5_widths
            }
        }

    except Exception as e:
        log_error(f"❌ analyze_bollinger_bands помилка: {e}")
        return {
            "bollinger": {
                "signal": "neutral",
                "position": 50,
                "width": 0.0,
                "status": "neutral",
                "score": 0.0,
                "raw_values": {},
                "last_5_widths": []
            }
        }


def analyze_support_resistance(symbol):
    """
    🛡️ Аналіз підтримки/опору на 15m:
    - Swing-рівні + легка кластеризація
    - Нормалізація відстані через ATR/BB-width/%
    - Симетричні пороги "near"
    - Коректно визначає пробої (у raw), але position -> {near_support|between|near_resistance}
    Повертає структуру, сумісну з існуючим пайплайном.
    """
    try:
        import math
        import pandas as pd

        df = get_klines_clean_bybit(symbol, interval="15m", limit=200)
        price = get_current_futures_price(symbol)

        if df is None or len(df) < 30 or price is None:
            support = resistance = float(price) if price else 0.0
            return {
                "support_resistance": {
                    "support": support,
                    "resistance": resistance,
                    "position": "unknown",
                    "distance_to_support": 0.0,
                    "distance_to_resistance": 0.0,
                    "score": 0.0,
                    "raw_values": {}
                }
            }

        # -- Витяг числових колонок
        df = df.copy()
        for c in ("open", "high", "low", "close"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["high", "low", "close"])
        if df.empty:
            support = resistance = float(price)
            return {
                "support_resistance": {
                    "support": support,
                    "resistance": resistance,
                    "position": "unknown",
                    "distance_to_support": 0.0,
                    "distance_to_resistance": 0.0,
                    "score": 0.0,
                    "raw_values": {}
                }
            }

        # ---------- Допоміжні обчислення ----------
        # ATR(14)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)

        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)

        atr = tr.rolling(14, min_periods=14).mean().iloc[-1]
        atr = float(atr) if pd.notna(atr) else 0.0

        # Bollinger width (20), абсолютна (upper-lower)
        sma20 = close.rolling(20, min_periods=20).mean()
        std20 = close.rolling(20, min_periods=20).std()
        bb_width_abs = float((std20.iloc[-1] * 4.0)) if pd.notna(std20.iloc[-1]) else 0.0  # 2σ вгору + 2σ вниз
        bb_width_pct = (bb_width_abs / float(sma20.iloc[-1])) if (pd.notna(sma20.iloc[-1]) and sma20.iloc[-1] > 0) else 0.0

        # ---------- Swing-рівні (фрактали) ----------
        # Локальні мінімуми/максимуми у вікні (left/right = 2)
        def _swing_points(series, is_low=True, left=2, right=2):
            s = series.values
            idxs = []
            for i in range(left, len(s) - right):
                window = s[i-left:i+right+1]
                val = s[i]
                if is_low:
                    if val == window.min() and (window[:left] > val).all() and (window[-right:] > val).all():
                        idxs.append(i)
                else:
                    if val == window.max() and (window[:left] < val).all() and (window[-right:] < val).all():
                        idxs.append(i)
            return idxs

        lookback = 120  # останні N барів для пошуку фракталів
        df_look = df.tail(lookback)
        lows_idx = _swing_points(df_look["low"], is_low=True, left=2, right=2)
        highs_idx = _swing_points(df_look["high"], is_low=False, left=2, right=2)

        swing_lows = df_look["low"].iloc[lows_idx].astype(float).tolist()
        swing_highs = df_look["high"].iloc[highs_idx].astype(float).tolist()

        # Якщо свінгів нема — fallback на останні 20 екстремумів (як було)
        if not swing_lows:
            swing_lows = df["low"].tail(20).astype(float).tolist()
        if not swing_highs:
            swing_highs = df["high"].tail(20).astype(float).tolist()

        # ---------- Легка кластеризація рівнів ----------
        # Об'єднуємо дуже близькі рівні, щоб не дублювати шум (поріг ~0.15 ATR або 0.1% ціни)
        def _cluster_levels(levels, tol_abs):
            if not levels:
                return []
            levels = sorted(levels)
            clusters = [[levels[0]]]
            for v in levels[1:]:
                if abs(v - clusters[-1][-1]) <= tol_abs:
                    clusters[-1].append(v)
                else:
                    clusters.append([v])
            # представник кластера — медіана
            import statistics as _st
            return [float(_st.median(c)) for c in clusters]

        tol_abs = max(0.15 * atr, 0.001 * float(price)) if atr > 0 else 0.0015 * float(price)
        lows_cl = _cluster_levels(swing_lows, tol_abs)
        highs_cl = _cluster_levels(swing_highs, tol_abs)

        # Вибираємо найближчу підтримку нижче/≈ ціни та опір вище/≈ ціни
        p = float(price)
        support_candidates = [lv for lv in lows_cl if lv <= p]
        resistance_candidates = [hv for hv in highs_cl if hv >= p]

        support = max(support_candidates) if support_candidates else (max(lows_cl) if lows_cl else None)
        resistance = min(resistance_candidates) if resistance_candidates else (min(highs_cl) if highs_cl else None)

        # Якщо все одно щось бракує — fallback: +/- max(2*ATR, 3% ціни)
        if support is None or math.isnan(support):
            fallback_s = p - max(2.0 * atr, 0.03 * p)
            support = float(fallback_s)
        if resistance is None or math.isnan(resistance):
            fallback_r = p + max(2.0 * atr, 0.03 * p)
            resistance = float(fallback_r)

        # sanity: якщо переплутались
        if support >= resistance:
            # розсунемо рівні навколо ціни
            half_span = max(2.0 * atr, 0.03 * p)
            support = p - half_span
            resistance = p + half_span

        # ---------- Нормалізація відстаней ----------
        dist_s_abs = max(0.0, p - support)
        dist_r_abs = max(0.0, resistance - p)

        # пороги "near": беремо кращий із 3 нормувань
        near_thr_atr = 0.60  # <= 0.60 * ATR
        near_thr_bw  = 0.35  # <= 0.35 * BB width
        near_thr_pct = 0.006 # <= 0.6% від ціни

        def _is_near(dist_abs):
            votes = []
            if atr > 0:
                votes.append(dist_abs <= near_thr_atr * atr)
            if bb_width_abs > 0:
                votes.append(dist_abs <= near_thr_bw * bb_width_abs)
            votes.append((dist_abs / p) <= near_thr_pct)
            return any(votes)

        near_s = _is_near(dist_s_abs)
        near_r = _is_near(dist_r_abs)

        # Breakout buffer (щоб відрізнити явний пробій від "майже біля"):
        breakout_buf = max(0.10 * atr, 0.10 * bb_width_abs, 0.003 * p)
        breakout_state = "none"
        if p < support - breakout_buf:
            breakout_state = "below_support"
        elif p > resistance + breakout_buf:
            breakout_state = "above_resistance"

        # ---------- Класифікація position (симетрична та стабільна) ----------
        # 1) явні пробої у raw (position лишаємо в домені твоєї системи)
        # 2) якщо обидва "near" -> беремо ближчий (з невеличким tie-breaker 0.9)
        # 3) інакше — хто "near", той і перемагає; інакше — between.
        position = "between"
        if near_s and near_r:
            if dist_s_abs <= dist_r_abs * 0.9:
                position = "near_support"
            elif dist_r_abs <= dist_s_abs * 0.9:
                position = "near_resistance"
            else:
                # практично на середині каналу
                position = "between"
        elif near_s:
            position = "near_support"
        elif near_r:
            position = "near_resistance"
        else:
            position = "between"

        # ---------- Оцінка score (плавна, але у звичному діапазоні) ----------
        # близько до рівня -> |score| до ~6; між рівнями -> 0
        def _score_from_dist(dist_abs):
            # нормуємо до найкращого з ATR/BB/pct
            parts = []
            if atr > 0:
                parts.append(dist_abs / (near_thr_atr * atr))
            if bb_width_abs > 0:
                parts.append(dist_abs / (near_thr_bw * bb_width_abs))
            parts.append((dist_abs / p) / near_thr_pct)
            x = min(parts)  # <1 → ближче порога
            x = max(0.0, min(1.5, x))
            return max(0.0, 1.0 - x)  # 1.0 при самому рівні, ~0 при далекій відстані

        score = 0.0
        if position == "near_support":
            score = round(6.0 * _score_from_dist(dist_s_abs), 2)
        elif position == "near_resistance":
            score = round(-6.0 * _score_from_dist(dist_r_abs), 2)
        else:
            score = 0.0

        # ---------- Дистанції у відсотках (як у твоїй версії) ----------
        distance_to_support = round(((p - support) / support) * 100.0, 2) if support else 0.0
        distance_to_resistance = round(((resistance - p) / resistance) * 100.0, 2) if resistance else 0.0

        log_message(
            f"🛡️ {symbol} | Price={p:.6f} | S={support:.6f} R={resistance:.6f} | "
            f"pos={position} | distS={dist_s_abs:.6f} distR={dist_r_abs:.6f} | "
            f"ATR={atr:.6f} BBw={bb_width_abs:.6f} ({bb_width_pct:.4f}%) | "
            f"score={score} | breakout={breakout_state}"
        )

        return {
            "support_resistance": {
                "support": round(float(support), 6),
                "resistance": round(float(resistance), 6),
                "position": position,  # тільки near_support/between/near_resistance
                "distance_to_support": distance_to_support,
                "distance_to_resistance": distance_to_resistance,
                "score": float(score),
                "raw_values": {
                    "price": round(float(p), 6),
                    "atr": round(float(atr), 6),
                    "bb_width_abs": round(float(bb_width_abs), 6),
                    "bb_width_pct": round(float(bb_width_pct), 6) if bb_width_pct else 0.0,
                    "swing_lows": [float(x) for x in swing_lows][-50:],
                    "swing_highs": [float(x) for x in swing_highs][-50:],
                    "clustered_lows": [float(x) for x in lows_cl][-20:],
                    "clustered_highs": [float(x) for x in highs_cl][-20:],
                    "breakout_state": breakout_state,
                    "near_support_by": {
                        "abs_dist": round(dist_s_abs, 6),
                        "via_atr": atr > 0 and (dist_s_abs <= near_thr_atr * atr),
                        "via_bbw": bb_width_abs > 0 and (dist_s_abs <= near_thr_bw * bb_width_abs),
                        "via_pct": (dist_s_abs / p) <= near_thr_pct
                    },
                    "near_resistance_by": {
                        "abs_dist": round(dist_r_abs, 6),
                        "via_atr": atr > 0 and (dist_r_abs <= near_thr_atr * atr),
                        "via_bbw": bb_width_abs > 0 and (dist_r_abs <= near_thr_bw * bb_width_abs),
                        "via_pct": (dist_r_abs / p) <= near_thr_pct
                    }
                }
            }
        }

    except Exception as e:
        log_error(f"❌ analyze_support_resistance помилка: {e}")
        return {
            "support_resistance": {
                "support": 0.0,
                "resistance": 0.0,
                "position": "unknown",
                "distance_to_support": 0.0,
                "distance_to_resistance": 0.0,
                "score": 0.0,
                "raw_values": {}
            }
        }



def get_volatility(symbol):
    """
    📊 Оцінка волатильності (15хв) із класифікацією та score.
    Повертає структурований dict для SignalStats.
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="15m", limit=150)
        if df is None or df.empty or len(df) < 20:
            result = {
                "volatility": {
                    "percentage": 0.0,
                    "level": "unknown",
                    "score": 0.0,
                    "raw_values": {}
                }
            }
           
            return result

        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df.dropna(subset=["close"], inplace=True)

        std_dev = df["close"].rolling(window=20).std().iloc[-1]
        avg_price = df["close"].rolling(window=20).mean().iloc[-1]

        if pd.isna(std_dev) or pd.isna(avg_price) or avg_price == 0:
            result = {
                "volatility": {
                    "percentage": 0.0,
                    "level": "unknown",
                    "score": 0.0,
                    "raw_values": {}
                }
            }
          
            return result

        volatility_pct = (std_dev / avg_price) * 100

        # 🧠 Категоризація
        if volatility_pct < 0.5:
            level = "very_low"
            score = -5.0
        elif volatility_pct < 1.0:
            level = "low"
            score = -2.0
        elif volatility_pct < 2.0:
            level = "medium"
            score = 0.0
        elif volatility_pct < 3.5:
            level = "high"
            score = 2.0
        else:
            level = "very_high"
            score = 5.0

        log_message(f"📊 Волатильність {symbol}: {volatility_pct:.2f}% → {level} | Score: {score}")

        result = {
            "volatility": {
                "percentage": round(volatility_pct, 2),
                "level": level,
                "score": round(score, 2),
                "raw_values": {
                    "std_dev": round(std_dev, 6),
                    "avg_price": round(avg_price, 6)
                }
            }
        }
       
        return result

    except Exception as e:
        log_error(f"❌ get_volatility помилка: {e}")
        result = {
            "volatility": {
                "percentage": 0.0,
                "level": "unknown",
                "score": 0.0,
                "raw_values": {}
            }
        }
      
        return result

    
def detect_candlestick_patterns(symbol, interval="15m", limit=40):
    """
    🕯️ Чутливіші та чистіші свічкові патерни (TA-Lib + власні фільтри якості).
    Повертає:
      {
        "candlestick": {
          "patterns": [{"type": "...", "direction": "...", "index": int, "quality": float}],
          "score": float,
          "raw_values": { ... діагностика ... }
        }
      }
    """
    try:
        df = get_klines_clean_bybit(symbol, interval=interval, limit=limit)
        if df is None or df.empty or len(df) < 10:
            return {"candlestick": {"patterns": [], "score": 0.0, "raw_values": {}}}

        df = df.dropna(subset=["open", "high", "low", "close"]).copy()
        open_, high, low, close = [df[c].astype(float).values for c in ["open","high","low","close"]]

        # TA-Lib сирі сигнали
        eng = talib.CDLENGULFING(open_, high, low, close)
        ham = talib.CDLHAMMER(open_, high, low, close)
        sst = talib.CDLSHOOTINGSTAR(open_, high, low, close)
        evs = talib.CDLEVENINGSTAR(open_, high, low, close)
        mns = talib.CDLMORNINGSTAR(open_, high, low, close)
        dji = talib.CDLDOJI(open_, high, low, close)

        n = len(df)
        last_n = min(12, n)          # дивимось ширше в історію, але з пріоритетом «свіжих»
        look_idxs = list(range(n - last_n, n))

        patterns = []
        raws = {}  # для діагностики по індексах

        def body(i):
            return abs(close[i] - open_[i])

        def range_(i):
            return max(high[i] - low[i], 1e-12)

        def upper_wick(i):
            return high[i] - max(open_[i], close[i])

        def lower_wick(i):
            return min(open_[i], close[i]) - low[i]

        # якісні умови
        def is_doji(i):   # дуже мале тіло
            return body(i) / range_(i) <= 0.08

        def is_hammer(i): # довга нижня тінь, короткий верх, невелике тіло
            return (lower_wick(i) >= 2.5 * body(i)) and (upper_wick(i) <= 0.35 * body(i)) and (body(i)/range_(i) <= 0.35)

        def is_shooting_star(i):
            return (upper_wick(i) >= 2.5 * body(i)) and (lower_wick(i) <= 0.35 * body(i)) and (body(i)/range_(i) <= 0.35)

        def is_engulf_bull(i):
            if i == 0: return False
            prev_body_low  = min(open_[i-1], close[i-1])
            prev_body_high = max(open_[i-1], close[i-1])
            cur_body_low   = min(open_[i], close[i])
            cur_body_high  = max(open_[i], close[i])
            # тіло bullish і повністю перекриває попереднє тіло
            return (close[i] > open_[i]) and (cur_body_low <= prev_body_low) and (cur_body_high >= prev_body_high)

        def is_engulf_bear(i):
            if i == 0: return False
            prev_body_low  = min(open_[i-1], close[i-1])
            prev_body_high = max(open_[i-1], close[i-1])
            cur_body_low   = min(open_[i], close[i])
            cur_body_high  = max(open_[i], close[i])
            return (close[i] < open_[i]) and (cur_body_low <= prev_body_low) and (cur_body_high >= prev_body_high)

        # вага за «свіжість» (останнє > попередні)
        def recency_weight(i):
            # i ближче до n-1 → вага ближча до 1.0; глибше → до 0.4
            pos = (i - (n - last_n)) / max(last_n - 1, 1)
            return 0.4 + 0.6 * pos

        # базові ваги типів
        base_w = {
            "engulfing": 8.0,
            "hammer": 6.0,
            "shooting_star": 6.0,
            "evening_star": 10.0,
            "morning_star": 10.0,
            "doji": 2.5
        }

        # обхід останніх свічок
        for i in look_idxs:
            r = {
                "idx": int(i),
                "open": float(open_[i]),
                "close": float(close[i]),
                "high": float(high[i]),
                "low": float(low[i]),
                "body": float(body(i)),
                "range": float(range_(i)),
                "u_wick": float(upper_wick(i)),
                "l_wick": float(lower_wick(i)),
                "talib": {
                    "engulfing": int(eng[i]),
                    "hammer": int(ham[i]),
                    "shooting_star": int(sst[i]),
                    "evening_star": int(evs[i]),
                    "morning_star": int(mns[i]),
                    "doji": int(dji[i]),
                }
            }
            raws[i] = r

            cand = []
            # суворі engulfing
            if is_engulf_bull(i) or eng[i] > 0:
                cand.append(("engulfing", "bullish"))
            if is_engulf_bear(i) or eng[i] < 0:
                cand.append(("engulfing", "bearish"))

            # hammer / shooting star з морфологією
            if is_hammer(i) or ham[i] != 0:
                cand.append(("hammer", "bullish"))
            if is_shooting_star(i) or sst[i] != 0:
                cand.append(("shooting_star", "bearish"))

            # evening/morning star з TA-Lib (вони самі вже строгі)
            if evs[i] != 0:
                cand.append(("evening_star", "bearish"))
            if mns[i] != 0:
                cand.append(("morning_star", "bullish"))

            # doji — лише «тонкі»
            if is_doji(i) or dji[i] != 0 and body(i)/range_(i) <= 0.12:
                cand.append(("doji", "neutral"))

            if not cand:
                continue

            w = recency_weight(i)
            for (ptype, direction) in cand:
                quality = base_w.get(ptype, 3.0) * w
                patterns.append({
                    "type": ptype,
                    "direction": direction,
                    "index": int(i),
                    "quality": round(quality, 2)
                })

        if not patterns:
            log_message(f"🕯️ Патернів не знайдено для {symbol}")
            return {"candlestick": {"patterns": [], "score": 0.0, "raw_values": {}}}

        # 1) усунення конфліктів: якщо є bull і bear одного типу — беремо найсвіжіший з вищою якістю
        dedup = {}
        for p in patterns:
            key = (p["type"], p["direction"])
            # для протилежних напрямків одного типу дозволимо лише найновіший запис
            existing_same = dedup.get(key)
            if existing_same is None or (p["index"] > existing_same["index"] and p["quality"] >= existing_same["quality"]):
                dedup[key] = p

        # 2) якщо після цього лишились і bull, і bear для одного типу — залишимо той, що ближче до поточної свічки
        by_type = {}
        for p in dedup.values():
            by_type.setdefault(p["type"], []).append(p)
        resolved = []
        for t, lst in by_type.items():
            if len({x["direction"] for x in lst}) == 2:
                lst.sort(key=lambda x: (x["index"], x["quality"]), reverse=True)
                resolved.append(lst[0])
            else:
                resolved.extend(lst)

        # підсумковий скор (обмежимо, щоб не «перегрівати»)
        total_score = round(min(sum(p["quality"] for p in resolved), 25.0), 2)

        # відсортуємо за «свіжістю/якістю»
        resolved.sort(key=lambda x: (x["index"], x["quality"]), reverse=True)

        log_message(f"🕯️ {symbol}: знайдено {len(resolved)} патернів → {', '.join(p['type'] for p in resolved)} | score={total_score}")

        return {
            "candlestick": {
                "patterns": resolved,
                "score": total_score,
                "raw_values": raws
            }
        }

    except Exception as e:
        log_error(f"❌ detect_candlestick_patterns помилка: {e}")
        return {"candlestick": {"patterns": [], "score": 0.0, "raw_values": {}}}


def analyze_rsi(symbol, period=14, interval="15"):
    """
    📉 RSI (15m) з підвищеною чутливістю:
    - Тренд за останні 3 бари RSI (сума дельт)
    - Зони 40/60 замість 45/55 для моментуму
    - Розширені лейбли: bullish_momentum / bearish_momentum, але не душимо інші сигнали
    """
    df = get_klines_clean_bybit(symbol, interval=interval, limit=120)
    if df is None or df.empty or len(df) < period + 10:
        return {
            "rsi": {
                "signal": "neutral",
                "value": None,
                "trend": "unknown",
                "score": 0.0,
                "raw_values": {},
                "last_5_values": []
            }
        }

    try:
        close = df["close"].astype(float)
        df['rsi'] = ta.momentum.rsi(close, window=period)
        if df['rsi'].isna().all():
            raise ValueError("RSI all NaN")

        latest = float(df['rsi'].iloc[-1])
        prev = float(df['rsi'].iloc[-2])
        last_5 = df['rsi'].tail(5).round(2).tolist()

        # Тренд за останні 3 дельти
        d3 = df['rsi'].diff().tail(3).sum()
        if d3 > 0:
            trend = "up"
        elif d3 < 0:
            trend = "down"
        else:
            trend = "flat"

        # Базові сигнали зон
        signal = "neutral"
        score = 0.0
        if latest >= 80:
            signal, score = "extremely_overbought", -6.0
        elif latest >= 70:
            signal, score = "overbought", -3.0
        elif latest <= 20:
            signal, score = "extremely_oversold", +6.0
        elif latest <= 30:
            signal, score = "oversold", +3.0

        # Моментум-зони 40/60
        if 40 < latest < 60:
            # лишаємо поточний signal (може бути neutral), але оцінюємо моментум
            pass
        elif latest >= 60 and trend == "up":
            signal, score = "bullish_momentum", max(score, +1.5)
        elif latest <= 40 and trend == "down":
            signal, score = "bearish_momentum", min(score, -1.5)

        return {
            "rsi": {
                "signal": signal,
                "value": round(latest, 2),
                "trend": trend,
                "score": round(score, 2),
                "raw_values": {
                    "latest_rsi": round(latest, 4),
                    "previous_rsi": round(prev, 4),
                    "delta3": round(float(d3), 4)
                },
                "last_5_values": last_5
            }
        }

    except Exception as e:
        log_error(f"❌ analyze_rsi помилка для {symbol}: {e}")
        return {
            "rsi": {
                "signal": "neutral",
                "value": None,
                "trend": "unknown",
                "score": 0.0,
                "raw_values": {},
                "last_5_values": []
            }
        }


def get_micro_trend_1m(symbol):
    """
    🔍 Мікро-тренд на 1m (чутливіша/стабільніша версія):
    - EMA10 (швидка) + EMA30 (повільна)
    - Середня похідна EMA10 за 3 бари (замість одиночної)
    - ATR(10) як міра мікроволатильності
    - Пороги м’якші, але з фільтрами від шуму
    СХЕМА ВИХОДУ НЕ ЗМІНЕНА.
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="1m", limit=200)
        if df is None or df.empty or len(df) < 40:
            return {
                "micro_trend_1m": {
                    "direction": "NEUTRAL",
                    "diff_pct": None,
                    "slope": None,
                    "score": 0.0,
                    "strength": "weak",
                    "last_price": None,
                    "ema10_trend": "flat",
                    "volatility": None,
                    "raw_values": {},
                    "last_5_values": {}
                },
                "microtrend_direction": "NEUTRAL"
            }

        # числові колонки
        for col in ("open", "high", "low", "close"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"])
        if df.empty:
            raise ValueError("no valid OHLC data")

        # EMA10 / EMA30
        ema_fast = df["close"].ewm(span=10, adjust=False).mean()
        ema_slow = df["close"].ewm(span=30, adjust=False).mean()

        # Похідна EMA10 + згладження за останні 3 бари
        ema10_diff = ema_fast.diff()
        ema10_slope_mean3 = ema10_diff.tail(3).mean()

        # ATR(10) як мікроволатильність (масштаб змін)
        # ATR≈ |high-low| з EMA усередненням
        tr = (df["high"] - df["low"]).abs()
        atr10 = tr.ewm(span=10, adjust=False).mean()

        last_close = float(df["close"].iloc[-1])
        last_ema_fast = float(ema_fast.iloc[-1])
        last_atr = float(atr10.iloc[-1]) if pd.notna(atr10.iloc[-1]) else 0.0

        # Захист від ділення на нуль / NaN
        if not np.isfinite(last_ema_fast) or last_ema_fast == 0:
            last_ema_fast = max(last_close, 1e-8)
        if not np.isfinite(last_atr):
            last_atr = 0.0
        if not np.isfinite(ema10_slope_mean3):
            ema10_slope_mean3 = 0.0

        # Наскільки ціна вище/нижче EMA10 у % (diff_pct)
        diff_pct = ((last_close - last_ema_fast) / last_ema_fast) * 100.0

        # Оцінка сили: нормалізуємо нахил відносно ціни (в %) і дивимось на ATR
        slope_pct = (ema10_slope_mean3 / last_ema_fast) * 100.0 if last_ema_fast else 0.0

        # Категоризація сили тренду (м’якша, але не шум)
        # додатково вимагаємо мінімальну волатильність, якщо ATR близько нуля — сила=weak
        if abs(slope_pct) > 0.06 and abs(diff_pct) > 0.5 and last_atr > 0:
            strength = "strong"
        elif abs(slope_pct) > 0.03 and abs(diff_pct) > 0.25 and last_atr > 0:
            strength = "moderate"
        else:
            strength = "weak"

        # Напрям EMA10 за останні 3 бари
        ema_trend = "up" if ema10_slope_mean3 > 0 else "down" if ema10_slope_mean3 < 0 else "flat"

        # Визначення напрямку (пороги чутливіші за попередні)
        trend = "NEUTRAL"
        score = 0.0

        # сильний ап/даун якщо і diff_pct, і slope_pct достатні
        if diff_pct > 0.6 and slope_pct > 0.05:
            trend = "STRONG_BULLISH"
            score = 4.0
        elif diff_pct > 0.25 and slope_pct > 0.0:
            trend = "BULLISH"
            score = 2.0
        elif diff_pct < -0.6 and slope_pct < -0.05:
            trend = "STRONG_BEARISH"
            score = -4.0
        elif diff_pct < -0.25 and slope_pct < 0.0:
            trend = "BEARISH"
            score = -2.0
        else:
            # якщо зовсім мало сигналів, лишаємо NEUTRAL;
            # але якщо низький ATR і майже нульові зсуви — UNCERTAIN
            if abs(diff_pct) < 0.15 and abs(slope_pct) < 0.01:
                trend = "UNCERTAIN"
                score = 0.0

        log_message(
            f"📈 [DEBUG] Micro1m {symbol} → Close={last_close:.5f}, EMA10={last_ema_fast:.5f}, "
            f"diff={diff_pct:.2f}%, slope%={slope_pct:.3f}%, ATR10={last_atr:.6f} → {trend} ({strength})"
        )

        return {
            "micro_trend_1m": {
                "direction": trend,
                "diff_pct": round(diff_pct, 2),
                "slope": round(float(ema10_slope_mean3), 5),
                "score": round(float(score), 2),
                "strength": strength,
                "last_price": round(last_close, 5),
                "ema10_trend": "up" if ema10_slope_mean3 > 0 else "down" if ema10_slope_mean3 < 0 else "flat",
                "volatility": round(float(last_atr), 6),
                "raw_values": {
                    "ema10_last": round(float(last_ema_fast), 6),
                    "slope_mean3": round(float(ema10_slope_mean3), 6),
                    "slope_pct": round(float(slope_pct), 4)
                },
                "last_5_values": {
                    "ema10": [float(x) if np.isfinite(x) else 0.0 for x in ema_fast.tail(5).round(6).tolist()],
                    "ema10_slope": [float(x) if np.isfinite(x) else 0.0 for x in ema10_diff.tail(5).round(6).tolist()],
                    "close": [float(x) if np.isfinite(x) else 0.0 for x in df["close"].tail(5).round(6).tolist()]
                }
            },
            "microtrend_direction": trend
        }

    except Exception as e:
        log_error(f"❌ get_micro_trend_1m помилка: {e}")
        return {
            "micro_trend_1m": {
                "direction": "NEUTRAL",
                "diff_pct": 0.0,
                "slope": 0.0,
                "score": 0.0,
                "strength": "weak",
                "last_price": 0.0,
                "ema10_trend": "flat",
                "volatility": 0.0,
                "raw_values": {},
                "last_5_values": {
                    "ema10": [],
                    "ema10_slope": [],
                    "close": []
                }
            },
            "microtrend_direction": "NEUTRAL"
        }


def calculate_macd(close_series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    try:
        ema_fast = close_series.ewm(span=fast, adjust=False).mean()
        ema_slow = close_series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return {
            "macd": macd_line.fillna(0),
            "signal": signal_line.fillna(0),
            "histogram": histogram.fillna(0)
        }
    except Exception as e:
        log_error(f"❌ [calculate_macd] Помилка: {e}")
        return {
            "macd": pd.Series([0] * len(close_series)),
            "signal": pd.Series([0] * len(close_series)),
            "histogram": pd.Series([0] * len(close_series))
        }

def calculate_rsi(close_series: pd.Series, period: int = 14):
    try:
        delta = close_series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

        rs = avg_gain / (avg_loss + 1e-6)
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50)
    except Exception as e:
        log_error(f"❌ [calculate_rsi] Помилка: {e}")
        return pd.Series([50] * len(close_series))


def detect_patterns_for_dataframe(df: pd.DataFrame) -> list:
    """
    🔍 Визначає найсильніший патерн на кожній свічці з TA-Lib.
    Повертає список патернів або 'none', якщо не знайдено.
    """
    try:
        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            raise ValueError("⛔️ Відсутні потрібні колонки OHLC в DataFrame.")

        df = df.dropna(subset=required_cols)

        # 🔢 Явний пріоритет патернів
        pattern_funcs = {
            "engulfing": talib.CDLENGULFING,
            "hammer": talib.CDLHAMMER,
            "shooting_star": talib.CDLSHOOTINGSTAR,
            "morning_star": talib.CDLMORNINGSTAR,
            "evening_star": talib.CDLEVENINGSTAR,
            "doji": talib.CDLDOJI,
        }

        results = {
            name: func(df["open"], df["high"], df["low"], df["close"])
            for name, func in pattern_funcs.items()
        }

        patterns = []
        for i in range(len(df)):
            selected_pattern = "none"
            for name in pattern_funcs.keys():  # Дотримуйся пріоритету
                series = results[name]
                if i >= len(series):
                    continue
                value = series.iloc[i]
                if value > 0:
                    selected_pattern = f"{name}_bull"
                    break
                elif value < 0:
                    selected_pattern = f"{name}_bear"
                    break
            patterns.append(selected_pattern)

        return patterns

    except Exception as e:
        log_error(f"❌ [detect_patterns_for_dataframe] Помилка: {e}")
        return ["none"] * len(df)


def calculate_stoch(df, period: int = 14) -> pd.DataFrame:
    try:
        required_cols = ["high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            raise ValueError("DataFrame має містити колонки: 'high', 'low', 'close'")

        low_min = df["low"].rolling(window=period).min()
        high_max = df["high"].rolling(window=period).max()
        denom = high_max - low_min

        stoch_k = np.where(denom == 0, 0, 100 * (df["close"] - low_min) / denom)
        stoch_k = pd.Series(stoch_k, index=df.index).fillna(0)
        stoch_d = stoch_k.rolling(window=3).mean().fillna(0)

        # 🎯 Додатковий сигнал
        signal = []
        for k, d in zip(stoch_k, stoch_d):
            if k > 80 and k < d:
                signal.append("bearish")
            elif k < 20 and k > d:
                signal.append("bullish")
            else:
                signal.append("neutral")

        return pd.DataFrame({
            "stoch_k": stoch_k,
            "stoch_d": stoch_d,
            "signal": signal
        })

    except Exception as e:
        log_error(f"❌ [calculate_stoch] Помилка: {e}")
        return pd.DataFrame({
            "stoch_k": [0]*len(df),
            "stoch_d": [0]*len(df),
            "signal": ["neutral"]*len(df)
        })


def detect_support_status(df: pd.DataFrame, window: int = 20, pct_threshold: float = 0.002) -> pd.Series:
    """
    📉 Визначає, чи знаходиться ціна поблизу підтримки/опору в межах заданого вікна.
    """
    try:
        if not all(col in df.columns for col in ["close", "low", "high"]):
            raise ValueError("DataFrame повинен містити колонки 'close', 'low', 'high'")

        status = ["neutral"] * len(df)

        for i in range(window, len(df)):
            window_df = df.iloc[i - window:i]
            recent_low = window_df["low"].min()
            recent_high = window_df["high"].max()
            current_price = df["close"].iloc[i]

            low_dist = abs(current_price - recent_low) / current_price
            high_dist = abs(current_price - recent_high) / current_price

            if low_dist <= pct_threshold:
                status[i] = "support"
            elif high_dist <= pct_threshold:
                status[i] = "resistance"

        return pd.Series(status, index=df.index)

    except Exception as e:
        log_error(f"❌ [detect_support_status] Помилка: {e}")
        return pd.Series(["neutral"] * len(df), index=df.index)


def add_sparklines(history_log: list, field: str = "price", window: int = 5) -> list:
    try:
        for i in range(len(history_log)):
            spark = []
            for j in range(i - window + 1, i + 1):
                if 0 <= j < len(history_log):
                    val = history_log[j].get(field)
                    if isinstance(val, (int, float)):
                        spark.append(val)
            history_log[i]["sparkline_" + field] = spark
        return history_log

    except Exception as e:
        log_error(f"❌ [add_sparklines] Помилка: {e}")
        return history_log


def get_micro_trend_5m(symbol):
    """
    📉 Розширений аналіз мікротренду на 5m (чутливіша/стійкіша версія):
    - EMA20 (швидша) + EMA50 (повільніша)
    - Середній нахил EMA20 за 3 бари (slope_mean3) → менше шуму
    - ATR(14) як реалістична міра волатильності (та її % до ціни)
    - М'якші пороги + прості breakout-умови
    СХЕМА ВИХОДУ НЕ ЗМІНЕНА.
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="5m", limit=120)
        if df is None or df.empty or len(df) < 20:
            return {
                "microtrend_direction": "flat",
                "micro_trend_5m": {
                    "direction": "flat",
                    "score": 0.0,
                    "change_pct": 0.0,
                    "volatility": 0.0,
                    "start_price": None,
                    "end_price": None,
                    "raw_values": {},
                    "last_5_values": {}
                }
            }

        # числові стовпці
        for col in ("open", "high", "low", "close"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce")
        df = df.dropna(subset=["open", "high", "low", "close"])
        if df.empty:
            raise ValueError("no valid OHLC data")

        # Вікно аналізу (останні ~30 хв = 6 барів по 5m)
        lookback_bars = 6
        recent = df.tail(max(lookback_bars, 6))

        start_price = float(recent["close"].iloc[0])
        end_price   = float(recent["close"].iloc[-1])
        if start_price == 0:
            start_price = 1e-8

        change_pct = ((end_price - start_price) / start_price) * 100.0

        # EMA20 / EMA50
        ema_fast = df["close"].ewm(span=20, adjust=False).mean()
        ema_slow = df["close"].ewm(span=50, adjust=False).mean()

        # Нахил EMA20 (середній за 3 бари)
        ema20_diff = ema_fast.diff()
        slope_mean3 = float(ema20_diff.tail(3).mean() or 0.0)

        last_close = float(df["close"].iloc[-1])
        last_ema20 = float(ema_fast.iloc[-1]) if pd.notna(ema_fast.iloc[-1]) else last_close
        last_ema50 = float(ema_slow.iloc[-1]) if pd.notna(ema_slow.iloc[-1]) else last_close

        if last_ema20 == 0:
            last_ema20 = max(last_close, 1e-8)

        # Нормалізований нахил у % до ціни
        slope_pct = (slope_mean3 / last_ema20) * 100.0

        # ATR(14) і його % до ціни як «волатильність»
        tr = (df["high"] - df["low"]).abs()
        atr14 = tr.ewm(span=14, adjust=False).mean()
        last_atr = float(atr14.iloc[-1]) if pd.notna(atr14.iloc[-1]) else 0.0
        vol_pct = (last_atr / last_close) * 100.0 if last_close > 0 else 0.0

        # Діапазон останніх барів (для breakout)
        hi_recent = float(recent["high"].max())
        lo_recent = float(recent["low"].min())

        # Базові пороги (м’якші, ніж у версії без EMA/ATR)
        direction = "flat"
        score = 0.0

        bullish_bias = (last_ema20 > last_ema50)
        bearish_bias = (last_ema20 < last_ema50)

        # Breakout-сигнали (не надто агресивні, але чутливіші)
        breakout_up = (last_close > hi_recent * 0.998) and (change_pct > 0.6)
        breakout_down = (last_close < lo_recent * 1.002) and (change_pct < -0.6)

        if (change_pct >= 1.2 and slope_pct > 0.04 and bullish_bias) or breakout_up:
            direction = "strong_bullish"
            score = 4.0
        elif change_pct >= 0.4 and slope_pct > 0.0:
            direction = "bullish"
            score = 2.0
        elif (change_pct <= -1.2 and slope_pct < -0.04 and bearish_bias) or breakout_down:
            direction = "strong_bearish"
            score = -4.0
        elif change_pct <= -0.4 and slope_pct < 0.0:
            direction = "bearish"
            score = -2.0
        else:
            direction = "flat"
            score = 0.0

        result = {
            "microtrend_direction": direction,
            "micro_trend_5m": {
                "direction": direction,
                "score": round(score, 2),
                "change_pct": round(change_pct, 2),
                # зберігаємо «volatility» як % (узгоджено з попереднім підходом)
                "volatility": round(vol_pct, 2),
                "start_price": round(start_price, 6),
                "end_price": round(end_price, 6),
                "raw_values": {
                    "ema20_last": round(last_ema20, 6),
                    "ema50_last": round(last_ema50, 6),
                    "slope_mean3": round(slope_mean3, 6),
                    "slope_pct": round(slope_pct, 4),
                    "atr14": round(last_atr, 6),
                    "hi_recent": round(hi_recent, 6),
                    "lo_recent": round(lo_recent, 6),
                    "bullish_bias": bullish_bias,
                    "bearish_bias": bearish_bias,
                    "breakout_up": breakout_up,
                    "breakout_down": breakout_down
                },
                "last_5_values": {
                    "close": [float(x) for x in df["close"].tail(5).round(6).tolist()],
                    "high":  [float(x) for x in df["high"].tail(5).round(6).tolist()],
                    "low":   [float(x) for x in df["low"].tail(5).round(6).tolist()]
                }
            }
        }

        log_message(
            f"📊 [DEBUG] {symbol} 5m → Δ={change_pct:.2f}%, slope%={slope_pct:.3f}%, "
            f"ATR%={vol_pct:.2f} → {direction} (ema20{ '>' if bullish_bias else '<' if bearish_bias else '=' }ema50)"
        )
        return result

    except Exception as e:
        log_error(f"❌ get_micro_trend_5m помилка для {symbol}: {e}")
        return {
            "microtrend_direction": "flat",
            "micro_trend_5m": {
                "direction": "flat",
                "score": 0.0,
                "change_pct": 0.0,
                "volatility": 0.0,
                "start_price": 0.0,
                "end_price": 0.0,
                "raw_values": {
                    "high": 0.0,
                    "low": 0.0
                },
                "last_5_values": {
                    "close": [],
                    "high": [],
                    "low": []
                }
            }
        }


def get_volume_category(symbol):
    """
    📊 Чутливіший аналіз обʼєму на 5m:
      - EMA(20) як згладжений baseline
      - median_ratio як базовий рівень активності
      - z-score спайків (аномалій)
    Повертає {"volume": {...}} як і раніше.
    """
    try:
        df = get_klines_clean_bybit(symbol, interval="5m", limit=288)
        if df is None or df.empty or "volume" not in df.columns or len(df) < 30:
            return {
                "volume": {
                    "level": "normal",
                    "score": 0.0,
                    "average_volume": 0.0,
                    "recent_volume": 0.0,
                    "raw_values": {"ratio": 0.0, "zscore": 0.0},
                    "last_5_values": []
                }
            }

        v = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        if v.sum() == 0:
            return {
                "volume": {
                    "level": "normal",
                    "score": 0.0,
                    "average_volume": 0.0,
                    "recent_volume": 0.0,
                    "raw_values": {"ratio": 0.0, "zscore": 0.0},
                    "last_5_values": []
                }
            }

        ema20 = v.ewm(span=20, adjust=False).mean()
        recent = float(v.iloc[-1])
        base = float(ema20.iloc[-1]) if pd.notna(ema20.iloc[-1]) else float(v.mean())
        base = max(base, 1e-8)

        ratio = recent / base

        # медіанний baseline по ratio → менше чутливий до викидів
        ratio_series = (v / (ema20.replace(0, pd.NA))).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        median_ratio = float(ratio_series.rolling(60, min_periods=30).median().iloc[-1] or 1.0)

        # z-score по лог-обʼєму, щоб ловити імпульсні свічки
        logv = np.log(np.clip(v, 1e-8, None))
        mean_l = float(logv.rolling(60, min_periods=30).mean().iloc[-1] or logv.mean())
        std_l  = float(logv.rolling(60, min_periods=30).std().iloc[-1] or logv.std() or 1e-8)
        zscore = (float(logv.iloc[-1]) - mean_l) / std_l

        # класифікація (чутливі пороги, але не «істеричні»)
        # спершу — аномальні спайки обʼєму
        if zscore >= 2.5 or ratio >= 2.2:
            level, score = "very_high", 5.0
        elif zscore >= 1.5 or ratio >= 1.6:
            level, score = "high", 2.0
        elif ratio <= 0.25:
            level, score = "very_low", -5.0
        elif ratio <= 0.55:
            level, score = "low", -2.0
        else:
            # якщо фоном медіанний рівень активності пригнічений — притискаємо до 'low'
            if median_ratio < 0.6 and ratio < 0.9:
                level, score = "low", -1.0
            else:
                level, score = "normal", 0.0

        return {
            "volume": {
                "level": level,
                "score": round(score, 2),
                "average_volume": round(float(v.mean()), 2),
                "recent_volume": round(recent, 2),
                "raw_values": {
                    "ratio": round(ratio, 4),
                    "median_ratio": round(median_ratio, 4),
                    "zscore": round(zscore, 3),
                    "ema20": round(base, 2)
                },
                "last_5_values": v.tail(5).round(2).tolist()
            }
        }

    except Exception as e:
        log_error(f"❌ [get_volume_category] Глобальна помилка для {symbol}: {e}")
        return {
            "volume": {
                "level": "normal",
                "score": 0.0,
                "average_volume": 0.0,
                "recent_volume": 0.0,
                "raw_values": {"ratio": 0.0, "zscore": 0.0},
                "last_5_values": []
            }
        }

def analyze_volume(symbol):
    """
    🔄 Сумісний контракт для build_monitor_snapshot:
    повертає {"volume_analysis": {...}} на основі get_volume_category(...)
    """
    vol = get_volume_category(symbol)
    # мапимо "volume" -> "volume_analysis" без зміни змісту
    return {
        "volume_analysis": {
            "level":        vol["volume"]["level"],
            "method":       "ema20_ratio_zscore",
            "raw_values":   vol["volume"]["raw_values"],
        }
    }


def detect_rsi_divergence(symbol, interval="5", limit=60):
    """
    🔍 RSI-дивергенції з відбором локальних екстремумів (swing points):
      - шукаємо локальні мінімуми/максимуми ціни та їх RSI
      - вимагаємо мінімальну відстань між точками (min_sep)
      - невеликий tolerance, щоб не ловити «пил»
    Повертає:
      {"rsi_divergence": {"type": "bullish"/"bearish"/"none", "score": +/-6.0, "raw_values": {...}}}
    """
    try:
        df = get_klines_clean_bybit(symbol, interval=interval, limit=limit)
        if df is None or df.empty or len(df) < 20:
            return {"rsi_divergence": {"type": "none", "score": 0.0, "raw_values": {}}}

        df = df.copy()
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["close"])
        if df.empty:
            return {"rsi_divergence": {"type": "none", "score": 0.0, "raw_values": {}}}

        rsi = calculate_rsi(df["close"]).fillna(50)
        df["rsi"] = rsi

        # локальні екстремуми (простий 3-барний підхід)
        def local_minima(s: pd.Series):
            return (s.shift(1) > s) & (s.shift(-1) > s)

        def local_maxima(s: pd.Series):
            return (s.shift(1) < s) & (s.shift(-1) < s)

        mins_idx = df.index[local_minima(df["close"]).fillna(False)]
        maxs_idx = df.index[local_maxima(df["close"]).fillna(False)]

        # візьмемо останні 6 кандидатів кожного типу
        mins_idx = mins_idx[-6:]
        maxs_idx = maxs_idx[-6:]

        # вимагаємо рознесення точок у часі (мін. 3 бари)
        min_sep = 3
        def filter_sep(idxs):
            kept = []
            for i in idxs:
                if not kept or (i - kept[-1]) >= min_sep:
                    kept.append(i)
            return kept

        mins_idx = filter_sep(list(mins_idx))
        maxs_idx = filter_sep(list(maxs_idx))

        raw = {}

        # === Bullish: price LL, RSI HL
        if len(mins_idx) >= 2:
            i1, i2 = mins_idx[-2], mins_idx[-1]
            p1, p2 = float(df.loc[i1, "close"]), float(df.loc[i2, "close"])
            r1, r2 = float(df.loc[i1, "rsi"]), float(df.loc[i2, "rsi"])

            raw["bullish"] = {
                "low_1": {"idx": int(i1), "price": round(p1, 6), "rsi": round(r1, 2)},
                "low_2": {"idx": int(i2), "price": round(p2, 6), "rsi": round(r2, 2)}
            }

            price_tol = 0.0005 * max(p1, p2)  # ~0.05% толеранс
            rsi_tol = 0.5                      # 0.5 пункту RSI

            if (p2 < p1 - price_tol) and (r2 > r1 + rsi_tol):
                return {"rsi_divergence": {"type": "bullish", "score": 6.0, "raw_values": raw["bullish"]}}

        # === Bearish: price HH, RSI LH
        if len(maxs_idx) >= 2:
            j1, j2 = maxs_idx[-2], maxs_idx[-1]
            p1, p2 = float(df.loc[j1, "close"]), float(df.loc[j2, "close"])
            r1, r2 = float(df.loc[j1, "rsi"]), float(df.loc[j2, "rsi"])

            raw["bearish"] = {
                "high_1": {"idx": int(j1), "price": round(p1, 6), "rsi": round(r1, 2)},
                "high_2": {"idx": int(j2), "price": round(p2, 6), "rsi": round(r2, 2)}
            }

            price_tol = 0.0005 * max(p1, p2)
            rsi_tol = 0.5

            if (p2 > p1 + price_tol) and (r2 < r1 - rsi_tol):
                return {"rsi_divergence": {"type": "bearish", "score": -6.0, "raw_values": raw["bearish"]}}

        return {"rsi_divergence": {"type": "none", "score": 0.0, "raw_values": raw}}

    except Exception as e:
        log_message(f"⚠️ [detect_rsi_divergence] Обробка завершена з винятком для {symbol}: {e}")
        return {"rsi_divergence": {"type": "none", "score": 0.0, "raw_values": {}}}
