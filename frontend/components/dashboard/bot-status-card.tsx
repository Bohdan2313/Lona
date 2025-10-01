import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BotStatus } from "@/types";

export function BotStatusCard({ status }: { status: BotStatus }) {
  const heartbeat = status.last_heartbeat ? new Date(status.last_heartbeat).toLocaleTimeString() : "—";
  return (
    <Card className="relative overflow-hidden">
      <div className="absolute right-6 top-6 h-28 w-28 rounded-full bg-sky-500/10 blur-3xl" />
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-xl">
          Bot orchestration
          <Badge className={status.active ? "border-emerald-400/60 bg-emerald-500/15 text-emerald-200" : "border-rose-500/50 bg-rose-500/10 text-rose-200"}>
            {status.active ? "Active" : "Idle"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4 text-sm text-slate-300 sm:grid-cols-3">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Last heartbeat</p>
          <p className="text-base font-medium text-slate-100">{heartbeat}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Version</p>
          <p className="text-base font-medium text-slate-100">{status.version ?? "v-next"}</p>
        </div>
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Latency</p>
          <p className="text-base font-medium text-slate-100">{status.latency_ms ? `${status.latency_ms} ms` : "—"}</p>
        </div>
      </CardContent>
    </Card>
  );
}
