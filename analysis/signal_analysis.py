import json
import os
from collections import defaultdict
from utils.logger import log_message, log_error

STATS_PATH = "data/signal_stats.json"
SUMMARY_PATH = "data/signal_analysis_summary.json"

def analyze_signal_stats():
    """
    📊 Аналізує всі збережені сигнали та створює рейтинг комбінацій.
    """
    if not os.path.exists(STATS_PATH):
        log_error("❌ signal_stats.json не знайдено.")
        return

    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except Exception as e:
        log_error(f"❌ Неможливо прочитати signal_stats.json: {e}")
        return

    grouped = defaultdict(list)

    for entry in stats:
        key = entry.get("key")
        pnl = entry.get("pnl_percent", 0)
        if key:
            grouped[key].append(pnl)

    summary = {}

    for key, pnls in grouped.items():
        count = len(pnls)
        avg_pnl = round(sum(pnls) / count, 2)
        win_rate = round(len([x for x in pnls if x > 0]) / count, 2)

        summary[key] = {
            "count": count,
            "avg_pnl": avg_pnl,
            "win_rate": win_rate
        }

    try:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # Вивести топ-5
        top_keys = sorted(summary.items(), key=lambda x: x[1]["avg_pnl"], reverse=True)[:5]
        log_message("📊 Топ-5 найприбутковіших ключів:")
        for i, (key, data) in enumerate(top_keys, start=1):
            log_message(f"{i}. 🔑 {key} | 📈 PnL={data['avg_pnl']}% | ✅ {data['win_rate']*100}% WinRate ({data['count']}x)")

    except Exception as e:
        log_error(f"❌ Неможливо записати signal_analysis_summary.json: {e}")


FULL_COMPONENTS_PATH = "data/full_component_analysis.json"

