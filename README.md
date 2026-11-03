# Public FPL collector — entry 1580840

Python 3.12+, standard library only. No FPL login, cookies, passwords or API keys are used.

```sh
python -m unittest discover -s tests -v
python collector.py
# Optional destination:
python collector.py --output data/snapshots
```

Each successful run atomically writes a new UTC timestamped JSON file under
`data/snapshots/`. The schema version, entry ID, collection start/completion times,
and each endpoint's URL and retrieval timestamp are included. Raw public payloads
are retained, including:

| Source | Contents |
| --- | --- |
| `bootstrap-static/` | Players, `now_cost` prices (integer tenths of £1m), availability status, injury/news text, playing chances; gameweek deadlines and completion flags |
| `fixtures/` | Fixtures, kickoff times, scores and completion state |
| `entry/1580840/history/` | Gameweek points, ranks, transfer costs, past season results and chips |
| `entry/1580840/transfers/` | Public transfer history and prices at transfer time |
| `entry/1580840/event/{event}/picks/` | All gameweeks published in entry history: squad picks, captain/vice-captain, multipliers, automatic substitutions and entry results |

## Squad interpretation

`publicly_confirmed_post_deadline` means the picks were published by the public
FPL API for that particular gameweek after its deadline. It does **not** mean
these are the manager's current live team or that points have finalized.
Multipliers, automatic substitutions, points and ranks can change while matches
are underway or results are being processed. Check event `finished` and
`data_checked` fields in the raw bootstrap payload when assessing finality.

`live_pre_deadline_team.available` is always false: the public API does not expose
that team. The collector never reconstructs it from transfers or previous picks.
Public transfers may be delayed or incomplete around deadlines. Injury/news and
prices reflect the retrieval time, not necessarily the time of an older squad.
No authenticated `my-team` endpoint is called. Entry IDs refer to the current FPL
season and may need changing next season; archived files preserve prior responses.

## Validation and failures

Required payload structures, player IDs, gameweek deadlines and squad coverage
are checked. Each published squad must contain 15 unique known players, positions
1–15 and one captain/vice-captain, and must be past its deadline. This is structural
validation, not a guarantee of upstream accuracy. Empty preseason results are
accepted; unexpected malformed responses fail the run. No partial snapshot is
published if any endpoint or validation fails, including picks temporarily
unavailable during deadline processing. Existing snapshots remain intact.

Requests use TLS verification and 30-second timeouts. Network/JSON failures,
HTTP 429 and selected 5xx responses receive up to four attempts with exponential
backoff; other HTTP failures stop immediately. Errors produce a nonzero exit code.
The next scheduled or manual run retries the full collection. There is no silent
fallback to stale data. Snapshots accumulate intentionally; monitor repository size.

## GitHub Actions

`.github/workflows/collect.yml` runs at **00:17, 08:17 and 16:17 UTC** daily and
supports **Actions → Collect public FPL data → Run workflow**. GitHub may delay
scheduled jobs; schedules run from the default branch, and GitHub may disable them
in inactive public repositories. Enable Actions and allow workflow `contents: write`
access. Branch protections must allow the bot to push, otherwise the job fails.
Manual runs commit to the selected branch. Concurrent runs on a branch are queued;
unrelated pushes can cause a push rejection, which is deliberately not force-pushed.

The workflow tests, collects, validates and commits new snapshots using GitHub's
ephemeral built-in token. No user credentials or secrets are required or stored.
Checkout disables persisted credentials; the push supplies authorization only for
that command. Failed collection prevents the commit step. All payload data comes
from public endpoints; no manager profile/name/email endpoint is collected.

Initial live API retrieval has not been verified in the authoring environment.
Run the manual workflow after installation to create the first real snapshot.

## Decision policy and model status

Read [DECISION_POLICY.md](DECISION_POLICY.md) before any transfer, captaincy, lineup, price or chip recommendation. **Cumbres data is collected for reporting only** and is forbidden as an optimizer input. The collector is operational; the calibrated forecasting engine, multiweek solver, chip-aware optimizer and backtesting described in the policy are **not yet implemented**. Until tested, label recommendations research-informed/provisional, never optimized. Do not infer live bank/FT/selling prices from public post-deadline picks.
