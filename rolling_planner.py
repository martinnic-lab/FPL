"""Exact finite-universe rolling planner using supplied joint points/appearance scenarios.

All data arguments are typed/allowlisted by research_runner. No network or league
input. Search limits fail explicitly; no truncated search is called an optimum.
"""
from functools import lru_cache
from itertools import combinations, permutations
from math import isclose
from forecasting import number
from engine import legal_squad, FORMATION, POSITIONS
from planning_rules import State, selling_price, next_ft, chip_allowed


def formation(ids, players):
    return (sum(players[i]['element_type'] == 1 for i in ids) == 1 and
            all(FORMATION[p][0] <= sum(players[i]['element_type'] == p for i in ids)
                <= FORMATION[p][1] for p in FORMATION))


def score(xi, bench, captain, vice, players, scenario, chip=None):
    """Resolve deterministic scenario: ordered outfield subs, GK and armband.

    An absent starter retains its nominal formation slot if not substituted.
    Enumerate assignments so simultaneous absences do not cause greedy errors.
    """
    points, played = scenario['points'], scenario['played']
    active = [i for i in xi if played[i]]
    if chip == 'bboost':
        active = list(xi) + list(bench)
    else:
        keeper = next(i for i in xi if players[i]['element_type'] == 1)
        if not played[keeper] and played[bench[3]]:
            active.append(bench[3])
        absent = [i for i in xi if not played[i] and players[i]['element_type'] != 1]
        available = [i for i in bench[:3] if played[i]]
        chosen = ()
        for n in range(min(len(absent), len(available)), 0, -1):
            found = False
            for subs in combinations(available, n):
                for removed in combinations(absent, n):
                    template = [i for i in xi if i not in removed] + list(subs)
                    if formation(template, players):
                        chosen, found = subs, True
                        break
                if found:
                    break
            if found:
                break
        active.extend(chosen)
    armband = captain if played[captain] else vice if played[vice] else None
    return sum(points[i] for i in active) + (2 if chip == '3xc' else 1) * (points[armband] if armband else 0)


def best_lineup(ids, players, scenarios, chip=None):
    if not legal_squad(ids, players):
        raise ValueError('Illegal squad')
    if not scenarios or not isclose(sum(s['probability'] for s in scenarios), 1., abs_tol=1e-8):
        raise ValueError('Scenario probabilities must sum to one')
    ids = tuple(sorted(ids))
    gks = [i for i in ids if players[i]['element_type'] == 1]
    out = [i for i in ids if i not in gks]
    best = None
    for keeper in gks:
        for group in combinations(out, 10):
            xi = (keeper,) + group
            if not formation(xi, players):
                continue
            # Captain fallback is independent of auto-sub choice.
            captain, vice = max(permutations(xi, 2), key=lambda pair: sum(
                s['probability'] * (s['points'][pair[0]] if s['played'][pair[0]] else
                                    s['points'][pair[1]] if s['played'][pair[1]] else 0)
                for s in scenarios))
            remaining = [i for i in out if i not in xi]
            for order in permutations(remaining):
                bench = order + (next(i for i in gks if i != keeper),)
                values = [score(xi, bench, captain, vice, players, s, chip) for s in scenarios]
                expected = sum(s['probability'] * v for s, v in zip(scenarios, values))
                if best is None or expected > best['expected']:
                    best = {'xi': list(xi), 'bench': list(bench), 'captain': captain,
                            'vice': vice, 'expected': expected,
                            'scenario_min': min(values), 'scenario_max': max(values)}
    return best


class SearchLimit(RuntimeError):
    pass


