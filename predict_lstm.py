import os
import json
import numpy as np
import joblib
from keras.models import load_model
from utils.get_klines_bybit import get_klines_clean_bybit
from utils.logger import log_message, log_error
from config import SKIP_1000_TOKENS  # ✅ новий прапор

LOOKBACK = 60

def predict_lstm(symbol):
    try:
        model_path = f"models/lstm_{symbol}.keras"  # ✅ новий формат
        scaler_path = f"models/scaler_{symbol}.pkl"

        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            log_message(f"⚠️ Немає моделі або scaler для {symbol}. Пропускаємо.")
            return None

        model = load_model(model_path)
        scaler = joblib.load(scaler_path)

        df = get_klines_clean_bybit(symbol, interval="1h", limit=150)
        if df is None or len(df) < LOOKBACK + 1:
            log_message(f"⚠️ Недостатньо даних для {symbol}")
            return None

        df["hlc_avg"] = (df["high"] + df["low"] + df["close"]) / 3
        df = df[["hlc_avg", "volume"]].copy()
        scaled = scaler.transform(df)

        last_seq = scaled[-LOOKBACK:]
        X_input = np.array(last_seq).reshape(1, LOOKBACK, 2)

        predicted_pct_change = model.predict(X_input)[0][0] * 100

        if abs(predicted_pct_change) > 20:
            log_message(f"⚠️ {symbol}: LSTM прогноз ±{predicted_pct_change:.2f}% — занадто екстремальний")
            return None

        log_message(f"📈 {symbol}: LSTM прогноз на 1 год: {predicted_pct_change:+.2f}%")
        return predicted_pct_change

    except Exception as e:
        log_error(f"❌ LSTM прогноз помилка для {symbol}: {e}")
        return None

if __name__ == "__main__":
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
    if SKIP_1000_TOKENS:
        symbols = [s for s in symbols if not s.startswith("1000")]
        log_message(f"🧹 Пропущено токени з префіксом 1000*, залишилось {len(symbols)} монет")

    results = {}
    for symbol in symbols:
        prediction = predict_lstm(symbol)
        if prediction is not None:
            results[symbol] = prediction

    with open("lstm_predictions.json", "w") as f:
        json.dump(results, f, indent=2)

    log_message("✅ Прогнози збережено у lstm_predictions.json")
