from utils.logger import log_message, log_error

import json
import os
import pandas as pd
import time
from datetime import datetime, timezone
from config import EXCHANGE, client
from config import ACTIVE_TRADES_FILE
from datetime import datetime, timedelta
from config import bybit
from utils.logger import load_active_trades


# -------------------- BALANCE --------------------

# ----- Баланс -----
def get_balance():
    """💰 Отримує доступний USDT баланс для ф’ючерсного акаунта (Binance/Bybit Unified)."""
    try:
        if EXCHANGE == "binance":
            balance_info = client.futures_account_balance()  # list of dicts
            # шукаємо USDT; беремо withdrawAvailable якщо є, інакше balance
            for item in balance_info:
                if item.get("asset") == "USDT":
                    # Binance futures повертає 'withdrawAvailable' і 'balance'
                    val = item.get("withdrawAvailable")
                    if val in (None, "", "0", 0):  # fallback
                        val = item.get("balance", 0)
                    return float(val or 0.0)
            return 0.0

        elif EXCHANGE == "bybit":
            # Unified account
            resp = client.get_wallet_balance(accountType="UNIFIED")
            if resp.get("retCode") != 0:
                log_error(f"get_balance() → bad resp: {resp.get('retMsg')}")
                return 0.0
            lists = (resp.get("result", {}) or {}).get("list", []) or []
            if not lists:
                return 0.0
            coins = lists[0].get("coin", []) or []
            for c in coins:
                if c.get("coin") == "USDT":
                    # пріоритет: availableToTrade → availableToWithdraw → availableBalance → equity
                    val = (c.get("availableToTrade") or
                           c.get("availableToWithdraw") or
                           c.get("availableBalance") or
                           c.get("equity") or 0)
                    return float(val or 0.0)
            return 0.0

        else:
            log_error(f"get_balance() → unknown EXCHANGE='{EXCHANGE}'")
            return 0.0

    except Exception as e:
        log_error(f"get_balance() → {e}")
        return 0.0


def get_usdt_balance():
    """
    💰 Отримує баланс USDT з Bybit або повертає MANUAL_BALANCE, якщо активовано.
    """
    try:
        # 🚀 Перемикач на використання MANUAL_BALANCE
        USE_MANUAL_BALANCE = True  # 👈 постав True для тестів
        MANUAL_BALANCE = 7.0       # 👈 баланс для тестів

        if USE_MANUAL_BALANCE:
            log_message(f"💸 Використовуємо MANUAL_BALANCE: {MANUAL_BALANCE} USDT")
            return MANUAL_BALANCE

        # 🔥 Реальний API запит
        response = client.get_wallet_balance(accountType="UNIFIED", recvWindow=10000)

        if response["retCode"] != 0:
            log_error(f"❌ get_usdt_balance() → Bad response: {response.get('retMsg')}")
            return 0.0

        balances = response.get("result", {}).get("list", [])
        if not balances:
            log_error("⚠️ get_usdt_balance() → Порожній список активів")
            return 0.0

        coins_info = balances[0].get("coin", [])
        for coin_data in coins_info:
            if coin_data.get("coin") == "USDT":
                raw_value = coin_data.get("availableToWithdraw", "0.0")
                if raw_value == "":
                    log_message("⚠️ Bybit повернув порожній баланс для USDT → вважаємо 0.0")
                    return 0.0
                return float(raw_value)

        log_error("⚠️ USDT не знайдено серед монет")
        return 0.0

    except Exception as e:
        error_text = str(e)
        if "timestamp" in error_text or "recv_window" in error_text or "10002" in error_text:
            log_message("⏱️ Timestamp помилка. Синхронізуй локальний час або перевір recvWindow.")
        log_error(f"❌ get_usdt_balance() → Помилка Bybit API: {e}")
        return 0.0



def get_all_usdt_pairs(min_volume_usdt=0, min_trade_usdt=5.0):
    """
    Повертає список USDT-пар, які реально можна торгувати на Bybit (фʼючерси).
    Фільтрує тільки ті, які:
    - активні
    - мають minNotionalValue <= min_trade_usdt
    """
    try:
        response = client.get_instruments_info(category="linear")
        data = response.get("result", {}).get("list", [])
        usdt_pairs = []

        if not data:
            log_message("⚠️ Не отримано монети з Bybit.")
            return []

        log_message(f"📦 Отримано {len(data)} монет з Bybit")

        for item in data:
            symbol = item.get("symbol", "")
            if not symbol.endswith("USDT"):
                continue

            if item.get("status") != "Trading":
                continue

            try:
                min_notional = float(item.get("lotSizeFilter", {}).get("minNotionalValue", 0))
                if min_notional > min_trade_usdt:
                    continue  # Занадто дорогий для мікротрейду

                usdt_pairs.append(symbol)

            except Exception as parse_err:
                log_message(f"⚠️ Пропущено {symbol} через помилку обробки: {parse_err}")
                continue

        log_message(f"✅ Відібрано {len(usdt_pairs)} USDT пар, придатних для мікро-торгівлі.")
        return usdt_pairs

    except Exception as e:
        log_error(f"❌ get_all_usdt_pairs() помилка: {e}")
        return []


