import json
import time
import os
from datetime import datetime
from utils.logger import log_message, log_error
from ai.gpt_engine import ask_gpt
from analysis.market import get_market_overview_for_gpt, get_crypto_news

NEWS_SIGNAL_PATH = "data/latest_news_signal.json"
SENTIMENT_PATH = "data/market_sentiment.json"

SYSTEM_PROMPT = """
Ти — AI-аналітик крипторинку. Аналізуй тільки новини та оцінюй загальний новинний настрій ринку.

✅ Формат відповіді:
trend: BULLISH / BEARISH / NEUTRAL
reason: дуже коротке пояснення (1-2 речення), чому саме такий тренд.

📌 Важливо:
- НЕ враховуй ціни BTC/ETH, обсяги, технічні індикатори.
- Оцінюй тільки текст новин (позитивні, негативні чи нейтральні).
"""


def analyze_news_with_gpt(news_list):
    try:
        if not isinstance(news_list, list) or not all(isinstance(n, dict) for n in news_list):
            raise ValueError("news_list має бути списком словників з полем 'title' та 'sentiment'")

        if not news_list:
            return {"trend": "NEUTRAL", "reason": "Новини відсутні."}

        titles = [f"- {n.get('title', 'No title')} ({n.get('sentiment', 'neutral')})" for n in news_list[:20]]

        prompt = (
            "Ось останні новини крипторинку:\n" +
            "\n".join(titles) +
            "\n\n🔍 Проаналізуй текст новин та оціни загальний новинний настрій ринку.\n"
            "Формат відповіді:\ntrend: BULLISH / BEARISH / NEUTRAL\nreason: коротке пояснення."
        )

        log_message("📰 [GPT-News] Аналіз новин GPT...")
        response = ask_gpt(prompt, system_prompt=SYSTEM_PROMPT)
        log_message(f"📬 Відповідь GPT: {response}")

        if not response.strip():
            log_message("⚠️ GPT повернув порожню відповідь. Використовуємо NEUTRAL.")
            response = "trend: NEUTRAL\nreason: GPT повернув порожню відповідь."

        result = {"trend": "NEUTRAL", "reason": "GPT не відповів"}
        for line in response.splitlines():
            if "trend:" in line.lower():
                trend_value = line.split(":", 1)[1].strip().upper()
                if trend_value not in ["BULLISH", "BEARISH", "NEUTRAL"]:
                    trend_value = "NEUTRAL"  # fallback, якщо GPT видав щось інше
                result["trend"] = trend_value
            elif "reason:" in line.lower():
                reason_text = line.split(":", 1)[1].strip()
                result["reason"] = reason_text

        os.makedirs("data", exist_ok=True)
        with open(NEWS_SIGNAL_PATH, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), **result}, f, indent=2)

        with open(SENTIMENT_PATH, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), **result}, f, indent=2)

        return result

    except Exception as e:
        log_error(f"❌ GPT аналіз новин — помилка: {e}")
        return {"trend": "NEUTRAL", "reason": "Помилка GPT"}


def run_news_analyzer(interval_minutes=5):
    while True:
        try:
            log_message("🔄 GPT News Analyzer: новий цикл")
            news = get_crypto_news()

            result = analyze_news_with_gpt(news)
            log_message(f"📊 Тренд: {result['trend']} | Причина: {result['reason']}")

        except Exception as e:
            log_error(f"❌ Глобальна помилка GPT Analyzer: {e}")

        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    run_news_analyzer()
