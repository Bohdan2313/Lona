# -*- coding: utf-8 -*-
"""
CheckTradeConditions — FINАЛ версія під твої поля з convert_snapshot_to_conditions()

Працює напряму з dict `conditions`, який ти формуєш у convert_snapshot_to_conditions(snapshot):
- використовує існуючі ключі (support_position, rsi_value, stoch_k, stoch_d, bollinger_position, patterns,
  macd_hist_direction, macd_crossed, rsi_trend, microtrend_1m, microtrend_5m, global_trend, volume_category, ...)
- безпечно добудовує бакети: rsi_bucket, stoch_k_bucket, stoch_d_bucket, boll_bucket, cci_bucket
- робить бінарні патерни: hammer, shooting_star, morning_star, evening_star, doji, bullish/bearish_engulfing
- застосовує правила з твого TOP-20 (pro-LONG/SHORT + exclusive)
- повертає score + пояснення, а також `allow`

Використання:
from check_trade_conditions import evaluate_long, evaluate_short, evaluate_both
res = evaluate_both(conditions)

Пороги (THRESH_*) можна підкрутити без зміни решти коду.
"""
from typing import Dict, Any, List, Tuple

# ===================== Helpers =====================

def _lc(x: Any) -> Any:
    return x.strip().lower() if isinstance(x, str) else x


def _to_float(x: Any, default: float | None = None) -> float | None:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


# ===================== Buckets =====================

RSI_BUCKET_EDGES = [
    (None, 30, "<=30"),
    (30, 40, "30-40"),
    (40, 50, "40-50"),
    (50, 60, "50-60"),
    (60, 70, "60-70"),
    (70, None, ">70"),
]

BOLL_BUCKET_EDGES = [
    (None, 30, "<=30"),
    (30, 45, "30-45"),
    (45, 55, "45-55"),
    (55, 70, "55-70"),
    (70, None, ">70"),
]

STOCH_BUCKET_EDGES = [
    (None, 20, "<=20"),
    (20, 40, "20-40"),
    (40, 60, "40-60"),
    (60, 80, "60-80"),
    (80, None, ">80"),
]

CCI_BUCKET_RULE = [
    ("<=-100", lambda v: v is not None and v <= -100),
    ("-100-0", lambda v: v is not None and -100 < v <= 0),
    ("0-100", lambda v: v is not None and 0 < v <= 100),
    (">100", lambda v: v is not None and v > 100),
]


def _bucket(value: float | None, edges: List[tuple]) -> str | None:
    if value is None:
        return None
    for lo, hi, label in edges:
        if (lo is None or value >= lo) and (hi is None or value <= hi):
            return label
    return None


