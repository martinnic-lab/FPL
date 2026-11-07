"""Time-safe FPL forecast backtesting and position-specific empirical calibration.

Predictions: LAST snapshot collected BEFORE a GW deadline (never after).
Targets: official finalized event/{gw}/live points, fetched AFTER GW is finished.
Model selection: expanding-window, walk-forward only; no future data leakage.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen

API = "https://fantasy.premierleague.com/api/"
MIN_TRAIN = 3
SHRINK = 100.0


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def select_predeadline(snapshots):
    """One latest predeadline forecast snapshot per GW, with strict cutoffs."""
    chosen = {}
    for snapshot in snapshots:
        bootstrap = snapshot["sources"]["bootstrap"]["data"]
        timestamp = parse_time(snapshot["sources"]["bootstrap"]["fetched_at"])
        for event in bootstrap["events"]:
            deadline = parse_time(event["deadline_time"])
            if timestamp >= deadline or not event.get("is_next"):
                continue
            gw = event["id"]
            if gw not in chosen or timestamp > chosen[gw][0]:
                chosen[gw] = (timestamp, bootstrap)
    return chosen


def prediction_rows(bootstrap):
    rows = {}
    for p in bootstrap["elements"]:
        try:
            predicted = float(p.get("ep_next") or 0)
        except (TypeError, ValueError):
            continue
        if math.isfinite(predicted) and predicted >= 0:
            rows[p["id"]] = (int(p["element_type"]), predicted)
    return rows


def fetch_final_points(gw):
    req = Request(API + f"event/{gw}/live/", headers={"User-Agent": "fpl-calibration/1.0"})
    with urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    return {int(p["id"]): float(p["stats"]["total_points"]) for p in data["elements"]}


def metrics(pairs):
    if not pairs:
        return {"n": 0, "mae": None, "rmse": None, "bias": None}
    errors = [forecast - actual for forecast, actual in pairs]
    return {"n": len(errors),
            "mae": round(sum(abs(x) for x in errors) / len(errors), 4),
            "rmse": round(math.sqrt(sum(x*x for x in errors) / len(errors)), 4),
            "bias": round(sum(errors) / len(errors), 4)}


def calibrate(raw, position, training):
    """Position-specific additive bias correction with regularized shrinkage."""
    examples = training.get(position, [])
    bias = sum(actual - forecast for forecast, actual in examples) / (len(examples) + SHRINK)
    return max(0.0, raw + bias)


def evaluate(chosen, targets, min_train=MIN_TRAIN):
    """Train only on completed GWs strictly earlier than each evaluated GW."""
    training = defaultdict(list)
    raw_pairs, calibrated_pairs = [], []
    weekly = []
    for gw in sorted(set(chosen) & set(targets)):
        _, bootstrap = chosen[gw]
        rows = prediction_rows(bootstrap)
        points = targets[gw]
        examples = [(pos, raw, points[pid]) for pid, (pos, raw) in rows.items()
                    if pid in points]
        if len(weekly) >= min_train:
            before, after = [], []
            for pos, raw, actual in examples:
                before.append((raw, actual))
                after.append((calibrate(raw, pos, training), actual))
            raw_pairs.extend(before)
            calibrated_pairs.extend(after)
            weekly.append({"gw": gw, "evaluated": True,
                           "raw": metrics(before), "calibrated": metrics(after)})
        else:
            weekly.append({"gw": gw, "evaluated": False, "reason": "warmup"})
        for pos, raw, actual in examples:
            training[pos].append((raw, actual))
    return {"method": "walk_forward_position_bias_shrinkage",
            "minimum_training_gameweeks": min_train,
            "raw": metrics(raw_pairs), "calibrated": metrics(calibrated_pairs),
            "per_gameweek": weekly,
            "position_adjustments": {str(pos): round(sum(y-x for x, y in rows) /
                                                       (len(rows) + SHRINK), 5)
                                     for pos, rows in training.items()},
            "warning": "Only evaluates official ep_next if historical predeadline snapshots exist. "
                       "A positive backtest result does not prove robust future performance."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", default="data/snapshots")
    ap.add_argument("--output", default="data/calibration-report.json")
    ap.add_argument("--targets", help="Optional local finalized live-points JSON keyed by GW then player ID")
    args = ap.parse_args()
    snapshots = [json.loads(p.read_text()) for p in sorted(Path(args.snapshots).glob("*.json"))]
    chosen = select_predeadline(snapshots)
    if args.targets:
        raw = json.loads(Path(args.targets).read_text())
        targets = {int(gw): {int(pid): float(v) for pid, v in vals.items()} for gw, vals in raw.items()}
    else:
        if not snapshots:
            raise SystemExit("No historical snapshots available")
        latest = snapshots[-1]["sources"]["bootstrap"]["data"]
        finalized = {e["id"] for e in latest["events"] if e.get("finished") and e.get("data_checked")}
        targets = {gw: fetch_final_points(gw) for gw in chosen if gw in finalized}
    report = evaluate(chosen, targets)
    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["eligible_gameweeks"] = sorted(set(chosen) & set(targets))
    report["source"] = "official predeadline snapshot ep_next versus finalized official live points"
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(f"Backtest: {report['calibrated']['n']} walk-forward player observations; "
          f"MAE={report['calibrated']['mae']}")


if __name__ == "__main__":
    main()
