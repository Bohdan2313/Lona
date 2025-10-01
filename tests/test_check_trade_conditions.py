from __future__ import annotations

from ai import check_trade_conditions as ctc


def test_evaluate_long_with_custom_logic(monkeypatch):
    rules = {
        "long": {
            "core": [["rsi_trend", "up"]],
            "pairs": [],
            "threshold": 1.0,
            "weights": {"core": 2.0, "pair": 1.0},
        },
        "short": {
            "core": [["rsi_trend", "down"]],
            "pairs": [],
            "threshold": 1.0,
            "weights": {"core": 2.0, "pair": 1.0},
        },
    }
    monkeypatch.setattr(ctc, "CUSTOM_RULES", rules)
    monkeypatch.setattr(ctc, "ENABLE_REJECTION_LOG", False)
    monkeypatch.setitem(ctc.ANTI_FALSE_OPEN, "min_pair_hits_long", 0)
    monkeypatch.setitem(ctc.ANTI_FALSE_OPEN, "min_pair_hits_short", 0)
    monkeypatch.setitem(ctc.ANTI_FALSE_OPEN, "hysteresis_bars", 0)
    monkeypatch.setitem(ctc.ANTI_FALSE_OPEN, "require_closed_candle", False)
    monkeypatch.setitem(ctc.ANTI_FALSE_OPEN, "atr_pct_bounds", (0.0, 999.0))
    monkeypatch.setattr(ctc, "MIN_BB_WIDTH", 0.0, raising=False)

    payload = ctc.evaluate_long({
        "rsi_trend": "up",
        "symbol": "BTCUSDT",
        "bars_in_state": 2,
        "atr_percent": 1.0,
        "bollinger_width": 1.0
    })
    assert payload["allow"] is True
    assert payload["score"] >= 2.0

    short_payload = ctc.evaluate_short({
        "rsi_trend": "down",
        "symbol": "BTCUSDT",
        "bars_in_state": 2,
        "atr_percent": 1.0,
        "bollinger_width": 1.0
    })
    assert short_payload["allow"] is True
    assert short_payload["score"] >= 2.0

    both = ctc.evaluate_both({"rsi_trend": "down", "symbol": "BTCUSDT"})
    assert both["decision"] in {"LONG", "SHORT", "SKIP"}
