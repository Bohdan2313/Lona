"use client";

import { useState } from "react";
import LayoutShell from "../../components/LayoutShell";
import { apiPost } from "../../lib/api";

export default function KeysPage() {
  const [apiKey, setApiKey] = useState("");
  const [secret, setSecret] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit() {
    setPending(true);
    setStatus(null);
    try {
      await apiPost("/keys", { api_key: apiKey, api_secret: secret });
      setStatus("Keys saved to .env (restart backend to apply)");
      setApiKey("");
      setSecret("");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setPending(false);
    }
  }

  return (
    <LayoutShell>
      <div className="card" style={{ maxWidth: 480 }}>
        <h2 style={{ marginTop: 0 }}>API Credentials</h2>
        <p style={{ color: "#94a3b8" }}>
          Provide Bybit API keys. When omitted the platform stays in DRY_RUN mode using mock data.
        </p>
        <label>API Key</label>
        <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Bybit API key" />
        <label style={{ marginTop: 16 }}>API Secret</label>
        <input
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
          placeholder="Bybit API secret"
          type="password"
        />
        <button className="primary" style={{ marginTop: 24 }} disabled={pending} onClick={submit}>
          {pending ? "Saving..." : "Save keys"}
        </button>
        {status && <p style={{ marginTop: 12, color: "#38bdf8" }}>{status}</p>}
      </div>
    </LayoutShell>
  );
}
