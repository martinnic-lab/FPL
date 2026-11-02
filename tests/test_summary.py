"""Unit tests for compact report gameweek state and squad provenance."""
import unittest
from summary import build

class SummaryTests(unittest.TestCase):
    def test_live_gameweek_not_mistaken_for_finished(self):
        player = {"id": 1, "web_name": "Example", "team": 1, "now_cost": 50,
                  "status": "a", "news": "", "chance_of_playing_next_round": None}
        events = [{"id": 9, "deadline_time": "2026-10-30T18:30:00Z",
                   "is_current": True, "is_next": False, "finished": False,
                   "data_checked": False},
                  {"id": 10, "deadline_time": "2026-11-06T18:30:00Z",
                   "is_current": False, "is_next": True, "finished": False}]
        snapshot = {"entry_id": 1580840, "completed_at": "2026-11-02T12:36:38Z",
                    "sources": {"bootstrap": {"data": {"elements": [player],
                    "teams": [{"id": 1, "short_name": "TST"}], "events": events}},
                    "history": {"data": {"current": [{"event": 9, "points": 50}],
                    "chips": []}}, "transfers": {"data": []}},
                    "squads": {}}
        result = build(snapshot)
        self.assertEqual(result["current_gameweek"], 9)
        self.assertIs(result["current_gameweek_finished"], False)
        self.assertEqual(result["next_gameweek"], 10)
        self.assertIs(result["live_predeadline_team_verified"], False)
        self.assertIs(result["current_bank_verified"], False)

if __name__ == "__main__":
    unittest.main()
