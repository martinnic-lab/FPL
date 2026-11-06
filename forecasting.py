"""Point-in-time forecast ingestion and expanding-window calibration. No fallback xPts.

The input is an explicit allowlist: league/rival fields cannot enter the model.
Calibration is an auditable additive bias correction, not a component forecaster.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from statistics import mean


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('UTC timestamp required')
    return result


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


FIELDS = {'season', 'gw', 'player', 'model', 'source_url', 'published_at',
          'retrieved_at', 'deadline', 'xpts', 'expected_minutes', 'start_probability',
          'components'}
COMPONENTS = {'appearance', 'goals', 'assists', 'clean_sheet', 'conceded',
              'saves', 'penalties', 'cards', 'bonus', 'defensive_contribution', 'own_goals'}


def validate_rows(rows, known_players, as_of):
    """Require complete source-backed GW totals, including double/blank GWs."""
    seen = set()
    for row in rows:
        if set(row) != FIELDS:
            raise ValueError('Forecast fields must match allowlist')
        key = row['season'], row['gw'], row['player'], row['model']
        if key in seen or row['player'] not in known_players:
            raise ValueError('Duplicate or unknown forecast player')
        seen.add(key)
        if type(row['gw']) is not int or not 1 <= row['gw'] <= 38:
            raise ValueError('Invalid gameweek')
        if not all(isinstance(row[k], str) and row[k] for k in ('season', 'model')):
            raise ValueError('Missing model/season')
        if not row['source_url'].startswith('https://'):
            raise ValueError('HTTPS source required')
        published, retrieved, deadline = map(utc, (row['published_at'], row['retrieved_at'], row['deadline']))
        if not published <= retrieved <= as_of < deadline:
            raise ValueError('Forecast unavailable at decision time or deadline passed')
        if not number(row['xpts']) or not number(row['expected_minutes']) or row['expected_minutes'] < 0:
            raise ValueError('Invalid forecast numbers')
        if not number(row['start_probability']) or not 0 <= row['start_probability'] <= 1:
            raise ValueError('Invalid starting probability')
        components = row['components']
        if set(components) != COMPONENTS or not all(number(v) for v in components.values()):
            raise ValueError('All scoring components, including defensive contributions, required')
        if not math.isclose(sum(components.values()), row['xpts'], abs_tol=1e-6):
            raise ValueError('Components do not reconcile to xPts')
    return rows


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def walk_forward(records, min_train=20):
    """Evaluate bias correction using only earlier, finalized outcomes.

    Records carry forecast provenance plus actual/actual_available_at. Equal-deadline
    rows form one fold; no player in a fold can train another player in that fold.
    Raw and corrected MAE/RMSE are returned; no assumed accuracy or ensemble weights.
    """
    if min_train < 1:
        raise ValueError('Positive training minimum required')
    keys = set()
    for r in records:
        key = r['season'], r['gw'], r['player'], r['model']
        if key in keys or not number(r['actual']) or not number(r['xpts']):
            raise ValueError('Duplicate or invalid evaluation record')
        keys.add(key)
        if not utc(r['published_at']) <= utc(r['retrieved_at']) < utc(r['deadline']) < utc(r['actual_available_at']):
            raise ValueError('Outcome/forecast chronology invalid')
    folds = []
    for deadline in sorted({r['deadline'] for r in records}, key=utc):
        for model in sorted({r['model'] for r in records}):
            train = [r for r in records if r['model'] == model and
                     utc(r['deadline']) < utc(deadline) and utc(r['actual_available_at']) < utc(deadline)]
            test = [r for r in records if r['deadline'] == deadline and r['model'] == model]
            if len(train) < min_train:
                continue
            bias = mean(r['actual'] - r['xpts'] for r in train)
            for r in test:
                folds.append({'season': r['season'], 'gw': r['gw'], 'player': r['player'],
                              'model': model, 'deadline': deadline, 'train_n': len(train),
                              'bias': bias, 'raw': r['xpts'], 'calibrated': r['xpts'] + bias,
                              'actual': r['actual']})
    metrics = {}
    for name in ('raw', 'calibrated'):
        errors = [r[name] - r['actual'] for r in folds]
        metrics[name] = {'mae': mean(map(abs, errors)),
                         'rmse': math.sqrt(mean(e*e for e in errors))} if errors else None
    return {'status': 'evaluated' if folds else 'blocked_insufficient_history',
            'folds': folds, 'metrics': metrics, 'input_sha256': digest(records),
            'method': 'expanding_window_model_bias_correction',
            'limitations': ['No empirical calibration claim without real held-out folds.',
                            'No ensemble or uncertainty calibration is inferred.']}
