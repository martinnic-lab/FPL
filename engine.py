"""Independent FPL decision engine: conservative baseline, legal lineups and transfers.

This is a reproducible baseline, NOT a calibrated expected-points model.
Cumbres data is deliberately never read or accepted.
"""
import argparse
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
from chip_planner import chip_screen
from projection_inputs import load_projections

POSITIONS = {1: 2, 2: 5, 3: 5, 4: 3}
MAX_CLUB = 3
FORMATION = {2: (3, 5), 3: (2, 5), 4: (1, 3)}
WEIGHTS = (1.0, .92, .85, .78, .72, .66)


def legal_squad(ids, players):
    if len(ids) != 15 or len(set(ids)) != 15:
        return False
    if any(i not in players for i in ids):
        return False
    if any(sum(players[i]["element_type"] == p for i in ids) != n for p, n in POSITIONS.items()):
        return False
    return all(sum(players[i]["team"] == t for i in ids) <= MAX_CLUB for t in {players[i]["team"] for i in ids})


def baseline_forecast(bootstrap, fixtures, gameweeks=1):
    """Forecast NEXT GW ONLY with official ep_next as anchor and modest fixture adjustment.

    Future weeks use an explicitly heuristic anchor; do NOT call it calibrated xPts.
    ep_next is a vendor-supplied official field, not a forecast we have validated.
    """
    events = bootstrap["events"]
    upcoming = [e["id"] for e in events if not e["finished"] and
                datetime.fromisoformat(e["deadline_time"].replace("Z", "+00:00")) > datetime.now(timezone.utc)]
    weeks = upcoming[:gameweeks]
    teams = {t["id"]: t for t in bootstrap["teams"]}
    games = {}
    for f in fixtures:
        if f.get("event") in weeks and not f.get("finished"):
            for team, opponent, home in ((f["team_h"], f["team_a"], True), (f["team_a"], f["team_h"], False)):
                games.setdefault((f["event"], team), []).append((opponent, home))
    forecasts = {}
    for p in bootstrap["elements"]:
        try:
            ep = max(0., float(p.get("ep_next") or 0))
        except (ValueError, TypeError):
            ep = 0.
        # Deliberately avoid claiming predictive accuracy for this fallback.
        forecast = {}
        for gw in weeks:
            fixtures_here = games.get((gw, p["team"]), [])
            if not fixtures_here:
                forecast[gw] = 0.
                continue
            values = []
            for opp, home in fixtures_here:
                own = teams[p["team"]]
                other = teams[opp]
                # official strength indexes: opponent strength relative to neutral 3
                attack = p["element_type"] in (3, 4)
                strength = other["strength_defence_home" if not home else "strength_defence_away"] if attack else other["strength_attack_home" if not home else "strength_attack_away"]
                neutral = (teams[p["team"]]["strength_defence_home"] + teams[p["team"]]["strength_defence_away"]) / 2 if attack else (own["strength_attack_home"] + own["strength_attack_away"]) / 2
                factor = max(.75, min(1.25, 1 + (neutral - strength) / 1200))
                values.append(ep * factor * (1.035 if home else .965))
            forecast[gw] = round(sum(values), 3)
        forecasts[p["id"]] = forecast
    return weeks, forecasts


def lineup(ids, players, forecast):
    """Exact best XI and ordered bench; deterministic, handles all legal formations."""
    assert legal_squad(ids, players)
    gks = [i for i in ids if players[i]["element_type"] == 1]
    outfield = [i for i in ids if players[i]["element_type"] != 1]
    keeper = max(gks, key=lambda i: (forecast.get(i, 0), -i))
    best = None
    for group in combinations(outfield, 10):
        counts = {pos: sum(players[i]["element_type"] == pos for i in group) for pos in (2, 3, 4)}
        if any(not FORMATION[pos][0] <= counts[pos] <= FORMATION[pos][1] for pos in counts):
            continue
        eleven = (keeper,) + group
        score = sum(forecast.get(i, 0) for i in eleven)
        if best is None or score > best[0]:
            best = (score, eleven)
    if best is None:
        raise ValueError("No legal XI")
    xi = list(best[1])
    bench = [i for i in outfield if i not in xi]
    bench.sort(key=lambda i: forecast.get(i, 0), reverse=True)
    bench.append(next(i for i in gks if i != keeper))
    captain = max(xi, key=lambda i: forecast.get(i, 0))
    vice = max((i for i in xi if i != captain), key=lambda i: forecast.get(i, 0))
    return {"xi": xi, "bench": bench, "captain": captain, "vice": vice,
            "expected": round(best[0] + forecast.get(captain, 0), 3),
            "bench_boost_increment": round(sum(forecast.get(i, 0) for i in bench), 3),
            "triple_captain_increment": round(forecast.get(captain, 0), 3)}


def plan_score(ids, players, weeks, forecasts):
    plans = {}
    score = 0.
    for j, gw in enumerate(weeks):
        l = lineup(ids, players, {i: forecasts[i].get(gw, 0) for i in ids})
        plans[str(gw)] = l
        score += WEIGHTS[min(j, len(WEIGHTS)-1)] * l["expected"]
    return round(score, 3), plans


