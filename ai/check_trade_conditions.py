# ===================== Rejection logging (мінімально інвазивно) =====================

import json, os, time
REJECTION_LOG_PATH = os.path.join("logs", "rejections.jsonl")
ENABLE_REJECTION_LOG = True
LOG_ONLY_CLOSED_CANDLE = False          # щоб не засмічувати лог сирими тиками
MAX_REASONS_IN_SUMMARY = 3             # коротке резюме

def _reason_summary(res: dict) -> str:
    reasons = res.get("reasons", []) or []
    if not reasons:
        return "no_reasons"
    return "; ".join(reasons[:MAX_REASONS_IN_SUMMARY])

def _key_evidence(ev: dict) -> dict:
    # витягнемо найкорисніше і стисло
    keys = [
        "support_position","global_trend","macd_hist_direction","macd_crossed",
        "rsi_trend","rsi_bucket","boll_bucket","stoch_k_bucket","stoch_d_bucket",
        "pat_bearish_engulfing","pat_bullish_engulfing","pat_hammer","pat_shooting_star",
        "microtrend_1m","microtrend_5m","atr_percent","bars_in_state","bar_closed"
    ]
    out = {}
    for k in keys:
        if k in ev:
            out[k] = ev.get(k)
    return out

# ===== Dedup cache for rejections (skip identical within N seconds) =====
_GLOBAL_REJ_CACHE = {}  # key: (symbol, side) -> {"sig": (rounded_score, reason_summary), "ts": epoch}

def _is_duplicate_rejection(symbol: str, side: str, payload: dict, window_sec: int = 15) -> bool:
    import time
    rs = round(float(payload.get("score", 0.0)), 2)
    sig = (rs, _reason_summary(payload))
    k = (symbol or "UNKNOWN", side)
    now = time.time()
    prev = _GLOBAL_REJ_CACHE.get(k)
    if prev and prev.get("sig") == sig and (now - prev.get("ts", 0)) < window_sec:
        return True
    _GLOBAL_REJ_CACHE[k] = {"sig": sig, "ts": now}
    return False


