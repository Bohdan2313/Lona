import json
import math
import itertools
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path('data/timeseries')
REPORT_DIR = Path('report')
REPORT_DIR.mkdir(exist_ok=True, parents=True)

CANON_PATTERNS = [
    'bullish_engulfing', 'bearish_engulfing', 'hammer',
    'shooting_star', 'morning_star', 'evening_star', 'doji'
]
LOWER_FIELDS = [
    'support_position', 'global_trend', 'volume_category', 'macd_trend',
    'macd_hist_direction', 'macd_crossed', 'rsi_trend', 'rsi_signal',
    'stoch_signal', 'bollinger_signal', 'microtrend_1m', 'microtrend_5m'
]
FLOAT_FIELDS = ['price', 'rsi_value', 'stoch_k', 'stoch_d',
                'bollinger_position', 'cci_value']
HORIZONS = [5, 15, 30, 60]


def read_json_file(path):
    with open(path, 'r') as f:
        content = f.read().strip()
    if not content:
        return []
    try:
        return [json.loads(line) for line in content.splitlines() if line.strip()]
    except json.JSONDecodeError:
        data = json.loads(content)
        return data if isinstance(data, list) else [data]


def normalize_record(rec):
    for field in LOWER_FIELDS:
        if field in rec and isinstance(rec[field], str):
            rec[field] = rec[field].lower()
    if rec.get('macd_crossed') not in {'none', 'bullish_cross', 'bearish_cross'}:
        rec['macd_crossed'] = 'none'
    for field in FLOAT_FIELDS:
        if field in rec:
            try:
                rec[field] = float(rec[field])
            except Exception:
                rec[field] = math.nan
        else:
            rec[field] = math.nan
    pc = rec.get('patterns_canon') or []
    for pat in CANON_PATTERNS:
        rec[f'pat_{pat}'] = 1 if pat in pc else 0
    freshness = {pat: math.inf for pat in CANON_PATTERNS}
    for p in rec.get('patterns') or []:
        ptype = p.get('type')
        direction = p.get('direction')
        index = p.get('index')
        if ptype == 'engulfing':
            canon = 'bullish_engulfing' if direction == 'bullish' else 'bearish_engulfing'
        else:
            canon = ptype
        if canon not in CANON_PATTERNS:
            continue
        try:
            idx = int(index)
        except Exception:
            continue
        freshness[canon] = min(freshness[canon], idx)
    for pat in CANON_PATTERNS:
        idx = freshness[pat]
        if idx is math.inf:
            cat = 'none'
        elif idx <= 2:
            cat = 'recent_<=2'
        elif idx <=5:
            cat = 'recent_<=5'
        else:
            cat = 'older'
        rec[f'fresh_{pat}'] = cat
    return rec


def discretize(rec):
    def bucket(val, edges):
        if math.isnan(val):
            return 'unknown'
        for i, edge in enumerate(edges):
            if val <= edge:
                return f'<= {edge}' if i == 0 else f'{edges[i-1]}-{edge}'
        return f'> {edges[-1]}'
    rec['rsi_bucket'] = bucket(rec['rsi_value'], [30,40,50,60,70])
    rec['boll_bucket'] = bucket(rec['bollinger_position'], [30,45,55,70])
    rec['stoch_k_bucket'] = bucket(rec['stoch_k'], [20,40,60,80])
    rec['stoch_d_bucket'] = bucket(rec['stoch_d'], [20,40,60,80])
    rec['cci_bucket'] = bucket(rec['cci_value'], [-100,0,100])
    return rec


