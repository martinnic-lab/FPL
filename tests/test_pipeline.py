import copy
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch

import collector
import summary
from forecasting import COMPONENTS
from research_runner import freshness, research
from test_collector import source
from test_engine import players
from decision_audit import evaluate


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)
        self.snapshot = collector.collect(source)
        self.ids = [1, 2] + list(range(4, 9)) + list(range(12, 17)) + list(range(20, 23))
        self.p = {i: dict(p, web_name=str(i), news='', chance_of_playing_next_round=None) for i, p in players().items() if i in self.ids+[23]}
        self.snapshot['completed_at'] = self.snapshot['started_at'] = self.now.isoformat()
        for s in self.snapshot['sources'].values():
            s['fetched_at'] = self.now.isoformat()
        b = self.snapshot['sources']['bootstrap']['data']
        b['elements'] = list(self.p.values())
        b['teams'] = [dict(id=i, short_name=str(i)) for i in self.p]
        b['events'] = [dict(id=1, deadline_time='2026-08-01T00:00:00Z', finished=True, is_current=True)] + [
            dict(id=g, deadline_time=(self.now+timedelta(days=g-9)).isoformat(), finished=False, is_next=g==10)
            for g in range(10, 16)]
        for pick, i in zip(self.snapshot['squads']['1']['source']['data']['picks'], self.ids):
            pick['element'] = i
        self.summary = summary.build(self.snapshot)
        rows = []
        for g in range(10, 16):
            for i in self.p:
                rows.append(dict(season='2026/27', gw=g, player=i, model='synthetic-test-only',
                                 source_url='https://example.test/fixture', published_at=self.now.isoformat(),
                                 retrieved_at=self.now.isoformat(), deadline=b['events'][g-9]['deadline_time'],
                                 xpts=4., expected_minutes=90., start_probability=1.,
                                 components={c: 4. if c=='appearance' else 0. for c in COMPONENTS}))
        self.bundle = dict(forecasts=rows, prices={str(g): {str(i): 50 for i in self.p} for g in range(10, 16)},
                           live=dict(verified_at=self.now.isoformat(), squad_ids=self.ids, bank=0, ft=1,
                                     purchase_prices={str(i):50 for i in self.ids}, selling_prices={str(i):50 for i in self.ids},
                                     used_chips=[], confirmed=True),
                           news=[dict(player=i, source_url='https://example.test/news', reviewed_at=self.now.isoformat()) for i in self.p],
                           chips=[], weights=[1.]*6, max_transfers=0,
                           scenarios={str(g):dict(source_url='https://example.test/scenarios', published_at=self.now.isoformat(),
                                                 retrieved_at=self.now.isoformat(), values=[dict(probability=1., points={str(i):4. for i in self.p}, played={str(i):True for i in self.p})]) for g in range(10, 16)})

    def test_end_to_end_and_cumbres_invariance(self):
        a = research(self.snapshot, self.summary, self.bundle, self.now)
        changed = copy.deepcopy(self.snapshot)
        changed['cumbres'] = dict(rival_captain=23, standings=[999])
        b = research(changed, self.summary, self.bundle, self.now)
        self.assertEqual(a['alternatives'], b['alternatives'])
        self.assertEqual(a['acceptance'], 'research_informed_provisional')
        self.assertEqual(a['weeks'], list(range(10, 16)))

    def test_missing_and_contaminated_sources_block(self):
        for change in ('missing', 'rival', 'inconsistent', 'live', 'news'):
            bundle = copy.deepcopy(self.bundle)
            if change == 'missing':
                bundle['forecasts'].pop()
            elif change == 'rival':
                bundle['cumbres'] = {}
            elif change == 'inconsistent':
                bundle['scenarios']['10']['values'][0]['points']['1'] = 30.
            elif change == 'live':
                bundle['live']['confirmed'] = False
            else:
                bundle['news'] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                research(self.snapshot, self.summary, bundle, self.now)

    def test_staleness_and_summary_mismatch(self):
        with self.assertRaises(ValueError):
            freshness(self.snapshot, self.summary, self.now+timedelta(hours=13))
        altered = dict(self.summary, current_gameweek_finished=False)
        with self.assertRaises(ValueError):
            freshness(self.snapshot, altered, self.now)

    def test_real_history_not_invented(self):
        from forecasting import walk_forward
        self.assertEqual(walk_forward([])['status'], 'blocked_insufficient_history')
        self.assertEqual(evaluate([])['status'], 'blocked_missing_decision_archive')

    def test_paired_decision_audit_and_leakage(self):
        from rolling_planner import best_lineup
        s = dict(probability=1., points={i:4. for i in self.p}, played={i:True for i in self.p})
        lineup = best_lineup(self.ids, self.p, [s])
        decision = {k:lineup[k] for k in ('xi','bench','captain','vice')}
        decision.update(chip=None, hit=0)
        frame = dict(season='2026/27', gw=10, deadline='2026-11-07T12:00:00Z',
                     forecast_available_at=self.now.isoformat(), archived_at=self.now.isoformat(),
                     actual_available_at='2026-11-10T00:00:00Z', players=self.p, actual=s,
                     policies={p:decision for p in ('rolling','roll','naive')})
        self.assertEqual(evaluate([frame])['mean_gain_vs_roll'], 0.)
        frame['archived_at'] = '2026-11-08T00:00:00Z'
        with self.assertRaises(ValueError):
            evaluate([frame])