def _log_rejection(symbol: str | None, side: str, payload: dict) -> None:

    symbol_key = symbol or payload.get("evidence", {}).get("symbol", "UNKNOWN")
    # анти-дубль
    if _is_duplicate_rejection(symbol_key, side, payload):
        return

    if not ENABLE_REJECTION_LOG:
        return
    try:
        if LOG_ONLY_CLOSED_CANDLE and not payload.get("evidence", {}).get("bar_closed", True):
            return
        os.makedirs(os.path.dirname(REJECTION_LOG_PATH), exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "symbol": symbol or payload.get("evidence", {}).get("symbol", "UNKNOWN"),
            "side": side,
            "score": payload.get("score", 0),
            "reason_summary": _reason_summary(payload),
            "key_evidence": _key_evidence(payload.get("evidence", {})),
            # корисно для швидкої фільтрації “чому саме відсікли”
            "matched": payload.get("matched", [])[:5]  # обрізаємо до 5 для стислості
        }
        with open(REJECTION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # ніяких падінь через лог — мовчки ігноруємо
        pass




# -*- coding: utf-8 -*-
"""
CheckTradeConditions — 15m regime-aware (drop-in) [ACTIVE MODE + TREND ALIGNMENT]
- API: evaluate_long, evaluate_short, evaluate_both(raw_conditions: dict) -> dict
- Працює з твоїми існуючими полями.
- Поєднує 2 сетапи: Mean-Reversion (відскок) і Momentum (пробій).

Очікувані поля:
- bar_closed: bool (закрита 15m свічка)
- bars_in_state: int (гістерезис)
- atr_percent: float | None
- support_position: "near_support" | "between" | "near_resistance"
- bollinger_position, bollinger_width
- rsi_value, rsi_trend; stoch_k, stoch_d
- macd_hist_direction, macd_crossed
- microtrend_1m, microtrend_5m
- global_trend, volume_category
- patterns (list[str]) → конвертуємо у бінарні прапори
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

def _bucket(value: float | None, edges: List[tuple]) -> str | None:
    if value is None:
        return None
    for lo, hi, label in edges:
        if (lo is None or value >= lo) and (hi is None or value <= hi):
            return label
    return None

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
    ("-100-0",  lambda v: v is not None and -100 < v <= 0),
    ("0-100",   lambda v: v is not None and 0 < v <= 100),
    (">100",    lambda v: v is not None and v > 100),
]

def _build_derived(conditions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормалізація чисел/рядків, бакети, патерни, безпечні дефолти.
    """
    c = dict(conditions or {})

    # --- Normalize numbers ---
    rsi_value = _to_float(c.get("rsi_value"), None)
    stoch_k   = _to_float(c.get("stoch_k"), None)
    stoch_d   = _to_float(c.get("stoch_d"), None)
    cci_value = _to_float(c.get("cci_value"), None)

    bp = _to_float(c.get("bollinger_position"), None)
    if bp is not None and 0.0 <= bp <= 1.0:
        bp = round(bp * 100.0, 2)
    c["bollinger_position"] = bp

    # --- Buckets ---
    c["rsi_bucket"]      = _bucket(rsi_value, RSI_BUCKET_EDGES)
    c["stoch_k_bucket"]  = _bucket(stoch_k,   STOCH_BUCKET_EDGES)
    c["stoch_d_bucket"]  = _bucket(stoch_d,   STOCH_BUCKET_EDGES)
    c["boll_bucket"]     = _bucket(bp,        BOLL_BUCKET_EDGES)

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
        "microtrend_1m","microtrend_5m","trend"
    ]:
        if k in c and isinstance(c[k], str):
            c[k] = _lc(c[k])

    # rsi_trend → нормалізація + fallback зі rsi_signal
    def _norm_trend(x: str | None) -> str:
        x = _lc(x) if isinstance(x, str) else None
        if x in {"up", "down", "bullish", "bearish", "neutral", "flat", "strong_bullish", "strong_bearish"}:
            return "up" if x == "bullish" else "down" if x == "bearish" else x
        return "neutral"

    c["rsi_trend"] = _norm_trend(c.get("rsi_trend"))

    if c["rsi_trend"] == "neutral":
        rsig = _lc(c.get("rsi_signal")) if isinstance(c.get("rsi_signal"), str) else None
        if rsig in {"bullish_momentum", "overbought", "bullish"}:
            c["rsi_trend"] = "up"
        elif rsig in {"bearish_momentum", "oversold", "bearish"}:
            c["rsi_trend"] = "down"
        

    # --- Pattern flags from list ---
    patterns = c.get("patterns") or []
    if isinstance(patterns, list):
        pset = {_lc(p) for p in patterns if isinstance(p, str)}
    else:
        pset = set()

    def pflag(name: str) -> str:
        return "yes" if name in pset else "no"

    c["pat_bullish_engulfing"] = pflag("bullish_engulfing")
    c["pat_bearish_engulfing"] = pflag("bearish_engulfing")
    c["pat_hammer"]            = pflag("hammer")
    c["pat_shooting_star"]     = pflag("shooting_star")
    c["pat_morning_star"]      = pflag("morning_star")
    c["pat_evening_star"]      = pflag("evening_star")
    c["pat_doji"]              = pflag("doji")

    # macd_crossed → нормалізація
    mc = c.get("macd_crossed")
    mc = _lc(mc) if isinstance(mc, str) else mc
    mapping = {
        "bull": "bullish_cross",
        "bullish": "bullish_cross",
        "up": "bullish_cross",
        "bear": "bearish_cross",
        "bearish": "bearish_cross",
        "down": "bearish_cross"
    }
    if mc in mapping:
       mc = mapping[mc]
    elif mc not in {"bullish_cross", "bearish_cross"}:
       mc = "none"
    c["macd_crossed"] = mc

    # safety defaults
    c.setdefault("microtrend_1m", "neutral")
    c.setdefault("microtrend_5m", "neutral")

    # гварди
    c["bar_closed"] = bool(c.get("bar_closed", True))
    try:
        c["bars_in_state"] = int(c.get("bars_in_state", 1))
    except Exception:
        c["bars_in_state"] = 1

    ap = _to_float(c.get("atr_percent"), None)
    if ap is not None and ap <= 0.0:
        ap = None
    if ap is None:
       al = _to_float(c.get("atr_level"), None)
       pr = _to_float(c.get("price") or c.get("current_price"), None)
       if al is not None and pr and pr > 0:
           ap = round((al / pr) * 100.0, 3)
    c["atr_percent"] = ap

    c["bollinger_width"] = _to_float(c.get("bollinger_width"), None)

    return c

