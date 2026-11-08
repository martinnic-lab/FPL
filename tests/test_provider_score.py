import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from provider_score import run


class ProviderScoreTests(unittest.TestCase):
    @patch("provider_score.fetch_final_points", return_value={1: 3.0, 2: 2.0})
    def test_three_way_equal_sample(self, fetch):
        now = datetime.now(timezone.utc)
        deadline = now - timedelta(days=1)
        asof = deadline - timedelta(hours=2)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            snap = {"sources": {"bootstrap": {"fetched_at": asof.isoformat(),
                "data": {"events": [{"id": 11, "deadline_time": deadline.isoformat(),
                                     "is_next": True, "finished": True,
                                     "data_checked": True}],
                         "elements": [{"id": 1, "element_type": 3, "ep_next": "3"},
                                      {"id": 2, "element_type": 2, "ep_next": "2"}]}}}}
            (snapshots / "one.json").write_text(json.dumps(snap))
            forecasts = root / "forecasts"
            for source, predicted in (("fplcat", 3.0), ("sidelinequant", 2.0)):
                path = forecasts / source / "gw11"
                path.mkdir(parents=True)
                (path / "one.csv").write_text(
                    "player_id,gw,expected_points,source,as_of_utc\n" +
                    "".join(f"{i},11,{predicted},{source},{asof.isoformat()}\n"
                            for i in (1, 2)))
            result = run(snapshots, forecasts)
            self.assertEqual(result["status"], "evaluated")
            self.assertEqual(result["common_observations"], 2)
            self.assertEqual(len(result["scores"]), 3)
            fetch.assert_called_once_with(11)


if __name__ == "__main__":
    unittest.main()
