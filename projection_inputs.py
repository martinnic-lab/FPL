"""Strictly validate independent player-by-GW forecast inputs.

No league or ownership data accepted. Does not certify source calibration.
"""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path


def load_projections(path, bootstrap):
    data = json.loads(Path(path).read_text())
    allowed = {"schema_version", "source", "generated_at_utc", "gameweeks", "players"}
    if set(data) != allowed or data["schema_version"] != 1:
        raise ValueError("Invalid forecast schema; only independent point projections accepted")
    source = data["source"]
    if not isinstance(source, str) or not source.strip() or "cumbres" in source.lower():
        raise ValueError("Missing or prohibited forecast provenance")
    timestamp = datetime.fromisoformat(data["generated_at_utc"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("Forecast timestamp invalid")
    if datetime.now(timezone.utc) - timestamp > timedelta(days=3):
        raise ValueError("Forecast older than 72 hours")
    weeks = data["gameweeks"]
    if not isinstance(weeks, list) or not 1 <= len(weeks) <= 6 or len(set(weeks)) != len(weeks):
        raise ValueError("Expected 1-6 distinct gameweeks")
    events = {e["id"]: e for e in bootstrap["events"]}
    if any(type(w) is not int or w not in events or events[w]["finished"] for w in weeks):
        raise ValueError("Unknown or finished gameweek")
    if weeks != sorted(weeks):
        raise ValueError("Gameweeks must be sorted")
    known = {p["id"] for p in bootstrap["elements"]}
    rows = data["players"]
    if not isinstance(rows, dict) or set(map(int, rows)) != known:
        raise ValueError("Forecasts must cover every current official player")
    out = {}
    for raw_id, values in rows.items():
        if not isinstance(values, dict) or set(values) != {str(w) for w in weeks}:
            raise ValueError(f"Missing weeks for player {raw_id}")
        out[int(raw_id)] = {}
        for w in weeks:
            v = values[str(w)]
            if type(v) not in (int, float) or not 0 <= v <= 30:
                raise ValueError(f"Invalid points forecast for player {raw_id}, GW{w}")
            out[int(raw_id)][w] = float(v)
    return weeks, out
