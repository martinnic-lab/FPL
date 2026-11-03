import unittest
from engine import legal_squad, lineup, optimize
from chip_planner import chip_screen


def players():
    d = {}
    k = 1
    for pos, count in ((1, 3), (2, 8), (3, 8), (4, 5)):
        for j in range(count):
            d[k] = {"id": k, "element_type": pos, "team": k,
                    "now_cost": 50, "status": "a"}
            k += 1
    return d


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.p = players()
        self.ids = [1, 2] + list(range(4, 9)) + list(range(12, 17)) + list(range(20, 23))
        self.f = {i: {10: 4., 11: 4.} for i in self.p}

    def test_legal_and_club_quota(self):
        self.assertTrue(legal_squad(self.ids, self.p))
        self.assertFalse(legal_squad(self.ids[:-1], self.p))
        self.assertFalse(legal_squad(self.ids[:-1] + [self.ids[0]], self.p))

    def test_lineup_and_bench(self):
        result = lineup(self.ids, self.p, {i: 4. for i in self.ids})
        self.assertEqual(len(result["xi"]), 11)
        self.assertEqual(len(result["bench"]), 4)
        self.assertEqual(result["expected"], 48.)
        self.assertEqual(result["bench_boost_increment"], 16.)
        self.assertNotIn(result["captain"], result["bench"])

    def test_no_live_finance_no_transfers(self):
        result = optimize(self.ids, self.p, [10, 11], self.f)
        self.assertEqual(result["status"], "lineup_only")
        self.assertEqual(result["plans"], [])

    def test_affordable_and_hits(self):
        result = optimize(self.ids, self.p, [10, 11], self.f,
                          bank_tenths=0, sell_prices={i: 50 for i in self.ids},
                          free_transfers=1, shortlist=2)
        self.assertEqual(result["status"], "screening_only")
        self.assertTrue(result["plans"])
        self.assertEqual(result["plans"][0]["moves"], [])

    def test_chip_one_per_week(self):
        lineups = {"10": {"bench_boost_increment": 9, "triple_captain_increment": 5},
                   "11": {"bench_boost_increment": 8, "triple_captain_increment": 12}}
        out = chip_screen(lineups, [{"name": "wildcard", "event": 5}])
        self.assertEqual(out["top_static_assignments"][0]["chip_weeks"],
                         {"bboost": 10, "3xc": 11})
        self.assertIn("freehit", out["remaining_first_half_chips"])


if __name__ == "__main__":
    unittest.main()
