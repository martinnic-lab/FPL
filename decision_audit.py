"""Score immutable pre-deadline decisions against later finalized outcomes.

This is paired, one-GW walk-forward auditing, not a continuous season replay.
Every policy's actual lineup must have been archived before the same deadline.
"""
from statistics import mean
from forecasting import utc, digest, number
from rolling_planner import score


def evaluate(frames):
    rows, seen = [], set()
    for f in sorted(frames, key=lambda f: utc(f['deadline'])):
        key = f['season'], f['gw']
        if key in seen:
            raise ValueError('Duplicate decision deadline')
        seen.add(key)
        if not utc(f['forecast_available_at']) <= utc(f['archived_at']) < utc(f['deadline']) < utc(f['actual_available_at']):
            raise ValueError('Decision/outcome chronology invalid')
        if set(f['policies']) != {'rolling', 'roll', 'naive'}:
            raise ValueError('Rolling, roll and naive baselines required')
        players = {int(i): p for i, p in f['players'].items()}
        actual = {k: {int(i): v for i, v in f['actual'][k].items()} for k in ('points', 'played')}
        if set(actual['points']) != set(players) or set(actual['played']) != set(players):
            raise ValueError('Complete finalized outcome coverage required')
        if any(not number(v) for v in actual['points'].values()) or any(type(v) is not bool for v in actual['played'].values()):
            raise ValueError('Invalid actual outcomes')
        values = {}
        for name, decision in f['policies'].items():
            ids = decision['xi'] + decision['bench']
            from engine import legal_squad
            from rolling_planner import formation
            if not legal_squad(ids, players) or not formation(decision['xi'], players) or len(decision['xi']) != 11 or len(decision['bench']) != 4:
                raise ValueError('Illegal archived decision')
            if decision['captain'] == decision['vice'] or not {decision['captain'], decision['vice']} <= set(decision['xi']):
                raise ValueError('Illegal captain pair')
            if players[decision['bench'][3]]['element_type'] != 1 or any(players[i]['element_type'] == 1 for i in decision['bench'][:3]):
                raise ValueError('Bench must contain outfield priorities then reserve GK')
            if decision['chip'] not in (None, 'wildcard', 'freehit', 'bboost', '3xc'):
                raise ValueError('Unknown archived chip')
            if not number(decision['hit']) or decision['hit'] < 0 or decision['hit'] % 4:
                raise ValueError('Invalid hit')
            values[name] = score(decision['xi'], decision['bench'], decision['captain'], decision['vice'],
                                 players, actual, decision['chip']) - decision['hit']
        rows.append({'season': f['season'], 'gw': f['gw'], 'points': values,
                     'gain_vs_roll': values['rolling']-values['roll'],
                     'gain_vs_naive': values['rolling']-values['naive']})
    return {'status': 'evaluated' if rows else 'blocked_missing_decision_archive',
            'method': 'paired_predeadline_one_gw_walk_forward_audit', 'rows': rows,
            'mean_gain_vs_roll': mean(r['gain_vs_roll'] for r in rows) if rows else None,
            'mean_gain_vs_naive': mean(r['gain_vs_naive'] for r in rows) if rows else None,
            'input_sha256': digest(frames),
            'limitation': 'Does not establish continuous season performance or validate archive authenticity.'}
