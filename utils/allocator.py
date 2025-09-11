# allocator.py

from typing import Dict, Any
from pybit.unified_trading import HTTP
from config import (
    MAX_ACTIVE_TRADES,
    SMART_AVG,
    DESIRED_ACTIVE_TRADES,          # скільки ХОЧЕМО активних трейдів
    ACCOUNT_SAFETY_BUFFER_PCT,      # напр. 0.05 = 5% загального балансу тримаємо в запасі
    ACCOUNT_MIN_FREE_USDT,          # напр. 0.0..50.0 — фіксована подушка
    BYBIT_API_KEY, BYBIT_API_SECRET
)
from utils.logger import log_error, log_message, load_active_trades

# Для реального балансу UNIFIED акаунту
_bybit = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET)


# ============================ Хелпери активних угод ============================

def get_open_trades_count() -> int:
    """Рахує кількість НЕЗАКРИТИХ угод із ActiveTrades."""
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            return sum(1 for t in trades.values() if isinstance(t, dict) and not t.get("closed"))
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
            return any(
                isinstance(rec, dict) and rec.get("symbol") == symbol and not rec.get("closed")
                for rec in trades.values()
            )
        elif isinstance(trades, list):
            return any(
                isinstance(rec, dict) and rec.get("symbol") == symbol and not rec.get("closed")
                for rec in trades
            )
    except Exception as e:
        log_error(f"[allocator] has_open_trade_for: {e}")
    return False


# ============================ Баланс / резерви ============================

def get_unified_equity() -> float:
    """
    Реальний equity UNIFIED акаунту (USDT).
    Якщо UNIFIED тимчасово 0, пробує FUNDING для діагностики.
    """
    try:
        resp = _bybit.get_wallet_balance(accountType="UNIFIED")
        eq = float(resp["result"]["list"][0].get("totalEquity", 0.0))
        if eq > 0:
            return eq
        # Фолбек (для дебагу/логів): покажемо, якщо гроші зависли у FUNDING
        try:
            fund = _bybit.get_wallet_balance(accountType="FUND")
            f_eq = float(fund["result"]["list"][0].get("totalWalletBalance", 0.0))
            if f_eq > 0:
                log_message(f"[ALLOC] UNIFIED equity=0, FUNDING balance≈{f_eq:.2f} — зроби Transfer: Funding→Unified")
        except Exception:
            pass
        return 0.0
    except Exception as e:
        log_error(f"[allocator.get_unified_equity] {e}")
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
        total_units = 0.0
        cur = 1.0
        for _ in range(max_adds + 1):
            total_units += cur
            cur *= factor
        return base * total_units
    else:
        # equal: (старт + max_adds докупок) * однаковий крок
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


def _used_margin_now() -> float:
    """
    Скільки маржі вже використано відкритими угодами (за даними active_trades.json).
    Якщо нема коректних даних — повертаємо 0 (буде «верхня» консервативна модель нижче).
    """
    try:
        trades = load_active_trades() or {}
        if isinstance(trades, dict):
            items = trades.values()
        elif isinstance(trades, list):
            items = trades
        else:
            return 0.0
        used = 0.0
        for rec in items:
            if not isinstance(rec, dict) or rec.get("closed"):
                continue
            smart = rec.get("smart_avg", {})
            used += float(smart.get("total_margin_used", 0.0) or 0.0)
        return max(0.0, used)
    except Exception as e:
        log_error(f"[allocator._used_margin_now] {e}")
        return 0.0


def _max_supported_trades(avail: float, reserved_per_trade: float, keep_reserve: float) -> int:
    """
    Скільки ПОВНИХ DCA-угод може потягнути баланс з урахуванням акаунтної подушки.
    """
    if reserved_per_trade <= 0:
        return 0
    budget_for_trades = max(0.0, avail - keep_reserve)
    return int(budget_for_trades // reserved_per_trade)


def _log_alloc_snapshot(avail, keep_reserve, reserved_full_trade, open_cnt, capacity_total, effective_limit, desired, hard_cap, used_reserved):
    try:
        log_message(
            "[ALLOC] "
            f"avail={avail:.2f}, keep={keep_reserve:.2f}, B={reserved_full_trade:.2f}, "
            f"used={used_reserved:.2f}, open={open_cnt}, cap={capacity_total}, "
            f"limit={effective_limit}, desired={desired}, hard_cap={hard_cap}"
        )
    except Exception:
        pass


# ============================ Головна функція ============================

def plan_allocation_for_new_trade(symbol: str) -> Dict[str, Any]:
    """
    Динамічний аллокатор:
    - Рахує capacity за реальним equity (UNIFIED).
    - Обмежує лімітом: MAX_ACTIVE_TRADES, DESIRED_ACTIVE_TRADES.
    - Враховує вже використану маржу відкритими угодами (active_trades.json).
    - Дає стартову суму для 1-ї сходинки (SMART_AVG.base_margin), якщо реально вистачає на повну DCA-угоду.
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

        # 1) Реальний баланс та параметри DCA
        avail = float(get_unified_equity())
        if avail <= 0:
            return {
                "allow": False,
                "reason": "no_balance_or_not_in_unified",
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
            _log_alloc_snapshot(avail, keep_reserve, reserved_full_trade, open_cnt, capacity_total, effective_limit, desired, hard_cap, _used_margin_now())
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

        # 4) Чи реально тягнемо ще ОДНУ повну DCA-угоду саме зараз?
        used_reserved = _used_margin_now()  # фактично зайнята маржа
        must_have_for_new = used_reserved + reserved_full_trade + keep_reserve
        if avail < must_have_for_new:
            lack = must_have_for_new - avail
            reason = f"insufficient_now_for_next (need={must_have_for_new:.2f}, avail={avail:.2f}, lack={lack:.2f}, keep={keep_reserve:.2f})"
            _log_alloc_snapshot(avail, keep_reserve, reserved_full_trade, open_cnt, capacity_total, effective_limit, desired, hard_cap, used_reserved)
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

        # 5) Ок — можна відкривати ще одну повну DCA-угоду
        base_margin = float(SMART_AVG.get("base_margin", 0.0))
        _log_alloc_snapshot(avail, keep_reserve, reserved_full_trade, open_cnt, capacity_total, effective_limit, desired, hard_cap, used_reserved)
        return {
            "allow": True,
            "reason": "ok",
            "amount_to_use": base_margin,               # стартовий крок (1-а сходинка)
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
