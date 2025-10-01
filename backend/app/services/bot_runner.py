"""Bot process orchestration utilities."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DRY_RUN, BYBIT_API_KEY, BYBIT_API_SECRET

REPO_ROOT = Path(__file__).resolve().parents[2]
BOT_ENTRYPOINT = REPO_ROOT / "run_llama_trading.py"


@dataclass
class RunnerState:
    running: bool = False
    mode: str = "mock"
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    message: Optional[str] = None
    process: Optional[subprocess.Popen] = field(default=None, repr=False)
    thread: Optional[threading.Thread] = field(default=None, repr=False)
    stop_event: Optional[threading.Event] = field(default=None, repr=False)


class BotRunner:
    """Controls the trading loop lifecycle in live or mock mode."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = RunnerState()
        self._mock_pnl = [0.0]

    # ------------------------------------------------------------------
    def _update_heartbeat(self, message: Optional[str] = None) -> None:
        with self._lock:
            self._state.last_heartbeat = datetime.utcnow()
            if message:
                self._state.message = message

    # ------------------------------------------------------------------
    def _mock_loop(self, stop_event: threading.Event) -> None:
        """Simple emulation loop that keeps the heartbeat fresh."""
        counter = 0
        while not stop_event.is_set():
            counter += 1
            pnl = self._mock_pnl[-1] + (0.2 if counter % 2 == 0 else -0.05)
            self._mock_pnl.append(round(pnl, 2))
            self._update_heartbeat(message=f"Mock heartbeat #{counter}")
            stop_event.wait(5)

    # ------------------------------------------------------------------
    def start(self) -> RunnerState:
        with self._lock:
            if self._state.running:
                return self._state

            self._state.started_at = datetime.utcnow()
            self._state.last_heartbeat = self._state.started_at

            live_mode = bool(BYBIT_API_KEY and BYBIT_API_SECRET)
            if live_mode:
                env = os.environ.copy()
                env.setdefault("PYTHONPATH", str(REPO_ROOT))
                env.setdefault("LONA_DRY_RUN", "1" if DRY_RUN else "0")
                process = subprocess.Popen(
                    ["python", str(BOT_ENTRYPOINT)],
                    cwd=str(REPO_ROOT),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._state.process = process
                self._state.mode = "live" if not DRY_RUN else "dry_run"
            else:
                stop_event = threading.Event()
                thread = threading.Thread(target=self._mock_loop, args=(stop_event,), daemon=True)
                thread.start()
                self._state.stop_event = stop_event
                self._state.thread = thread
                self._state.mode = "mock"

            self._state.running = True
            self._state.message = "Bot started"
            return self._state

    # ------------------------------------------------------------------
    def stop(self) -> RunnerState:
        with self._lock:
            if not self._state.running:
                return self._state

            if self._state.process:
                self._state.process.terminate()
                try:
                    self._state.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._state.process.kill()
                self._state.process = None

            if self._state.stop_event:
                self._state.stop_event.set()
                if self._state.thread:
                    self._state.thread.join(timeout=5)
                self._state.stop_event = None
                self._state.thread = None

            self._state.running = False
            self._state.message = "Bot stopped"
            return self._state

    # ------------------------------------------------------------------
    def status(self) -> RunnerState:
        with self._lock:
            return self._state

    # ------------------------------------------------------------------
    def pnl_series(self) -> list[dict[str, float]]:
        """Return mock PnL if we are in mock mode."""
        with self._lock:
            if self._state.mode == "mock":
                return [
                    {"timestamp": datetime.utcnow().isoformat(), "pnl": value}
                    for value in self._mock_pnl[-20:]
                ]
        return []


runner = BotRunner()