def process_symbol(records):
    by_ts = {}
    for r in records:
        ts = r.get('ts')
        price = r.get('price')
        if ts is None or price is None:
            continue
        by_ts[ts] = r
    recs = [normalize_record(discretize(by_ts[k])) for k in sorted(by_ts.keys())]
    times = [datetime.fromisoformat(r['ts']) for r in recs]
    prices = [r['price'] for r in recs]
    for idx, r in enumerate(recs):
        for h in HORIZONS:
            end_time = times[idx] + timedelta(minutes=h)
            max_price = prices[idx]
            min_price = prices[idx]
            rise_time = None
            fall_time = None
            j = idx + 1
            while j < len(recs) and times[j] <= end_time:
                p = prices[j]
                if p > max_price:
                    max_price = p
                if p < min_price:
                    min_price = p
                if rise_time is None and p >= prices[idx]*1.01:
                    rise_time = (times[j]-times[idx]).total_seconds()/60
                if fall_time is None and p <= prices[idx]*0.99:
                    fall_time = (times[j]-times[idx]).total_seconds()/60
                j += 1
            ret = (max_price - prices[idx])/prices[idx]
            dd = (min_price - prices[idx])/prices[idx]
            r[f'ret_{h}'] = ret
            r[f'dd_{h}'] = dd
            r[f'rise_{h}'] = 1 if ret >= 0.01 else 0
            r[f'fall_{h}'] = 1 if dd <= -0.01 else 0
            r[f'ttr_{h}'] = rise_time
            r[f'ttf_{h}'] = fall_time
    return recs


def compute_baselines(records, h, strat_cols):
    rise_col = f'rise_{h}'
    fall_col = f'fall_{h}'
    total = len(records)
    base_rise = sum(r[rise_col] for r in records)/total if total else 0
    base_fall = sum(r[fall_col] for r in records)/total if total else 0
    result = {
        'p_base_rise': base_rise,
        'p_base_fall': base_fall
    }
    for strat in strat_cols:
        d = {}
        for r in records:
            val = r.get(strat)
            if val is None:
                continue
            d.setdefault(val, {'rise':0,'fall':0,'count':0})
            d[val]['rise'] += r[rise_col]
            d[val]['fall'] += r[fall_col]
            d[val]['count'] += 1
        res = {}
        for val, v in d.items():
            if v['count']:
                res[val] = {rise_col: v['rise']/v['count'], fall_col: v['fall']/v['count']}
        result[strat] = res
    return result


def is_nan(v):
    return v is None or (isinstance(v,float) and math.isnan(v))


