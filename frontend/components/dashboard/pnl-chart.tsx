"use client";

import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts";
import type { PnlPoint } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function formatTimestamp(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function PnlChart({ series }: { series: PnlPoint[] }) {
  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle className="text-xl">Performance drift</CardTitle>
      </CardHeader>
      <CardContent className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={series} margin={{ left: 0, right: 0, top: 16, bottom: 0 }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.8} />
                <stop offset="100%" stopColor="#0f172a" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="timestamp" tickFormatter={formatTimestamp} stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={{
                background: "rgba(15,23,42,0.95)",
                border: "1px solid rgba(56,189,248,0.35)",
                borderRadius: 16,
                color: "#e2e8f0",
                fontSize: 12,
              }}
              formatter={(value: number) => [`${value.toFixed(2)}%`, "PnL"]}
              labelFormatter={(value) => formatTimestamp(value as string)}
            />
            <Area type="monotone" dataKey="pnl" stroke="#38bdf8" strokeWidth={2} fill="url(#pnlGradient)" />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
