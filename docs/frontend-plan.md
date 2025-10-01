# Frontend Page Plan

## Dashboard (`/`)
- Hero cards: bot status (mode, uptime), account balance (from config), DRY_RUN badge.
- Action buttons: Start/Stop bot (calls `/start_bot`, `/stop_bot`).
- Active trades table with sortable columns (symbol, side, entry, leverage, PnL%).
- Profit & Loss area chart pulling `/pnl_chart` data.

## Settings (`/settings`)
- Form sections grouped into *General*, *Capital Management*, *Smart Averaging (DCA)*.
- Input controls mapped to config keys: `DESIRED_ACTIVE_TRADES`, `MANUAL_BALANCE`, `MANUAL_LEVERAGE`, `SMART_AVG.*`.
- Save button triggers POST `/config`; include unsaved changes indicator.

## Conditions Editor (`/conditions`)
- Two-column layout: JSON editor with syntax highlight + helper panel listing available indicators (RSI, MACD, etc.).
- Live validation (ensure arrays of `[metric, value]`, numeric thresholds) before enabling save.
- Preview card shows computed summary (core hits, pair hits) using simulated payload.

## API Keys (`/keys`)
- Secure form with copy-to-clipboard instructions.
- Notes about DRY_RUN fallback when keys absent.
- Status badge that reads `/status` to show current runner mode.

## Auth (`/login`)
- Simple email/password form storing JWT/token in `localStorage` (placeholder until backend auth exists).
- Protect dashboard routes by checking token on client side.

## Shared components
- `TopBar` with navigation and status indicator.
- `Sidebar` for route navigation.
- `ConfigCard` reusable container for grouped settings.
- `TradesTable` with virtualization for large data sets.
- `PnLChart` wrapping `recharts` area chart.