def get_current_futures_price(symbol: str):
    """💰 Отримує поточну ціну фʼючерсного контракту з Bybit (unified API)"""
    try:
        response = client.get_tickers(category="linear", symbol=symbol)
        
        if response["retCode"] != 0:
            log_error(f"❌ get_current_futures_price({symbol}) → Bad response: {response.get('retMsg')}")
            return None

        result = response.get("result", {})
        if not result or "list" not in result or not result["list"]:
            log_error(f"⚠️ get_current_futures_price({symbol}) → Порожній список")
            return None

        price = float(result["list"][0]["lastPrice"])
        log_message(f"💰 Поточна ціна {symbol} (futures): {price:.2f}")
        return price

    except Exception as e:
        log_error(f"❌ get_current_futures_price помилка для {symbol}: {e}")
        return None



def get_historical_data(symbol, interval='1m', limit=100):
    """
    Завантажує historical OHLCV дані.
    """
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except Exception as e:
        log_error(f"⚠️ Помилка get_historical_data для {symbol}: {e}")
        return None
    

BLACKLIST_PATH = "data/loss_blacklist.json"
BLACKLIST_DURATION_SECONDS = 2 * 60 * 60  # 2 години


def add_to_blacklist(symbol):
    try:
        if not os.path.exists(BLACKLIST_PATH):
            with open(BLACKLIST_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f)

        with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
            blacklist = json.load(f)

        blacklist[symbol] = time.time()  # ✅ Зберігаємо timestamp (секунди)

        with open(BLACKLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(blacklist, f, indent=2)

        log_message(f"🚫 {symbol} додано до blacklist на 4 години")

    except Exception as e:
        log_error(f"❌ add_to_blacklist помилка: {e}")



def get_current_futures_klines_data(symbol, interval="1", limit=100):
    """
    📊 Отримує останні N свічок для USDT Futures на Bybit.
    Повертає DataFrame з колонками: timestamp, open, high, low, close, volume.
    """
    try:
        response = client.get_kline(
            category="linear",  # USDT Futures
            symbol=symbol,
            interval=str(interval),
            limit=limit
        )

        result = response.get("result", {}).get("list", [])
        if not result:
            return pd.DataFrame()

        # Bybit API повертає від нових до старих — реверсуємо для зручності
        klines = list(reversed(result))

        df = pd.DataFrame(klines, columns=[
            "timestamp", "open", "high", "low", "close", "volume", "turnover"
        ])

        # Використовуємо тільки потрібні колонки
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]

        # Перетворення типів
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Видаляємо невалідні рядки
        df = df.dropna()

        if df.empty:
         return df

    except Exception as e:
        log_error(f"❌ [get_current_futures_klines_data] Bybit помилка для {symbol}: {e}")
        return pd.DataFrame()


def get_price_change(symbol, minutes=5):
    try:
        interval = "1" if minutes <= 5 else "3" if minutes <= 15 else "5"
        df = get_current_futures_klines_data(symbol, interval=interval)
        if isinstance(df, pd.DataFrame) and not df.empty:
            now = int(time.time() * 1000)
            window_start = now - (minutes * 60 * 1000)

            recent = df[df['timestamp'].astype('int64') >= window_start]
            if len(recent) >= 2:
                open_price = recent.iloc[0]['close']
                close_price = recent.iloc[-1]['close']
                if open_price > 0:
                    change_pct = ((close_price - open_price) / open_price) * 100
                    return round(change_pct, 2)
        return 0.0
    except Exception as e:
        log_error(f"[get_price_change] Помилка: {e}")
        return 0.0
    

TRADES_LOG_PATH = "logs/scalping_trades.log"  # заміни, якщо інший

