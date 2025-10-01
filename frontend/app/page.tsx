"use client";

import useSWR from "swr";
import LayoutShell from "../components/LayoutShell";
import DashboardHeader from "../components/DashboardHeader";
import BotControls from "../components/BotControls";
import MetricGrid from "../components/MetricGrid";
import TradesTable from "../components/TradesTable";
import PnlChart from "../components/PnlChart";
import { apiGet } from "../lib/api";
import type { BotStatus, TradesResponse } from "../types";

type PnlResponse = { series: { timestamp: string; pnl: number }[] };

const fetcher = (path: string) => apiGet(path);

export default function DashboardPage() {
  const { data: status, mutate: mutateStatus } = useSWR<BotStatus>("/status", fetcher, {
    refreshInterval: 10000
  });
  const { data: trades } = useSWR<TradesResponse>("/open_trades", fetcher, {
    refreshInterval: 15000
  });
  const { data: pnl } = useSWR<PnlResponse>("/pnl_chart", fetcher, {
    refreshInterval: 30000
  });

  const metrics = [
    {
      label: "Last heartbeat",
      value: status?.last_heartbeat ? new Date(status.last_heartbeat).toLocaleTimeString() : "—"
    },
    {
      label: "Runner mode",
      value: status?.mode?.toUpperCase() ?? "MOCK"
    },
    {
      label: "Trades active",
      value: trades?.trades.length ?? 0,
      description: "Open positions being tracked"
    }
  ];

  return (
    <LayoutShell>
      <DashboardHeader status={status} />
      <BotControls onUpdate={(next) => mutateStatus(next, { revalidate: true })} />
      <MetricGrid metrics={metrics} />
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
        <PnlChart series={pnl?.series ?? []} />
        <TradesTable trades={trades?.trades ?? []} />
      </div>
    </LayoutShell>
  );
}
