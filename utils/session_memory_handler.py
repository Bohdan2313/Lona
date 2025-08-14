# 📁 Файл: utils/session_memory_handler.py

import os
import json
from datetime import datetime
from utils.logger import log_error, log_message

# Абсолютний шлях до папки session_memory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SESSION_DIR = os.path.join(BASE_DIR, "..", "session_memory")
os.makedirs(SESSION_DIR, exist_ok=True)  # ✅ ОК
log_message(f"📂 SESSION_DIR = {SESSION_DIR}")


def get_session_path(symbol):
    return os.path.join(SESSION_DIR, f"{symbol}_session.json")


def create_session(symbol):
    try:
        # 🧱 Перевірка чи існує директорія
        os.makedirs(SESSION_DIR, exist_ok=True)

        path = get_session_path(symbol)
        data = {
            "symbol": symbol,
            "snapshots": [],
            "summary": {},
            "open_trade": {},
            "pnl_log": []
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log_message(f"📁 Сесія створена: {path}")

    except Exception as e:
        log_error(f"❌ create_session() помилка для {symbol}: {e}")


def safe_load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"❌ safe_load_json() помилка: {e}")
        return {}


def append_snapshot(symbol, snapshot):
    try:
        path = get_session_path(symbol)

        # 🔐 Якщо файл не існує — створюємо пусту сесію
        if not os.path.exists(path):
            log_message(f"⚠️ Файл сесії {path} не знайдено — створюємо нову.")
            create_session(symbol)

        data = safe_load_json(path)
        data.setdefault("snapshots", []).append(snapshot)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log_message(f"📸 Снапшот додано до сесії: {symbol}")

    except Exception as e:
        log_error(f"❌ append_snapshot error for {symbol}: {e}")


def update_summary(symbol, summary):
    try:
        path = get_session_path(symbol)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["summary"] = summary
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log_error(f"❌ update_summary error for {symbol}: {e}")

def update_trade(symbol, entry_price, direction, leverage):
    try:
        path = get_session_path(symbol)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["open_trade"] = {
            "entry_price": entry_price,
            "direction": direction,
            "leverage": leverage,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log_error(f"❌ update_trade error for {symbol}: {e}")

def append_pnl(symbol, pnl):
    try:
        path = get_session_path(symbol)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["pnl_log"].append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "pnl": pnl
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        log_error(f"❌ append_pnl error for {symbol}: {e}")

def build_llama_session_prompt(symbol):
    try:
        path = get_session_path(symbol)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        prompt = f"""
SESSION ANALYSIS FOR {symbol}
-----------------------------

1. 24h Summary:
Long Signals: {data['summary'].get('long_signals', 0)}
Short Signals: {data['summary'].get('short_signals', 0)}
Whale Spikes: {data['summary'].get('whale_spikes', 0)}
RSI OB/OS: OB={data['summary'].get('rsi_overbought', 0)}, OS={data['summary'].get('rsi_oversold', 0)}
Patterns: Bullish={data['summary'].get('bullish_patterns', 0)}, Bearish={data['summary'].get('bearish_patterns', 0)}

2. Current Trade:
Entry: {data['open_trade'].get('entry_price', '?')} @ {data['open_trade'].get('direction', '?')}x{data['open_trade'].get('leverage', '?')}
Start Time: {data['open_trade'].get('start_time', '?')}

3. PnL Log:
"""
        for p in data["pnl_log"][-10:]:
            prompt += f"{p['time']} → {p['pnl']}%\n"

        return prompt.strip()

    except Exception as e:
        log_error(f"❌ build_llama_session_prompt error: {e}")
        return "⚠️ Failed to load session."

def build_behavioral_snapshot_sequence(symbol, limit=240):
    """
    🧠 Формує рядок із останніх снапшотів моніторингу монети (до 240)
    """
    try:
        path = get_session_path(symbol)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        snapshots = data.get("snapshots", [])[-limit:]
        lines = []

        for snap in snapshots:
            line = (
                f"[{snap['timestamp']}] "
                f"Price={snap['price']}, Trend={snap['trend']}, Volume={snap['volume_category']}, "
                f"Whale={snap['whale_score']}, Sentiment={snap['sentiment']}, "
                f"MACD={snap['indicators']['macd']}, RSI={snap['indicators']['rsi']}, "
                f"Stoch={snap['indicators']['stoch']}, Bollinger={snap['indicators']['bollinger']}, "
                f"Support={snap['indicators']['support_status']}, "
                f"1m={snap['micro']['1m']['change_pct']}% ({snap['micro']['1m']['pattern']}), "
                f"3m={snap['micro']['3m']['change_pct']}% ({snap['micro']['3m']['pattern']}), "
                f"5m={snap['micro']['5m']['change_pct']}% ({snap['micro']['5m']['pattern']})"
            )
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        log_error(f"❌ build_behavioral_snapshot_sequence error: {e}")
        return "⚠️ Failed to build snapshot sequence."
