import pandas as pd
import numpy as np

from dotenv import load_dotenv
import os
from utils.get_klines_bybit import get_klines_clean_bybit
from analysis.market import analyze_market
from predict_lstm import predict_lstm
from analysis.indicators import get_volatility
from utils.logger import log_message, log_error

from analysis.whales import get_whale_score


from config import bybit  # переконайся, що імпорт є

def risk_management(balance, symbol, market_type="futures", leverage=5):
    """📊 Оптимізоване динамічне управління капіталом"""
    try:
        df = get_klines_clean_bybit(symbol, limit=50)
        if df is None or df.empty:
            log_message(f"❌ {symbol} | Дані відсутні → Ризик за замовчуванням (5%)")
            return max(balance * 0.05, 10)

        for col in ["high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.dropna(inplace=True)
        if df.empty:
            log_message(f"❌ {symbol} | Дані NaN після обробки → Ризик за замовчуванням (5%)")
            return max(balance * 0.05, 10)

        # Волатильність і обʼєм
        volatility = np.mean(df["high"] - df["low"]) / df["close"].mean() * 100
        avg_volume = df["volume"].mean()
        log_message(f"📊 {symbol} | Волатильність: {volatility:.2f}%, Обʼєм: {avg_volume:.2f}")

        # Аналіз тренду і прогнозу
        analysis = analyze_market(symbol) or {}
        trend = analysis.get("trend", "neutral")
        lstm_prediction = predict_lstm(symbol) or 0
        log_message(f"📈 {symbol} | Тренд: {trend}, LSTM прогноз: {lstm_prediction:.2f}%")

        # Базовий ризик
        risk_percent = 0.1

        # Адаптація за ринком
        if volatility < 1.0 and avg_volume > 5_000_000:
            risk_percent += 0.05
            log_message("🟢 Низька волатильність + висока ліквідність → ризик +5%")
        elif volatility > 3.0 or avg_volume < 500_000:
            risk_percent -= 0.05
            log_message("🔴 Висока волатильність або низька ліквідність → ризик -5%")

        # LSTM прогноз
        if lstm_prediction > 0.5:
            risk_percent += 0.03
            log_message("📈 LSTM позитивний → ризик +3%")
        elif lstm_prediction < -0.5:
            risk_percent -= 0.03
            log_message("📉 LSTM негативний → ризик -3%")

        # Тренд
        if trend == "bullish":
            risk_percent += 0.03
            log_message("📈 Тренд bullish → ризик +3%")
        elif trend == "bearish":
            risk_percent -= 0.03
            log_message("📉 Тренд bearish → ризик -3%")

        # 🧾 Адаптація під фʼючерси (Bybit)
        if market_type == "futures":
            try:
                balances = bybit.get_wallet_balance(accountType="UNIFIED")
                usdt_balance = float(balances['result']['list'][0]['coin'][0]['walletBalance'])
                max_allowed = usdt_balance * leverage * 0.05
                adjusted_risk = min(risk_percent, max_allowed / balance)

                if adjusted_risk != risk_percent:
                    log_message(f"⚠️ Обмеження маржі → ризик обмежено {adjusted_risk*100:.2f}%")
                risk_percent = adjusted_risk

                if leverage > 5:
                    risk_percent *= 0.85
                    log_message("⚠️ Плече > 5 → ризик * 0.85")
                if leverage > 10:
                    risk_percent *= 0.7
                    log_message("⚠️ Плече > 10 → ризик * 0.7")
            except Exception as e:
                log_message(f"⚠️ {symbol} | Помилка перевірки маржі (Bybit): {e}")

        # Межі ризику
        risk_percent = max(0.02, min(risk_percent, 0.25))
        final_risk = round(balance * risk_percent, 2)

        log_message(f"💰 Фінальний ризик для {symbol}: {risk_percent*100:.2f}% → {final_risk:.2f} USDT")
        return final_risk

    except Exception as e:
        log_message(f"❌ risk_management(): {e}")
        return max(balance * 0.05, 10)

def calculate_amount_to_use(score, total_balance, leverage=30, risk_cap=0.25):
    """
    💡 Визначення розміру позиції на основі score, балансу і ризиків.
    - total_balance: баланс, який реально доступний (наприклад, 20 USDT)
    - leverage: множник для позиції (25x, 30x)
    - risk_cap: скільки максимум від балансу можна ризикнути (наприклад, 25%)
    """

    if score < 30:
        return 0

    # 💡 Формула — яка частка маржі дозволена
    if score < 50:
        margin_risk = total_balance * 0.01
    elif score < 70:
        margin_risk = total_balance * 0.03
    elif score < 90:
        margin_risk = total_balance * 0.07
    else:
        margin_risk = total_balance * 0.15

    # 🛡 Обмеження на ризик
    max_margin_allowed = total_balance * risk_cap
    final_margin = min(margin_risk, max_margin_allowed)

    # 📈 Розрахунок позиції з урахуванням плеча
    position_size = round(final_margin * leverage, 2)

    # 🧾 Мінімум Binance — 5 USDT (можна виставити свою межу)
    if position_size < 5:
        log_message(f"⚠️ Позиція ({position_size} USDT) нижче мінімуму — піднімаємо до 5 USDT")
        position_size = 5

    log_message(
        f"⚖️ Розмір позиції: {position_size} USDT | Маржа: {final_margin:.2f} USDT | "
        f"Score: {score} | Leverage: {leverage}x"
    )
    return position_size



def adjust_leverage_by_score(score):
    """📈 Динамічне плече на основі сили сигналу"""
    if score < 30:
        return 0
    elif score < 50:
        return 3
    elif score < 70:
        return 10
    elif score < 90:
        return 25
    else:
        return 50


def analyze_liquidity_risk(symbol):
    """
    🛡️ Аналіз ризику штучного пробиття рівнів і ліквідації.
    """
    try:
        market =get_klines_clean_bybit(symbol)
        whale_score = get_whale_score(symbol)
        volatility = get_volatility(symbol)

        support = market.get("support")
        resistance = market.get("resistance")
        current_price = market.get("price")

        # Груба логіка: якщо ціна дуже близька до підтримки/опору + whale активність → ризик ліквідації високий
        distance_to_support = abs(current_price - support) / current_price * 100 if support else None
        distance_to_resistance = abs(current_price - resistance) / current_price * 100 if resistance else None

        prompt = (
            f"Аналіз ризику ліквідації по {symbol}.\n"
            f"Поточна ціна: {current_price}\n"
            f"Підтримка: {support}\n"
            f"Опір: {resistance}\n"
            f"Відстань до підтримки: {round(distance_to_support, 2) if distance_to_support else 'N/A'}%\n"
            f"Відстань до опору: {round(distance_to_resistance, 2) if distance_to_resistance else 'N/A'}%\n"
            f"Волатильність: {volatility}\n"
            f"Whale-активність: {whale_score}\n\n"
            f"Чи є високий ризик штучного пробиття рівнів і ліквідації? Відповідай: 'yes' або 'no'."
        )

       
       

    except Exception as e:
        log_message(f"❌ Помилка аналізу ризику ліквідації: {e}")
        return False
    


def get_stop_loss(symbol):
    try:
        # Тестове значення або розрахунок
        return -10.0  # -10%
    except Exception as e:
        log_error(f"⚠️ Помилка get_stop_loss для {symbol}: {e}")
        return None

def get_take_profit(symbol):
    try:
        return 7.0  # +7%
    except Exception as e:
        log_error(f"⚠️ Помилка get_take_profit для {symbol}: {e}")
        return None

def get_trailing_info(symbol):
    try:
        return {
            "trailing_start": 5.0,  # % коли увімкнеться трейлінг
            "trailing_distance": 2.0  # % відступу
        }
    except Exception as e:
        log_error(f"⚠️ Помилка get_trailing_info для {symbol}: {e}")
        return None