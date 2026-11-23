import unittest
from datetime import datetime, timedelta, timezone
from provider_collect import parse_fplcat, parse_sideline, validate


class ProviderTests(unittest.TestCase):
    def test_fplcat_normalization(self):
        now = datetime.now(timezone.utc)
        d = {"gameweek": 11, "computed_at": now.isoformat(),
             "deadline": (now + timedelta(days=1)).isoformat(),
             "players": [{"id": i, "xp": 3.0} for i in range(1, 601)]}
        deadline, rows = parse_fplcat(d)
        self.assertEqual(validate(deadline, rows), 11)
        self.assertEqual(rows[0]["expected_points"], 3.0)

    def test_sideline_double_fixture_aggregation(self):
        now = datetime.now(timezone.utc)
        d = {"gameweek": 11, "generated_at": now.isoformat(),
             "deadline": (now + timedelta(days=1)).isoformat(),
             "rows": [{"player_id": i, "xP": 2.0} for i in range(1, 601)] +
                     [{"player_id": 1, "xP": 3.0}]}
        deadline, rows = parse_sideline(d)
        self.assertEqual(validate(deadline, rows), 11)
        self.assertEqual(rows[0]["expected_points"], 5.0)

    def test_postdeadline_rejected(self):
        now = datetime.now(timezone.utc)
        d = {"gameweek": 11, "computed_at": now.isoformat(),
             "deadline": (now - timedelta(seconds=1)).isoformat(),
             "players": [{"id": i, "xp": 3.0} for i in range(1, 601)]}
        deadline, rows = parse_fplcat(d)
        with self.assertRaises(ValueError):
            validate(deadline, rows)


if __name__ == "__main__":
    unittest.main()
