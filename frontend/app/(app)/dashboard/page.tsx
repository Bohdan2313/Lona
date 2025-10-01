"use client";

import useSWR from "swr";
import { BotStatusCard } from "@/components/dashboard/bot-status-card";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { OpenTradesTable } from "@/components/dashboard/open-trades-table";
import { PnlChart } from "@/components/dashboard/pnl-chart";
import { mockConditions, mockConfig, mockPnl, mockStatus, mockTrades } from "@/lib/mock-data";
import { apiGet } from "@/lib/api";
import type { BotStatus, TradesResponse, PnlPoint } from "@/types";

const fetcher = (path: string) => apiGet(path);

export default function DashboardPage() {
  const { data: status } = useSWR<BotStatus>("/status/bot", fetcher, {
    fallbackData: mockStatus,
    refreshInterval: 10000,
  });

  const { data: trades } = useSWR<TradesResponse>("/trades/open", fetcher, {
    fallbackData: mockTrades,
    refreshInterval: 15000,
  });

  const { data: pnl } = useSWR<PnlPoint[]>("/analytics/pnl", fetcher, {
    fallbackData: mockPnl,
    refreshInterval: 20000,
  });

  const openPositions = trades?.positions ?? trades?.trades ?? mockTrades.positions;

  const metrics = [
    {
      label: "Open positions",
      value: String(openPositions.length ?? 0),
      description: "Live derivatives currently managed",
    },
    {
      label: "Desired concurrency",
      value: `${mockConfig.DESIRED_ACTIVE_TRADES}`,
      description: "Configured ceiling for simultaneous bots",
    },
    {
      label: "Strategy mode",
      value: mockConditions.mode,
      description: "Conditions module currently orchestrating",
    },
  ];

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.4em] text-sky-300">Control center</p>
        <h1 className="text-3xl font-semibold text-slate-100">Mission dashboard</h1>
        <p className="text-sm text-slate-400">
          Monitor heartbeat, PnL drift, and live exposures for the AI-Lona execution engine.
        </p>
      </div>

      <BotStatusCard status={status ?? mockStatus} />

      <KpiGrid metrics={metrics} />

      <div className="grid gap-6 lg:grid-cols-3">
        <PnlChart series={pnl ?? mockPnl} />
        <div className="lg:col-span-1">
          <div className="flex items-center justify-between pb-4">
            <h2 className="text-lg font-semibold text-slate-100">Open positions</h2>
            <span className="text-xs uppercase tracking-[0.3em] text-slate-500">LIVE FEED</span>
          </div>
          <OpenTradesTable trades={openPositions} />
        </div>
      </div>
    </div>
  );
}
