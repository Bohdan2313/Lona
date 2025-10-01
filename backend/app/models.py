"""Pydantic models shared across the FastAPI layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class APIKeys(BaseModel):
    api_key: str = Field(..., description="Bybit API key")
    api_secret: str = Field(..., description="Bybit API secret")


class ConfigPayload(BaseModel):
    data: Dict[str, Any]


class ConditionPayload(BaseModel):
    mode: Optional[str] = Field(None, description="Active ruleset mode")
    long: Optional[Dict[str, Any]] = None
    short: Optional[Dict[str, Any]] = None
    fasttrack: Optional[Dict[str, Any]] = None
    regime_bonus: Optional[float] = None
    weights: Optional[Dict[str, Any]] = None
    decision_delta: Optional[float] = None
    trend_alignment: Optional[Dict[str, Any]] = None
    fallback: Optional[str] = None


class BotStatus(BaseModel):
    running: bool
    mode: str
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    message: Optional[str] = None


class TradeRecord(BaseModel):
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    quantity: float
    leverage: Optional[float] = None
    opened_at: Optional[str] = None
    pnl_percent: Optional[float] = None
    status: Optional[str] = None


class TradesResponse(BaseModel):
    trades: List[TradeRecord]
