import { useMemo } from "react";

import { TradeConditions, ConditionSet, IndicatorCondition, IndicatorPair } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

function ConditionList({
  title,
  conditions,
  onChange,
}: {
  title: string;
  conditions: IndicatorCondition[];
  onChange: (next: IndicatorCondition[]) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{title}</p>
      <div className="space-y-3">
        {conditions.map((condition, index) => (
          <div key={`${condition[0]}-${index}`} className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Indicator</Label>
              <Input
                value={condition[0]}
                onChange={(event) => {
                  const next = [...conditions];
                  next[index] = [event.target.value, next[index][1]];
                  onChange(next);
                }}
              />
            </div>
            <div className="space-y-1">
              <Label>State / value</Label>
              <Input
                value={condition[1]}
                onChange={(event) => {
                  const next = [...conditions];
                  next[index] = [next[index][0], event.target.value];
                  onChange(next);
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ConditionPairList({
  title,
  conditions,
  onChange,
}: {
  title: string;
  conditions: IndicatorPair[];
  onChange: (next: IndicatorPair[]) => void;
}) {
  return (
    <div className="space-y-3">
      <p className="text-xs uppercase tracking-[0.3em] text-slate-500">{title}</p>
      <div className="space-y-3">
        {conditions.map((condition, index) => (
          <div key={`pair-${index}`} className="grid grid-cols-2 gap-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
            {[0, 1].map((slot) => (
              <div key={slot} className="space-y-1">
                <Label>Indicator {slot + 1}</Label>
                <Input
                  value={condition[slot][0]}
                  onChange={(event) => {
                    const next = [...conditions];
                    const pair = [...next[index]] as IndicatorPair;
                    pair[slot] = [event.target.value, pair[slot][1]];
                    next[index] = pair;
                    onChange(next);
                  }}
                />
                <Label className="mt-2">State</Label>
                <Input
                  value={condition[slot][1]}
                  onChange={(event) => {
                    const next = [...conditions];
                    const pair = [...next[index]] as IndicatorPair;
                    pair[slot] = [pair[slot][0], event.target.value];
                    next[index] = pair;
                    onChange(next);
                  }}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

const buildIndicatorOptions = (value: ConditionSet): Record<string, string[]> => {
  const registry: Record<string, Set<string>> = {};
  const register = ([indicator, option]: IndicatorCondition) => {
    if (!registry[indicator]) {
      registry[indicator] = new Set();
    }
    registry[indicator].add(option);
  };

  value.core.forEach(register);
  value.pairs.forEach((pair) => {
    pair.forEach(register);
  });

  return Object.fromEntries(
    Object.entries(registry)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([indicator, options]) => [indicator, Array.from(options).sort()])
  );
};

function ConditionSetEditor({ title, value, onChange }: { title: string; value: ConditionSet; onChange: (next: ConditionSet) => void }) {
  const antiFilters = (value.anti_filters ?? {}) as Record<string, any>;
  const indicatorPalette = useMemo(() => buildIndicatorOptions(value), [value]);

  const updateAntiFilters = (key: string, nextValue: any) => {
    const next = { ...antiFilters, [key]: nextValue };
    onChange({ ...value, anti_filters: next });
  };

  const toggleCoreCondition = (indicator: string, option: string) => {
    const exists = value.core.some(([field, val]) => field === indicator && val === option);
    let nextCore: IndicatorCondition[];
    if (exists) {
      nextCore = value.core.filter(([field, val]) => !(field === indicator && val === option));
    } else {
      nextCore = [...value.core, [indicator, option]];
    }
    onChange({ ...value, core: nextCore });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Індикаторний палітровий вибір</p>
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(indicatorPalette).map(([indicator, options]) => (
              <div key={indicator} className="space-y-2 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
                <h4 className="text-sm font-semibold text-slate-100">{indicator}</h4>
                <div className="flex flex-wrap gap-2">
                  {options.map((option) => {
                    const active = value.core.some(([field, val]) => field === indicator && val === option);
                    return (
                      <Button
                        key={option}
                        type="button"
                        size="sm"
                        variant={active ? "default" : "outline"}
                        className={
                          active
                            ? "border-sky-500/60 bg-sky-600/20 text-sky-100 hover:bg-sky-600/30"
                            : "border-slate-800/80 bg-transparent text-slate-300 hover:text-slate-100"
                        }
                        onClick={() => toggleCoreCondition(indicator, option)}
                      >
                        {option}
                      </Button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <ConditionList
          title="Core conditions"
          conditions={value.core}
          onChange={(core) => onChange({ ...value, core })}
        />
        <ConditionPairList
          title="Pair confirmations"
          conditions={value.pairs}
          onChange={(pairs) => onChange({ ...value, pairs })}
        />
        <div className="grid gap-4 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Signal threshold</Label>
            <Slider
              min={0}
              max={20}
              step={0.1}
              value={value.threshold ?? 0}
              onChange={(event) => onChange({ ...value, threshold: Number(event.currentTarget.value) })}
            />
            <p className="text-xs text-slate-400">{(value.threshold ?? 0).toFixed(1)} pts required</p>
          </div>
          <div className="space-y-2">
            <Label>Minimum pair hits</Label>
            <Input
              type="number"
              value={antiFilters.min_pair_hits ?? 0}
              onChange={(event) => updateAntiFilters("min_pair_hits", Number(event.currentTarget.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Require closed candle</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/60 bg-slate-950/30 px-4 py-3">
              <span className="text-xs text-slate-400">Only confirm signals after candle close.</span>
              <Switch
                checked={Boolean(antiFilters.require_closed_candle)}
                onClick={() => updateAntiFilters("require_closed_candle", !antiFilters.require_closed_candle)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Exclusive blockers</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/60 bg-slate-950/30 px-4 py-3">
              <span className="text-xs text-slate-400">Disqualify trades when blockers trigger.</span>
              <Switch
                checked={Boolean(antiFilters.exclusive_blockers)}
                onClick={() => updateAntiFilters("exclusive_blockers", !antiFilters.exclusive_blockers)}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function TradeConditionsForm({
  conditions,
  onChange,
  onSave,
  onReset,
  onUseDefaults,
  saving,
}: {
  conditions: TradeConditions;
  onChange: (next: TradeConditions) => void;
  onSave: () => Promise<void>;
  onReset: () => void;
  onUseDefaults: () => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-6">
      <Tabs defaultValue="long">
        <TabsList>
          <TabsTrigger value="long">Long logic</TabsTrigger>
          <TabsTrigger value="short">Short logic</TabsTrigger>
        </TabsList>
        <TabsContent value="long">
          <ConditionSetEditor
            title="Long orchestration"
            value={conditions.long}
            onChange={(next) => onChange({ ...conditions, long: next })}
          />
        </TabsContent>
        <TabsContent value="short">
          <ConditionSetEditor
            title="Short orchestration"
            value={conditions.short}
            onChange={(next) => onChange({ ...conditions, short: next })}
          />
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>Fast track & scoring</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Mode</Label>
            <Input value={conditions.mode} onChange={(event) => onChange({ ...conditions, mode: event.target.value })} />
          </div>
          <div className="space-y-2">
            <Label>Regime bonus</Label>
            <Input
              type="number"
              step="0.01"
              value={conditions.regime_bonus ?? 0}
              onChange={(event) => onChange({ ...conditions, regime_bonus: Number(event.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>Decision delta</Label>
            <Input
              type="number"
              step="0.01"
              value={conditions.decision_delta ?? 0}
              onChange={(event) => onChange({ ...conditions, decision_delta: Number(event.target.value) })}
            />
          </div>
          <div className="space-y-2">
            <Label>Fallback strategy</Label>
            <Input
              value={conditions.fallback ?? ""}
              onChange={(event) => onChange({ ...conditions, fallback: event.target.value })}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSave} disabled={saving}>
          {saving ? "Збереження..." : "Зберегти"}
        </Button>
        <Button type="button" variant="secondary" onClick={onReset} disabled={saving}>
          Скасувати зміни
        </Button>
        <Button type="button" variant="outline" onClick={onUseDefaults} disabled={saving}>
          По замовчуванню
        </Button>
      </div>
    </div>
  );
}
