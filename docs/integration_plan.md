# Backend ↔ Frontend Integration Plan

## 1. FastAPI surface
| Endpoint | Method | Purpose | Request | Response |
|----------|--------|---------|---------|----------|
|`/status`|GET|Runtime state of bot runner (running flag, mode, timestamps).|—|`BotStatus` JSON.| 
|`/start_bot`|POST|Start subprocess/thread for trading loop (live if keys, mock otherwise).|—|`BotStatus` snapshot.| 
|`/stop_bot`|POST|Gracefully terminates subprocess or mock loop.|—|`BotStatus` snapshot.| 
|`/config`|GET|Fetch merged UI configuration for dashboard sliders.|—|Full config dict.| 
|`/config`|POST|Persist edited configuration coming from Settings UI.|`{ "data": {...} }`|Updated dict.| 
|`/open_trades`|GET|Expose normalised active trades for dashboard table.|—|`{ "trades": [...] }`| 
|`/pnl_chart`|GET|Return mock/live PnL cumulative series for charting.|—|`{ "series": [...] }`| 
|`/conditions`|GET|Retrieve current custom SON conditions.|—|`ConditionPayload`.| 
|`/conditions`|POST|Overwrite custom condition JSON from editor.|`ConditionPayload`|Saved payload.| 
|`/keys`|POST|Store Bybit API keys (current .env based placeholder).|`APIKeys`|`{"status":"saved"}`|

## 2. Frontend wiring
- **Dashboard page** uses `/status`, `/open_trades`, `/pnl_chart` (poll every 10s for status, 30s for analytics). 
- **Settings page** fetches `/config` on mount, posts updates on save; leverages schema hints from config defaults for form controls.
- **Conditions editor** loads `/conditions`, allows JSON diff editing with validation prior to POST.
- **API Keys page** posts to `/keys` and surfaces runner mode (live/mock) depending on `/status`.
- **Auth scaffold** protects routes client-side (email/pass placeholder until multi-user is ready).

## 3. Bot orchestration
1. Frontend `Start` button → POST `/start_bot`.
2. Backend `BotRunner` decides between subprocess vs mock mode and tracks state for `/status`.
3. `Stop` button → POST `/stop_bot`; API ensures subprocess termination and resets heartbeat.
4. In live mode the subprocess executes `run_llama_trading.py`; in mock mode heartbeat increments and mock PnL is produced for analytics endpoint.

## 4. Config propagation lifecycle
1. On login, Settings UI loads `/config` and populates controls (balance, leverage, DCA, etc.).
2. User edits values → POST `/config` to persist. FastAPI writes to `config/config_ui.json` via shared helper.
3. Trading modules (which import `config.UI`) automatically read the updated file on next bot restart.

## 5. Custom conditions editing lifecycle
1. Conditions editor fetches `/conditions` (parsed JSON model) and renders structured editor (core pairs, thresholds, anti-filters, fasttrack).
2. Submit posts JSON back; backend writes to `config/custom_conditions.json`. `ai.check_trade_conditions` picks up changes after reload (optionally add hot-reload hook in future).

## 6. Testing & automation
- `pytest` suite covers config persistence, condition IO, custom rule scoring, and API smoke tests.
- `scripts/run_api.sh` launches FastAPI via uvicorn.
- `scripts/run_bot.sh` executes trading pipeline (subprocess or mock).
- `scripts/run_tests.sh` wraps the pytest invocation.
- Dockerfile builds Python backend with Uvicorn entrypoint and exposes port 8000.

## 7. Future extensions
- Persist user accounts & keys in database (Supabase/Auth.js) once multi-tenant support is prioritised.
- Replace `.env` key storage with Secrets manager (Vault) or encrypted storage.
- Stream telemetry via WebSocket channel for near real-time dashboard updates.
