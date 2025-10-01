"use client";

import { AreaChart, Area, ResponsiveContainer, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

interface PnlPoint {
  timestamp: string;
  pnl: number;
}

export default function PnlChart({ series }: { series: PnlPoint[] }) {
  return (
    <div className="card" style={{ height: 320 }}>
      <h3 style={{ marginTop: 0 }}>PnL Trend</h3>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 20, left: 0, right: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="pnl" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis dataKey="timestamp" tickFormatter={(value) => value.slice(5, 10)} stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(148,163,184,0.3)" }} />
          <Area type="monotone" dataKey="pnl" stroke="#38bdf8" strokeWidth={2} fill="url(#pnl)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
