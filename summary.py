"""Build a compact, source-labeled decision summary from a validated public snapshot."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

def build(snapshot):
    bootstrap = snapshot["sources"]["bootstrap"]["data"]
    players = {p["id"]: p for p in bootstrap["elements"]}
    teams = {t["id"]: t["short_name"] for t in bootstrap["teams"]}
    events = bootstrap["events"]
    history = snapshot["sources"]["history"]["data"]
    gameweeks = history["current"]
    latest = max((r["event"] for r in gameweeks), default=None)
    next_event = next((e for e in events if e.get("is_next")), None)
    current_event = next((e for e in events if e.get("is_current")), None)
    if next_event is None:
        next_event = next((e for e in events if not e.get("finished") and
                           datetime.fromisoformat(e["deadline_time"].replace("Z", "+00:00")) >
                           datetime.now(timezone.utc)), None)
    squad = snapshot["squads"].get(str(latest)) if latest else None
    picks = squad["source"]["data"]["picks"] if squad else []
    player_rows = []
    for pick in sorted(picks, key=lambda p: p["position"]):
        p = players[pick["element"]]
        player_rows.append({
            "id": p["id"], "name": p["web_name"], "club": teams.get(p["team"]),
            "position": pick["position"], "captain": pick["is_captain"],
            "vice_captain": pick["is_vice_captain"],
            "current_market_price_tenths": p["now_cost"],
            "status": p["status"], "news": p.get("news", ""),
            "chance_next_round": p.get("chance_of_playing_next_round")
        })
    transfers = snapshot["sources"]["transfers"]["data"]
    compact_transfers = []
    for t in sorted(transfers, key=lambda x: x["time"], reverse=True)[:25]:
        compact_transfers.append({
            "gameweek": t["event"], "time": t["time"],
            "out": players.get(t["element_out"], {}).get("web_name"),
            "in": players.get(t["element_in"], {}).get("web_name"),
            "out_cost_tenths": t["element_out_cost"],
            "in_cost_tenths": t["element_in_cost"]
        })
    return {
        "schema_version": 1, "entry_id": snapshot["entry_id"],
        "collected_at_utc": snapshot["completed_at"],
        "latest_public_squad_gameweek": latest,
        "squad_scope": "post_deadline_public_only",
        "live_predeadline_team_verified": False,
        "current_bank_verified": False,
        "current_free_transfers_verified": False,
        "current_selling_prices_verified": False,
        "current_gameweek": current_event["id"] if current_event else None,
        "current_gameweek_finished": current_event.get("finished") if current_event else None,
        "current_gameweek_data_checked": current_event.get("data_checked") if current_event else None,
        "latest_public_squad_gameweek_finished": next((e.get("finished") for e in events if e["id"] == latest), None),
        "next_gameweek": next_event["id"] if next_event else None,
        "next_deadline_utc": next_event["deadline_time"] if next_event else None,
        "squad": player_rows,
        "confirmed_public_transfers_recent": compact_transfers,
        "recent_results": gameweeks[-8:],
        "used_chips": history.get("chips", []),
        "notes": [
            "Public picks represent the most recently published deadline, not the live editable team.",
            "Market prices are not the manager's selling prices.",
            "Public transfer publication may lag live changes.",
            "Do not prescribe an unconditional affordable transfer without live bank, selling prices and FT count.",
            "Do not call a gameweek complete unless the official finished flag is true.",
            "Check match appearances and dated team news before repeating an old injury warning."
        ]
    }

def main():
    directory = Path("data/snapshots")
    snapshots = sorted(directory.glob("*.json"))
    if not snapshots:
        raise SystemExit("No validated snapshot exists")
    source = json.loads(snapshots[-1].read_text(encoding="utf-8"))
    output = build(source)
    if output["squad"] and len(output["squad"]) != 15:
        raise SystemExit("Invalid compact squad")
    target = Path("data/latest-summary.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Summary written: {target} ({len(output['squad'])} players)")

if __name__ == "__main__":
    main()
