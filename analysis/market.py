# analysis/market.py

import os
import requests
import datetime
import pandas as pd
import numpy as np
import talib
from dotenv import load_dotenv
from config import client
from utils.tools import get_current_futures_price
from config import VOLUME_THRESHOLDS
from utils.logger import log_message, log_error
from utils.logger import log_error
from utils.telegram_bot import send_telegram_message
from openai import OpenAI

from analysis.sentiment import get_crypto_news, get_news_sentiment
from analysis.whales import get_whale_data
import json
import os
import time

from utils.get_klines_bybit import get_klines_clean_bybit
import openai
from pybit.unified_trading import HTTP
openai.api_key = os.getenv("OPENAI_API_KEY")


# 📥 Завантаження ключів із .env
load_dotenv()
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")


def get_order_book_top(symbol, depth=10):
    """
    📊 Отримання топових bid/ask із ордербука та формування DICT для SignalStats.
    """
    try:
        response = client.get_orderbook(
            category="linear",
            symbol=symbol,
            limit=depth
        )

        if response.get("retCode", 0) != 0:
            msg = f"⚠️ Order book помилка: {response.get('retMsg')}"
           
            result = {
                "order_book": {
                    "status": "error",
                    "message": msg,
                    "bids": [],
                    "asks": [],
                    "top_bid": {},
                    "top_ask": {}
                }
            }
          
            return result

        bids = response["result"]["bids"][:depth]
        asks = response["result"]["asks"][:depth]

        top_bid = {
            "price": float(bids[0][0]),
            "volume": float(bids[0][1])
        } if bids else {}

        top_ask = {
            "price": float(asks[0][0]),
            "volume": float(asks[0][1])
        } if asks else {}

        result = {
            "order_book": {
                "status": "ok",
                "bids": [{"price": float(b[0]), "volume": float(b[1])} for b in bids],
                "asks": [{"price": float(a[0]), "volume": float(a[1])} for a in asks],
                "top_bid": top_bid,
                "top_ask": top_ask
            }
        }
       
        return result

    except Exception as e:
        error_msg = f"❌ get_order_book_top помилка: {e}"
        log_error(error_msg)
        result = {
            "order_book": {
                "status": "error",
                "message": error_msg,
                "bids": [],
                "asks": [],
                "top_bid": {},
                "top_ask": {}
            }
        }
     
        return result


def get_current_price(symbol):
    """💰 Отримує поточну ціну криптовалюти з Bybit Unified API"""
    try:
        response = client.get_tickers(category="linear", symbol=symbol)

        if response.get("retCode", 0) != 0:
            log_error(f"⚠️ Bad response for {symbol}: {response.get('retMsg')}")
            return None

        result = response.get("result", {})
        if not result or "list" not in result or not result["list"]:
            log_error(f"⚠️ Порожній список цін для {symbol}")
            return None

        price = float(result["list"][0]["lastPrice"])
        log_message(f"💰 Поточна ціна {symbol}: {price:.2f} USDT")
        return price

    except Exception as e:
        log_error(f"❌ [get_current_price] {symbol}: {e}")
        return None



def get_top_symbols(min_volume=1_000_000, limit=60):
    try:
        response = client.get_tickers(category="linear")
        if not response or "result" not in response or "list" not in response["result"]:
            log_error("❌ Не вдалося отримати список монет із Bybit")
            return []

        symbols = []
        for item in response["result"]["list"]:
            symbol = item.get("symbol")
            volume = float(item.get("turnover24h", 0))

            if not symbol or not symbol.endswith("USDT"):
                continue

            if volume >= min_volume:
                symbols.append({"symbol": symbol, "volume": volume})

        sorted_symbols = sorted(symbols, key=lambda x: x["volume"], reverse=True)
        top_symbols = [s["symbol"] for s in sorted_symbols[:limit]]
    
        return top_symbols

    except Exception as e:
        log_error(f"❌ get_top_symbols помилка: {e}")
        return []


import time


TREND_CACHE = {}

