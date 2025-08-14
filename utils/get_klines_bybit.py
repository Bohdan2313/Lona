# utils/get_klines_bybit.py

import time
import pandas as pd
from utils.logger import log_message, log_error,log_debug
from config import bybit


# --- кеші на рівні модуля ---
import time
import pandas as pd

# ── Кеш підтримуваних інструментів / deny-list ────────────────────────────────
_SUPPORTED = {"ts": 0.0, "linear": set(), "spot": set()}
_UNSUPPORTED = {}  # symbol -> ts
_SUPPORTED_TTL = 900        # 15 хв
_UNSUPPORTED_TTL = 3600     # 60 хв

# Універсальна мапа інтервалів для v5 (вимагає хвилини як рядок)
_INTERVAL_MAP = {"1h": "60", "15m": "15", "5m": "5", "1m": "1"}

def _refresh_supported_sets():
    """Оновлює множини підтримуваних символів для linear/spot з кешем на 15 хв."""
    now = time.time()
    if now - _SUPPORTED["ts"] < _SUPPORTED_TTL:
        return

    try:
        linear = bybit.get_instruments_info(category="linear").get("result", {}).get("list", []) or []
        spot   = bybit.get_instruments_info(category="spot").get("result", {}).get("list", []) or []
        _SUPPORTED["linear"] = {x.get("symbol") for x in linear if x.get("symbol")}
        _SUPPORTED["spot"]   = {x.get("symbol") for x in spot if x.get("symbol")}
        _SUPPORTED["ts"] = now
        log_debug(f"✅ Supported sets refreshed: linear={len(_SUPPORTED['linear'])}, spot={len(_SUPPORTED['spot'])}")
    except Exception as e:
        try:
            lin_t  = bybit.get_tickers(category="linear").get("result", {}).get("list", []) or []
            spot_t = bybit.get_tickers(category="spot").get("result", {}).get("list", []) or []
            _SUPPORTED["linear"] = {x.get("symbol") for x in lin_t if x.get("symbol")}
            _SUPPORTED["spot"]   = {x.get("symbol") for x in spot_t if x.get("symbol")}
            _SUPPORTED["ts"] = now
            log_debug(f"♻️ Supported sets via tickers: linear={len(_SUPPORTED['linear'])}, spot={len(_SUPPORTED['spot'])}")
        except Exception as e2:
            log_error(f"❌ Не вдалось оновити supported sets: {e2}")

def _resolve_category(symbol: str):
    """Повертає 'linear' або 'spot' якщо символ підтримується; інакше None."""
    _refresh_supported_sets()
    if symbol in _SUPPORTED["linear"]:
        return "linear"
    if symbol in _SUPPORTED["spot"]:
        return "spot"
    return None

def get_klines_clean_bybit(symbol, interval="1h", limit=200, category=None):
    """
    📦 Отримує Kline-дані від Bybit і повертає чистий DataFrame.
    - Без сліпого fallback з linear → spot (категорію визначаємо наперед).
    - Позначаємо 'unsupported' (retCode 10001) у deny-list на 60 хв.
    - Тихо повертаємо None, якщо символ не підтримується або даних нема.
    """
    try:
        # deny-list: якщо нещодавно було 10001 — пропускаємо
        ts = _UNSUPPORTED.get(symbol)
        if ts and (time.time() - ts) < _UNSUPPORTED_TTL:
            log_debug(f"⛔ {symbol} у deny-list (unsupported) — skip до TTL")
            return None

        # визначаємо категорію (якщо не передали явно)
        cat = category or _resolve_category(symbol)
        if cat is None:
            log_debug(f"⛔ {symbol} не підтримується ні в linear, ні в spot — skip")
            _UNSUPPORTED[symbol] = time.time()
            return None

        # конвертуємо інтервал для v5 (і для linear, і для spot)
        converted_interval = _INTERVAL_MAP.get(interval, str(interval))

        # виклик API
        resp = bybit.get_kline(category=cat, symbol=symbol, interval=converted_interval, limit=limit)

        # обробка коду відповіді
        ret_code = resp.get("retCode")
        if ret_code not in (None, 0):
            if int(ret_code) == 10001:  # Not supported symbols
                _UNSUPPORTED[symbol] = time.time()
                log_message(f"⛔ {symbol}: Not supported (retCode=10001) — додано в deny-list на 60 хв")
                return None
            log_error(f"❌ get_kline retCode={ret_code} для {symbol} ({cat}/{converted_interval})")
            return None

        result = resp.get("result", {}) or {}
        kline_data = result.get("list", []) or []
        if not kline_data:
            log_debug(f"ℹ️ Порожні klines для {symbol} ({cat}/{converted_interval}) — skip")
            return None

        # Bybit v5: елементи — масиви [ts, open, high, low, close, volume, turnover]
        # інколи приходить без 'turnover' → підлаштуємось під фактичну довжину
        base_cols = ["timestamp", "open", "high", "low", "close", "volume", "turnover"]
        df = pd.DataFrame(kline_data, columns=base_cols[:len(kline_data[0])])

        # типи колонок
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(pd.to_numeric(df["timestamp"], errors="coerce"), unit="ms", errors="coerce")

        for c in ("open", "high", "low", "close", "volume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # чистка і сортування
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp").reset_index(drop=True)

        df = df.dropna(subset=[c for c in ("open", "high", "low", "close") if c in df.columns])

        if df.empty:
            return None

        log_debug(f"✅ kline OK: {symbol} {cat} {interval}->{converted_interval} rows={len(df)}")
        return df

    except Exception as e:
        msg = str(e)
        if "10001" in msg and "Not supported" in msg:
            _UNSUPPORTED[symbol] = time.time()
            log_message(f"⛔ {symbol}: позначено unsupported через виняток 10001")
            return None

        log_error(f"❌ get_klines_clean_bybit помилка для {symbol}: {e}")
        return None
