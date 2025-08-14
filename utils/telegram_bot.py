import requests
import os
from utils.logger import log_error

# 💬 Telegram Bot Token та Chat ID
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# 🌐 Отримання останнього повідомлення

last_update_id = None


# 📤 Відправка повідомлення назад у Telegram
def send_telegram_message(message: str):
    try:
        url = f"{API_URL}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            log_error(f"❌ Не вдалося надіслати повідомлення: {response.text}")
    except Exception as e:
        log_error(f"❌ Помилка у send_telegram_message: {e}")