def analyze_market(symbol: str, market_type: str = "spot") -> dict | None:
    """
    📡 Аналіз ринку для конкретного токену (визначає лише загальний тренд токену)
    """
    try:
        log_message(f"📡 Аналіз ринку для {symbol}")

        intervals = ["1h", "15m", "5m"]
        df = None

        # === Спроба отримати дані з кількох інтервалів ===
        for interval in intervals:
            df = get_klines_clean_bybit(symbol, interval=interval, limit=300)
            if df is not None and not df.empty and len(df) >= 50:
                log_message(f"✅ Дані отримано для {symbol} на інтервалі {interval}")
                break

        if df is None or df.empty:
            # 🛡 Використати кеш, якщо даних нема
            cached = TREND_CACHE.get(symbol)
            if cached and (time.time() - cached["timestamp"]) < 300:
                return cached["data"]
            else:
                return None

        # === Індикатори ===
        df["SMA_50"] = talib.SMA(df["close"], timeperiod=50)
        df["SMA_200"] = talib.SMA(df["close"], timeperiod=200)
        df["CCI"] = talib.CCI(df["high"], df["low"], df["close"], timeperiod=14)
        df["MACD"], df["MACD_Signal"], _ = talib.MACD(df["close"], 12, 26, 9)
        df["ATR"] = talib.ATR(df["high"], df["low"], df["close"], 14)
        df["RSI"] = talib.RSI(df["close"], 14)

        df.fillna(method="ffill", inplace=True)
        df.fillna(method="bfill", inplace=True)
        df.dropna(inplace=True)

        # === Голосування індикаторів ===
        votes_bullish, votes_bearish = 0, 0

        sma_50, sma_200 = df["SMA_50"].iloc[-1], df["SMA_200"].iloc[-1]
        sma_diff_pct = ((sma_50 - sma_200) / max(sma_200, 1e-8)) * 100
        if sma_diff_pct > 1.0: votes_bullish += 1
        elif sma_diff_pct < -1.0: votes_bearish += 1

        macd, macd_sig = df["MACD"].iloc[-1], df["MACD_Signal"].iloc[-1]
        if macd > macd_sig: votes_bullish += 1
        elif macd < macd_sig: votes_bearish += 1

        rsi = df["RSI"].iloc[-1]
        if rsi > 55: votes_bullish += 1
        elif rsi < 45: votes_bearish += 1

        cci = df["CCI"].iloc[-1]
        if cci > 50: votes_bullish += 1
        elif cci < -50: votes_bearish += 1

        # === Підсумок голосування ===
        if votes_bullish >= 3:
            trend = "bullish"
        elif votes_bearish >= 3:
            trend = "bearish"
        else:
            trend = "neutral"

        # === Інші показники ===
        atr_level = df["ATR"].iloc[-1]
        volatility = round(df["ATR"].mean() / max(df["close"].mean(), 1e-8) * 100, 2)
        volume_category = analyze_volume(symbol)

        log_message(
            f"📊 {symbol} → Trend: {trend}, Votes: {votes_bullish}↑/{votes_bearish}↓, "
            f"MACD: {'bullish' if macd > macd_sig else 'bearish'}, "
            f"RSI: {rsi:.2f}, CCI: {cci:.2f}, ATR: {atr_level:.2f}, "
            f"Volatility: {volatility:.2f}%, Volume: {volume_category}"
        )

        result = {
            "trend": trend,
            "macd_trend": "bullish" if macd > macd_sig else "bearish",
            "cci_signal": "overbought" if cci > 100 else "oversold" if cci < -100 else "neutral",
            "atr_level": atr_level,
            "volatility": volatility,
            "rsi": rsi,
            "volume_category": volume_category
        }

        # === Кешування результату ===
        TREND_CACHE[symbol] = {
            "timestamp": time.time(),
            "trend": trend,
            "data": result
        }

        return result

    except Exception as e:
        log_error(f"❌ analyze_market помилка для {symbol}: {e}")
        return None



import time

# === Глобальний кеш для глобального тренду
GLOBAL_TREND_CACHE = {}

# === Глобальний кеш тренду
GLOBAL_TREND_CACHE = {}

def analyze_global_trend():
    """
    📈 Аналіз глобального ринку (BTC, ETH, ТОП-альти) — визначає глобальний тренд.
    """
    try:
        coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
        weights = {"BTCUSDT": 0.25, "ETHUSDT": 0.25, "SOLUSDT": 0.16, "BNBUSDT": 0.17, "ADAUSDT": 0.17}
        intervals = ["1h", "15m", "5m"]  # Порядок fallback
        changes = {}
        total_score = 0.0

        for coin in coins:
            coin_change = None

            for interval in intervals:
                df = get_klines_clean_bybit(coin, interval=interval, limit=24)
                if df is not None and not df.empty:
                    start_price = df["close"].iloc[0]
                    end_price = df["close"].iloc[-1]
                    pct_change = ((end_price - start_price) / start_price) * 100
                    coin_change = round(pct_change, 2)
                    log_message(f"📊 {coin} [{interval}]: {coin_change:.2f}%")
                    break  # ✅ Використати перший доступний інтервал з даними
                else:
                    log_message(f"⚠️ Немає даних для {coin} на {interval}")

            if coin_change is not None:
                changes[coin] = coin_change
                total_score += coin_change * weights.get(coin, 0.1)
            else:
                log_message(f"⚠️ {coin} пропущено — відсутні дані на всіх інтервалах.")

        # === Визначення напрямку
        if total_score > 0.7:
            direction = "bullish"
        elif total_score < -0.7:
            direction = "bearish"
        else:
            direction = "neutral"

        result = {
            "global_trend": {
                "direction": direction,
                "score": round(total_score, 2),
                "raw_values": changes
            }
        }

        log_message(f"🌍 Глобальний тренд: {direction.upper()} | Score: {round(total_score, 2)} | Зміни: {changes}")

        # === Кешування
        GLOBAL_TREND_CACHE["last"] = {
            "timestamp": time.time(),
            "data": result
        }

        return result

    except Exception as e:
        log_error(f"❌ analyze_global_trend помилка: {e}")

        # 🛡 Використати кеш, якщо є
        cached = GLOBAL_TREND_CACHE.get("last")
        if cached and (time.time() - cached["timestamp"]) < 300:
            log_message("♻️ Використано кешований глобальний тренд.")
            return cached["data"]

        # 📦 Повернути neutral як fallback
        return {
            "global_trend": {
                "direction": "neutral",
                "score": 0.0,
                "raw_values": {}
            }
        }