def _build_derived(conditions: Dict[str, Any]) -> Dict[str, Any]:
    """Створює похідні фічі: *_bucket та патерни yes/no.
    НЕ модифікує вхідний dict — повертає новий.
    """
    c = dict(conditions or {})

    # --- Normalize numbers ---
    rsi_value = _to_float(c.get("rsi_value"), None)
    stoch_k = _to_float(c.get("stoch_k"), None)
    stoch_d = _to_float(c.get("stoch_d"), None)

    # Bollinger position може бути у 0..1 — convert to 0..100
    bp = _to_float(c.get("bollinger_position"), None)
    if bp is not None:
        if 0.0 <= bp <= 1.0:
            bp = round(bp * 100.0, 2)
    c["bollinger_position"] = bp

    cci_value = _to_float(c.get("cci_value"), None)

    # --- Buckets ---
    c["rsi_bucket"] = _bucket(rsi_value, RSI_BUCKET_EDGES)
    c["stoch_k_bucket"] = _bucket(stoch_k, STOCH_BUCKET_EDGES)
    c["stoch_d_bucket"] = _bucket(stoch_d, STOCH_BUCKET_EDGES)
    c["boll_bucket"] = _bucket(bp, BOLL_BUCKET_EDGES)

    cci_bucket = None
    for label, rule in CCI_BUCKET_RULE:
        if rule(cci_value):
            cci_bucket = label
            break
    c["cci_bucket"] = cci_bucket

    # --- Normalize strings ---
    for k in [
        "support_position","global_trend","volume_category",
        "macd_trend","macd_hist_direction","macd_crossed",
        "rsi_trend","rsi_signal",
        "stoch_signal","bollinger_signal","cci_signal",
        "microtrend_1m","microtrend_5m",
    ]:
        if k in c and isinstance(c[k], str):
            c[k] = _lc(c[k])

    # --- Pattern flags from list ---
    patterns = c.get("patterns") or []
    if isinstance(patterns, list):
        pset = { _lc(p) for p in patterns if isinstance(p, str) }
    else:
        pset = set()

    def pflag(name: str) -> str:
        return "yes" if name in pset else "no"

    c["pat_bullish_engulfing"] = pflag("bullish_engulfing")
    c["pat_bearish_engulfing"] = pflag("bearish_engulfing")
    c["pat_hammer"] = pflag("hammer")
    c["pat_shooting_star"] = pflag("shooting_star")
    c["pat_morning_star"] = pflag("morning_star")
    c["pat_evening_star"] = pflag("evening_star")
    c["pat_doji"] = pflag("doji")

    # macd_crossed → нормалізація до {none, bullish_cross, bearish_cross}
    mc = _lc(c.get("macd_crossed")) if isinstance(c.get("macd_crossed"), str) else c.get("macd_crossed")
    if mc not in {"bullish_cross", "bearish_cross"}:
        mc = "none"
    c["macd_crossed"] = mc

    # safety defaults, якщо чогось немає
    c.setdefault("microtrend_1m", "neutral")
    c.setdefault("microtrend_5m", "neutral")

    return c


# ===================== Rule Engine =====================

Pair = List[Tuple[str, str]]

LONG_CORE: List[Tuple[str, str]] = [
    ("boll_bucket", "<=30"),
    ("rsi_bucket", "<=30"),
    ("stoch_d_bucket", "<=20"),
    ("macd_hist_direction", "down"),
    ("macd_crossed", "none"),
    ("rsi_trend", "down"),
    ("microtrend_1m", "bearish"),
    ("microtrend_5m", "strong_bearish"),
    ("support_position", "near_support"),
]

LONG_PAIRS: List[Pair] = [
    [("boll_bucket", "<=30"), ("macd_hist_direction", "down")],
    [("boll_bucket", "<=30"), ("rsi_trend", "down")],
    [("macd_hist_direction", "down"), ("rsi_trend", "down")],
    [("microtrend_1m", "bearish"), ("stoch_d_bucket", "<=20")],
    [("rsi_bucket", "<=30"), ("stoch_d_bucket", "<=20")],
    [("rsi_bucket", "<=30"), ("support_position", "near_support")],
    [("pat_hammer", "yes"), ("rsi_bucket", "<=30")],
]

SHORT_CORE: List[Tuple[str, str]] = [
    ("boll_bucket", ">70"),
    ("rsi_bucket", ">70"),
    ("stoch_d_bucket", ">80"),
    ("stoch_k_bucket", ">80"),
    ("macd_hist_direction", "up"),
    ("macd_crossed", "bullish_cross"),
    ("rsi_trend", "up"),
    ("microtrend_1m", "bullish"),
    ("microtrend_5m", "strong_bullish"),
    ("support_position", "near_resistance"),
    ("bollinger_signal", "bullish_momentum"),
]

SHORT_PAIRS: List[Pair] = [
    [("boll_bucket", ">70"), ("macd_hist_direction", "up")],
    [("boll_bucket", ">70"), ("rsi_trend", "up")],
    [("boll_bucket", ">70"), ("microtrend_5m", "strong_bullish")],
    [("bollinger_signal", "bullish_momentum"), ("rsi_trend", "up")],
    [("macd_crossed", "bullish_cross"), ("stoch_k_bucket", ">80")],
    [("global_trend", "bearish"), ("microtrend_5m", "strong_bullish")],
    [("boll_bucket", ">70"), ("support_position", "near_resistance")],
]