def get_past_trades(symbol, limit=5):
    try:
        if not os.path.exists(TRADES_LOG_PATH):
            return []

        with open(TRADES_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        symbol = symbol.upper()
        results = []

        for line in reversed(lines):
            if symbol in line:
                parts = line.strip().split("|")
                if len(parts) >= 5:
                    pnl_part = parts[3].strip().replace("PnL:", "").replace("%", "")
                    reason_part = parts[4].strip().replace("Причина закриття:", "")
                    try:
                        pnl = float(pnl_part)
                        results.append({"pnl": pnl, "reason": reason_part})
                    except:
                        continue
            if len(results) >= limit:
                break

        return results

    except Exception as e:
        log_error(f"[get_past_trades] Помилка: {e}")
        return []



def get_position_quantity(symbol, position_side):
    try:
        positions = client.futures_position_information(symbol=symbol)
        for pos in positions:
            if pos['symbol'] == symbol and pos['positionSide'] == position_side:
                return abs(float(pos['positionAmt']))
    except Exception as e:
        log_error(f"❌ get_position_quantity() помилка: {e}")
    return 0


def get_klines(symbol: str, interval: str = "1m", lookback: int = 30) -> pd.DataFrame:
    """
    🕰️ Отримує історичні свічки Bybit за останні N хвилин.
    Повертає DataFrame з колонками open_time, open, high, low, close, volume.
    """
    try:
        end_time = int(datetime.utcnow().timestamp() * 1000)
        start_time = end_time - (lookback * 60 * 1000)

        response = client.get_kline(
            category="linear",  # або "inverse" якщо COIN-M
            symbol=symbol,
            interval=interval,
            start=start_time,
            end=end_time,
            limit=min(lookback, 200)
        )

        result = response.get("result", {}).get("list", [])
        if not result:
            return None

        # Bybit віддає від нових до старих, треба перевернути
        klines = list(reversed(result))

        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume"
        ])

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)

        return df

    except Exception as e:
        log_error(f"❌ [get_klines] Помилка для {symbol}: {e}")
        return None


COOLDOWN_FILE = "data/cooldown_success.json"

def add_successful_cooldown(symbol: str, hours: int = 0, minutes: int = 20):
    try:
        cooldown_data = {}
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE, "r") as f:
                cooldown_data = json.load(f)

        cooldown_until = datetime.now() + timedelta(hours=hours, minutes=minutes)
        cooldown_data[symbol] = cooldown_until.strftime("%Y-%m-%d %H:%M:%S")

        with open(COOLDOWN_FILE, "w") as f:
            json.dump(cooldown_data, f, indent=2)
    except Exception as e:
        log_error(f"❌ [add_successful_cooldown] Error: {e}")


def is_in_cooldown(symbol: str) -> bool:
    try:
        if not os.path.exists(COOLDOWN_FILE):
            return False

        with open(COOLDOWN_FILE, "r") as f:
            cooldown_data = json.load(f)

        cooldown_str = cooldown_data.get(symbol)
        if not cooldown_str:
            return False

        cooldown_until = datetime.strptime(cooldown_str, "%Y-%m-%d %H:%M:%S")
        return datetime.now() < cooldown_until
    except Exception as e:
        log_error(f"❌ [is_in_cooldown] Error: {e}")
        return False



def make_json_safe(obj):
    """
    🔒 Рекурсивно конвертує всі об'єкти в JSON-friendly формат.
    - NumPy → float
    - datetime → isoformat
    - DataFrame/Series → list
    - Decimal → float
    """
    import numpy as np
    import pandas as pd
    from datetime import datetime
    from decimal import Decimal

    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, (np.integer, np.floating, Decimal)):
        return float(obj)
    elif isinstance(obj, (np.ndarray, pd.Series, pd.DataFrame)):
        return obj.tolist()
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    else:
        return str(obj)

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






def is_position_open_api(symbol, side, retries=3, delay=1):
    """
    📡 Перевіряє тільки на біржі, чи позиція ще відкрита (ігнорує локальний ActiveTradesFile)
    """
    symbol_clean = symbol.split("_")[0]

    for attempt in range(retries):
        try:
            response = bybit.get_positions(category="linear", symbol=symbol_clean)
            positions = response.get("result", {}).get("list", [])

            for pos in positions:
                size = float(pos.get("size", 0))
                pos_side = pos.get("side", "").upper()

                if size > 0:
                    if pos_side:
                        if (side.upper() == "LONG" and pos_side == "BUY") or \
                           (side.upper() == "SHORT" and pos_side == "SELL"):
                            log_message(f"✅ is_position_open_api: знайдено {symbol_clean} ({pos_side}) на біржі")
                            return True
                    else:
                        return True

            log_message(f"❌ is_position_open_api: {symbol_clean} закрита на біржі (спроба {attempt + 1}/{retries})")
        except Exception as e:
         time.sleep(delay)

    return False


