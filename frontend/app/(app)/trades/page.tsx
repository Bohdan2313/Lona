"use client";

import useSWR from "swr";
import { OpenTradesTable } from "@/components/dashboard/open-trades-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { mockTrades } from "@/lib/mock-data";
import { apiGet } from "@/lib/api";
import type { TradesResponse } from "@/types";

const fetcher = (path: string) => apiGet(path);

export default function TradesPage() {
  const { data } = useSWR<TradesResponse>("/trades/open", fetcher, {
    fallbackData: mockTrades,
    refreshInterval: 15000,
  });

  const trades = data?.positions ?? data?.trades ?? mockTrades.positions;
  const longCount = trades.filter((trade) => trade.side.toUpperCase() === "LONG").length;
  const shortCount = trades.length - longCount;

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.4em] text-sky-300">Trades</p>
        <h1 className="text-3xl font-semibold text-slate-100">Live positions</h1>
        <p className="text-sm text-slate-400">
          Inspect open contracts, leverage envelopes, and exposure split across directions.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Total positions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-100">{trades.length}</p>
            <p className="text-xs text-slate-500">Currently orchestrated by LonaMind</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Long exposure</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-emerald-300">{longCount}</p>
            <p className="text-xs text-slate-500">Directional bias seeking upside momentum</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Short exposure</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-rose-300">{shortCount}</p>
            <p className="text-xs text-slate-500">Downside hedges or conviction shorts</p>
          </CardContent>
        </Card>
      </div>

      <OpenTradesTable trades={trades} />
    </div>
  );
}