def main():
    all_records = []
    for date_dir in sorted(DATA_DIR.iterdir()):
        if not date_dir.is_dir():
            continue
        for file in sorted(date_dir.iterdir()):
            if not (file.suffix in ('.json','.jsonl')):
                continue
            data = read_json_file(file)
            if not data:
                continue
            recs = process_symbol(data)
            all_records.extend(recs)
    if not all_records:
        print('No data')
        return

    baselines = {}
    rules_long = []
    rules_short = []

    feature_cols = [
        'support_position','global_trend','volume_category','macd_trend',
        'rsi_trend','rsi_bucket','stoch_signal','bollinger_signal',
        'microtrend_1m'
    ]
    for pat in CANON_PATTERNS:
        feature_cols.append(f'pat_{pat}')
    strat_cols = ['support_position','global_trend','volume_category']

    for h in HORIZONS:
        baselines[h] = compute_baselines(all_records, h, strat_cols)
        rise_col = f'rise_{h}'
        fall_col = f'fall_{h}'
        stats = {
            'rise': defaultdict(lambda: {'support':0,'event':0,'time':0.0,'examples':[],
                                         'strata':{c:defaultdict(lambda:{'support':0,'event':0,'time':0.0}) for c in strat_cols}}),
            'fall': defaultdict(lambda: {'support':0,'event':0,'time':0.0,'examples':[],
                                         'strata':{c:defaultdict(lambda:{'support':0,'event':0,'time':0.0}) for c in strat_cols}})
        }
        for row in all_records:
            features = []
            for col in feature_cols:
                val = row.get(col)
                if is_nan(val):
                    continue
                if col.startswith('pat_'):
                    val = 'yes' if val == 1 else 'no'
                features.append(f'{col}={val}')
            for r in range(1,3):
                for combo in itertools.combinations(features, r):
                    key = tuple(sorted(combo))
                    for event, col_e, time_col in [('rise', rise_col, f'ttr_{h}'), ('fall', fall_col, f'ttf_{h}')]:
                        stats[event][key]['support'] += 1
                        for strat in strat_cols:
                            sval = row.get(strat)
                            stats[event][key]['strata'][strat][sval]['support'] += 1
                        if row[col_e] == 1:
                            stats[event][key]['event'] += 1
                            tval = row.get(time_col)
                            if tval is not None:
                                stats[event][key]['time'] += tval
                            for strat in strat_cols:
                                sval = row.get(strat)
                                stats[event][key]['strata'][strat][sval]['event'] += 1
                                if tval is not None:
                                    stats[event][key]['strata'][strat][sval]['time'] += tval
                            if len(stats[event][key]['examples']) < 3:
                                stats[event][key]['examples'].append({'symbol': row['symbol'], 'ts': row['ts']})
        for event, rule_list in [('rise', rules_long), ('fall', rules_short)]:
            baseline = baselines[h]['p_base_rise'] if event=='rise' else baselines[h]['p_base_fall']
            for features, data in stats[event].items():
                support = data['support']
                if support < 30:
                    continue
                p_event = data['event']/support if support else 0
                lift = p_event / baseline if baseline>0 else 0
                if not (lift >=1.25 and p_event - baseline >= 0.08):
                    continue
                mean_time = data['time']/data['event'] if data['event']>0 else None
                rule = {
                    'horizon': h,
                    'features': list(features),
                    'support': support,
                    'p_event': p_event,
                    'p_baseline': baseline,
                    'lift': lift,
                    'mean_time_to_event_min': mean_time,
                    'strata': {c: 'any' for c in strat_cols},
                    'examples': data['examples'][:3]
                }
                for strat in strat_cols:
                    best = None
                    for sval, sdata in data['strata'][strat].items():
                        s_support = sdata['support']
                        if s_support < 30 or sval not in baselines[h][strat]:
                            continue
                        p_s = sdata['event']/s_support if s_support else 0
                        baseline_s = baselines[h][strat][sval][rise_col if event=='rise' else fall_col]
                        lift_s = p_s / baseline_s if baseline_s>0 else 0
                        if lift_s >= lift + 0.1 and p_s - baseline_s >= 0.05:
                            if best is None or lift_s > best[0]:
                                best = (lift_s, sval)
                    if best:
                        rule['strata'][strat] = best[1]
                rule_list.append(rule)

    with open(REPORT_DIR/'baselines.json', 'w') as f:
        json.dump(baselines, f, indent=2)
    with open(REPORT_DIR/'rules_long.json', 'w') as f:
        json.dump(rules_long, f, indent=2)
    with open(REPORT_DIR/'rules_short.json', 'w') as f:
        json.dump(rules_short, f, indent=2)

    def top_rules(rules, topn, max_len):
        filtered = [r for r in rules if len(r['features'])<=max_len]
        return sorted(filtered, key=lambda x: x['lift'], reverse=True)[:topn]
    lines = []
    lines.append('# Summary of Rules\n')
    lines.append('## Top 10 single conditions for rise\n')
    for r in top_rules(rules_long,10,1):
        lines.append(f"h={r['horizon']} {r['features']} support={r['support']} p={r['p_event']:.2f} lift={r['lift']:.2f}")
    lines.append('\n## Top 10 single conditions for fall\n')
    for r in top_rules(rules_short,10,1):
        lines.append(f"h={r['horizon']} {r['features']} support={r['support']} p={r['p_event']:.2f} lift={r['lift']:.2f}")
    lines.append('\n## Top 10 combos (<=2 features) for rise\n')
    for r in top_rules(rules_long,10,2):
        lines.append(f"h={r['horizon']} {r['features']} support={r['support']} p={r['p_event']:.2f} lift={r['lift']:.2f}")
    lines.append('\n## Top 10 combos (<=2 features) for fall\n')
    for r in top_rules(rules_short,10,2):
        lines.append(f"h={r['horizon']} {r['features']} support={r['support']} p={r['p_event']:.2f} lift={r['lift']:.2f}")
    lines.append('\n')
    with open(REPORT_DIR/'summary.md', 'w') as f:
        f.write('\n'.join(lines))

if __name__ == '__main__':
    main()
