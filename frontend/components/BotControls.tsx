"use client";

import { useState, useTransition } from "react";
import type { BotStatus } from "../types";
import { apiPost } from "../lib/api";

export default function BotControls({ onUpdate }: { onUpdate?: (status: BotStatus) => void }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function trigger(endpoint: "/start_bot" | "/stop_bot") {
    setError(null);
    startTransition(async () => {
      try {
        const status = await apiPost<BotStatus>(endpoint, {});
        onUpdate?.(status);
      } catch (err) {
        setError((err as Error).message);
      }
    });
  }

  return (
    <div className="card" style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <button className="primary" disabled={pending} onClick={() => trigger("/start_bot")}>
        Start Bot
      </button>
      <button
        className="primary"
        style={{ background: "linear-gradient(135deg,#f87171,#f97316)", color: "#0f172a" }}
        disabled={pending}
        onClick={() => trigger("/stop_bot")}
      >
        Stop Bot
      </button>
      {error && <span style={{ color: "#f97316" }}>{error}</span>}
    </div>
  );
}
