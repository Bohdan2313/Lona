"use client";

import { useEffect, useState } from "react";
import LayoutShell from "../../components/LayoutShell";
import { apiGet, apiPost } from "../../lib/api";
import type { ConfigPayload } from "../../types";

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigPayload | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ConfigPayload>("/config").then(setConfig).catch((err) => setMessage(err.message));
  }, []);

  function updateField(path: string, value: any) {
    setConfig((prev) => {
      if (!prev) return prev;
      const next = { ...prev } as any;
      const segments = path.split(".");
      let cursor = next;
      for (let i = 0; i < segments.length - 1; i += 1) {
        const key = segments[i];
        cursor[key] = cursor[key] ?? {};
        cursor = cursor[key];
      }
      cursor[segments[segments.length - 1]] = value;
      return { ...next };
    });
  }

  async function save() {
    if (!config) return;
    setSaving(true);
    setMessage(null);
    try {
      await apiPost("/config", { data: config });
      setMessage("Configuration saved");
    } catch (err) {
      setMessage((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <LayoutShell>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Trading Parameters</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 16 }}>
          <div>
            <label>Desired active trades</label>
            <input
              type="number"
              value={config?.DESIRED_ACTIVE_TRADES ?? ""}
              onChange={(e) => updateField("DESIRED_ACTIVE_TRADES", Number(e.target.value))}
            />
          </div>
          <div>
            <label>Manual balance (USDT)</label>
            <input
              type="number"
              value={config?.MANUAL_BALANCE ?? ""}
              onChange={(e) => updateField("MANUAL_BALANCE", Number(e.target.value))}
            />
          </div>
          <div>
            <label>Manual leverage</label>
            <input
              type="number"
              value={config?.MANUAL_LEVERAGE ?? ""}
              onChange={(e) => updateField("MANUAL_LEVERAGE", Number(e.target.value))}
            />
          </div>
        </div>
        <h3>Smart Averaging</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 16 }}>
          <div>
            <label>DCA enabled</label>
            <select
              value={config?.SMART_AVG?.enabled ? "true" : "false"}
              onChange={(e) => updateField("SMART_AVG.enabled", e.target.value === "true")}
            >
              <option value="true">True</option>
              <option value="false">False</option>
            </select>
          </div>
          <div>
            <label>DCA step %</label>
            <input
              type="number"
              step="0.001"
              value={config?.SMART_AVG?.dca_step_pct ?? ""}
              onChange={(e) => updateField("SMART_AVG.dca_step_pct", Number(e.target.value))}
            />
          </div>
          <div>
            <label>TP from average %</label>
            <input
              type="number"
              step="0.001"
              value={config?.SMART_AVG?.tp_from_avg_pct ?? ""}
              onChange={(e) => updateField("SMART_AVG.tp_from_avg_pct", Number(e.target.value))}
            />
          </div>
        </div>
        <button className="primary" style={{ marginTop: 24 }} disabled={saving} onClick={save}>
          {saving ? "Saving..." : "Save changes"}
        </button>
        {message && <p style={{ marginTop: 16, color: "#38bdf8" }}>{message}</p>}
      </div>
    </LayoutShell>
  );
}
