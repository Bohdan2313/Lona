"use client";

import { useEffect, useMemo, useState } from "react";

import { TradeConditionsForm } from "@/components/settings/trade-conditions-form";
import { Button } from "@/components/ui/button";
import { mockConditions } from "@/lib/mock-data";
import { apiGet, apiPost } from "@/lib/api";
import type { TradeConditions } from "@/types";

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

export default function ConditionsSettingsPage() {
  const [conditions, setConditions] = useState<TradeConditions | null>(null);
  const [initialConditions, setInitialConditions] = useState<TradeConditions | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const defaults = useMemo(() => clone(mockConditions), []);

  useEffect(() => {
    apiGet<TradeConditions>("/conditions")
      .then((data) => {
        const payload = Object.keys(data || {}).length ? data : defaults;
        setConditions(clone(payload));
        setInitialConditions(clone(payload));
      })
      .catch(() => {
        setConditions(clone(defaults));
        setInitialConditions(clone(defaults));
      });
  }, [defaults]);

  async function saveConditions() {
    if (!conditions) return;
    setLoading(true);
    setMessage(null);
    try {
      await apiPost("/conditions", conditions);
      setInitialConditions(clone(conditions));
      setMessage("Правила збережені");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function resetConditions() {
    setConditions(initialConditions ? clone(initialConditions) : clone(defaults));
    setMessage("Повернули попередні значення");
  }

  async function useDefaultEngine() {
    setLoading(true);
    setMessage(null);
    try {
      await apiPost("/conditions", {});
      setConditions(clone(defaults));
      setInitialConditions(clone(defaults));
      setMessage("Custom умови вимкнено — працюють стандартні правила check_trade_conditions.py");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <p className="text-xs uppercase tracking-[0.4em] text-sky-300">Unified operations</p>
        <h1 className="text-3xl font-semibold text-slate-100">Правила входу та маржинальні сценарії</h1>
        <p className="text-sm text-slate-400">
          Формуйте кастомні правила для RSI, MACD, трендових та патернових кластерів, а також контролюйте анти-фільтри та пороги
          прийняття угоди.
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

      {conditions ? (
        <TradeConditionsForm
          conditions={conditions}
          onChange={setConditions}
          onSave={saveConditions}
          onReset={resetConditions}
          onUseDefaults={useDefaultEngine}
          saving={loading}
        />
      ) : (
        <div className="rounded-2xl border border-slate-800/70 bg-slate-950/40 px-6 py-16 text-center text-slate-500">
          Завантаження правил...
        </div>
      )}
    </div>
  );
}