# ===================== Regime detection =====================

def _detect_regime(c: Dict[str, Any]) -> Dict[str, Any]:
    atrp = _to_float(c.get("atr_percent"), None)
    bbw  = _to_float(c.get("bollinger_width"), None)
    gtr  = c.get("global_trend", "neutral")

    low_vol  = (atrp is not None and atrp <= 0.6)
    high_vol = (atrp is not None and atrp >= 4.5)
    ranged   = (bbw is not None and bbw < 6.0) or (not high_vol and not low_vol)
    trending = gtr in {"bullish","strong_bullish","bearish","strong_bearish"}

    return {
        "is_low_vol":  bool(low_vol),
        "is_high_vol": bool(high_vol),
        "is_trend":    bool(trending),
        "is_range":    bool(ranged and not trending),
    }

# ===================== Tunables =====================

# Ваги та пороги
W_CORE   = 1.5
W_PAIR   = 2.8
W_BONUS  = 1.2

# --- ACTIVE MODE thresholds ---
THRESH_LONG  = 4.5
THRESH_SHORT = 4.5

# Політика вирівнювання по тренду (залишаємо вимкнено — окремо зроблено жорсткий шорт-гейт нижче)
TREND_ALIGNMENT = {
    "align_with_global": False,
    "align_with_micro5": False,
    "allow_flat_as_neutral": False,
    "bearish_block_levels": {"bearish","strong_bearish"},
    "bullish_block_levels": {"bullish","strong_bullish"},
    "micro_bearish_levels": {"bearish","strong_bearish"},
    "micro_bullish_levels": {"bullish","strong_bullish"},
}

# Анти-фальстарт гварди (для лонгів без змін; додаткові жорсткі правила для шортів — у _apply_anti_filters)
ANTI_FALSE_OPEN = {
    "require_closed_candle": False,
    "hysteresis_bars": 2,
    "min_pair_hits_long": 0,
    "min_pair_hits_short": 0,
    "need_long_confirm_any": False,
    "need_short_confirm_any": False,
    "atr_pct_bounds": (0.35, 8.0),
    "exclusive_blockers": True
}

DECISION_DELTA = 0.5

# Підтвердження (залишаються для довідки/можливих експериментів)
CONFIRM_LONG = [
    ("rsi_trend", "up"),
    ("macd_crossed", "bullish_cross"),
    ("macd_hist_direction", "up"),
    ("stoch_signal", "bullish_cross"),
    ("pat_hammer", "yes"),
    ("pat_bullish_engulfing", "yes"),
]

CONFIRM_SHORT = [
    ("rsi_trend", "down"),
    ("macd_crossed", "bearish_cross"),
    ("macd_hist_direction", "down"),
    ("stoch_signal", "bearish_cross"),
    ("pat_shooting_star", "yes"),
    ("pat_bearish_engulfing", "yes"),
]

# Блокатори (залишив як було)
BLOCK_LONG  = [
    ("global_trend", "strong_bearish"),
    ("global_trend", "bearish"),
]
BLOCK_SHORT = [
    ("global_trend", "strong_bullish"),
    ("global_trend", "bullish"),
]

# ===================== Rule Engine =====================

Pair = List[Tuple[str, str]]

