"""Collect public mini-league standings for FPL entry 1580840.

Read-only. Discover league IDs from public entry profile, page through league
standings, and publish a compact, timestamped comparison. No authentication.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request

BASE = "https://fantasy.premierleague.com/api/"
ENTRY = 1580840

def get(path):
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": "Mozilla/5.0 (compatible; FPL-league-collector/1.0)",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def collect():
    profile = get(f"entry/{ENTRY}/")
    memberships = profile.get("leagues", {})
    classic = memberships.get("classic", [])
    h2h = memberships.get("h2h", [])
    output = {"entry_id": ENTRY,
              "collected_at_utc": datetime.now(timezone.utc).isoformat(),
              "source": f"{BASE}entry/{ENTRY}/",
              "classic": [], "h2h_memberships": h2h}
    for league in classic:
        league_id = league["id"]
        # Ignore massive global leagues; keep user-created and smaller public
        # leagues, and always keep anything named Cumbres.
        name = league.get("name", "")
        if league.get("league_type") == "s" and "cumbres" not in name.lower():
            continue
        standings = []
        page = 1
        while page <= 20:
            data = get(f"leagues-classic/{league_id}/standings/?page_standings={page}")
            table = data.get("standings", {})
            standings.extend(table.get("results", []))
            if not table.get("has_next", False):
                break
            page += 1
        mine = next((r for r in standings if r.get("entry") == ENTRY), None)
        output["classic"].append({
            "league_id": league_id, "league_name": name,
            "standings_source": f"{BASE}leagues-classic/{league_id}/standings/",
            "my_position": mine.get("rank") if mine else league.get("entry_rank"),
            "my_total": mine.get("total") if mine else None,
            "entries_fetched": len(standings),
            "complete": not table.get("has_next", False),
            "standings": [{"rank": r.get("rank"), "entry": r.get("entry"),
                           "team": r.get("entry_name"), "manager": r.get("player_name"),
                           "total": r.get("total"), "event_total": r.get("event_total")}
                          for r in standings]})
    return output

if __name__ == "__main__":
    result = collect()
    target = Path("data/latest-leagues.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Collected {len(result['classic'])} classic mini-leagues and {len(result['h2h_memberships'])} H2H memberships.")
