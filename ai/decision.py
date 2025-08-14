
from ai.check_trade_conditions import evaluate_long, evaluate_short
from typing import Dict, Any, Optional


def _to_result(side: str, allow: bool, score: float, reasons, matched, evidence, min_points: Optional[int] = None):
    """
    Приводимо відповідь до формату, який очікує scalping.py:
    - open_trade: "LONG"/"SHORT" або None
    - add_to_watchlist: bool
    - watch_reason: текст для watchlist
    """
    if isinstance(min_points, int):
        allow = score >= float(min_points)

    open_trade = side if allow else None
    add_to_watchlist = not allow
    # лаконічна причина (не на 10 рядків), але інформативна
    reason = "; ".join(reasons) if reasons else "rules_not_matched"

    return {
        "open_trade": open_trade,
        "add_to_watchlist": add_to_watchlist,
        "watch_reason": reason,
        "score": float(score),
        "side": side,
        "matched": matched or [],
        "evidence": evidence or {},
    }

def check_trade_conditions_long(conditions: Dict[str, Any], min_points: Optional[int] = None) -> Dict[str, Any]:
    """
    API-сов сумісний з існуючим scalping.py.
    """
    res = evaluate_long(conditions)  # {allow, score, reasons, matched, evidence, side="LONG"}
    return _to_result(
        side="LONG",
        allow=bool(res.get("allow")),
        score=float(res.get("score", 0.0)),
        reasons=res.get("reasons", []),
        matched=res.get("matched", []),
        evidence=res.get("evidence", {}),
        min_points=min_points,
    )

def check_trade_conditions_short(conditions: Dict[str, Any], min_points: Optional[int] = None) -> Dict[str, Any]:
    """
    API-сов сумісний з існуючим scalping.py.
    """
    res = evaluate_short(conditions)  # {allow, score, reasons, matched, evidence, side="SHORT"}
    return _to_result(
        side="SHORT",
        allow=bool(res.get("allow")),
        score=float(res.get("score", 0.0)),
        reasons=res.get("reasons", []),
        matched=res.get("matched", []),
        evidence=res.get("evidence", {}),
        min_points=min_points,
    )
