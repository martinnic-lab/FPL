import unittest
from datetime import datetime, timedelta, timezone
from calibration import select_predeadline, evaluate, calibrate


def snapshot(gw, fetched, deadline, prediction):
    return {"sources": {"bootstrap": {"fetched_at": fetched.isoformat(),
        "data": {"events": [{"id": gw, "is_next": True,
                             "deadline_time": deadline.isoformat()}],
                 "elements": [{"id": 1, "element_type": 1, "ep_next": prediction}]}}}}


class CalibrationTests(unittest.TestCase):
    def test_last_predeadline_only(self):
        deadline = datetime(2026, 11, 21, 11, tzinfo=timezone.utc)
        snaps = [snapshot(11, deadline - timedelta(days=2), deadline, 2),
                 snapshot(11, deadline - timedelta(hours=1), deadline, 3),
                 snapshot(11, deadline + timedelta(hours=1), deadline, 100)]
        chosen = select_predeadline(snaps)
        self.assertEqual(chosen[11][1]["elements"][0]["ep_next"], 3)

    def test_next_week_only(self):
        deadline = datetime(2026, 11, 21, 11, tzinfo=timezone.utc)
        s = snapshot(11, deadline - timedelta(hours=1), deadline, 3)
        s["sources"]["bootstrap"]["data"]["events"].append({
            "id": 12, "is_next": False,
            "deadline_time": (deadline + timedelta(days=7)).isoformat()})
        self.assertEqual(set(select_predeadline([s])), {11})

    def test_walk_forward_does_not_use_future_targets(self):
        deadline = datetime(2026, 11, 21, 11, tzinfo=timezone.utc)
        chosen = {gw: (deadline, {"elements": [
            {"id": 1, "element_type": 1, "ep_next": 4}]}) for gw in range(1, 5)}
        targets = {1: {1: 0}, 2: {1: 0}, 3: {1: 0}, 4: {1: 10}}
        result = evaluate(chosen, targets, min_train=3)
        self.assertEqual(result["calibrated"]["n"], 1)
        self.assertLess(calibrate(4, 1, {1: [(4, 0)] * 3}), 4)
        self.assertEqual(result["per_gameweek"][0]["evaluated"], False)


if __name__ == "__main__":
    unittest.main()
