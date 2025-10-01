import { Card, CardContent } from "@/components/ui/card";

export function KpiGrid({ metrics }: { metrics: { label: string; value: string; description?: string }[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {metrics.map((metric) => (
        <Card key={metric.label} className="border-slate-800/80 bg-slate-950/60">
          <CardContent className="space-y-2">
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{metric.label}</p>
            <p className="text-2xl font-semibold text-slate-100">{metric.value}</p>
            {metric.description && <p className="text-xs text-slate-400">{metric.description}</p>}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
