export type BotStatus = {
  active: boolean;
  last_heartbeat?: string;
  version?: string;
  latency_ms?: number;
};

export type OpenTrade = {
  id: string;
  symbol: string;
  side: "LONG" | "SHORT" | string;
  entry_price: number;
  leverage: number;
  quantity: number;
  pnl_percent: number;
  opened_at?: string;
};

export type TradesResponse = {
  positions?: OpenTrade[];
  trades?: OpenTrade[];
};

export type SmartAverageConfig = {
  enabled: boolean;
  leverage: number;
  base_margin: number;
  max_adds: number;
  dca_step_pct: number;
  dca_mode: string;
  dca_factor: number;
  tp_from_avg_pct: number;
  alt_tp_from_avg_pct: number;
  max_margin_per_trade: number;
  min_liq_buffer: number;
  atr_pause_pct: number;
  trend_flip_cut_pct: number;
  cooldown_min: number;
  anchor: string;
};

export type TradeConfig = {
  DESIRED_ACTIVE_TRADES: number;
  MAX_LONG_TRADES: number;
  MAX_SHORT_TRADES: number;
  ACCOUNT_SAFETY_BUFFER_PCT: number;
  ACCOUNT_MIN_FREE_USDT: number;
  USE_DYNAMIC_SYMBOLS: boolean;
  GET_TOP_SYMBOLS_CONFIG: {
    min_volume: number;
    limit: number;
  };
  MAX_ACTIVE_TRADES: number;
  DRY_RUN: boolean;
  USE_MANUAL_BALANCE: boolean;
  MANUAL_BALANCE: number;
  USE_MANUAL_LEVERAGE: boolean;
  MANUAL_LEVERAGE: number;
  USE_EXCHANGE_TP: boolean;
  TP_USE_IOC: boolean;
  TP_EPSILON: number;
  SMART_AVG: SmartAverageConfig;
};

export type IndicatorCondition = [string, string];
export type IndicatorPair = [IndicatorCondition, IndicatorCondition];

export type ConditionSet = {
  core: IndicatorCondition[];
  pairs: IndicatorPair[];
  threshold?: number;
  anti_filters?: Record<string, unknown>;
};

export type FastTrackConfig = {
  enable: boolean;
  min_cores: number;
  min_pairs: number;
  min_bars_in_state: number;
  allow_open_candle: boolean;
  min_bb_width: number;
  prox_hi: number;
  prox_lo: number;
};

export type TradeConditions = {
  mode: string;
  long: ConditionSet;
  short: ConditionSet;
  fasttrack?: FastTrackConfig;
  regime_bonus?: number;
  weights?: Record<string, number>;
  decision_delta?: number;
  trend_alignment?: Record<string, unknown>;
  fallback?: string;
};

export type PnlPoint = {
  timestamp: string;
  pnl: number;
};