# --- Mean-Reversion (LONG) ---
MR_LONG_CORE: List[Tuple[str, str]] = [
    ("support_position", "near_support"),
    ("boll_bucket", "<=30"),
    ("rsi_bucket", "<=30"),
    ("stoch_d_bucket", "<=20"),
]
MR_LONG_PAIRS: List[Pair] = [
    [("rsi_bucket", "30-40"), ("boll_bucket", "<=30")],
    [("rsi_trend", "up"), ("macd_hist_direction", "up")],
    [("macd_crossed", "bullish_cross"), ("rsi_trend", "up")],
    [("pat_hammer", "yes"), ("rsi_trend", "up")],
    [("pat_bullish_engulfing", "yes"), ("rsi_trend", "up")],
    [("pat_bullish_engulfing", "yes"), ("support_position", "near_support")],
    [("microtrend_1m", "bullish"), ("microtrend_5m", "neutral")],
    [("microtrend_1m", "bullish"), ("microtrend_5m", "bullish")],
    [("microtrend_1m", "strong_bullish"), ("microtrend_5m", "bullish")],
]

# --- Momentum (LONG) ---
MO_LONG_CORE: List[Tuple[str, str]] = [
    ("boll_bucket", "55-70"),
    ("rsi_bucket", "50-60"),
    ("macd_hist_direction", "up"),
]
MO_LONG_PAIRS: List[Pair] = [
    [("rsi_trend", "up"), ("microtrend_1m", "bullish")],
    [("microtrend_1m", "bullish"), ("microtrend_5m", "neutral")],
    [("microtrend_1m", "bullish"), ("microtrend_5m", "bullish")],
    [("volume_category", "high"), ("rsi_trend", "up")],
    [("volume_category", "very_high"), ("rsi_trend", "up")],
]

# --- Mean-Reversion (SHORT) ---
MR_SHORT_CORE: List[Tuple[str, str]] = [
    ("support_position", "near_resistance"),
    ("boll_bucket", ">70"),
    ("rsi_bucket", ">70"),
    ("stoch_k_bucket", ">80"),
]
MR_SHORT_PAIRS: List[Pair] = [
    [("rsi_bucket", "60-70"), ("boll_bucket", ">70")],
    [("rsi_trend", "down"), ("macd_hist_direction", "down")],
    [("macd_crossed", "bearish_cross"), ("rsi_trend", "down")],
    [("pat_shooting_star", "yes"), ("rsi_trend", "down")],
    [("pat_bearish_engulfing", "yes"), ("rsi_trend", "down")],
    [("pat_bearish_engulfing", "yes"), ("support_position", "near_resistance")],
    [("microtrend_1m", "bearish"), ("microtrend_5m", "neutral")],
    [("microtrend_1m", "bearish"), ("microtrend_5m", "bearish")],
    [("microtrend_1m", "bearish"), ("microtrend_5m", "strong_bearish")],
]

# --- Momentum (SHORT) ---
MO_SHORT_CORE: List[Tuple[str, str]] = [
    ("boll_bucket", "30-45"),
    ("rsi_bucket", "50-60"),
    ("macd_hist_direction", "down"),
]
MO_SHORT_PAIRS: List[Pair] = [
    [("rsi_trend", "down"), ("microtrend_1m", "bearish")],
    [("microtrend_1m", "bearish"), ("microtrend_5m", "neutral")],
    [("microtrend_1m", "bearish"), ("microtrend_5m", "bearish")],
    [("volume_category", "high"), ("rsi_trend", "down")],
    [("volume_category", "very_high"), ("rsi_trend", "down")],
]

def _has(c: Dict[str, Any], k: str, v: str) -> bool:
    return c.get(k) == v

def _all(c: Dict[str, Any], pairs: Pair) -> bool:
    return all(_has(c, k, v) for k, v in pairs)

def _score_block(c: Dict[str, Any], core: List[Tuple[str, str]], pairs: List[Pair], side: str, tag: str) -> Dict[str, Any]:
    score = 0.0
    reasons: List[str] = []
    matched: List[str] = []

    core_hits = [(k, v) for (k, v) in core if _has(c, k, v)]
    if core_hits:
        score += W_CORE * len(core_hits)
        reasons.append(f"{side}.{tag}.core hits={len(core_hits)} → {core_hits}")
        matched.extend([f"{k}={v}" for k, v in core_hits])

    pair_hits: List[Pair] = []
    for pp in pairs:
        if _all(c, pp):
            score += W_PAIR
            pair_hits.append(pp)
            matched.append("&".join([f"{k}={v}" for k, v in pp]))

    if pair_hits:
        reasons.append(f"{side}.{tag}.pairs hits={len(pair_hits)} → {pair_hits}")

    return {"score": score, "matched": matched, "reasons": reasons, "_pair_hits_count": len(pair_hits)}

