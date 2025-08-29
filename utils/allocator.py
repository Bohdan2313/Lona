# allocator.py

from typing import Dict, Any, Optional

from config import (
    MAX_ACTIVE_TRADES,
    USE_MANUAL_BALANCE, MANUAL_BALANCE,
    SMART_AVG,
    DESIRED_ACTIVE_TRADES,          # скільки ти ХОЧЕШ активних трейдів
    ACCOUNT_SAFETY_BUFFER_PCT,      # напр. 0.05 = 5% загального балансу тримаємо в запасі
    ACCOUNT_MIN_FREE_USDT,          # напр. 0.0..50.0 — фіксована подушка
)
from utils.tools import get_balance
from utils.logger import log_error, load_active_trades


# ============================ Хелпери активних угод ============================

def get_open_trades_count() -> int:
    """Рахує кількість НЕЗАКРИТИХ угод із ActiveTrades."""
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            return sum(1 for t in trades.values() if not t.get("closed"))
        elif isinstance(trades, list):
            return sum(1 for t in trades if isinstance(t, dict) and not t.get("closed"))
    except Exception as e:
        log_error(f"[allocator] get_open_trades_count: {e}")
    return 0

def has_open_trade_for(symbol: str) -> bool:
    """Перевіряє, чи є вже відкрита угода по символу."""
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            return any(isinstance(rec, dict) and rec.get("symbol") == symbol and not rec.get("closed")
                       for rec in trades.values())
        elif isinstance(trades, list):
            return any(isinstance(rec, dict) and rec.get("symbol") == symbol and not rec.get("closed")
                       for rec in trades)
    except Exception as e:
        log_error(f"[allocator] has_open_trade_for: {e}")
    return False


# ============================ Баланс / резерви ============================

def get_available_balance() -> float:
    """Повертає доступний USDT баланс з урахуванням MANUAL/реального режиму."""
    try:
        if USE_MANUAL_BALANCE:
            return float(MANUAL_BALANCE)
        return float(get_balance() or 0.0)
    except Exception as e:
        log_error(f"[allocator.get_available_balance] {e}")
        return 0.0

def _dca_total_needed_per_trade(cfg: Dict[str, Any]) -> float:
    """
    Скільки МАРЖІ потрібно зарезервувати під ОДНУ угоду з урахуванням усіх докупок.
    Підтримує equal та progressive режим.
    """
    base = float(cfg.get("base_margin", 0.0))
    max_adds = int(cfg.get("max_adds", 0))
    mode = str(cfg.get("dca_mode", "equal")).lower()
    factor = float(cfg.get("dca_factor", 1.2))

    if base <= 0:
        return 0.0

    if mode == "progressive":
        total = 0.0
        cur = 1.0
        for _ in range(max_adds + 1):
            total += cur
            cur *= factor
        return base * total
    else:
        return base * (1 + max_adds)

def _account_keep_reserve(avail: float) -> float:
    """Скільки тримаємо як подушку по акаунту (pct + фікс)."""
    try:
        pct = float(ACCOUNT_SAFETY_BUFFER_PCT)
    except Exception:
        pct = 0.0
    try:
        fixed = float(ACCOUNT_MIN_FREE_USDT)
    except Exception:
        fixed = 0.0
    return max(0.0, avail * pct) + max(0.0, fixed)