W_CORE = 1.0
W_PAIR = 2.0
THRESH_LONG = 4.0
THRESH_SHORT = 4.0


def _has(c: Dict[str, Any], k: str, v: str) -> bool:
    return c.get(k) == v


def _all(c: Dict[str, Any], pairs: Pair) -> bool:
    return all(_has(c, k, v) for k, v in pairs)


def _score_side(c: Dict[str, Any], core: List[Tuple[str, str]], pairs: List[Pair], side: str) -> Dict[str, Any]:
    score = 0.0
    reasons: List[str] = []
    matched: List[str] = []

    core_hits = [(k, v) for (k, v) in core if _has(c, k, v)]
    if core_hits:
        score += W_CORE * len(core_hits)
        reasons.append(f"{side}.core hits={len(core_hits)} → {core_hits}")
        matched.extend([f"{k}={v}" for k, v in core_hits])

    pair_hits: List[Pair] = []
    for pp in pairs:
        if _all(c, pp):
            score += W_PAIR
            pair_hits.append(pp)
            matched.append("&".join([f"{k}={v}" for k, v in pp]))

    if pair_hits:
        reasons.append(f"{side}.pairs hits={len(pair_hits)} → {pair_hits}")

    return {"score": score, "matched": matched, "reasons": reasons}


def evaluate_long(raw_conditions: Dict[str, Any]) -> Dict[str, Any]:
    c = _build_derived(raw_conditions)
    res = _score_side(c, LONG_CORE, LONG_PAIRS, "LONG")
    allow = res["score"] >= THRESH_LONG
    return {
        "allow": bool(allow),
        "score": round(res["score"], 3),
        "matched": res["matched"],
        "reasons": res["reasons"],
        "side": "LONG",
        "evidence": {k: c.get(k) for k in [
            "support_position","global_trend","volume_category","macd_trend",
            "macd_hist_direction","macd_crossed","rsi_trend","rsi_signal","rsi_bucket",
            "stoch_signal","stoch_k_bucket","stoch_d_bucket","bollinger_signal","boll_bucket",
            "cci_signal","cci_bucket","microtrend_1m","microtrend_5m",
            "pat_bullish_engulfing","pat_bearish_engulfing","pat_hammer","pat_shooting_star",
            "pat_morning_star","pat_evening_star","pat_doji"
        ] if k in c}
    }


def evaluate_short(raw_conditions: Dict[str, Any]) -> Dict[str, Any]:
    c = _build_derived(raw_conditions)
    res = _score_side(c, SHORT_CORE, SHORT_PAIRS, "SHORT")
    allow = res["score"] >= THRESH_SHORT
    return {
        "allow": bool(allow),
        "score": round(res["score"], 3),
        "matched": res["matched"],
        "reasons": res["reasons"],
        "side": "SHORT",
        "evidence": {k: c.get(k) for k in [
            "support_position","global_trend","volume_category","macd_trend",
            "macd_hist_direction","macd_crossed","rsi_trend","rsi_signal","rsi_bucket",
            "stoch_signal","stoch_k_bucket","stoch_d_bucket","bollinger_signal","boll_bucket",
            "cci_signal","cci_bucket","microtrend_1m","microtrend_5m",
            "pat_bullish_engulfing","pat_bearish_engulfing","pat_hammer","pat_shooting_star",
            "pat_morning_star","pat_evening_star","pat_doji"
        ] if k in c}
    }


def evaluate_both(raw_conditions: Dict[str, Any]) -> Dict[str, Any]:
    L = evaluate_long(raw_conditions)
    S = evaluate_short(raw_conditions)
    decision = "SKIP"
    if L["allow"] and not S["allow"]:
        decision = "LONG"
    elif S["allow"] and not L["allow"]:
        decision = "SHORT"
    elif L["allow"] and S["allow"]:
        # якщо обидва дозволені — беремо більший score
        decision = "LONG" if L["score"] >= S["score"] else "SHORT"
    return {"decision": decision, "long": L, "short": S}