def _apply_regime_bonus(side: str, tag: str, regime: Dict[str, Any], scorepack: Dict[str, Any]) -> None:
    # невеликий бонус, якщо сетап відповідає режиму
    if side == "LONG":
        if tag == "MR" and (regime["is_range"] or regime["is_low_vol"]):
            scorepack["score"] += W_BONUS
            scorepack["reasons"].append(f"{side}.{tag}.bonus regime")
        if tag == "MO" and (regime["is_trend"] or regime["is_high_vol"]):
            scorepack["score"] += W_BONUS
            scorepack["reasons"].append(f"{side}.{tag}.bonus regime")
    else:
        if tag == "MR" and (regime["is_range"] or regime["is_low_vol"]):
            scorepack["score"] += W_BONUS
            scorepack["reasons"].append(f"{side}.{tag}.bonus regime")
        if tag == "MO" and (regime["is_trend"] or regime["is_high_vol"]):
            scorepack["score"] += W_BONUS
            scorepack["reasons"].append(f"{side}.{tag}.bonus regime")

# ===================== Anti-noise & Alignment filters =====================

def _meets_pairs_quorum(res: Dict[str, Any], min_pairs: int) -> bool:
    if not min_pairs:
        return True
    return int(res.get("_pair_hits_count", 0)) >= int(min_pairs)

def _any_of(c: Dict[str, Any], pairs_list: List[Tuple[str, str]]) -> bool:
    return any(c.get(k) == v for (k, v) in pairs_list)

def _blocked_by(c: Dict[str, Any], blockers: List[Tuple[str, str]]) -> bool:
    if not blockers or not ANTI_FALSE_OPEN.get("exclusive_blockers", True):
        return False
    return any(c.get(k) == v for k, v in blockers)

def _trend_alignment_blocks(side: str, c: Dict[str, Any]) -> str | None:
    """
    Повертає текст причини блокування за трендом або None.
    """
    if not TREND_ALIGNMENT:
        return None

    g = c.get("global_trend", "neutral")
    m5 = c.get("microtrend_5m", "neutral")

    allow_flat = TREND_ALIGNMENT.get("allow_flat_as_neutral", True)
    bear_levels = TREND_ALIGNMENT.get("bearish_block_levels", {"bearish","strong_bearish"})
    bull_levels = TREND_ALIGNMENT.get("bullish_block_levels", {"bullish","strong_bullish"})
    micro_bear = TREND_ALIGNMENT.get("micro_bearish_levels", {"bearish","strong_bearish"})
    micro_bull = TREND_ALIGNMENT.get("micro_bullish_levels", {"bullish","strong_bullish"})

    # Глобальний тренд
    if TREND_ALIGNMENT.get("align_with_global", True):
        if side == "LONG" and g in bear_levels:
            return f"align: global_bear({g})"
        if side == "SHORT" and g in bull_levels:
            return f"align: global_bull({g})"

    # Мікро 5m
    if TREND_ALIGNMENT.get("align_with_micro5", True):
        if side == "LONG" and m5 in micro_bear:
            if not (allow_flat and m5 in {"flat","neutral"}):
                return f"align: micro5_bear({m5})"
        if side == "SHORT" and m5 in micro_bull:
            if not (allow_flat and m5 in {"flat","neutral"}):
                return f"align: micro5_bull({m5})"

    return None

