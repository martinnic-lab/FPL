import copy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from forecasting import COMPONENTS, validate_rows, walk_forward
from planning_rules import State, chip_allowed, next_ft, selling_price
from rolling_planner import best_lineup, score, solve, SearchLimit
from test_engine import players


class RulesTests(unittest.TestCase):
    def test_ft_and_prices(self):
        self.assertEqual([next_ft(1, 0), next_ft(5, 0), next_ft(1, 3)], [2, 5, 1])
        self.assertEqual(next_ft(3, 10, 'wildcard'), 3)
        self.assertEqual(next_ft(3, 10, 'freehit'), 3)
        self.assertEqual([selling_price(75, p) for p in (74, 75, 76, 77, 78)], [74, 75, 75, 76, 76])
        with self.assertRaises(ValueError):
            next_ft(6, 0)

    def test_chips_expiry_reset_and_adjacency(self):
        used = ((5, 'wildcard'), (19, 'freehit'))
        self.assertFalse(chip_allowed(19, 'wildcard', used))
        self.assertTrue(chip_allowed(20, 'wildcard', used))
        self.assertFalse(chip_allowed(20, 'freehit', used))
        self.assertTrue(chip_allowed(21, 'freehit', used))
        self.assertFalse(chip_allowed(1, 'freehit', ()))
        self.assertFalse(chip_allowed(10, 'bboost', ((10, '3xc'),)))


