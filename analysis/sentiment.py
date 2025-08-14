# analysis/sentiment.py

import os
import time
import datetime
import requests
from utils.logger import log_message, log_error
# Змінні кешу
last_news_update = 0
cached_news = []


def get_crypto_news(limit=None):
    """
    📢 Отримує останні новини з CryptoPanic API та визначає ринковий сентимент (з підтримкою limit).
    Захищено від пошкодженого кешу.
    """
    global last_news_update, cached_news

    API_KEY = os.getenv("CRYPTOPANIC_API_KEY")
    if not API_KEY:
        log_error("❌ API ключ для CryptoPanic не знайдено.")
        return []

    url = f"https://cryptopanic.com/api/developer/v2/posts/?auth_token={API_KEY}"

    # ✅ Перевіряємо кеш
    if time.time() - last_news_update < 3600:
        log_message("🔄 Використовуємо кешовані новини.")
        if isinstance(cached_news, list) and all(isinstance(n, dict) for n in cached_news):
            return cached_news[:limit] if limit else cached_news
        else:
            log_error("⚠️ Кешовані новини пошкоджені або мають неправильний формат. Очищаємо.")
            cached_news = []

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        time.sleep(1)

        data = response.json()
        if "results" not in data or not data["results"]:
            log_message("⚪ Новини відсутні або порожні.")
            return []

        news_list = []
        bullish_news = 0
        bearish_news = 0

        for news in data["results"]:
            title = news.get("title", "").lower()
            sentiment = "neutral"

            if any(word in title for word in ["bullish", "rally", "breakout", "surge", "record high", "skyrocket", "partnership", "announcement"]):
                sentiment = "bullish"
                bullish_news += 1
            elif any(word in title for word in ["crash", "collapse", "bearish", "sell-off", "hacked", "scam", "exploit"]):
                sentiment = "bearish"
                bearish_news += 1

            news_list.append({"title": title, "sentiment": sentiment})

        log_message(f"📰 Отримано {len(news_list)} новин: {bullish_news} bullish / {bearish_news} bearish")

        # 🔐 Зберігаємо в лог
        with open("crypto_news.log", "a", encoding="utf-8", errors="ignore") as log_file:
            log_file.write(f"{datetime.datetime.now()} | Bullish: {bullish_news} | Bearish: {bearish_news}\n")
            for item in news_list:
                log_file.write(f"{item['sentiment'].upper()} | {item['title']}\n")

        # 🧠 Оновлюємо кеш
        cached_news = news_list
        last_news_update = time.time()

        return news_list[:limit] if limit else news_list

    except requests.exceptions.RequestException as e:
        log_error(f"❌ Запит до CryptoPanic не вдався: {e}")
    except ValueError:
        log_error("❌ Некоректна відповідь від CryptoPanic API.")
    except Exception as e:
        log_error(f"❌ Невідома помилка get_crypto_news(): {e}")

    return []



def get_news_sentiment(symbol):
    """📈 Визначає настрій новин по символу"""
    try:
        if not os.path.exists("crypto_news.log"):
            log_error("❌ Файл новин не знайдено.")
            return "neutral"

        with open("crypto_news.log", "r", encoding="utf-8", errors="ignore") as f:
            news = f.readlines()

        score = 0
        count = 0

        for line in reversed(news):
            line_lower = line.lower()
            if symbol.lower() in line_lower:
                if "bullish" in line_lower:
                    score += 1
                    count += 1
                elif "bearish" in line_lower:
                    score -= 1
                    count += 1

                if count >= 10:
                    break

        if count == 0:
            return "neutral"

        avg_score = score / count
        if avg_score > 0.3:
            return "positive"
        elif avg_score < -0.3:
            return "negative"
        else:
            return "neutral"

    except Exception as e:
        log_error(f"❌ Помилка при обробці новин: {e}")
        return "neutral"