def optimize(ids, players, weeks, forecasts, bank_tenths=None, sell_prices=None,
             free_transfers=None, max_transfers=2, shortlist=18):
    """Exact legal 0/1/2 swap search within bounded, transparent candidate pool.

    Requires verified live bank and individual selling prices for affordability.
    If missing, only return current-squad lineup and explicit unavailable status.
    Future transfer/chip effects are NOT yet modeled; results are screening only.
    """
    base, lineups = plan_score(ids, players, weeks, forecasts)
    result = {"current_weighted_points": base, "current_lineups": lineups,
              "status": "lineup_only", "plans": [],
              "caveats": ["Official ep_next fixture-adjusted heuristic, not calibrated forecasts.",
                          "Static six-week squad: no future transfers, auto-sub simulation or chip sequencing.",
                          "No Cumbres data used."]}
    if bank_tenths is None or sell_prices is None or free_transfers is None:
        result["caveats"].append("Verified live bank, free transfers and selling prices required for affordable transfers.")
        return result
    if any(i not in sell_prices for i in ids):
        raise ValueError("Missing selling prices for owned player(s)")
    if not legal_squad(ids, players):
        raise ValueError("Illegal starting squad")
    if free_transfers < 0 or bank_tenths < 0:
        raise ValueError("Invalid live finances")
    result["status"] = "screening_only"
    current = set(ids)
    candidates = {}
    for pos in POSITIONS:
        pool = [i for i, p in players.items() if p["element_type"] == pos and i not in current and p["status"] == "a"]
        pool.sort(key=lambda i: sum(WEIGHTS[j] * forecasts[i].get(gw, 0) for j, gw in enumerate(weeks)), reverse=True)
        candidates[pos] = pool[:shortlist]
    scored = [(base, [], bank_tenths, 0)]
    max_transfers = min(max_transfers, 2)
    for n in range(1, max_transfers + 1):
        for outgoing in combinations(ids, n):
            choices = [candidates[players[i]["element_type"]] for i in outgoing]
            if n == 1:
                incoming_groups = ((x,) for x in choices[0])
            else:
                incoming_groups = ((a, b) for a in choices[0] for b in choices[1] if a != b)
            for incoming in incoming_groups:
                new = list((current - set(outgoing)) | set(incoming))
                if not legal_squad(new, players):
                    continue
                remaining = bank_tenths + sum(sell_prices[i] for i in outgoing) - sum(players[i]["now_cost"] for i in incoming)
                if remaining < 0:
                    continue
                hits = 4 * max(0, n - free_transfers)
                val, _ = plan_score(new, players, weeks, forecasts)
                scored.append((round(val - hits, 3), list(zip(outgoing, incoming)), remaining, hits))
    scored.sort(key=lambda t: (t[0], -len(t[1])), reverse=True)
    result["plans"] = [{"net_weighted_points": s, "gain_vs_roll": round(s - base, 3),
                        "moves": [{"out": a, "in": b} for a, b in moves],
                        "bank_after_tenths": remaining, "hit": hit}
                       for s, moves, remaining, hit in scored[:10]]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", help="Validated public snapshot JSON")
    ap.add_argument("--projections", help="Validated independent per-player per-GW forecast JSON; see ENGINE.md")
    ap.add_argument("--live", help="Optional user-confirmed JSON: bank_tenths, free_transfers, sell_prices_tenths by player ID")
    ap.add_argument("--output", default="data/latest-engine.json")
    args = ap.parse_args()
    if args.snapshot:
        snapshot = json.loads(Path(args.snapshot).read_text())
    else:
        paths = sorted(Path("data/snapshots").glob("*.json"))
        if not paths:
            ap.error("No snapshots")
        snapshot = json.loads(paths[-1].read_text())
    b = snapshot["sources"]["bootstrap"]["data"]
    fixtures = snapshot["sources"]["fixtures"]["data"]
    players = {p["id"]: p for p in b["elements"]}
    weeks, forecasts = load_projections(args.projections, b) if args.projections else baseline_forecast(b, fixtures)
    gw = max(map(int, snapshot["squads"]))
    picks = snapshot["squads"][str(gw)]["source"]["data"]["picks"]
    ids = [p["element"] for p in picks]
    live = json.loads(Path(args.live).read_text()) if args.live else {}
    sell = {int(k): v for k, v in live.get("sell_prices_tenths", {}).items()} if live else None
    result = optimize(ids, players, weeks, forecasts, live.get("bank_tenths"),
                      sell, live.get("free_transfers"))
    result["chip_screen"] = chip_screen(result["current_lineups"], snapshot["sources"]["history"]["data"].get("chips", []))
    if not args.projections or len(weeks) < 6:
        result["chip_screen"]["status"] = "insufficient_future_forecasts_for_chip_scheduling"
        result["chip_screen"]["top_static_assignments"] = []
    else:
        result["chip_screen"]["status"] = "external_forecast_static_screen_only"
    if not args.projections:
        result["caveats"].append("Only next GW is screened: official ep_next cannot legitimately be recycled into future gameweeks.")
    else:
        result["caveats"].append("External forecasts are not validated by this engine for statistical calibration; inspect provenance.")
    result.update({"generated_at_utc": datetime.now(timezone.utc).isoformat(),
                   "snapshot_collected_at_utc": snapshot["completed_at"],
                   "public_squad_gw": gw, "forecast_gameweeks": weeks,
                   "forecast_method": "external_user_supplied" if args.projections else "uncalibrated_official_ep_next_next_gw_only",
                   "live_team_verified": bool(live),
                   "cumbres_is_optimizer_input": False})
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {args.output}; status={result['status']}; {len(weeks)} GWs")


if __name__ == "__main__":
    main()