def analyze_volume(symbol):
    """
    📊 Safe аналіз обсягу торгів із фокусом на Bybit.
    - Основний шлях: по свічках (ratio поточного до середнього).
    - Fallback: Bybit tickers → turnover24hUsd.
    - Жодних min_binance_volume. Гнучкі дефолти, якщо в конфігу немає ключів.
    Повертає: {"volume_analysis": {"level": "...", "method": "...", "raw_values": {...}}}
    """
    try:
        always_active = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        thresholds = VOLUME_THRESHOLDS if 'VOLUME_THRESHOLDS' in globals() else {}

        # --- дефолти для ratio ---
        very_high_ratio = float(thresholds.get("very_high_ratio", 3.0))
        high_ratio      = float(thresholds.get("high_ratio", 1.8))
        low_ratio       = float(thresholds.get("low_ratio", 0.6))
        very_low_ratio  = float(thresholds.get("very_low_ratio", 0.35))

        # --- дефолти для fallback turnover (USD, 24h) ---
        # якщо хочеш — задай це у конфігу як:
        # VOLUME_THRESHOLDS = {"turnover_usd": {"very_high": 100_000_000, "high": 50_000_000, "normal": 10_000_000, "low": 1_000_000}, ...}
        turnover_cfg = thresholds.get("turnover_usd", {})
        to_vhigh  = float(turnover_cfg.get("very_high", 100_000_000))  # >= 100M
        to_high   = float(turnover_cfg.get("high",       50_000_000))  # >= 50M
        to_norm   = float(turnover_cfg.get("normal",     10_000_000))  # >= 10M
        to_low    = float(turnover_cfg.get("low",         1_000_000))  # < 10M → low/very_low

        # --- основний шлях: за свічками Bybit ---
        df = get_klines_clean_bybit(symbol, interval="1h", limit=50)
        if df is not None and not df.empty and "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            df.dropna(inplace=True)

            if len(df) >= 5:
                current_volume = float(df["volume"].iloc[-1])
                avg_volume = float(df["volume"].iloc[:-1].rolling(window=20).mean().iloc[-1])

                if not (avg_volume > 0):
                    fallback_level = "normal" if symbol in always_active else "very_low"
                    return {
                        "volume_analysis": {
                            "level": fallback_level,
                            "method": "avg_volume_nan",
                            "raw_values": {}
                        }
                    }

                ratio = current_volume / avg_volume

                if ratio >= very_high_ratio:
                    level = "very_high"
                elif ratio >= high_ratio:
                    level = "high"
                elif ratio <= very_low_ratio:
                    level = "very_low"
                elif ratio <= low_ratio:
                    level = "low"
                else:
                    level = "normal"

                if symbol in always_active and level == "very_low":
                    level = "normal"
                    log_message(f"⚖️ {symbol} — топ монета, very_low → normal (прощено)")

                log_message(f"📊 Обʼєм {symbol}: Поточний={current_volume:.0f}, "
                            f"Середній={avg_volume:.0f}, Ratio={ratio:.2f} → {level}")
                return {
                    "volume_analysis": {
                        "level": level,
                        "method": "standard",
                        "raw_values": {
                            "current_volume": round(current_volume, 2),
                            "average_volume": round(avg_volume, 2),
                            "ratio": round(ratio, 4)
                        }
                    }
                }

            # даних замало → впадемо у fallback нижче
        else:
            log_message(f"ℹ️ {symbol}: немає валідних свічок для обсягу → fallback на tickers")

        # --- Fallback: Bybit tickers (turnover24hUsd) ---
        try:
            response = client.get_tickers(category="linear", symbol=symbol)
            data = response.get("result", {}).get("list", [])
            if not data:
                raise ValueError("Empty API list")

            t = data[0]
            # Bybit інколи віддає 'turnover24h' у COIN-деномінації; беремо USD, якщо є
            turnover_usd = float(t.get("turnover24hUsd") or t.get("turnover24h") or 0.0)

            if turnover_usd >= to_vhigh:
                level = "very_high"
            elif turnover_usd >= to_high:
                level = "high"
            elif turnover_usd >= to_norm:
                level = "normal"
            else:
                level = "low" if symbol in always_active else "very_low"

            log_message(f"📊 Fallback {symbol}: turnover24hUsd={turnover_usd:.0f} → {level}")
            return {
                "volume_analysis": {
                    "level": level,
                    "method": "fallback_api",
                    "raw_values": {"turnover24hUsd": round(turnover_usd, 2)}
                }
            }

        except Exception as api_error:
            log_error(f"❌ Fallback API помилка для {symbol}: {api_error}")
            return {
                "volume_analysis": {
                    "level": "very_low",
                    "method": "fallback_api_error",
                    "raw_values": {}
                }
            }

    except Exception as e:
        log_error(f"❌ analyze_volume() глобальна помилка для {symbol}: {e}")
        return {
            "volume_analysis": {
                "level": "very_low",
                "method": "exception",
                "raw_values": {}
            }
        }



