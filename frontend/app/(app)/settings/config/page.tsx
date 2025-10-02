"use client";

import { useEffect, useMemo, useState } from "react";

import { TradeConfigurationForm } from "@/components/settings/trade-configuration-form";
import { Button } from "@/components/ui/button";
import { mockConfig } from "@/lib/mock-data";
import { apiGet, apiPost } from "@/lib/api";
import type { TradeConfig } from "@/types";

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

export default function ConfigSettingsPage() {
  const [config, setConfig] = useState<TradeConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const defaultConfig = useMemo(() => clone(mockConfig), []);

  useEffect(() => {
    apiGet<TradeConfig>("/config")
      .then((data) => setConfig(clone(data)))
      .catch(() => setConfig(clone(defaultConfig)));
  }, [defaultConfig]);

  function updateConfig(path: string, value: any) {
    setConfig((prev) => {
      if (!prev) return prev;
      const next: TradeConfig = JSON.parse(JSON.stringify(prev));
      if (path.includes(".")) {
        const segments = path.split(".");
        let cursor: any = next;
        for (let i = 0; i < segments.length - 1; i += 1) {
          cursor = cursor[segments[i]];
        }
        cursor[segments[segments.length - 1]] = value;
      } else {
        (next as any)[path] = value;
      }
      return next;
    });
  }

  async function saveConfig() {
    if (!config) return;
    setLoading(true);
    setMessage(null);
    try {
      await apiPost("/config", { data: config });
      setMessage("Конфіг збережено успішно");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function resetToDefaults() {
    setConfig(clone(defaultConfig));
    setMessage("Повернено типові значення");
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.4em] text-sky-300">Configurable intelligence</p>
        <h1 className="text-3xl font-semibold text-slate-100">Тактичні параметри стратегії</h1>
        <p className="text-sm text-slate-400">
          Керуйте кількістю одночасних угод, ручними лімітами та повним SMART_AVG профілем безпосередньо з SaaS-пульта.
        </p>
      </div>

      {message && (
        <div className="flex items-center justify-between rounded-2xl border border-sky-500/40 bg-sky-500/10 px-5 py-3 text-sm text-sky-200">
          <span>{message}</span>
          <Button size="sm" variant="ghost" className="text-xs text-slate-300" onClick={() => setMessage(null)}>
            Закрити
          </Button>
        </div>
      )}

      {config ? (
        <TradeConfigurationForm
          config={config}
          onChange={updateConfig}
          onSave={saveConfig}
          onReset={resetToDefaults}
          saving={loading}
        />
      ) : (
        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-6 py-16 text-center text-slate-500">
          Завантаження конфігу...
        </div>
      )}
    </div>
  );
}