def get_current_position_size(symbol, side):
    """
    📦 Повертає розмір відкритої позиції на біржі (size) або 0 якщо нема
    """
    try:
        response = bybit.get_positions(category="linear", symbol=symbol.split("_")[0])
        positions = response.get("result", {}).get("list", [])
        for pos in positions:
            size = float(pos.get("size", 0))
            pos_side = pos.get("side", "").upper()
            if size > 0 and (
                (side.upper() == "LONG" and pos_side == "BUY") or
                (side.upper() == "SHORT" and pos_side == "SELL")
            ):
                log_message(f"✅ get_current_position_size: знайдено {size} контрактів для {symbol}")
                return size
        return 0.0
    except Exception as e:
        log_error(f"❌ [get_current_position_size] Помилка для {symbol}: {e}")
        return 0.0




# ---------- Innovation / Risky symbols helpers ----------
import json, os
from datetime import datetime, timezone

def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _days_since_ts_ms(ts_ms):
    if not ts_ms:
        return None
    try:
        dt = datetime.fromtimestamp(int(ts_ms)/1000.0, tz=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None

def build_innovation_cache():
    """
    Спроба оновити кеш із Bybit instruments info (якщо client доступний).
    Якщо ні — створимо/залишимо порожній кеш.
    """
    from config import INNOVATION_CACHE_FILE
    cache = {}
    try:
        from config import client
        # Unified Trading: /v5/market/instruments-info  (linear)
        res = client.get_instruments_info(category="linear") or {}
        items = (res.get("result") or {}).get("list") or []
        for it in items:
            sym = it.get("symbol")
            if not sym:
                continue
            innovation = str(it.get("innovation", "0")) in {"1","true","True"}
            list_ts = it.get("launchTime") or it.get("listTime") or it.get("createdTime")
            try:
                list_ts = int(list_ts)
            except Exception:
                list_ts = None
            cache[sym] = {"innovation": innovation, "listing_ts": list_ts}
    except Exception:
        # нічого страшного — працюватимемо тільки по евристиках обороту/віку, якщо з’являться
        cache = _load_json(INNOVATION_CACHE_FILE, {})  # не перетираємо старе
    _save_json(INNOVATION_CACHE_FILE, cache)
    return cache

def is_innovation_or_risky_symbol(symbol: str,
                                  turnover_24h_usd: float | None = None,
                                  listed_days: int | None = None) -> dict:
    """
    Повертає прапорці ризику для символа.
    - innovation: з кешу Bybit instruments (якщо є)
    - young: вік лістингу < INNOVATION_MIN_LISTING_DAYS (з кешу або з аргументу listed_days)
    - thin: 24h оборот < INNOVATION_MIN_24H_TURNOVER (якщо переданий)
    - risky: об’єднаний прапорець (будь-який True)
    """
    from config import INNOVATION_CACHE_FILE, INNOVATION_MIN_LISTING_DAYS, INNOVATION_MIN_24H_TURNOVER
    cache = _load_json(INNOVATION_CACHE_FILE, {})
    meta = cache.get(symbol) or {}

    innovation = bool(meta.get("innovation", False))

    days = listed_days
    if days is None:
        days = _days_since_ts_ms(meta.get("listing_ts"))

    young = (days is not None and days < int(INNOVATION_MIN_LISTING_DAYS))

    thin = False
    try:
        if turnover_24h_usd is not None:
            thin = float(turnover_24h_usd) < float(INNOVATION_MIN_24H_TURNOVER)
    except Exception:
        thin = False

    risky = innovation or young or thin
    return {"innovation": innovation, "young": young, "thin": thin, "risky": risky, "days_listed": days}


ACTIVE_TRADES_FILE_SIMPLE = "data/ActiveTradesSimple.json"


def get_open_trades_count_by_side(position_side: str, retries: int = 2, delay_sec: float = 0.3) -> int:
    """
    📊 Повертає кількість відкритих угод за напрямком LONG або SHORT
    🔁 Перевіряє 2 рази (із затримкою), щоб переконатись, якщо файл оновлюється.
    """
    position_side = position_side.upper()
    
    for attempt in range(retries):
        try:
            with open(ACTIVE_TRADES_FILE_SIMPLE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("Формат ActiveTradesSimple некоректний (очікував dict)")

            count = sum(1 for trade in data.values() if str(trade.get("side", "")).upper() == position_side)
            return count

        except Exception as e:
            log_error(f"[get_open_trades_count_by_side] Спроба {attempt + 1}: {e}")
            time.sleep(delay_sec)

    return 0  # fallback, якщо нічого не вдалось прочитати
