from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import subprocess
from fastapi.responses import JSONResponse
import psutil
from fastapi import Query 


app = FastAPI()

# Дозволяємо фронтенду звертатись до бекенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # У продакшні вказати конкретно frontend адресу
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== ROOT ==========
@app.get("/")
def root():
    return {"message": "Welcome to AI-Lona SaaS Backend 🎯"}

# ========== СТАТУС БОТА ==========
@app.get("/status")
def get_status():
    return {
        "bot_status": "active",
        "daily_profit": 12.4,
        "telegram": True
    }

# ========== МОДЕЛЬ І ЗБЕРЕЖЕННЯ КЛЮЧІВ ==========
class APIKeys(BaseModel):
    api_key: str
    api_secret: str

@app.post("/save_keys")
async def save_keys(keys: APIKeys):
    try:
        save_path = "user_api_keys.json"
        with open(save_path, "w") as f:
            json.dump(keys.dict(), f)
        return {"status": "success", "message": "API ключі збережено ✅"}
    except Exception as e:
        return {"status": "error", "message": f"Помилка: {str(e)}"}


@app.get("/keys_status")
def keys_status():
    try:
        with open("user_api_keys.json", "r") as f:
            data = json.load(f)
            if data.get("api_key") and data.get("api_secret"):
                return {"status": "saved"}
    except:
        pass
    return {"status": "not_saved"}



@app.post("/start_bot")
def start_bot():
    try:
        # Можна запускати що завгодно: python-файл, sh-скрипт, etc.
        subprocess.Popen(["python", "bot.py"])
        return JSONResponse(content={"status": "success", "message": "Бот запущено ✅"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})



@app.post("/stop_bot")
def stop_bot():
    try:
        stopped = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'bot.py' in proc.info['cmdline']:
                proc.kill()
                stopped = True
        if stopped:
            return JSONResponse(content={"status": "success", "message": "Бота зупинено 🛑"})
        else:
            return JSONResponse(content={"status": "info", "message": "Бот не запущено"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.get("/is_bot_running")
def is_bot_running():
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if 'bot.py' in proc.info['cmdline']:
                return {"running": True}
        return {"running": False}
    except Exception as e:
        return {"error": str(e)}


@app.get("/open_trades")
def open_trades():
    try:
        with open("ActiveTradesSimple.json", "r") as f:
            trades = json.load(f)
            return {"trades": trades}
    except Exception as e:
        return {"trades": [], "error": str(e)}



@app.post("/close_trade")
def close_trade(symbol: str = Query(...)):
    try:
        # TODO: Тут встав справжню логіку закриття угоди
        print(f"[DEBUG] Закриваємо угоду для: {symbol}")
        return {"status": "success", "message": f"Угоду {symbol} закрито ✅"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/pnl_chart_data")
def pnl_chart_data():
    # Тимчасові фейкові дані
    return {
        "pnl": [
            {"date": "2024-07-01", "pnl": 2.3},
            {"date": "2024-07-02", "pnl": -1.1},
            {"date": "2024-07-03", "pnl": 4.5},
            {"date": "2024-07-04", "pnl": 0.0},
            {"date": "2024-07-05", "pnl": 3.7}
        ]
    }

