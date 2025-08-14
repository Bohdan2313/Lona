import statistics
import datetime
from utils.logger import log_message, log_error
from utils.session_memory_handler import update_summary
from utils.get_klines_bybit import get_klines_clean_bybit
from utils.logger import sanitize_signals


def build_textual_chart(symbol, interval="1m", limit=30):
    """
    📈 Формує текстовий графік для LLaMA на основі історичних свічок.
    Повертає стрічку з форматом:
    [HH:MM] Open: x | High: x | Low: x | Close: x
    """
    try:
        df = get_klines_clean_bybit(symbol, interval=interval, limit=limit)

        if df is None or df.empty:
            return "⚠️ Немає історичних даних."

        lines = [f"📊 Textual Chart for {symbol} ({interval}, last {limit} candles):"]

        for index, row in df.iterrows():
            time_str = row.name.strftime("[%H:%M]") if isinstance(row.name, datetime.datetime) else f"[{index}]"
            o = round(row["open"], 5)
            h = round(row["high"], 5)
            l = round(row["low"], 5)
            c = round(row["close"], 5)
            lines.append(f"{time_str} Open: {o} | High: {h} | Low: {l} | Close: {c}")

        return "\n".join(lines)

    except Exception as e:
        log_error(f"❌ [build_textual_chart] Помилка: {e}")
        return f"⚠️ Chart error: {e}"

# Приклад використання
if __name__ == "__main__":
    log_message(build_textual_chart("BTCUSDT"))
