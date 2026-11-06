"""Fail-closed, read-only research pipeline; public status never exposes live finances."""
import argparse
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

import collector
from forecasting import utc, number, validate_rows, digest, walk_forward
from planning_rules import State, selling_price
from rolling_planner import solve, SearchLimit


def freshness(snapshot, summary, now):
    collector.validate(snapshot)
    if not timedelta(0) <= now - utc(snapshot['completed_at']) <= timedelta(hours=12):
        raise ValueError('Public snapshot stale or future-dated')
    if summary['collected_at_utc'] != snapshot['completed_at']:
        raise ValueError('Summary does not match snapshot')
    for field in ('current_gameweek', 'current_gameweek_finished',
                  'latest_public_squad_gameweek', 'next_deadline_utc'):
        if field not in summary:
            raise ValueError('Missing freshness field: ' + field)
    b = snapshot['sources']['bootstrap']['data']
    current = next((e for e in b['events'] if e.get('is_current')), None)
    if summary['current_gameweek'] != (current['id'] if current else None) or summary['current_gameweek_finished'] != (current['finished'] if current else None):
        raise ValueError('Summary current-gameweek mismatch')
    latest = max(map(int, snapshot['squads']), default=None)
    if summary['latest_public_squad_gameweek'] != latest:
        raise ValueError('Public squad mismatch')
    upcoming = sorted((e for e in b['events'] if utc(e['deadline_time']) > now), key=lambda e: e['id'])
    if not upcoming or summary['next_deadline_utc'] != upcoming[0]['deadline_time']:
        raise ValueError('Missing/passed/inconsistent next deadline')
    for name in ('bootstrap', 'fixtures', 'history'):
        if not timedelta(0) <= now - utc(snapshot['sources'][name]['fetched_at']) <= timedelta(hours=12):
            raise ValueError('Stale source: ' + name)
    return upcoming[:6]


