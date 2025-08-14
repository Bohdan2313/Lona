import os
import time
import joblib
import numpy as np
import pandas as pd
from keras.models import Sequential
from keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from dotenv import load_dotenv
from utils.get_klines_bybit import get_klines_clean_bybit
from utils.logger import log_message
from utils.tools import get_all_usdt_pairs
import tensorflow as tf
from config import SKIP_1000_TOKENS  # ✅ новий прапор

# Завантаження .env
load_dotenv()

# Фіксація сидів
np.random.seed(42)
tf.random.set_seed(42)

LOOKBACK = 60
PREDICT_SHIFT = 12

def prepare_data(symbol, interval="1h"):
    df = get_klines_clean_bybit(symbol, interval=interval, limit=200)
    if df is None or len(df) < LOOKBACK + PREDICT_SHIFT + 1:
        log_message(f"⚠️ Недостатньо даних для {symbol}")
        return None

    df["hlc_avg"] = (df["high"] + df["low"] + df["close"]) / 3
    df = df[["hlc_avg", "volume"]].copy()
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(df)

    X, y = [], []
    for i in range(LOOKBACK, len(scaled) - PREDICT_SHIFT):
        X_window = scaled[i - LOOKBACK:i]
        future_price = df["hlc_avg"].iloc[i + PREDICT_SHIFT]
        current_price = df["hlc_avg"].iloc[i]
        pct_change = (future_price - current_price) / current_price
        X.append(X_window)
        y.append(pct_change)

    return np.array(X), np.array(y), scaler

def train_lstm(symbol):
    result = prepare_data(symbol)
    if result is None:
        return

    X, y, scaler = result
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = Sequential()
    model.add(LSTM(64, return_sequences=False, input_shape=(X.shape[1], X.shape[2])))
    model.add(Dropout(0.3))
    model.add(Dense(1))
    model.compile(optimizer="adam", loss="mse")

    start_time = time.time()
    history = model.fit(X_train, y_train, epochs=40, batch_size=16, verbose=0, validation_data=(X_test, y_test))
    duration = time.time() - start_time

    os.makedirs("models", exist_ok=True)
    model.save(f"models/lstm_{symbol}.keras")  # ✅ новий формат
    joblib.dump(scaler, f"models/scaler_{symbol}.pkl")

    val_loss = history.history["val_loss"][-1]
    log_message(f"✅ [{symbol}] Модель навчена за {duration:.2f} сек. Val loss: {val_loss:.6f}")

if __name__ == "__main__":
    symbols = get_all_usdt_pairs(min_volume_usdt=100000)
    if SKIP_1000_TOKENS:
        symbols = [s for s in symbols if not s.startswith("1000")]
        log_message(f"🧹 Пропущено токени з префіксом 1000*, залишилось {len(symbols)} монет")

    log_message(f"🧠 Початок навчання LSTM для {len(symbols)} монет")

    for i, symbol in enumerate(symbols, 1):
        log_message(f"🔄 {i}/{len(symbols)} → Навчання {symbol}")
        train_lstm(symbol)
