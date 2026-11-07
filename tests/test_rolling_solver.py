import unittest
from rolling_solver import search
from test_engine import players


class RollingTests(unittest.TestCase):
    def setUp(self):
        self.players = players()
        self.ids = [1, 2] + list(range(4, 9)) + list(range(12, 17)) + list(range(20, 23))
        self.forecasts = {i: {11: 4., 12: 4.} for i in self.players}

    def test_roll_banks_transfer(self):
        result = search(self.ids, self.players, [11, 12], self.forecasts,
                        bank=0, free_transfers=1,
                        selling_prices={i: 50 for i in self.ids},
                        beam_width=2, per_position=1)
        self.assertEqual(result["best"]["actions"][0]["out"], None)
        self.assertEqual(result["best"]["actions"][0]["free_transfers_next"], 2)

    def test_missing_selling_prices(self):
        with self.assertRaises(ValueError):
            search(self.ids, self.players, [11, 12], self.forecasts,
                   bank=0, free_transfers=1, selling_prices={})

    def test_legal_outputs(self):
        result = search(self.ids, self.players, [11, 12], self.forecasts,
                        bank=0, free_transfers=1,
                        selling_prices={i: 50 for i in self.ids},
                        beam_width=2, per_position=1)
        self.assertEqual(len(result["best"]["actions"]), 2)
        self.assertTrue(all(len(a["xi"]) == 11 for a in result["best"]["actions"]))


if __name__ == "__main__":
    unittest.main()
