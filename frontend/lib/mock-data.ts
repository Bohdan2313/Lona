import { BotStatus, TradeConditions, TradeConfig, TradesResponse, PnlPoint } from "@/types";

export const mockStatus: BotStatus = {
  active: true,
  last_heartbeat: new Date().toISOString(),
  version: "1.4.2",
  latency_ms: 124,
};

export const mockTrades: TradesResponse = {
  positions: [
    {
      id: "1",
      symbol: "BTCUSDT",
      side: "LONG",
      entry_price: 60542.4,
      leverage: 5,
      quantity: 0.85,
      pnl_percent: 3.8,
      opened_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    },
    {
      id: "2",
      symbol: "ETHUSDT",
      side: "SHORT",
      entry_price: 3220.25,
      leverage: 7,
      quantity: 12,
      pnl_percent: -0.7,
      opened_at: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
    },
  ],
};

export const mockConfig: TradeConfig = {
  DESIRED_ACTIVE_TRADES: 5,
  MAX_LONG_TRADES: 4,
  MAX_SHORT_TRADES: 1,
  ACCOUNT_SAFETY_BUFFER_PCT: 0.001,
  ACCOUNT_MIN_FREE_USDT: 0,
  USE_DYNAMIC_SYMBOLS: true,
  GET_TOP_SYMBOLS_CONFIG: { min_volume: 2000000, limit: 20 },
  MAX_ACTIVE_TRADES: 5,
  DRY_RUN: false,
  USE_MANUAL_BALANCE: true,
  MANUAL_BALANCE: 32,
  USE_MANUAL_LEVERAGE: true,
  MANUAL_LEVERAGE: 5,
  USE_EXCHANGE_TP: false,
  TP_USE_IOC: true,
  TP_EPSILON: 0.0007,
  SMART_AVG: {
    enabled: true,
    leverage: 5,
    base_margin: 32,
    max_adds: 30,
    dca_step_pct: 0.025,
    dca_mode: "equal",
    dca_factor: 1.3,
    tp_from_avg_pct: 0.012,
    alt_tp_from_avg_pct: 0.012,
    max_margin_per_trade: 1800,
    min_liq_buffer: 0,
    atr_pause_pct: 999,
    trend_flip_cut_pct: 0.01,
    cooldown_min: 25,
    anchor: "ladder",
  },
};

export const mockConditions: TradeConditions = {
  mode: "CUSTOM",
  long: {
    core: [
      ["macd_crossed", "bullish_cross"],
      ["macd_hist_direction", "up"],
      ["rsi_trend", "up"],
      ["microtrend_5m", "bullish"],
    ],
    pairs: [
      [["support_position", "near_support"], ["microtrend_1m", "bullish"]],
      [["boll_bucket", "<=30"], ["rsi_bucket", "<=30"]],
    ],
    threshold: 9.5,
    anti_filters: {
      require_closed_candle: true,
      hysteresis_bars: 1,
      min_pair_hits: 2,
    },
  },
  short: {
    core: [
      ["macd_crossed", "bearish_cross"],
      ["macd_hist_direction", "down"],
      ["rsi_trend", "down"],
      ["microtrend_5m", "bearish"],
    ],
    pairs: [
      [["support_position", "near_resistance"], ["microtrend_1m", "bearish"]],
      [["boll_bucket", ">70"], ["rsi_bucket", ">70"]],
    ],
    threshold: 9.5,
    anti_filters: {
      require_closed_candle: true,
      hysteresis_bars: 1,
      min_pair_hits: 2,
    },
  },
  fasttrack: {
    enable: true,
    min_cores: 2,
    min_pairs: 1,
    min_bars_in_state: 1,
    allow_open_candle: true,
    min_bb_width: 0.003,
    prox_hi: 0.98,
    prox_lo: 0.98,
  },
  regime_bonus: 0.8,
  weights: { core: 3.5, pair: 1.6 },
  decision_delta: 0.5,
  fallback: "default",
};

export const mockPnl: PnlPoint[] = Array.from({ length: 10 }, (_, index) => ({
  timestamp: new Date(Date.now() - (9 - index) * 60 * 60 * 1000).toISOString(),
  pnl: Math.round((Math.sin(index / 2) * 4 + index) * 100) / 100,
}));