def _max_supported_trades(avail: float, reserved_per_trade: float, keep_reserve: float) -> int:
    """
    Скільки ПОВНИХ DCA-угод може потягнути баланс з урахуванням акаунтної подушки.
    """
    if reserved_per_trade <= 0:
        return 0
    budget_for_trades = max(0.0, avail - keep_reserve)
    return int(budget_for_trades // reserved_per_trade)


# ============================ Головна функція ============================

def plan_allocation_for_new_trade(
    symbol: str,
) -> Dict[str, Any]:
    """
    Динамічний аллокатор:
    - Рахує capacity за балансом (скільки ПОВНИХ DCA-угод реально тягнемо).
    - Обмежує лімітом біржі/конфігом: MAX_ACTIVE_TRADES.
    - Авто-зменшує бажану кількість, якщо не вистачає балансу.
    - Дає стартову суму для 1-ї сходинки (SMART_AVG.base_margin), лише якщо вистачає
      на повний DCA і для вже відкритих угод.
    """
    try:
        # 0) Слоти та дубль-символ
        open_cnt = int(get_open_trades_count())
        if has_open_trade_for(symbol):
            return {
                "allow": False,
                "reason": "duplicate_symbol",
                "amount_to_use": 0.0,
                "reserved_per_trade": 0.0,
                "open_trades": open_cnt,
                "effective_limit": 0,
                "desired": int(DESIRED_ACTIVE_TRADES),
                "capacity_total": 0
            }

        # 1) Баланс та параметри DCA
        avail = float(get_available_balance())
        if avail <= 0:
            return {
                "allow": False,
                "reason": "no_balance",
                "amount_to_use": 0.0,
                "reserved_per_trade": 0.0,
                "open_trades": open_cnt,
                "effective_limit": 0,
                "desired": int(DESIRED_ACTIVE_TRADES),
                "capacity_total": 0
            }

        reserved_full_trade = _dca_total_needed_per_trade(SMART_AVG)
        if reserved_full_trade <= 0:
            return {
                "allow": False,
                "reason": "cfg_error_reserved_full_trade<=0",
                "amount_to_use": 0.0,
                "reserved_per_trade": 0.0,
                "open_trades": open_cnt,
                "effective_limit": 0,
                "desired": int(DESIRED_ACTIVE_TRADES),
                "capacity_total": 0
            }

        keep_reserve = _account_keep_reserve(avail)
        capacity_total = _max_supported_trades(avail, reserved_full_trade, keep_reserve)

        # 2) Ефективний ліміт активних угод
        desired = int(DESIRED_ACTIVE_TRADES)
        hard_cap = int(MAX_ACTIVE_TRADES)
        effective_limit = max(0, min(hard_cap, desired, capacity_total))

        # 3) Якщо вже відкрито >= ефективного ліміту — нові заборонені
        if open_cnt >= effective_limit:
            reason = f"no_slots_dynamic (open={open_cnt}, limit={effective_limit}, desired={desired}, hard_cap={hard_cap}, capacity={capacity_total})"
            return {
                "allow": False,
                "reason": reason,
                "amount_to_use": 0.0,
                "reserved_per_trade": reserved_full_trade,
                "open_trades": open_cnt,
                "effective_limit": effective_limit,
                "desired": desired,
                "capacity_total": capacity_total
            }

        # 4) Перевірка: вистачає ЛИШЕ на ще одну повну DCA-угоду прямо зараз?
        # Резерв уже відкритих (логічна модель): open_cnt * reserved_full_trade
        used_reserved = open_cnt * reserved_full_trade
        must_have_for_new = used_reserved + reserved_full_trade + keep_reserve
        if avail < must_have_for_new:
            # Теоретично capacity_total мав це вже врахувати; але якщо DESIRED/limit змінився між тиками — пояснимо явно.
            lack = must_have_for_new - avail
            reason = f"insufficient_now_for_next (need={must_have_for_new:.2f}, avail={avail:.2f}, lack={lack:.2f}, keep={keep_reserve:.2f})"
            return {
                "allow": False,
                "reason": reason,
                "amount_to_use": 0.0,
                "reserved_per_trade": reserved_full_trade,
                "open_trades": open_cnt,
                "effective_limit": effective_limit,
                "desired": desired,
                "capacity_total": capacity_total
            }

        # 5) Якщо ми тут — можна відкривати ще 1 повну DCA-угоду
        base_margin = float(SMART_AVG.get("base_margin", 0.0))
        return {
            "allow": True,
            "reason": "ok",
            "amount_to_use": base_margin,               # стартовий бюджет (1-ша сходинка)
            "reserved_per_trade": reserved_full_trade,  # повний резерв під DCA (для довідки)
            "open_trades": open_cnt,
            "effective_limit": effective_limit,
            "desired": desired,
            "capacity_total": capacity_total
        }

    except Exception as e:
        log_error(f"[plan_allocation_for_new_trade] {e}")
        return {
            "allow": False,
            "reason": "exception",
            "amount_to_use": 0.0,
            "reserved_per_trade": 0.0,
            "open_trades": 0,
            "effective_limit": 0,
            "desired": 0,
            "capacity_total": 0
        }