class ForecastTests(unittest.TestCase):
    def row(self):
        return dict(season='2026/27', gw=10, player=1, model='test-fixture',
                    source_url='https://example.test/forecast', published_at='2026-11-05T00:00:00Z',
                    retrieved_at='2026-11-05T01:00:00Z', deadline='2026-11-06T18:30:00Z',
                    xpts=4., expected_minutes=80., start_probability=.9,
                    components={c: 4. if c == 'appearance' else 0. for c in COMPONENTS})

    def test_provenance_no_missing_or_rival_fields(self):
        row = self.row()
        now = datetime(2026, 11, 6, tzinfo=timezone.utc)
        validate_rows([row], {1}, now)
        for key, value in [('xpts', float('nan')), ('retrieved_at', '2026-11-07T00:00:00Z'), ('cumbres_ownership', .8)]:
            bad = dict(row, **{key: value})
            with self.assertRaises(ValueError):
                validate_rows([bad], {1}, now)
        with self.assertRaises(ValueError):
            validate_rows([row, row], {1}, now)

    def test_walk_forward_no_same_fold_or_late_results_leakage(self):
        records = []
        for gw in (1, 2, 3):
            records.append(dict(self.row(), gw=gw, deadline=f'2026-11-{gw+10:02d}T00:00:00Z',
                                actual=6., actual_available_at=f'2026-11-{gw+11:02d}T00:00:00Z'))
        result = walk_forward(records, min_train=1)
        self.assertEqual(len(result['folds']), 1)  # GW1 finalized at GW2 deadline, not before
        self.assertEqual(result['folds'][0]['train_n'], 1)
        self.assertEqual(result['metrics']['calibrated']['mae'], 0.)
        changed = copy.deepcopy(records)
        changed[-1]['actual'] = 99.
        self.assertEqual(walk_forward(changed, 1)['folds'][0]['bias'], 2.)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.all = players()
        self.ids = [1, 2] + list(range(4, 9)) + list(range(12, 17)) + list(range(20, 23))
        self.p = {i: self.all[i] for i in self.ids + [23]}
        self.s = dict(probability=1., points={i: 4. for i in self.p}, played={i: True for i in self.p})
        self.state = State(tuple((i, 50) for i in self.ids), 0, 1)

    def test_auto_sub_and_captain_fallback(self):
        xi = [1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 22]
        bench = [16, 7, 8, 2]
        s = copy.deepcopy(self.s)
        s['played'][4] = False
        s['points'][4] = 0
        s['points'][16] = 100  # MID cannot replace absent DEF in a three-DEF XI
        self.assertEqual(score(xi, bench, 4, 20, self.p, s), 48.)
        self.assertEqual(score(xi, bench, 4, 20, self.p, s, '3xc'), 52.)
        self.assertEqual(score(xi, bench, 4, 20, self.p, s, 'bboost'), 156.)
        s['played'][1], s['points'][1] = False, 0
        self.assertEqual(score(xi, bench, 4, 20, self.p, s), 48.)

    def test_rolling_and_transfer_search(self):
        # Real lineups, small universe: future upgraded striker justifies a transfer.
        s2 = copy.deepcopy(self.s)
        s2['points'][23] = 12.
        out = solve(self.state, self.p, [10, 11], {10: self.s_list(), 11: [s2]},
                    {g: {i: 50 for i in self.p} for g in (10, 11)})
        self.assertGreaterEqual(out['alternatives'][0]['gain_vs_roll_then_optimize'], 0)
        self.assertTrue(any(not r['plan'][0]['in'] and not r['plan'][0]['chip'] for r in out['alternatives']))
        self.assertEqual(len(out['alternatives'][0]['plan']), 2)

    def s_list(self):
        return [copy.deepcopy(self.s)]

    def test_six_gw_ft_banking_and_limit(self):
        # State-machine test isolates banking; lineup accuracy is tested separately.
        def quick(ids, players, scenarios, chip):
            return {'expected': 10., 'xi': list(ids[:11]), 'bench': list(ids[11:]), 'captain': ids[0], 'vice': ids[1]}
        weeks = list(range(10, 16))
        with patch('rolling_planner.best_lineup', quick):
            out = solve(self.state, self.p, weeks, {g: self.s_list() for g in weeks},
                        {g: {i: 50 for i in self.p} for g in weeks}, max_transfers=0)
            self.assertEqual([a['next_ft'] for a in out['alternatives'][0]['plan']], [2, 3, 4, 5, 5, 5])
            with self.assertRaises(SearchLimit):
                solve(self.state, self.p, weeks, {g: self.s_list() for g in weeks},
                      {g: {i: 50 for i in self.p} for g in weeks}, state_limit=1)

    def test_freehit_restores_holdings_and_bank(self):
        def quick(ids, players, scenarios, chip):
            return {'expected': 100. if 23 in ids else 0.}
        prices = {g: {i: 50 for i in self.p} for g in (19, 20)}
        with patch('rolling_planner.best_lineup', quick):
            out = solve(self.state, self.p, [19, 20], {19: self.s_list(), 20: self.s_list()}, prices,
                        max_transfers=0, chips=('freehit',))
        fh = next(r for r in out['alternatives'] if r['plan'][0]['chip'] == 'freehit')
        self.assertIn(23, fh['plan'][0]['in'])
        self.assertEqual(fh['plan'][1]['lineup']['expected'], 0.)
        self.assertEqual(fh['plan'][1]['bank'], 0)

    def test_two_transfers_and_banking_opportunity_cost(self):
        # Hand-computable state/transfer oracle: taking +2 now costs a future
        # four-point hit; rolling enables the +20 double move next week for free.
        p = {i:self.all[i] for i in self.ids + [23, 24]}
        p[25] = dict(self.all[24], id=25, team=25)
        scenarios = {}
        prices = {}
        for g in (10, 11):
            pts = {i:0. for i in p}
            pts.update({23:2., 24:0., 25:0.} if g==10 else {23:0., 24:10., 25:10.})
            scenarios[g] = [dict(probability=1., points=pts, played={i:True for i in p})]
            prices[g] = {i:50 for i in p}
        def quick(ids, players, scenarios, chip):
            return {'expected':sum(scenarios[0]['points'][i] for i in ids)}
        with patch('rolling_planner.best_lineup', quick):
            out = solve(self.state, p, [10, 11], scenarios, prices)
        best = out['alternatives'][0]
        self.assertEqual(best['objective'], 20.)
        self.assertEqual(best['plan'][0]['in'], [])
        self.assertEqual(best['plan'][1]['in'], [24, 25])
        self.assertEqual(best['plan'][1]['hit'], 0)
        one = State(self.state.holdings, 0, 1)
        with patch('rolling_planner.best_lineup', quick):
            out = solve(one, p, [11], {11:scenarios[11]}, {11:prices[11]})
        self.assertEqual(out['alternatives'][0]['plan'][0]['hit'], 4)
        self.assertEqual(out['alternatives'][0]['objective'], 16.)


if __name__ == '__main__':
    unittest.main()
