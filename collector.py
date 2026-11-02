"""Collect only unauthenticated, public Fantasy Premier League data."""
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = 'https://fantasy.premierleague.com/api/'
ENTRY = 1580840


class CollectionError(Exception):
    pass


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def require(condition, message):
    if not condition:
        raise CollectionError(message)


def rows(value, fields, label):
    require(isinstance(value, list), f'{label}: expected list')
    for row in value:
        require(isinstance(row, dict) and all(k in row for k in fields),
                f'{label}: missing required fields {fields}')
    return value


def fetch(path):
    url = BASE + path
    for attempt in range(4):
        try:
            request = Request(url, headers={'User-Agent': 'public-fpl-collector/1.0',
                                           'Accept': 'application/json'})
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
            return {'url': url, 'fetched_at': utcnow(), 'data': payload}
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise CollectionError(f'{path}: HTTP {exc.code}') from exc
            failure = f'HTTP {exc.code}'
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            failure = type(exc).__name__
        if attempt < 3:
            time.sleep(2 ** attempt)
    raise CollectionError(f'{path}: failed after 4 attempts ({failure})')


def validate(snapshot):
    sources = snapshot['sources']
    bootstrap = sources['bootstrap']['data']
    require(isinstance(bootstrap, dict), 'bootstrap: expected object')
    players = rows(bootstrap.get('elements'), ('id', 'now_cost', 'status', 'news',
                   'chance_of_playing_next_round'), 'players')
    require(players, 'players: empty response')
    player_ids = {p['id'] for p in players}
    require(len(player_ids) == len(players), 'players: duplicate IDs')
    events = rows(bootstrap.get('events'), ('id', 'deadline_time', 'finished'), 'events')
    require(events, 'events: empty response')
    for event in events:
        datetime.fromisoformat(event['deadline_time'].replace('Z', '+00:00'))
    rows(sources['fixtures']['data'], ('id', 'event', 'team_h', 'team_a', 'finished'), 'fixtures')
    history = sources['history']['data']
    require(isinstance(history, dict), 'history: expected object')
    results = rows(history.get('current'), ('event', 'points', 'total_points', 'rank'), 'results')
    rows(history.get('past'), ('season_name', 'total_points'), 'past results')
    rows(history.get('chips'), ('name', 'event'), 'chips')
    rows(sources['transfers']['data'], ('event', 'element_in', 'element_out', 'time',
                                       'element_in_cost', 'element_out_cost'), 'transfers')
    require(set(snapshot['squads']) == {str(r['event']) for r in results},
            'squads must cover every published entry result')
    event_map = {e['id']: e for e in events}
    for key, squad in snapshot['squads'].items():
        event = int(key)
        require(event in event_map, 'unknown squad gameweek')
        require(datetime.fromisoformat(event_map[event]['deadline_time'].replace('Z', '+00:00'))
                <= datetime.fromisoformat(snapshot['started_at'].replace('Z', '+00:00')),
                'refusing pre-deadline squad')
        data = squad['source']['data']
        require(isinstance(data, dict), 'picks: expected object')
        require(data.get('entry_history', {}).get('event') == event, 'picks: event mismatch')
        picks = rows(data.get('picks'), ('element', 'position', 'multiplier', 'is_captain',
                                        'is_vice_captain'), 'picks')
        require(len(picks) == 15 and len({p['element'] for p in picks}) == 15,
                'picks: expected 15 distinct players')
        require({p['position'] for p in picks} == set(range(1, 16)), 'picks: invalid positions')
        require(all(p['element'] in player_ids for p in picks), 'picks: unknown player')
        require(sum(p['is_captain'] is True for p in picks) == 1 and
                sum(p['is_vice_captain'] is True for p in picks) == 1, 'picks: invalid captains')


def collect(get=fetch):
    snapshot = {'schema_version': 1, 'entry_id': ENTRY, 'started_at': utcnow(),
                'live_pre_deadline_team': {'available': False,
                    'reason': 'Not exposed by the official public API; never inferred from transfers or old picks.'},
                'sources': {}, 'squads': {}}
    for name, path in [('bootstrap', 'bootstrap-static/'), ('fixtures', 'fixtures/'),
                       ('history', f'entry/{ENTRY}/history/'),
                       ('transfers', f'entry/{ENTRY}/transfers/')]:
        snapshot['sources'][name] = get(path)
    history = snapshot['sources']['history']['data']
    require(isinstance(history, dict), 'history: expected object')
    results = rows(history.get('current'), ('event',), 'results')
    for result in results:
        event = result['event']
        require(type(event) is int and 1 <= event <= 38, 'invalid gameweek')
        snapshot['squads'][str(event)] = {
            'status': 'publicly_confirmed_post_deadline',
            'results_note': 'Points, ranks, multipliers and automatic substitutions may change until finalized.',
            'source': get(f'entry/{ENTRY}/event/{event}/picks/')}
    snapshot['completed_at'] = utcnow()
    validate(snapshot)
    return snapshot


def save(snapshot, directory):
    validate(snapshot)
    directory.mkdir(parents=True, exist_ok=True)
    name = snapshot['completed_at'].replace(':', '').replace('.', '-') + '.json'
    target = directory / name
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            json.dump(snapshot, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.write('\n')
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/snapshots'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    try:
        logging.info('Saved %s', save(collect(), args.output))
    except (CollectionError, OSError, ValueError, KeyError, TypeError) as exc:
        logging.error('Collection failed; no snapshot published: %s', exc)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
