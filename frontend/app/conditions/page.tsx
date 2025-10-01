"use client";

import { useEffect, useState } from "react";
import LayoutShell from "../../components/LayoutShell";
import { apiGet, apiPost } from "../../lib/api";
import type { ConditionPayload } from "../../types";

function formatPayload(payload: ConditionPayload | null): string {
  return JSON.stringify(payload, null, 2);
}

export default function ConditionsPage() {
  const [value, setValue] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiGet<ConditionPayload>("/conditions")
      .then((data) => setValue(formatPayload(data)))
      .catch((err) => setError(err.message));
  }, []);

  async function save() {
    try {
      setError(null);
      const parsed = JSON.parse(value) as ConditionPayload;
      setSaving(true);
      await apiPost("/conditions", parsed);
      setError("Conditions saved");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <LayoutShell>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Custom Trade Conditions</h2>
        <p style={{ color: "#94a3b8" }}>
          Edit SON overrides for long/short logic. Ensure arrays follow the `["metric", "value"]` convention.
        </p>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={20}
          spellCheck={false}
          style={{ fontFamily: "monospace", fontSize: 13 }}
        />
        <button className="primary" style={{ marginTop: 24 }} disabled={saving} onClick={save}>
          {saving ? "Saving..." : "Save conditions"}
        </button>
        {error && <p style={{ marginTop: 12, color: error.includes("saved") ? "#38bdf8" : "#f97316" }}>{error}</p>}
      </div>
    </LayoutShell>
  );
}
