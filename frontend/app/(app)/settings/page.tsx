"use client";

import { useEffect, useState } from "react";
import { TradeConfigurationForm } from "@/components/settings/trade-configuration-form";
import { TradeConditionsForm } from "@/components/settings/trade-conditions-form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { mockConfig, mockConditions } from "@/lib/mock-data";
import { apiGet, apiPost } from "@/lib/api";
import type { TradeConditions, TradeConfig } from "@/types";

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

export default function SettingsPage() {
  const [config, setConfig] = useState<TradeConfig | null>(null);
  const [conditions, setConditions] = useState<TradeConditions | null>(null);
  const [initialConditions, setInitialConditions] = useState<TradeConditions | null>(null);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadingConditions, setLoadingConditions] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    apiGet<TradeConfig>("/config/ui")
      .then(setConfig)
      .catch(() => setConfig(clone(mockConfig)));
    apiGet<TradeConditions>("/conditions")
      .then((data) => {
        setConditions(data);
        setInitialConditions(clone(data));
      })
      .catch(() => {
        const fallback = clone(mockConditions);
        setConditions(fallback);
        setInitialConditions(clone(fallback));
      });
  }, []);

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
    setLoadingConfig(true);
    setMessage(null);
    try {
      await apiPost("/config/ui", config);
      setMessage("Configuration saved");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setLoadingConfig(false);
    }
  }

  async function saveConditions() {
    if (!conditions) return;
    setLoadingConditions(true);
    setMessage(null);
    try {
      await apiPost("/conditions", conditions);
      setInitialConditions(clone(conditions));
      setMessage("Conditions saved");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setLoadingConditions(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.4em] text-sky-300">Settings</p>
        <h1 className="text-3xl font-semibold text-slate-100">Strategy configuration</h1>
        <p className="text-sm text-slate-400">
          Calibrate trade concurrency, risk envelopes, and the AI condition matrix powering LonaMind.
        </p>
      </div>

      {message && (
        <div className="rounded-2xl border border-sky-500/40 bg-sky-500/10 px-5 py-3 text-sm text-sky-200">
          {message}
        </div>
      )}

      <Tabs defaultValue="config" className="space-y-6">
        <TabsList>
          <TabsTrigger value="config">Trade configuration</TabsTrigger>
          <TabsTrigger value="logic">Trade conditions</TabsTrigger>
        </TabsList>
        <TabsContent value="config">
          {config ? (
            <TradeConfigurationForm
              config={config}
              onChange={updateConfig}
              onSave={saveConfig}
              onReset={() => setConfig(clone(mockConfig))}
              saving={loadingConfig}
            />
          ) : (
            <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-6 py-16 text-center text-slate-500">
              Loading configuration...
            </div>
          )}
        </TabsContent>
        <TabsContent value="logic">
          {conditions ? (
            <TradeConditionsForm
              conditions={conditions}
              onChange={setConditions}
              onSave={saveConditions}
              onReset={() => setConditions(initialConditions ? clone(initialConditions) : clone(mockConditions))}
              onUseDefaults={() => setConditions(clone(mockConditions))}
              saving={loadingConditions}
            />
          ) : (
            <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-6 py-16 text-center text-slate-500">
              Loading conditions...
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
