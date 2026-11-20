"""Archive free independent FPL projections before the GW deadline.

FPL Cat permits free personal benchmarking; Sideline Quant publishes CC BY 4.0.
Never use ownership, rival, or Cumbres fields for optimization.
"""
import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCES = {
    "fplcat": "https://fplcat.com/api/v1/projections",
    "sidelinequant": "https://sidelinequant.com/data/latest.json",
}
FIELDS = ("player_id", "gw", "expected_points", "source", "as_of_utc")


def timestamp(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("Naive provider timestamp")
    return t


def parse_fplcat(data):
    gw = int(data["gameweek"])
    as_of = data["computed_at"]
    deadline = data["deadline"]
    rows = [{"player_id": int(p["id"]), "gw": gw,
             "expected_points": float(p["xp"]), "source": "FPL Cat",
             "as_of_utc": as_of} for p in data["players"]]
    return deadline, rows


def parse_sideline(data):
    gw = int(data["gameweek"])
    as_of = data["generated_at"]
    deadline = data["deadline"]
    entries = data.get("rows", data.get("players"))
    if not isinstance(entries, list):
        raise ValueError("Unknown Sideline Quant rows structure")
    totals = {}
    for p in entries:
        pid = int(p["player_id"])
        totals[pid] = totals.get(pid, 0.) + float(p["xP"])
    rows = [{"player_id": pid, "gw": gw, "expected_points": round(xp, 5),
             "source": "Sideline Quant", "as_of_utc": as_of}
            for pid, xp in totals.items()]
    return deadline, rows


def validate(deadline, rows):
    if not 500 <= len(rows) <= 1200:
        raise ValueError("Unexpected player coverage")
    gw = rows[0]["gw"]
    as_of = timestamp(rows[0]["as_of_utc"])
    if not 1 <= gw <= 38 or as_of >= timestamp(deadline):
        raise ValueError("Postdeadline or invalid projections")
    if as_of > datetime.now(timezone.utc):
        raise ValueError("Future-dated forecast")
    ids = [r["player_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate FPL IDs")
    if any(r["gw"] != gw or timestamp(r["as_of_utc"]) != as_of or
           not 0 <= r["expected_points"] <= 30 for r in rows):
        raise ValueError("Inconsistent forecast rows")
    return gw


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "Nicho11s-personal-FPL-research/1.0",
                                       "Accept": "application/json"}), timeout=30) as r:
        return json.load(r)


def archive(provider, data, directory):
    deadline, rows = (parse_fplcat(data) if provider == "fplcat"
                      else parse_sideline(data))
    gw = validate(deadline, rows)
    target = Path(directory) / provider / f"gw{gw:02d}"
    target.mkdir(parents=True, exist_ok=True)
    name = timestamp(rows[0]["as_of_utc"]).strftime("%Y%m%dT%H%M%SZ")
    path = target / f"{name}.csv"
    if path.exists():
        return path
    with path.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/provider-forecasts")
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    args = parser.parse_args()
    providers = SOURCES if args.source == "all" else {args.source: SOURCES[args.source]}
    succeeded = 0
    for name, url in providers.items():
        try:
            path = archive(name, fetch(url), args.output)
            print(f"{name}: {path}")
            succeeded += 1
        except Exception as exc:
            print(f"{name}: unavailable ({type(exc).__name__}: {exc})")
    if succeeded == 0:
        raise SystemExit("No usable independent provider forecasts")


if __name__ == "__main__":
    main()
