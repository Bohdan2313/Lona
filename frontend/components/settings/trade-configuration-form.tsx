import { TradeConfig } from "@/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

function formatNumber(value: number | undefined, fractionDigits = 2) {
  if (value === undefined || Number.isNaN(value)) return "";
  return Number(value.toFixed(fractionDigits));
}

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
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Execution envelope</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Desired active trades</Label>
            <Input
              type="number"
              value={config.DESIRED_ACTIVE_TRADES}
              onChange={(event) => onChange("DESIRED_ACTIVE_TRADES", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Max long positions</Label>
            <Input
              type="number"
              value={config.MAX_LONG_TRADES}
              onChange={(event) => onChange("MAX_LONG_TRADES", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Max short positions</Label>
            <Input
              type="number"
              value={config.MAX_SHORT_TRADES}
              onChange={(event) => onChange("MAX_SHORT_TRADES", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Manual balance (USDT)</Label>
            <Input
              type="number"
              value={config.MANUAL_BALANCE}
              onChange={(event) => onChange("MANUAL_BALANCE", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Manual leverage</Label>
            <Input
              type="number"
              value={config.MANUAL_LEVERAGE}
              onChange={(event) => onChange("MANUAL_LEVERAGE", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Account buffer %</Label>
            <Input
              type="number"
              step="0.001"
              value={formatNumber(config.ACCOUNT_SAFETY_BUFFER_PCT, 3)}
              onChange={(event) => onChange("ACCOUNT_SAFETY_BUFFER_PCT", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Minimum free USDT</Label>
            <Input
              type="number"
              value={config.ACCOUNT_MIN_FREE_USDT}
              onChange={(event) => onChange("ACCOUNT_MIN_FREE_USDT", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Dynamic symbol discovery</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <div className="space-y-1 text-xs text-slate-400">
                <p className="text-sm font-medium text-slate-100">Use dynamic symbols</p>
                <p>Automatically rotate assets by market depth.</p>
              </div>
              <Switch
                checked={config.USE_DYNAMIC_SYMBOLS}
                onClick={() => onChange("USE_DYNAMIC_SYMBOLS", !config.USE_DYNAMIC_SYMBOLS)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Top symbols volume filter</Label>
            <Input
              type="number"
              value={config.GET_TOP_SYMBOLS_CONFIG.min_volume}
              onChange={(event) =>
                onChange(
                  "GET_TOP_SYMBOLS_CONFIG",
                  { ...config.GET_TOP_SYMBOLS_CONFIG, min_volume: Number(event.target.value) },
                )
              }
            />
          </div>
          <div className="space-y-2">
            <Label>Top symbols limit</Label>
            <Input
              type="number"
              value={config.GET_TOP_SYMBOLS_CONFIG.limit}
              onChange={(event) =>
                onChange(
                  "GET_TOP_SYMBOLS_CONFIG",
                  { ...config.GET_TOP_SYMBOLS_CONFIG, limit: Number(event.target.value) },
                )
              }
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Smart averaging</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Smart averaging</Label>
            <div className="flex items-center justify-between rounded-2xl border border-slate-800/70 bg-slate-950/40 p-4">
              <div className="space-y-1 text-xs text-slate-400">
                <p className="text-sm font-medium text-slate-100">Enable laddering</p>
                <p>Allow the bot to average into volatility.</p>
              </div>
              <Switch
                checked={config.SMART_AVG.enabled}
                onClick={() => onChange("SMART_AVG.enabled", !config.SMART_AVG.enabled)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>DCA leverage</Label>
            <Input
              type="number"
              value={config.SMART_AVG.leverage}
              onChange={(event) => onChange("SMART_AVG.leverage", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Base margin</Label>
            <Input
              type="number"
              value={config.SMART_AVG.base_margin}
              onChange={(event) => onChange("SMART_AVG.base_margin", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Max adds</Label>
            <Input
              type="number"
              value={config.SMART_AVG.max_adds}
              onChange={(event) => onChange("SMART_AVG.max_adds", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>DCA step %</Label>
            <Slider
              min={0}
              max={0.1}
              step={0.001}
              value={config.SMART_AVG.dca_step_pct}
              onChange={(event) => onChange("SMART_AVG.dca_step_pct", Number(event.currentTarget.value))}
            />
            <p className="text-xs text-slate-400">{(config.SMART_AVG.dca_step_pct * 100).toFixed(2)}%</p>
          </div>
          <div className="space-y-2">
            <Label>Take profit from average %</Label>
            <Input
              type="number"
              step="0.001"
              value={config.SMART_AVG.tp_from_avg_pct}
              onChange={(event) => onChange("SMART_AVG.tp_from_avg_pct", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Alt take profit %</Label>
            <Input
              type="number"
              step="0.001"
              value={config.SMART_AVG.alt_tp_from_avg_pct}
              onChange={(event) => onChange("SMART_AVG.alt_tp_from_avg_pct", Number(event.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Max margin per trade</Label>
            <Input
              type="number"
              value={config.SMART_AVG.max_margin_per_trade}
              onChange={(event) => onChange("SMART_AVG.max_margin_per_trade", Number(event.target.value))}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={onSave} disabled={saving}>
          {saving ? "Saving..." : "Save configuration"}
        </Button>
        <Button type="button" variant="secondary" onClick={onReset} disabled={saving}>
          Reset to defaults
        </Button>
      </div>
    </div>
  );
}
