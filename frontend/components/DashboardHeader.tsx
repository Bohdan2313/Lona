"use client";

import type { BotStatus } from "../types";

export default function DashboardHeader({ status }: { status?: BotStatus }) {
  const running = status?.running;
  const badgeColor = running ? "rgba(34,197,94,0.25)" : "rgba(244,63,94,0.25)";
  const badgeText = running ? "Running" : "Stopped";
  const subtitle = status?.mode ? status.mode.toUpperCase() : "MOCK";
  const startedAt = status?.started_at
    ? new Date(status.started_at).toLocaleString()
    : "—";
  return (
    <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 24 }}>AI-Lona Control Center</h2>
        <p style={{ marginTop: 8, color: "#94a3b8" }}>Mode: {subtitle} · Started: {startedAt}</p>
      </div>
      <span
        style={{
          padding: "8px 16px",
          borderRadius: 999,
          background: badgeColor,
          color: running ? "#4ade80" : "#f87171",
          fontWeight: 600
        }}
      >
        {badgeText}
      </span>
    </div>
  );
}
