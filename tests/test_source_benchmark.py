import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from source_benchmark import load_rows, benchmark


class SourceBenchmarkTests(unittest.TestCase):
    def test_common_sample_and_ranking(self):
        t = datetime(2026, 11, 21, 11, tzinfo=timezone.utc)
        forecasts = {("A", 11, 1): (t - timedelta(hours=1), 5.),
                     ("B", 11, 1): (t - timedelta(hours=1), 1.),
                     ("A", 11, 2): (t - timedelta(hours=1), 10.)}
        result = benchmark(forecasts, {11: {1: 1., 2: 0.}})
        self.assertEqual(result["common_observations"], 1)
        self.assertEqual(result["ranked_by_mae"][0], "B")

    def test_reject_postdeadline_forecasts(self):
        t = datetime(2026, 11, 21, 11, tzinfo=timezone.utc)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "data.csv"
            path.write_text("player_id,gw,expected_points,source,as_of_utc\n"
                            f"1,11,20,A,{(t + timedelta(minutes=1)).isoformat()}\n"
                            f"1,11,4,A,{(t - timedelta(hours=1)).isoformat()}\n")
            rows = load_rows([path], {11: t})
            self.assertEqual(rows[("A", 11, 1)][1], 4.)


if __name__ == "__main__":
    unittest.main()
