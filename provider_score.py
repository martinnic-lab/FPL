"""Grade archived provider forecasts on identical player/GW observations.

Uses official predeadline snapshot deadlines and finalized FPL live scores.
Never uses current/revised projections to grade historical gameweeks.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from calibration import fetch_final_points
from source_benchmark import load_rows, benchmark


def official_context(snapshots):
    deadlines, finalized = {}, set()
    for path in sorted(Path(snapshots).glob("*.json")):
        snap = json.loads(path.read_text())
        for event in snap["sources"]["bootstrap"]["data"]["events"]:
            gw = int(event["id"])
            deadlines[gw] = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))
            if event.get("finished") and event.get("data_checked"):
                finalized.add(gw)
    return deadlines, finalized


def run(snapshots, forecasts):
    deadlines, finalized = official_context(snapshots)
    exports = sorted(Path(forecasts).glob("*/*/*.csv"))
    if not exports:
        return {"status": "no_archived_provider_forecasts", "exports": 0}
    rows = load_rows(exports, deadlines)
    eligible = sorted(finalized & {gw for _, gw, _ in rows})
    if not eligible:
        return {"status": "awaiting_finalized_gameweeks", "exports": len(exports),
                "providers": sorted({s for s, _, _ in rows})}
    actual = {gw: fetch_final_points(gw) for gw in eligible}
    report = benchmark(rows, actual, min_common=20)
    report["finalized_gameweeks"] = eligible
    report["exports"] = len(exports)
    report["comparison_policy"] = "Same player/GW intersection; latest predeadline forecast per source"
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshots", default="data/snapshots")
    p.add_argument("--forecasts", default="data/provider-forecasts")
    p.add_argument("--output", default="data/provider-comparison.json")
    args = p.parse_args()
    report = run(args.snapshots, args.forecasts)
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