def _apply_anti_filters(side: str, c: Dict[str, Any], res_total: Dict[str, Any], allow: bool) -> Tuple[bool, Dict[str, Any]]:
    if not allow:
        return allow, res_total

    # ---------- ДОДАТКОВІ ЖОРСТКІ ПРАВИЛА ДЛЯ ШОРТІВ ----------
    if side == "SHORT":
        g = str(c.get("global_trend", "neutral")).lower()
        m5 = str(c.get("microtrend_5m", "neutral")).lower()

        # 0) Шорт лише у bearish/strong_bearish
        if g not in {"bearish", "strong_bearish"}:
            allow = False
            res_total["reasons"].append("short: require_global_bearish")
        # 1) Не шортимо коли micro 5m bullish/strong_bullish
        if allow and m5 in {"bullish", "strong_bullish"}:
            allow = False
            res_total["reasons"].append("short: micro5_bullish_block")
        # 2) Потрібна закрита 15m свічка
        if allow and not bool(c.get("bar_closed", True)):
            allow = False
            res_total["reasons"].append("short: need_closed_15m")
        # 3) Мінімум 2 збіги з парних правил
        if allow and int(res_total.get("_pair_hits_count", 0)) < 2:
            allow = False
            res_total["reasons"].append("short: need_pair_hits>=2")
        # 4) Хоч один підтверджувальний сигнал
        if allow and not _any_of(c, CONFIRM_SHORT):
            allow = False
            res_total["reasons"].append("short: need_confirm_any")

    if not allow:
        return allow, res_total

    # ---------- БАЗОВІ (як було) ----------
    # 0) Вирівнювання по тренду (вимкнено флагами; лишаємо на випадок, якщо ти увімкнеш)
    align_reason = _trend_alignment_blocks(side, c)
    if align_reason:
        allow = False
        res_total["reasons"].append(align_reason)

    # 1) Закрита свічка (глобальний прапор; для лонгів — без змін)
    if allow and ANTI_FALSE_OPEN["require_closed_candle"] and not bool(c.get("bar_closed", True)):
        allow = False
        res_total["reasons"].append("anti: wait_close")

    # 2) Гістерезис
    hb = int(ANTI_FALSE_OPEN.get("hysteresis_bars", 0) or 0)
    if allow and hb > 0:
        try:
            bis = int(c.get("bars_in_state", 0))
        except Exception:
            bis = 0
        if bis < hb:
            allow = False
            res_total["reasons"].append(f"anti: hysteresis<{hb}")

    # 3) ATR% межі (якщо дані є)
    lo, hi = ANTI_FALSE_OPEN.get("atr_pct_bounds", (0.0, 999.0))
    ap = c.get("atr_percent", None)
    if allow and ap is not None and ap > 0.0:
        if (ap < lo) or (ap > hi):
            allow = False
            res_total["reasons"].append(f"anti: atr_out({round(float(ap),3)} not in {lo}-{hi})")

    # 4) Мінімальна к-ть підтверджень / блокатори (як було)
    if side == "LONG":
        if allow and not _meets_pairs_quorum(res_total, int(ANTI_FALSE_OPEN.get("min_pair_hits_long", 0) or 0)):
            allow = False
            res_total["reasons"].append("anti: pairs_quorum_long")
        if allow and ANTI_FALSE_OPEN.get("need_long_confirm_any", False):
            if not _any_of(c, CONFIRM_LONG):
                allow = False
                res_total["reasons"].append("anti: need_confirm_long")
        if allow and _blocked_by(c, BLOCK_LONG):
            allow = False
            res_total["reasons"].append("anti: long_blocked")
    else:
        if allow and not _meets_pairs_quorum(res_total, int(ANTI_FALSE_OPEN.get("min_pair_hits_short", 0) or 0)):
            allow = False
            res_total["reasons"].append("anti: pairs_quorum_short")
        if allow and ANTI_FALSE_OPEN.get("need_short_confirm_any", False):
            if not _any_of(c, CONFIRM_SHORT):
                allow = False
                res_total["reasons"].append("anti: need_confirm_short")
        if allow and _blocked_by(c, BLOCK_SHORT):
            allow = False
            res_total["reasons"].append("anti: short_blocked")

    return allow, res_total

# ===================== Public API =====================

