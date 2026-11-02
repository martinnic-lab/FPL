import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import collector as c


def source(path):
    if path == 'bootstrap-static/':
        data = {'elements': [dict(id=i, now_cost=50, status='a', news='',
                 chance_of_playing_next_round=None) for i in range(1, 16)],
                'events': [dict(id=1, deadline_time='2020-01-01T12:00:00Z', finished=False)]}
    elif path == 'fixtures/':
        data = [dict(id=1, event=1, team_h=1, team_a=2, finished=False)]
    elif path.endswith('history/'):
        data = {'current': [dict(event=1, points=50, total_points=50, rank=1)], 'past': [], 'chips': []}
    elif path.endswith('transfers/'):
        data = []
    else:
        data = {'entry_history': {'event': 1}, 'picks': [dict(element=i, position=i,
                multiplier=1, is_captain=i == 1, is_vice_captain=i == 2) for i in range(1, 16)]}
    return dict(url=c.BASE + path, fetched_at=c.utcnow(), data=data)


class Tests(unittest.TestCase):
    def test_collect_and_roundtrip(self):
        snapshot = c.collect(source)
        self.assertFalse(snapshot['live_pre_deadline_team']['available'])
        self.assertEqual(snapshot['squads']['1']['status'], 'publicly_confirmed_post_deadline')
        with tempfile.TemporaryDirectory() as directory:
            target = c.save(snapshot, Path(directory))
            self.assertEqual(json.loads(target.read_text()), snapshot)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_invalid_data_never_saved(self):
        snapshot = c.collect(source)
        snapshot['squads']['1']['source']['data']['picks'].pop()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(c.CollectionError):
                c.save(snapshot, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_future_squad_rejected(self):
        snapshot = c.collect(source)
        snapshot['sources']['bootstrap']['data']['events'][0]['deadline_time'] = '2099-01-01T00:00:00Z'
        with self.assertRaises(c.CollectionError):
            c.validate(snapshot)

    def test_preseason_empty_history(self):
        def get(path):
            result = source(path)
            if path.endswith('history/'):
                result['data']['current'] = []
            return result
        self.assertEqual(c.collect(get)['squads'], {})

    def test_failed_request_aborts_collection(self):
        def get(path):
            if path.endswith('picks/'):
                raise c.CollectionError('not yet published')
            return source(path)
        with self.assertRaises(c.CollectionError):
            c.collect(get)

    @patch('collector.time.sleep')
    @patch('collector.urlopen')
    def test_retry_transient_http(self, opener, sleep):
        opener.side_effect = HTTPError('url', 503, 'unavailable', {}, None)
        with self.assertRaises(c.CollectionError):
            c.fetch('fixtures/')
        self.assertEqual(opener.call_count, 4)
        self.assertEqual(sleep.call_count, 3)

    @patch('collector.urlopen')
    def test_no_retry_permanent_http(self, opener):
        opener.side_effect = HTTPError('url', 404, 'missing', {}, None)
        with self.assertRaises(c.CollectionError):
            c.fetch('fixtures/')
        self.assertEqual(opener.call_count, 1)


if __name__ == '__main__':
    unittest.main()
