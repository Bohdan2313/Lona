import { format } from "date-fns";
import type { OpenTrade } from "@/types";
import { Table, TCell, TH, THead, TRow } from "@/components/ui/table";

export function OpenTradesTable({ trades }: { trades: OpenTrade[] }) {
  return (
    <Table>
      <THead>
        <TRow>
          <TH className="px-5 py-4">Symbol</TH>
          <TH>Side</TH>
          <TH>Entry</TH>
          <TH>Leverage</TH>
          <TH>Quantity</TH>
          <TH>PnL%</TH>
          <TH>Opened</TH>
        </TRow>
      </THead>
      <tbody>
        {trades.map((trade) => (
          <TRow key={trade.id} className="text-sm">
            <TCell className="font-semibold tracking-[0.2em] text-slate-200">{trade.symbol}</TCell>
            <TCell className={trade.side.toUpperCase() === "LONG" ? "text-emerald-300" : "text-rose-300"}>{trade.side}</TCell>
            <TCell>${trade.entry_price.toLocaleString()}</TCell>
            <TCell>{trade.leverage}x</TCell>
            <TCell>{trade.quantity}</TCell>
            <TCell className={trade.pnl_percent >= 0 ? "text-emerald-300" : "text-rose-300"}>
              {trade.pnl_percent.toFixed(2)}%
            </TCell>
            <TCell>{trade.opened_at ? format(new Date(trade.opened_at), "HH:mm") : "—"}</TCell>
          </TRow>
        ))}
        {trades.length === 0 && (
          <TRow>
            <TCell colSpan={7} className="py-6 text-center text-slate-500">
              No open positions at the moment.
            </TCell>
          </TRow>
        )}
      </tbody>
    </Table>
  );
}