def _public_payload(side: str, allow: bool, res: Dict[str, Any], c: Dict[str, Any], regime: Dict[str, Any]) -> Dict[str, Any]:
    ev_keys = [
        "support_position","global_trend","volume_category","macd_trend",
        "macd_hist_direction","macd_crossed","rsi_trend","rsi_signal","rsi_bucket",
        "stoch_signal","stoch_k_bucket","stoch_d_bucket","bollinger_signal","boll_bucket",
        "cci_signal","cci_bucket","microtrend_1m","microtrend_5m",
        "pat_bullish_engulfing","pat_bearish_engulfing","pat_hammer","pat_shooting_star",
        "pat_morning_star","pat_evening_star","pat_doji",
        "bar_closed","bars_in_state","atr_percent","bollinger_width"
    ]
    payload = {
        "allow": bool(allow),
        "score": round(float(res.get("score", 0.0)), 3),
        "matched": list(res.get("matched", [])),
        "reasons": list(res.get("reasons", [])),
        "side": side,
        "evidence": {k: c.get(k) for k in ev_keys if k in c}
    }
    payload["reasons"].append(f"regime: trend={regime['is_trend']} range={regime['is_range']} hiVol={regime['is_high_vol']} loVol={regime['is_low_vol']}")
    return payload

def evaluate_long(raw_conditions: Dict[str, Any]) -> Dict[str, Any]:
    c = _build_derived(raw_conditions)
    regime = _detect_regime(c)

    mr = _score_block(c, MR_LONG_CORE, MR_LONG_PAIRS, "LONG", "MR")
    mo = _score_block(c, MO_LONG_CORE, MO_LONG_PAIRS, "LONG", "MO")
    _apply_regime_bonus("LONG", "MR", regime, mr)
    _apply_regime_bonus("LONG", "MO", regime, mo)

    res = {
        "score": mr["score"] + mo["score"],
        "matched": mr["matched"] + mo["matched"],
        "reasons": mr["reasons"] + mo["reasons"],
        "_pair_hits_count": mr["_pair_hits_count"] + mo["_pair_hits_count"],
    }

    allow = res["score"] >= THRESH_LONG
    allow, res = _apply_anti_filters("LONG", c, res, allow)

    payload = _public_payload("LONG", allow, res, c, regime)
    if not payload["allow"]:
        _log_rejection(c.get("symbol"), "LONG", payload)
    return payload


def evaluate_short(raw_conditions: Dict[str, Any]) -> Dict[str, Any]:
    c = _build_derived(raw_conditions)
    regime = _detect_regime(c)

    mr = _score_block(c, MR_SHORT_CORE, MR_SHORT_PAIRS, "SHORT", "MR")
    mo = _score_block(c, MO_SHORT_CORE, MO_SHORT_PAIRS, "SHORT", "MO")
    _apply_regime_bonus("SHORT", "MR", regime, mr)
    _apply_regime_bonus("SHORT", "MO", regime, mo)

    res = {
        "score": mr["score"] + mo["score"],
        "matched": mr["matched"] + mo["matched"],
        "reasons": mr["reasons"] + mo["reasons"],
        "_pair_hits_count": mr["_pair_hits_count"] + mo["_pair_hits_count"],
    }

    allow = res["score"] >= THRESH_SHORT
    allow, res = _apply_anti_filters("SHORT", c, res, allow)

    payload = _public_payload("SHORT", allow, res, c, regime)
    if not payload["allow"]:
        _log_rejection(c.get("symbol"), "SHORT", payload)
    return payload


def evaluate_both(raw_conditions: Dict[str, Any]) -> Dict[str, Any]:
    L = evaluate_long(raw_conditions)
    S = evaluate_short(raw_conditions)
    decision = "SKIP"
    if L["allow"] and not S["allow"]:
        decision = "LONG"
    elif S["allow"] and not L["allow"]:
        decision = "SHORT"
    elif L["allow"] and S["allow"]:
        if abs((L["score"] or 0.0) - (S["score"] or 0.0)) < float(DECISION_DELTA):
            decision = "SKIP"
        else:
            decision = "LONG" if L["score"] >= S["score"] else "SHORT"
    return {"decision": decision, "long": L, "short": S}