def solve(initial, players, weeks, scenarios, prices, *, max_transfers=2,
          chips=(), weights=None, state_limit=10000, action_limit=100000):
    """Exhaustive DP over declared candidate universe and weekly transfer cap.

    Prices are explicit conditional paths, not price forecasts. Lineups reoptimize
    each GW; transfer plans assume current forecasts (receding horizon). WC/FH
    enumerate complete legal squads. No terminal FT/chip value is manufactured.
    """
    if not weeks or weeks != list(range(weeks[0], weeks[0] + len(weeks))) or len(weeks) > 6:
        raise ValueError('Consecutive horizon of 1-6 GWs required')
    if type(max_transfers) is not int or not 0 <= max_transfers <= 15 or not set(chips) <= {'wildcard', 'freehit', 'bboost', '3xc'}:
        raise ValueError('Invalid action limits')
    weights = weights or [1.] * len(weeks)
    if len(weights) != len(weeks) or any(not 0 < w <= 1 for w in weights):
        raise ValueError('Explicit positive discount weights required')
    if not legal_squad([i for i, _ in initial.holdings], players) or initial.bank < 0:
        raise ValueError('Invalid initial state')
    next_ft(initial.ft, 0)
    for purchase in dict(initial.holdings).values():
        selling_price(purchase, purchase)
    for gw in weeks:
        if set(prices[gw]) != set(players) or any(type(v) is not int or v < 0 for v in prices[gw].values()):
            raise ValueError('Complete integer market-price path required')
        for s in scenarios[gw]:
            if set(s['points']) != set(players) or set(s['played']) != set(players):
                raise ValueError('Complete scenario coverage required')
            if (not number(s['probability']) or not 0 <= s['probability'] <= 1 or
                any(not number(v) for v in s['points'].values()) or
                any(type(v) is not bool for v in s['played'].values()) or
                any(s['points'][i] != 0 and not s['played'][i] for i in players)):
                raise ValueError('Invalid scenario values')
    visited = 0
    examined = 0

    @lru_cache(None)
    def lineup(ids, gw, chip):
        return best_lineup(ids, players, scenarios[gw], chip)

    def actions(state, gw):
        nonlocal examined
        owned = dict(state.holdings)
        ids = set(owned)
        market = prices[gw]
        for chip in (None,) + tuple(chips):
            if not chip_allowed(gw, chip, state.used):
                continue
            if chip in ('wildcard', 'freehit'):
                targets = combinations(sorted(players), 15)
            else:
                def normal():
                    yield tuple(sorted(ids))
                    for n in range(1, min(max_transfers, len(players)-15) + 1):
                        for outgoing in combinations(sorted(ids), n):
                            for incoming in combinations(sorted(set(players)-ids), n):
                                yield tuple(sorted((ids-set(outgoing)) | set(incoming)))
                targets = normal()
            for target in targets:
                examined += 1
                if examined > action_limit:
                    raise SearchLimit('Action limit exceeded; no optimum published')
                if not legal_squad(target, players):
                    continue
                incoming, outgoing = set(target)-ids, ids-set(target)
                bank = state.bank + sum(selling_price(owned[i], market[i]) for i in outgoing) - sum(market[i] for i in incoming)
                if bank < 0:
                    continue
                holdings = tuple((i, owned[i] if i in owned else market[i]) for i in target)
                hit = 0 if chip in ('wildcard', 'freehit') else 4 * max(0, len(incoming)-state.ft)
                used = tuple(sorted(state.used + ((gw, chip),))) if chip else state.used
                after = State(state.holdings if chip == 'freehit' else holdings,
                              state.bank if chip == 'freehit' else bank,
                              next_ft(state.ft, len(incoming), chip), used)
                l = lineup(tuple(target), gw, chip)
                yield after, {'gw': gw, 'in': sorted(incoming), 'out': sorted(outgoing),
                              'chip': chip, 'hit': hit, 'bank': bank, 'next_ft': after.ft,
                              'lineup': l}

    @lru_cache(None)
    def future(j, state):
        nonlocal visited
        if j == len(weeks):
            return 0., ()
        visited += 1
        if visited > state_limit:
            raise SearchLimit('State limit exceeded; no optimum published')
        best = None
        for after, action in actions(state, weeks[j]):
            tail, plan = future(j+1, after)
            value = weights[j] * (action['lineup']['expected'] - action['hit']) + tail
            if best is None or value > best[0]:
                best = value, (action,) + plan
        if best is None:
            raise ValueError('No feasible continuation')
        return best

    alternatives = []
    for after, action in actions(initial, weeks[0]):
        tail, plan = future(1, after)
        value = weights[0] * (action['lineup']['expected']-action['hit']) + tail
        alternatives.append({'objective': value, 'plan': [action] + list(plan)})
    alternatives.sort(key=lambda r: r['objective'], reverse=True)
    roll = next(r for r in alternatives if not r['plan'][0]['in'] and not r['plan'][0]['chip'])
    selected = alternatives[:3]
    if roll not in selected:
        selected.append(roll)
    for r in selected:
        r['gain_vs_roll_then_optimize'] = r['objective'] - roll['objective']
    return {'status': 'conditional_finite_universe_optimum', 'alternatives': selected,
            'states': visited, 'actions_examined': examined, 'candidate_ids': sorted(players), 'max_transfers_per_week': max_transfers,
            'weights': weights, 'weeks': weeks,
            'limitations': ['Conditional on supplied joint scenarios and market-price path.',
                            'No terminal FT or chip value beyond horizon; not a season optimum.',
                            'Scenario range is not a calibrated confidence interval.',
                            'Wildcard/Free Hit only searched if explicitly enabled.',
                            'Research-informed provisional until real forecast and decision backtests pass.']}
