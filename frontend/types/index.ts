export interface BotStatus {
  running: boolean;
  mode: string;
  started_at?: string;
  last_heartbeat?: string;
  message?: string;
}

export interface TradeRecord {
  trade_id: string;
  symbol: string;
  side: string;
  entry_price: number;
  quantity: number;
  leverage?: number;
  pnl_percent?: number;
  status?: string;
  opened_at?: string;
}

export interface TradesResponse {
  trades: TradeRecord[];
}

export type ConfigPayload = Record<string, any>;

export interface ConditionPayload {
  mode?: string;
  long?: Record<string, any>;
  short?: Record<string, any>;
  fasttrack?: Record<string, any>;
  regime_bonus?: number;
  weights?: Record<string, any>;
  decision_delta?: number;
  trend_alignment?: Record<string, any>;
  fallback?: string;
}
