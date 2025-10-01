from __future__ import annotations

import pytest

pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import bot_runner


def test_status_endpoint(monkeypatch):
    client = TestClient(app)

    def fake_status():
        state = bot_runner.RunnerState()
        state.running = True
        state.mode = "mock"
        return state

    monkeypatch.setattr(bot_runner.runner, "status", fake_status)

    response = client.get("/status")
    assert response.status_code == 200
    assert response.json()["running"] is True


def test_open_trades_endpoint(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "backend.app.services.trades.load_open_trades",
        lambda: [
            {
                "trade_id": "t1",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 100.0,
                "quantity": 1.0,
            }
        ],
    )

    response = client.get("/open_trades")
    assert response.status_code == 200
    data = response.json()
    assert data["trades"][0]["symbol"] == "BTCUSDT"
