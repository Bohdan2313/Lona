"use client";

import type { TradeRecord } from "../types";

export default function TradesTable({ trades }: { trades: TradeRecord[] }) {
  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>Open Trades</h3>
        <span style={{ color: "#94a3b8" }}>{trades.length} active</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry</th>
              <th>Qty</th>
              <th>Leverage</th>
              <th>PnL %</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => (
              <tr key={trade.trade_id}>
                <td>{trade.symbol}</td>
                <td>{trade.side}</td>
                <td>{trade.entry_price.toFixed(2)}</td>
                <td>{trade.quantity}</td>
                <td>{trade.leverage ?? "—"}</td>
                <td>{trade.pnl_percent?.toFixed(2) ?? "—"}</td>
                <td>{trade.status ?? "open"}</td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: 32, color: "#94a3b8" }}>
                  No open trades
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