def research(snapshot, summary, bundle, now):
    weeks = freshness(snapshot, summary, now)
    if set(bundle) != {'forecasts', 'scenarios', 'prices', 'live', 'news', 'chips', 'weights', 'max_transfers'}:
        raise ValueError('Research bundle must match allowlist; league data forbidden')
    all_players = {p['id']: p for p in snapshot['sources']['bootstrap']['data']['elements']}
    rows = validate_rows(bundle['forecasts'], all_players, now)
    if not rows or len({(r['season'], r['model']) for r in rows}) != 1 or rows[0]['season'] != '2026/27':
        raise ValueError('One same-season, same-model forecast required')
    ids = {r['player'] for r in rows}
    players = {i: {k: all_players[i][k] for k in ('id', 'element_type', 'team', 'now_cost')} for i in ids}
    expected = {(e['id'], i) for e in weeks for i in ids}
    if {(r['gw'], r['player']) for r in rows} != expected:
        raise ValueError('Complete same-model six-GW coverage required; no missing-as-zero')
    deadlines = {e['id']: e['deadline_time'] for e in weeks}
    if any(utc(r['deadline']) != utc(deadlines[r['gw']]) or now-utc(r['retrieved_at']) > timedelta(hours=24) for r in rows):
        raise ValueError('Forecast deadline mismatch or stale forecast')
    live = bundle['live']
    if set(live) != {'verified_at', 'squad_ids', 'bank', 'ft', 'purchase_prices', 'selling_prices', 'used_chips', 'confirmed'} or live['confirmed'] is not True:
        raise ValueError('Explicit confirmed live state required')
    if not timedelta(0) <= now-utc(live['verified_at']) <= timedelta(hours=4):
        raise ValueError('Live state expired')
    purchases = {int(k): v for k, v in live['purchase_prices'].items()}
    sells = {int(k): v for k, v in live['selling_prices'].items()}
    if set(purchases) != set(live['squad_ids']) or set(sells) != set(purchases) or not set(purchases) <= ids:
        raise ValueError('Live holdings coverage invalid')
    if any(sells[i] != selling_price(purchases[i], players[i]['now_cost']) for i in purchases):
        raise ValueError('Verified selling prices inconsistent with market/purchase prices')
    if type(live['bank']) is not int or live['bank'] < 0:
        raise ValueError('Integer live bank required')
    official_used = sorted((c['event'], c['name']) for c in snapshot['sources']['history']['data']['chips'])
    if sorted(map(tuple, live['used_chips'])) != official_used:
        raise ValueError('Chip inventory must reconcile with refreshed official history')
    news = bundle['news']
    if {r['player'] for r in news} != ids or len(news) != len(ids):
        raise ValueError('Dated team news review required for every candidate')
    for item in news:
        if set(item) != {'player', 'source_url', 'reviewed_at'} or not item['source_url'].startswith('https://') or not timedelta(0) <= now-utc(item['reviewed_at']) <= timedelta(hours=24):
            raise ValueError('Invalid/stale team-news evidence')
    prices = {int(g): {int(i): p for i, p in ps.items()} for g, ps in bundle['prices'].items()}
    if any(prices[weeks[0]['id']][i] != players[i]['now_cost'] for i in ids):
        raise ValueError('Initial price path must match official market')
    scenarios = {}
    for gw_text, envelope in bundle['scenarios'].items():
        if set(envelope) != {'source_url', 'published_at', 'retrieved_at', 'values'}:
            raise ValueError('Scenario provenance required')
        if (not envelope['source_url'].startswith('https://') or
            not utc(envelope['published_at']) <= utc(envelope['retrieved_at']) <= now or
            now-utc(envelope['retrieved_at']) > timedelta(hours=24)):
            raise ValueError('Scenario source unavailable at decision time')
        gw = int(gw_text)
        scenarios[gw] = []
        for s in envelope['values']:
            if set(s) != {'probability', 'points', 'played'} or not number(s['probability']) or not 0 <= s['probability'] <= 1:
                raise ValueError('Invalid scenario')
            points = {int(i): v for i, v in s['points'].items()}
            played = {int(i): v for i, v in s['played'].items()}
            if set(points) != ids or set(played) != ids or any(not number(v) for v in points.values()) or any(type(v) is not bool for v in played.values()):
                raise ValueError('Invalid scenario player coverage')
            if any(points[i] != 0 and not played[i] for i in ids):
                raise ValueError('Non-playing player cannot score')
            scenarios[gw].append(dict(probability=s['probability'], points=points, played=played))
    if set(scenarios) != set(deadlines) or set(prices) != set(deadlines):
        raise ValueError('Scenario/price horizon mismatch')
    for r in rows:
        mean = sum(s['probability']*s['points'][r['player']] for s in scenarios[r['gw']])
        if abs(mean-r['xpts']) > 1e-6:
            raise ValueError('Joint scenarios do not reconcile to source xPts')
    state = State(tuple(sorted(purchases.items())), live['bank'], live['ft'], tuple(official_used))
    result = solve(state, players, list(deadlines), scenarios, prices,
                   chips=tuple(bundle['chips']), weights=bundle['weights'], max_transfers=bundle['max_transfers'])
    result.update(input_sha256=digest(bundle), snapshot_sha256=digest(snapshot),
                  generated_at=now.isoformat(), forecast_model=rows[0]['model'],
                  forecast_provenance=rows,
                  acceptance='research_informed_provisional', cumbres_is_optimizer_input=False)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot')
    ap.add_argument('--summary', default='data/latest-summary.json')
    ap.add_argument('--research-input', help='Private, source-backed research bundle; never uploaded by Actions')
    ap.add_argument('--history', help='Archived point-in-time forecasts and finalized outcomes')
    ap.add_argument('--output', default='data/latest-research-status.json')
    args = ap.parse_args()
    if args.research_input and args.output == 'data/latest-research-status.json':
        ap.error('Private research requires explicit private output path')
    now = datetime.now(timezone.utc)
    result = {'status': 'blocked_missing_sources', 'generated_at': now.isoformat(),
              'acceptance': 'research_informed_provisional', 'cumbres_is_optimizer_input': False,
              'blockers': ['Archived independent xPts/minutes/component forecasts and joint scenarios required.',
                           'Verified live squad, purchase/selling prices, bank, FTs and chip inventory required.',
                           'Real walk-forward forecast and decision evaluation not yet completed.']}
    try:
        path = Path(args.snapshot) if args.snapshot else sorted(Path('data/snapshots').glob('*.json'))[-1]
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        summary = json.loads(Path(args.summary).read_text(encoding='utf-8'))
        weeks = freshness(snapshot, summary, now)
        result['public_data_gate'] = 'passed'
        result['forecast_gameweeks'] = [e['id'] for e in weeks]
        if args.research_input:
            result = research(snapshot, summary, json.loads(Path(args.research_input).read_text(encoding='utf-8')), now)
        if args.history:
            result['forecast_backtest'] = walk_forward(json.loads(Path(args.history).read_text(encoding='utf-8')))
    except (ValueError, KeyError, TypeError, IndexError, OSError, collector.CollectionError, SearchLimit) as exc:
        result.update(status='blocked_invalid_or_stale_inputs', reason=str(exc))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(result['status'])
    return 2 if result['status'] == 'blocked_invalid_or_stale_inputs' else 0


if __name__ == '__main__':
    raise SystemExit(main())
