"""Compare frozen predeadline third-party forecasts against finalized FPL points.

Input files are user-authorized CSV exports, never scraped from protected pages.
CSV columns: player_id,gw,expected_points,source,as_of_utc.
One row per player per GW per source; immutable snapshot files in inputs/.
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from calibration import metrics


def load_rows(paths, deadlines):
    forecasts = {}
    for path in paths:
        with Path(path).open(newline="") as handle:
            for row in csv.DictReader(handle):
                if set(("player_id", "gw", "expected_points", "source", "as_of_utc")) - set(row):
                    raise ValueError("Missing required CSV columns")
                gw, pid = int(row["gw"]), int(row["player_id"])
                source = row["source"].strip()
                if not source or "cumbres" in source.lower():
                    raise ValueError("Invalid source")
                as_of = datetime.fromisoformat(row["as_of_utc"].replace("Z", "+00:00"))
                if as_of.tzinfo is None:
                    raise ValueError("Timestamp must include timezone")
                if gw not in deadlines or as_of >= deadlines[gw]:
                    continue
                expected = float(row["expected_points"])
                if not math.isfinite(expected) or not 0 <= expected <= 30:
                    raise ValueError("Invalid expected points")
                key = (source, gw, pid)
                if key not in forecasts or as_of > forecasts[key][0]:
                    forecasts[key] = (as_of, expected)
    return forecasts


def benchmark(forecasts, actual, min_common=1):
    """Use identical (GW, player) sample for every compared source."""
    sources = sorted({source for source, _, _ in forecasts})
    if len(sources) < 2:
        return {"status": "insufficient_sources", "sources": sources}
    keys = set.intersection(*(
        {(gw, pid) for source, gw, pid in forecasts if source == s and
         gw in actual and pid in actual[gw]} for s in sources
    ))
    if len(keys) < min_common:
        return {"status": "insufficient_common_observations",
                "sources": sources, "common_observations": len(keys)}
    scores = {}
    for source in sources:
        pairs = [(forecasts[(source, gw, pid)][1], actual[gw][pid])
                 for gw, pid in sorted(keys)]
        scores[source] = metrics(pairs)
    ranked = sorted(sources, key=lambda s: (scores[s]["mae"], scores[s]["rmse"]))
    return {"status": "evaluated", "common_observations": len(keys),
            "scores": scores, "ranked_by_mae": ranked,
            "warning": "Ranking is descriptive, not statistically significant. "
                       "Only compare forecasts frozen before the deadline."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("exports", nargs="+", help="Authorized normalized CSV exports")
    parser.add_argument("--deadlines", required=True, help="JSON mapping GW to ISO deadline")
    parser.add_argument("--actual", required=True, help="JSON mapping GW to player-id points")
    parser.add_argument("--output", default="data/source-benchmark.json")
    args = parser.parse_args()
    deadlines = {int(gw): datetime.fromisoformat(t.replace("Z", "+00:00"))
                 for gw, t in json.loads(Path(args.deadlines).read_text()).items()}
    actual = {int(gw): {int(pid): float(v) for pid, v in points.items()}
              for gw, points in json.loads(Path(args.actual).read_text()).items()}
    result = benchmark(load_rows(args.exports, deadlines), actual)
    result["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