def get_market_overview_for_gpt():
    try:
        def get_daily_price_change(symbol):
            df = get_klines_clean_bybit(symbol, interval="1h", limit=24)
            if df is None or df.empty:
                return 0
            open_price = df.iloc[0]["open"]
            close_price = df.iloc[-1]["close"]
            change = ((close_price - open_price) / open_price) * 100
            return round(change, 2)

        btc_price = get_current_futures_price("BTCUSDT")
        eth_price = get_current_futures_price("ETHUSDT")

        btc_change = get_daily_price_change("BTCUSDT")
        eth_change = get_daily_price_change("ETHUSDT")

        global_trend = analyze_global_trend()
        whale_info = get_whale_data()
        sentiment = get_news_sentiment("BTCUSDT")
        news = get_crypto_news(limit=3)

        whale_summary = whale_info.get("summary", "немає даних")
        formatted_news = "\n".join(
            [f"- {n['title']} ({n.get('sentiment', 'neutral')})" for n in news]
        )

        overview_text = (
            f"📊 BTC: {btc_change}% | ETH: {eth_change}% | Тренд ринку: {global_trend}\n"
            f"🐋 Whale-активність: {whale_summary}\n"
            f"📰 Сентимент новин (BTC): {sentiment}\n"
            f"📚 Новини:\n{formatted_news if formatted_news else 'немає новин'}"
        )

        return {
            "btc_change": btc_change,
            "eth_change": eth_change,
            "btc_price": btc_price,
            "eth_price": eth_price,
            "market_trend": global_trend,
            "overview_text": overview_text
        }

    except Exception as e:
        return {
            "btc_change": 0,
            "eth_change": 0,
            "btc_price": "?",
            "eth_price": "?",
            "market_trend": "UNKNOWN",
            "overview_text": f"⚠️ Не вдалося отримати огляд ринку: {e}"
        }



NEWS_SIGNAL_PATH = "data/latest_news_signal.json"

def get_news_trend_summary():
    """
    📰 Отримує короткий підсумок GPT-новин для SignalStats.
    Повертає структурований dict.
    """
    try:
        if not os.path.exists(NEWS_SIGNAL_PATH):
            log_message("📰 DEBUG: NEWS_SIGNAL_PATH не існує.")
            result = {
                "news_summary": {
                    "status": "no_data",
                    "trend": "unknown",
                    "reason": "Новин немає.",
                    "hours_ago": None
                }
            }
         
            return result

        with open(NEWS_SIGNAL_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        timestamp = data.get("timestamp", 0)
        hours_ago = round((time.time() - timestamp) / 3600, 2)
        trend = data.get("trend", "UNKNOWN")
        reason = data.get("reason", "Без пояснення")

        if hours_ago > 3:
            status = "stale"
            summary_text = f"⚠️ Новини застарілі (>{int(hours_ago)} год.) | Тренд: {trend} | Причина: {reason}"
        else:
            status = "fresh"
            summary_text = f"📰 GPT-новини: {trend} | {reason}"

        log_message(f"📰 DEBUG get_news_trend_summary() → {summary_text}")

        result = {
            "news_summary": {
                "status": status,
                "trend": trend,
                "reason": reason,
                "hours_ago": hours_ago
            }
        }
      
        return result

    except Exception as e:
        error_msg = f"⚠️ Помилка читання новин: {e}"
        log_error(f"❌ get_news_trend_summary() помилка: {e}")
        result = {
            "news_summary": {
                "status": "error",
                "trend": "unknown",
                "reason": error_msg,
                "hours_ago": 0.0
            }
        }
  
        return result
