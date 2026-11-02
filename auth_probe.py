"""Read-only authentication probe. Never print credentials or private FPL responses."""
import json
import os
import sys
import urllib.error
import urllib.request

ENTRY = 1580840
BASE = "https://fantasy.premierleague.com/api"

def fetch(path, cookie):
    req = urllib.request.Request(
        BASE + path,
        headers={"Cookie": cookie, "User-Agent": "Mozilla/5.0 (compatible; FPL-private-check/1.0)",
                 "Accept": "application/json", "Referer": "https://fantasy.premierleague.com/"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("FPL returned a non-200 response")
        return json.load(response)

def main():
    cookie = os.environ.get("FPL_SESSION_COOKIE", "").strip()
    if not cookie:
        print("NOT_CONFIGURED: add FPL_SESSION_COOKIE as a GitHub Actions repository secret.")
        return 2
    if any(x in cookie for x in ("\\r", "\\n")) or len(cookie) > 8192:
        print("INVALID_CONFIGURATION: cookie contains invalid characters or is too long.")
        return 2
    try:
        me = fetch("/me/", cookie)
        player = me.get("player") or {}
        if str(player.get("entry")) != str(ENTRY):
            print("AUTH_FAILED: session is invalid or belongs to a different FPL entry.")
            return 1
        team = fetch(f"/my-team/{ENTRY}/", cookie)
        picks = team.get("picks", [])
        transfers = team.get("transfers", {})
        if len(picks) != 15 or len({p.get("element") for p in picks}) != 15:
            print("SCHEMA_FAILED: expected 15 unique picks.")
            return 1
        if not isinstance(transfers, dict) or "bank" not in transfers:
            print("SCHEMA_FAILED: transfer budget missing.")
            return 1
        # Never print or persist private picks, account information, bank, or cookies.
        print("AUTH_OK: verified entry ownership, 15 private picks and transfer budget.")
        return 0
    except urllib.error.HTTPError as e:
        print(f"AUTH_FAILED: FPL HTTP status {e.code}; session may be expired.")
        return 1
    except Exception:
        print("AUTH_FAILED: FPL connection or response validation failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
