import { TradeConfig } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;

export function TradeConfigurationForm({
  config,
  onChange,
  onSave,
  onReset,
  saving,
}: {
  config: TradeConfig;
  onChange: (path: string, value: any) => void;
  onSave: () => Promise<void>;
  onReset: () => void;
  saving: boolean;
}) {
  const desiredTrades = Number(config.DESIRED_ACTIVE_TRADES ?? 0);
  const maxLong = Number(config.MAX_LONG_TRADES ?? 0);
  const maxShort = Number(config.MAX_SHORT_TRADES ?? 0);
  const dcaStep = Number(config.SMART_AVG.dca_step_pct ?? 0);
  const dcaFactor = Number(config.SMART_AVG.dca_factor ?? 1);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Конкуренція угод</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <Label className="text-xs uppercase tracking-[0.3em] text-slate-500">DESIRED ACTIVE TRADES</Label>
            <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <Slider
                min={0}
                max={20}
                step={1}
                value={desiredTrades}
                onChange={(event) => onChange("DESIRED_ACTIVE_TRADES", Number(event.currentTarget.value))}
              />
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Активні одночасно</span>
                <Input
                  type="number"
                  min={0}
                  max={50}
                  value={desiredTrades}
                  onChange={(event) => onChange("DESIRED_ACTIVE_TRADES", Number(event.target.value))}
                  className="h-8 w-24 bg-slate-900 text-right text-sm"
                />
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <Label className="text-xs uppercase tracking-[0.3em] text-slate-500">MAX LONG TRADES</Label>
            <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <Slider
                min={0}
                max={20}
                step={1}
                value={maxLong}
                onChange={(event) => onChange("MAX_LONG_TRADES", Number(event.currentTarget.value))}
              />
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Лонги одночасно</span>
                <Input
                  type="number"
                  min={0}
                  max={50}
                  value={maxLong}
                  onChange={(event) => onChange("MAX_LONG_TRADES", Number(event.target.value))}
                  className="h-8 w-24 bg-slate-900 text-right text-sm"
                />
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <Label className="text-xs uppercase tracking-[0.3em] text-slate-500">MAX SHORT TRADES</Label>
            <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <Slider
                min={0}
                max={20}
                step={1}
                value={maxShort}
                onChange={(event) => onChange("MAX_SHORT_TRADES", Number(event.currentTarget.value))}
              />
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Шорти одночасно</span>
                <Input
                  type="number"
                  min={0}
                  max={50}
                  value={maxShort}
                  onChange={(event) => onChange("MAX_SHORT_TRADES", Number(event.target.value))}
                  className="h-8 w-24 bg-slate-900 text-right text-sm"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ручні обмеження</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label className="text-sm text-slate-300">Manual balance (USDT)</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <div>
                <p className="text-sm font-medium text-slate-100">Фіксований капітал</p>
                <p className="text-xs text-slate-500">Використати ручне значення замість балансу біржі.</p>
              </div>
              <Switch
                checked={config.USE_MANUAL_BALANCE}
                onClick={() => onChange("USE_MANUAL_BALANCE", !config.USE_MANUAL_BALANCE)}
              />
            </div>
            <Input
              type="number"
              min={0}
              value={config.MANUAL_BALANCE}
              disabled={!config.USE_MANUAL_BALANCE}
              onChange={(event) => onChange("MANUAL_BALANCE", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label className="text-sm text-slate-300">Manual leverage</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <div>
                <p className="text-sm font-medium text-slate-100">Фіксоване плече</p>
                <p className="text-xs text-slate-500">Перекрити автоматичні налаштування біржі.</p>
              </div>
              <Switch
                checked={config.USE_MANUAL_LEVERAGE}
                onClick={() => onChange("USE_MANUAL_LEVERAGE", !config.USE_MANUAL_LEVERAGE)}
              />
            </div>
            <Input
              type="number"
              min={0}
              value={config.MANUAL_LEVERAGE}
              disabled={!config.USE_MANUAL_LEVERAGE}
              onChange={(event) => onChange("MANUAL_LEVERAGE", Number(event.target.value))}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>SMART_AVG профіль</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <Label className="text-sm text-slate-300">Ладер увімкнено</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/70 bg-slate-950/40 px-4 py-3">
              <span className="text-xs text-slate-500">Активувати DCA алгоритм для позицій.</span>
              <Switch
                checked={config.SMART_AVG.enabled}
                onClick={() => onChange("SMART_AVG.enabled", !config.SMART_AVG.enabled)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Leverage</Label>
            <Input
              type="number"
              min={0}
              value={config.SMART_AVG.leverage}
              onChange={(event) => onChange("SMART_AVG.leverage", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Base margin (USDT)</Label>
            <Input
              type="number"
              min={0}
              value={config.SMART_AVG.base_margin}
              onChange={(event) => onChange("SMART_AVG.base_margin", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Max adds</Label>
            <Input
              type="number"
              min={0}
              value={config.SMART_AVG.max_adds}
              onChange={(event) => onChange("SMART_AVG.max_adds", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>DCA step</Label>
            <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <Slider
                min={0}
                max={0.1}
                step={0.001}
                value={dcaStep}
                onChange={(event) => onChange("SMART_AVG.dca_step_pct", Number(event.currentTarget.value))}
              />
              <p className="text-xs text-slate-400">{formatPercent(dcaStep)}</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>DCA factor</Label>
            <div className="space-y-3 rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <Slider
                min={1}
                max={3}
                step={0.05}
                value={dcaFactor}
                onChange={(event) => onChange("SMART_AVG.dca_factor", Number(event.currentTarget.value))}
              />
              <p className="text-xs text-slate-400">x{dcaFactor.toFixed(2)}</p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Primary take profit %</Label>
            <Input
              type="number"
              step="0.0001"
              value={config.SMART_AVG.tp_from_avg_pct}
              onChange={(event) => onChange("SMART_AVG.tp_from_avg_pct", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Alternative take profit %</Label>
            <Input
              type="number"
              step="0.0001"
              value={config.SMART_AVG.alt_tp_from_avg_pct}
              onChange={(event) => onChange("SMART_AVG.alt_tp_from_avg_pct", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Max margin per trade (USDT)</Label>
            <Input
              type="number"
              min={0}
              value={config.SMART_AVG.max_margin_per_trade}
              onChange={(event) => onChange("SMART_AVG.max_margin_per_trade", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Min liquidity buffer %</Label>
            <Input
              type="number"
              step="0.0001"
              value={config.SMART_AVG.min_liq_buffer}
              onChange={(event) => onChange("SMART_AVG.min_liq_buffer", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>ATR pause %</Label>
            <Input
              type="number"
              step="0.01"
              value={config.SMART_AVG.atr_pause_pct}
              onChange={(event) => onChange("SMART_AVG.atr_pause_pct", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Trend flip cut %</Label>
            <Input
              type="number"
              step="0.0001"
              value={config.SMART_AVG.trend_flip_cut_pct}
              onChange={(event) => onChange("SMART_AVG.trend_flip_cut_pct", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Cooldown (minutes)</Label>
            <Input
              type="number"
              min={0}
              value={config.SMART_AVG.cooldown_min}
              onChange={(event) => onChange("SMART_AVG.cooldown_min", Number(event.target.value))}
            />
          </div>

          <div className="space-y-2">
            <Label>Anchor</Label>
            <Input
              value={config.SMART_AVG.anchor}
              onChange={(event) => onChange("SMART_AVG.anchor", event.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSave} disabled={saving}>
          {saving ? "Збереження..." : "Зберегти"}
        </Button>
        <Button type="button" variant="secondary" onClick={onReset} disabled={saving}>
          По замовчуванню
        </Button>
      </div>
    </div>
  );
}
