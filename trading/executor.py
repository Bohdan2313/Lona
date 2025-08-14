import time
import json
from datetime import datetime
import os
from utils.logger import log_message, log_error
from utils.tools import get_current_futures_price
from config import bybit
import numpy as np
import pandas as pd
from utils.logger import deep_sanitize
from config import USE_MANUAL_LEVERAGE, MANUAL_LEVERAGE


SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

def json_safe(obj):
    """🛡️ Рекурсивно робить об'єкт безпечним для JSON"""
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_safe(v) for v in obj]
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    else:
        return str(obj)

def write_journal_entry(
    symbol, side, leverage, result, gpt_decision,
    signals=None, notes=None, violated_rules=None,
    pnl_result=None, duration_minutes=None, exit_reason=None, exit_price=None,
    llama_reflection=None
):
    journal_file = "logs/ai_journal.json"
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    try:
        # 🐞 Debug вхідних даних
        log_message("🐞 DEBUG write_journal_entry input:\n" + json.dumps(deep_sanitize({
            'symbol': symbol,
            'side': side,
            'leverage': leverage,
            'result': result,
            'gpt_decision': gpt_decision,
            'signals': signals,
            'notes': notes,
            'violated_rules': violated_rules,
            'pnl_result': pnl_result,
            'duration_minutes': duration_minutes,
            'exit_reason': exit_reason,
            'exit_price': exit_price,
            'llama_reflection': llama_reflection
        }), indent=2, ensure_ascii=False))

        # 📝 Створюємо новий запис
        new_entry = {
            "timestamp": timestamp,
            "symbol": symbol or "N/A",
            "side": side or "N/A",
            "leverage": leverage or "N/A",
            "result": result if isinstance(result, dict) else {"raw_result": str(result)},
            "signals": signals if isinstance(signals, dict) else {"warning": f"signals не dict ({type(signals)})", "raw": str(signals)},
            "gpt_decision": gpt_decision or "N/A",
            "notes": notes or "",
            "violated_rules": violated_rules or [],
            "reflection_used": bool(llama_reflection),
            "llama_reflection": llama_reflection or "⚠️ Reflection відсутній.",
            "pnl_result": {
                "pnl_percent": pnl_result.get("pnl_percent") if pnl_result else None,
                "exit_price": exit_price,
                "exit_reason": exit_reason,
                "duration_minutes": duration_minutes
            }
        }
        new_entry = deep_sanitize(new_entry)

        log_message("🐞 DEBUG journal entry перед записом:\n" + json.dumps(new_entry, indent=2, ensure_ascii=False))

        # 📖 Читаємо журнал або створюємо новий
        if os.path.exists(journal_file):
            try:
                with open(journal_file, "r", encoding="utf-8") as f:
                    journal = json.load(f)
            except Exception as e_read:
                log_error(f"⚠️ Помилка читання журналу: {e_read}. Створюємо новий.")
                journal = []
        else:
            journal = []

        journal.append(new_entry)
        journal = journal[-500:]  # 🧹 Максимум 500 записів

        with open(journal_file, "w", encoding="utf-8") as f:
            json.dump(journal, f, ensure_ascii=False, indent=2)

        log_message(f"✅ Записано в журнал: {symbol} ({side}) → PnL: {pnl_result.get('pnl_percent') if pnl_result else 'N/A'}%")

    except Exception as e:
        log_error(f"❌ Загальна помилка запису в журнал: {e}")


def round_qty_bybit(symbol, qty):
    import math
    try:
        info = bybit.get_instruments_info(category="linear", symbol=symbol)
        qty_step = float(info["result"]["list"][0]["lotSizeFilter"]["qtyStep"])
        rounded_qty = math.floor(qty / qty_step) * qty_step
        return round(rounded_qty, 8)
    except Exception as e:
        log_error(f"❌ [round_qty_bybit] Помилка: {e}")
        return round(qty, 8)

