#!/usr/bin/env python3
"""Strict multi-source audit. Standard library only. Never invent forecasts."""
import argparse
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

VALID = {'solio', 'fpltoolkit', 'lineupoptimizer', 'rotowire'}

def run(records):
    grouped = defaultdict(list)
    errors = []
    for i, r in enumerate(records):
        try:
            source = r['source']; gw = int(r['gw']); player = int(r['player_id'])
            stamp = dt.datetime.fromisoformat(r['collected_at_utc'].replace('Z', '+00:00'))
            assert stamp.tzinfo is not None
            assert source in VALID and gw > 0 and player > 0
            assert r.get('source_url', '').startswith('https://')
            xp = r.get('xpts')
            if xp is not None:
                xp = float(xp)
                assert 0 <= xp <= 50 and source != 'rotowire'
            minutes = r.get('expected_minutes')
            if minutes is not None:
                minutes = float(minutes)
                assert 0 <= minutes <= 120
            grouped[(gw, player)].append({'source': source, 'xpts': xp, 'minutes': minutes, 'collected_at_utc': r['collected_at_utc'], 'source_url': r['source_url']})
        except (KeyError, ValueError, TypeError, AssertionError) as e:
            errors.append({'row': i, 'reason': str(e) or 'invalid record'})
    rows = []
    for (gw, player), items in sorted(grouped.items()):
        by_source = {x['source']: x for x in items}  # latest supplied record per source
        numeric = [x for x in by_source.values() if x['xpts'] is not None]
        values = [x['xpts'] for x in numeric]
        spread = round(max(values) - min(values), 3) if len(values) >= 2 else None
        rows.append({'gw': gw, 'player_id': player, 'sources': list(by_source.values()), 'numeric_source_count': len(values), 'range_xpts': spread, 'outlier_flag': spread is not None and spread >= 1.0, 'consensus_status': 'unvalidated_independence' if len(values) >= 2 else 'insufficient_numeric_sources', 'consensus_xpts': None})
    return {'schema_version': 1, 'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'research_only': True, 'optimized': False, 'rows': rows, 'rejected_records': errors}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    data = json.loads(Path(a.inputs).read_text())
    result = run(data['records'])
    out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\\n')
    print(f'Audited {len(result["rows"])} player-GW rows; rejected {len(result["rejected_records"])} records')
