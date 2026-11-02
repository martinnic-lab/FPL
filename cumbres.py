"""Public Cumbres rival audit: GW9 squads, captaincy, and overlap.

No authentication, cookies, or private pre-deadline data. Reads latest league
standings and official post-deadline picks. Never treats a GW as finished.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen

BASE = "https://fantasy.premierleague.com/api/"
ENTRY = 1580840
LEAGUE = 602612

def fetch(path):
    request = Request(BASE + path, headers={"User-Agent": "fpl-public-rival-audit/1.0",
                                             "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)

def main():
    summary = json.loads(Path("data/latest-summary.json").read_text())
    leagues = json.loads(Path("data/latest-leagues.json").read_text())
    league = next(x for x in leagues["classic"] if x["league_id"] == LEAGUE)
    gw = summary["latest_public_squad_gameweek"]
    assert gw <= summary["current_gameweek"]
    players = fetch("bootstrap-static/")["elements"]
    names = {p["id"]: p["web_name"] for p in players}
    rows = []
    my_ids = None
    for rival in league["standings"]:
        entry = rival["entry"]
        picks = fetch(f"entry/{entry}/event/{gw}/picks/")["picks"]
        assert len(picks) == 15 and len({p["element"] for p in picks}) == 15
        ids = {p["element"] for p in picks}
        if entry == ENTRY:
            my_ids = ids
        captain = next((p for p in picks if p["is_captain"]), None)
        rows.append({"rank": rival["rank"], "entry": entry, "team": rival["team"],
                     "total": rival["total"],
                     "captain": names.get(captain["element"]) if captain else None,
                     "captain_id": captain["element"] if captain else None,
                     "squad_player_ids": sorted(ids),
                     "squad_names": sorted(names.get(pid, str(pid)) for pid in ids)})
    assert my_ids is not None
    for r in rows:
        r["shared_with_me"] = len(my_ids.intersection(r["squad_player_ids"]))
        r["differentials_vs_me"] = sorted(names.get(pid, str(pid)) for pid in
                                          set(r["squad_player_ids"]) - my_ids)
    out = {"entry_id": ENTRY, "league_id": LEAGUE, "league_name": league["league_name"],
           "collected_at_utc": datetime.now(timezone.utc).isoformat(),
           "public_picks_gameweek": gw, "current_gameweek_finished": summary["current_gameweek_finished"],
           "private_live_squad_verified": False, "standings": rows}
    target = Path("data/latest-cumbres-rivals.json")
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"Audited {len(rows)} public Cumbres squads for GW{gw}.")

if __name__ == "__main__":
    main()
