"use client";

interface Metric {
  label: string;
  value: string | number;
  description?: string;
}

export default function MetricGrid({ metrics }: { metrics: Metric[] }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
      {metrics.map((metric) => (
        <div key={metric.label} className="card" style={{ padding: 20 }}>
          <p style={{ margin: 0, fontSize: 12, letterSpacing: "0.1em", color: "#94a3b8" }}>{metric.label}</p>
          <h3 style={{ margin: "8px 0 0 0", fontSize: 28 }}>{metric.value}</h3>
          {metric.description && <p style={{ color: "#94a3b8", marginTop: 6 }}>{metric.description}</p>}
        </div>
      ))}
    </div>
  );
}
