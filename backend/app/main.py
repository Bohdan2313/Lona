"""FastAPI gateway that exposes trading bot controls to the SaaS frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.app.models import (
    APIKeys,
    BotStatus,
    ConditionPayload,
    ConfigPayload,
    TradesResponse,
)
from backend.app.services import analytics, bot_runner, conditions, config_store, trades

app = FastAPI(title="AI-Lona SaaS Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "Welcome to AI-Lona SaaS Backend"}


@app.get("/status", response_model=BotStatus)
def get_status() -> BotStatus:
    state = bot_runner.runner.status()
    return BotStatus(
        running=state.running,
        mode=state.mode,
        started_at=state.started_at,
        last_heartbeat=state.last_heartbeat,
        message=state.message,
    )


@app.post("/start_bot", response_model=BotStatus)
def start_bot() -> BotStatus:
    state = bot_runner.runner.start()
    return BotStatus(
        running=state.running,
        mode=state.mode,
        started_at=state.started_at,
        last_heartbeat=state.last_heartbeat,
        message=state.message,
    )


@app.post("/stop_bot", response_model=BotStatus)
def stop_bot() -> BotStatus:
    state = bot_runner.runner.stop()
    return BotStatus(
        running=state.running,
        mode=state.mode,
        started_at=state.started_at,
        last_heartbeat=state.last_heartbeat,
        message=state.message,
    )


@app.get("/config")
def get_config() -> Dict[str, Any]:
    return config_store.read_config()


@app.post("/config")
def update_config(payload: ConfigPayload) -> Dict[str, Any]:
    return config_store.write_config(payload.data)


@app.get("/open_trades", response_model=TradesResponse)
def open_trades() -> TradesResponse:
    records = trades.load_open_trades()
    return TradesResponse(trades=records)


@app.get("/pnl_chart")
def pnl_chart() -> Dict[str, Any]:
    return {"series": analytics.load_pnl_series()}


@app.get("/conditions", response_model=ConditionPayload)
def get_conditions() -> ConditionPayload:
    data = conditions.load_conditions()
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="Умови мають бути словником")
    return ConditionPayload(**data)


@app.post("/conditions", response_model=ConditionPayload)
def save_conditions(payload: ConditionPayload) -> ConditionPayload:
    data = payload.model_dump(exclude_none=True)
    saved = conditions.save_conditions(data)
    return ConditionPayload(**saved)


@app.post("/keys")
def save_api_keys(keys: APIKeys) -> Dict[str, str]:
    data = {"BYBIT_API_KEY": keys.api_key, "BYBIT_API_SECRET": keys.api_secret}
    # тимчасово зберігаємо у .env
    try:
        with open(".env", "w", encoding="utf-8") as fh:
            for key, value in data.items():
                fh.write(f"{key}={value}\n")
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"Не вдалося зберегти ключі: {exc}") from exc
    return {"status": "saved"}
