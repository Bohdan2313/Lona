# analysis/whales.py

import os
import requests
from utils.logger import log_message, log_error
from utils.get_klines_bybit import get_klines_clean_bybit
from dotenv import load_dotenv
from config import bybit


load_dotenv()


def get_whale_alert_data(min_value=100000):
    """
    📊 Отримує великі китові транзакції через Whale Alert API.
    """
    API_KEY = os.getenv("WHALE_ALERT_API_KEY")
    url = f"https://api.whale-alert.io/v1/transactions?api_key={API_KEY}&min_value={min_value}"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "transactions" in data and data["transactions"]:
            log_message(f"✅ Whale Alert: {len(data['transactions'])} транзакцій знайдено.")
            return {"status": "ok", "transactions": data["transactions"]}
        else:
            log_message("⚠️ Whale Alert: транзакції не знайдено.")
            return {"status": "no_transactions", "transactions": []}

    except requests.exceptions.Timeout:
        log_error("⏳ Whale Alert API таймаут.")
    except requests.exceptions.RequestException as e:
        log_error(f"⚠️ Whale Alert API недоступний: {e}")
    except Exception as e:
        log_error(f"❌ Whale Alert невідома помилка: {e}")

    # Повертаємо помилку, якщо API недоступне
    return {"status": "error", "transactions": []}




def get_whale_score(symbol="BTCUSDT"):
    """
    📈 Генерує китовий бал для символу на основі Whale Alert.
    """
    try:
        data = get_whale_data(symbol)
        alert_count = len(data.get("whale_alert", {}).get("transactions", []))
        total = alert_count

        score = min(round(alert_count * 3), 100)

        if not isinstance(score, (int, float)):
            log_error(f"❌ Whale Score для {symbol} не число: {score}. Присвоюємо 0.")
            score = 0

        log_message(f"🐳 Whale Score для {symbol}: {score} (Alert={alert_count})")

        return {
            "whale_score": {
                "score": score,
                "raw_values": {
                    "whale_alert_count": alert_count,
                    "total_events": total
                }
            }
        }

    except Exception as e:
        log_error(f"❌ get_whale_score помилка для {symbol}: {e}")
        return {
            "whale_score": {
                "score": 0,
                "raw_values": {}
            }
        }


def get_whale_data(symbol="BTCUSDT"):
    """
    🔍 Отримує китові транзакції лише з Whale Alert.
    """
    try:
        log_message(f"📡 Отримання китових транзакцій для {symbol}")
        whale_alert_data = get_whale_alert_data()
        return {
            "whale_alert": whale_alert_data
        }
    except Exception as e:
        log_error(f"❌ get_whale_data помилка для {symbol}: {e}")
        return {
            "whale_alert": {"status": "error", "transactions": []}
        }