def round_price_bybit(symbol, price):
    import math
    try:
        info = bybit.get_instruments_info(category="linear", symbol=symbol)
        tick_size = float(info["result"]["list"][0]["priceFilter"]["tickSize"])
        precision = abs(round(math.log10(tick_size)))
        return round(price, precision)
    except Exception as e:
        log_error(f"❌ [round_price_bybit] Помилка: {e}")
        return price

log_message("🐞 DEBUG executor.py імпортовано та використовується")



class OrderExecutor:

    def __init__(self, symbol, side, amount_to_use, target_price=None, position_side=None, leverage=None,
                 bypass_price_check=False, force_take_profit_pct=None):
        self.symbol = symbol
        self.side = side  # ✅ Передається реально: "Buy" або "Sell"
        self.amount_to_use = amount_to_use
        self.target_price = target_price
        self.position_side = position_side.upper() if position_side else "LONG"  # ✅ LONG або SHORT
        self.leverage = leverage
        self.force_take_profit_pct = force_take_profit_pct
        self.price = None
        self.quantity = None
        self.bypass_price_check = bypass_price_check
        

        self.leverage = leverage
        if not self.leverage:
            raise Exception("❌ Leverage не передане в OrderExecutor!")


    def prepare_order(self):
        log_message(f"🐞 DEBUG prepare_order() для {self.symbol}")

        target_price = self.target_price
        if not isinstance(target_price, (int, float)) or target_price <= 0:
            raise Exception(f"❌ Некоректне target_price: {target_price}")

        if self.bypass_price_check:
            current_price = get_current_futures_price(self.symbol)
            if not current_price:
                raise Exception(f"❌ Поточна ціна недоступна для {self.symbol}")
            self.price = current_price
            log_message(f"🚀 [Sniper] Вхід без перевірки: ціна {self.price}")
        else:
            tolerance = 0.002
            for attempt in range(200):
                current_price = get_current_futures_price(self.symbol)
                if current_price:
                    price_diff = abs(current_price - target_price) / target_price
                    if price_diff <= tolerance:
                        break
                time.sleep(3)
            else:
                raise Exception(f"❌ Ціна {target_price} не досягнута.")
            self.price = current_price

        notional_value = self.amount_to_use * self.leverage
        self.quantity = round(notional_value / self.price, 3)
        if self.quantity <= 0:
            raise Exception("❌ Недостатньо суми для ордера.")


    def place_order(self):
        try:
            rounded_qty = round_qty_bybit(self.symbol, self.quantity)
            response = bybit.place_order(
                category="linear",
                symbol=self.symbol,
                side=self.side,  # ✅ "Buy" або "Sell"
                positionSide=self.position_side,  # ✅ "LONG" або "SHORT"
                orderType="Market",
                qty=str(rounded_qty)
            )

            if response.get("retCode") == 0:
                log_message(f"✅ Ордер створено: {response['result'].get('orderId', '?')}")
                return True
            else:
                log_error(f"❌ Помилка від Bybit: {response}")
                return False
        except Exception as e:
            log_error(f"❌ place_order() виняток: {e}")
            return False

    def execute(self):
        log_message(f"🟢 Виконання execute() для {self.symbol}")
        try:
            self.prepare_order()
            log_message(f"🔧 Встановлюю плече {self.leverage}x на Bybit для {self.symbol} ({self.position_side})")

            self.set_safe_leverage()

            if self.place_order():
                result = {
                    "symbol": self.symbol,
                    "side": self.side,
                    "entry_price": self.price,
                    "quantity": self.quantity,
                    "position_side": self.position_side,
                    "leverage": self.leverage
                }
                

                log_message("🐞 DEBUG execute() результат:\n" + json.dumps(json_safe(result), indent=2, ensure_ascii=False))
                return result
            else:
                return {"error": "Order not placed"}
        except Exception as e:
            log_error(f"❌ execute() виняток: {e}")
            return {"error": str(e)}

    def close_position(self):
        """
        ❌ Закриває позицію на біржі через Market ордер з ретраями
        """
        try:
            MAX_RETRIES = 3
            close_side = "Sell" if self.position_side == "LONG" else "Buy"
            symbol_clean = self.symbol.split("_")[0]

            for attempt in range(1, MAX_RETRIES + 1):
                log_message(f"🔁 [close_position] Спроба {attempt}/{MAX_RETRIES} закрити {symbol_clean}")

                response = bybit.get_positions(category="linear", symbol=symbol_clean, positionSide=self.position_side)
                positions = response.get("result", {}).get("list", [])
                current_qty = 0.0

                for pos in positions:
                    if pos.get("symbol") == symbol_clean:
                        size = float(pos.get("size", 0))
                        if size > 0:
                            current_qty = size
                            break

                if current_qty <= 0:
                    log_message(f"⚠️ [close_position] Немає відкритої позиції для {symbol_clean} (спроба {attempt})")
                    time.sleep(1)
                    continue

                # 🧮 Якщо передано amount_to_use — використовуємо його, інакше закриваємо весь обсяг
                target_qty = self.amount_to_use if self.amount_to_use else current_qty
                rounded_qty = round_qty_bybit(symbol_clean, target_qty)

                response = bybit.place_order(
                    category="linear",
                    symbol=symbol_clean,
                    side=close_side,  # ✅ "Sell" для LONG, "Buy" для SHORT
                    positionSide=self.position_side,
                    orderType="Market",
                    qty=str(rounded_qty),
                    reduceOnly=True,
                    closeOnTrigger=True
                )

                if response.get("retCode") == 0:
                    log_message(f"✅ Позиція {symbol_clean} закрита: {response['result'].get('orderId', '?')}")
                    return True
                else:
                    log_error(f"❌ [close_position] Помилка від Bybit: {response}")
                    time.sleep(1)

            log_error(f"❌ [close_position] Не вдалося закрити {symbol_clean} після {MAX_RETRIES} спроб")
            return False

        except Exception as e:
            log_error(f"❌ [close_position] Виняток: {e}")
            return False

    def set_safe_leverage(self):
        """
        🔧 Встановлює безпечне плече для символу:
        - якщо self.leverage підтримується → використовує його
        - якщо ні → виставляє min або max з біржі
        """
        try:
            response = bybit.get_instruments_info(category="linear", symbol=self.symbol)
            symbols_info = response.get("result", {}).get("list", [])

            if not symbols_info:
                log_error(f"⚠️ Не вдалося отримати info для {self.symbol}, використовую дефолтне плече (10x)")
                return

            leverage_filter = symbols_info[0].get("leverageFilter", {})
            min_leverage = int(float(leverage_filter.get("minLeverage", 1)))
            max_leverage = int(float(leverage_filter.get("maxLeverage", 100)))

            if self.leverage > max_leverage:
                log_message(f"⚠️ Плече {self.leverage}x > max {max_leverage}x → встановлюю max")
                safe_leverage = max_leverage
            elif self.leverage < min_leverage:
                log_message(f"⚠️ Плече {self.leverage}x < min {min_leverage}x → встановлюю min")
                safe_leverage = min_leverage
            else:
                safe_leverage = self.leverage

            result = bybit.set_leverage(
                 category="linear",
                symbol=self.symbol,
                leverage=safe_leverage
            )

            if result.get("retCode") == 0:
                log_message(f"✅ Плече {safe_leverage}x встановлено для {self.symbol}")
            else:
                log_error(f"❌ Не вдалося встановити плече: {result}")

        except Exception as e:
            log_error(f"❌ set_safe_leverage помилка для {self.symbol}: {e}")
            log_message("⚠️ Використовую плече за замовчуванням біржі (ймовірно 10x)")
