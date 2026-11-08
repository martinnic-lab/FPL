# Independent FPL engine — baseline implementation

This is a **working baseline screening engine**, not yet a calibrated season optimizer. Read [DECISION_POLICY.md](DECISION_POLICY.md).

## Inputs and execution

```bash
python -m unittest discover -s tests -v
python collector.py
python summary.py
python engine.py
# Optionally, after the user explicitly verifies LIVE pre-deadline details:
python engine.py --live private-live.json --output data/private-engine.json
```

`private-live.json` schema (never commit this file):

```json
{
  "bank_tenths": 65,
  "free_transfers": 2,
  "sell_prices_tenths": {"31": 47}
}
```

Example values above are **illustrative only**; all 15 owned players require real current selling prices for transfer screening. The engine will refuse incomplete selling prices. Never infer these values from public history or screenshots from previous deadlines.

## Implemented

- Official snapshot input, current post-deadline public squad, next six deadlines and fixtures.
- Conservative *uncalibrated* official `ep_next` baseline for **the next GW only**; never recycle next-GW forecasts into later gameweeks. Independent timestamped multiweek projections may be supplied via `--projections`. This is a screening heuristic, not an empirically validated xPts forecast.
- Exact legal XI search over formations, goalkeeper, captain, vice and ordered substitutes; 15-player squad validation and maximum three per club.
- Compare rolling with zero/one/two legal transfers; affordability from verified selling prices and bank; four-point hits for transfers beyond free transfers.
- Static first-half Bench Boost and Triple Captain opportunity screen only when independently supplied multiweek projections cover at least six GWs; otherwise chip scheduling is explicitly withheld.
- Explicit **no live finance → no transfer recommendations** gate.
- Cumbres data deliberately excluded from the engine's inputs. Its collector and reports remain separate.
- Unit tests for legality, lineup, missing live details, transfers and chips.

## Not yet implemented (do not overclaim)

- Calibrated player minutes, xG/xA, clean-sheet, defensive contribution, bonus and injury probability projections with time-split backtests.
- A proper sequential solver with future transfers, price uncertainty, auto-sub distributions, free-transfer roll value and multiweek chip effects.
- Free Hit temporary-squad optimizer, complete second-half Wildcard/chip strategy and exact chip rule-state tests.
- Full squad optimization (rather than bounded candidate screening), ensemble calibration and out-of-sample decision auditing.
- Authenticated live team, live bank/FT/selling prices. **Public data alone cannot provide them.**

The default scheduled output `data/latest-engine.json` is **next-GW lineup-only** unless verified live data is explicitly provided. Multiweek estimates require independent per-GW projections. Never treat the heuristic output as sufficient evidence to execute transfers.

## Safety and separation

No credentials are collected. Never commit `private-live.json` or personal auth tokens. Price-watch alerts are independent of Cumbres ownership. Cumbres standings, rivals and captaincy can be viewed for entertainment, but must not enter feature engineering or decisions.

## Independent projections input

Use `python engine.py --projections forecasts.json` with a timestamped JSON file containing exactly `schema_version: 1`, `source` (nonempty independent provenance), `generated_at_utc` (within 72 hours), `gameweeks` (sorted list of up to six future GW IDs) and `players` (object mapping **every official player ID** to an object of string GW IDs and numeric nonnegative expected points). This input is schema-validated, **not statistically calibrated by this repository**. No Cumbres ownership, captains or rival standings are accepted. Multiweek screening remains static and excludes future transfer sequencing.

## New development: historical calibration and sequential search

`python calibration.py` selects the last **predeadline** official `ep_next` snapshot for each gameweek, fetches official `event/{gw}/live/` targets only for games with both `finished` and `data_checked`, and performs a walk-forward position-specific regularized bias calibration. The weekly `.github/workflows/calibrate.yml` runs tests and publishes `data/calibration-report.json`. If fewer than four completed, properly snapshotted GWs are available, it will report **zero evaluated observations**, not fabricated validation. This is a first calibration benchmark, not a comprehensive minutes/xG/defensive-contribution forecast.

`python engine.py --projections forecasts.json --live private-live.json --rolling` enables an opt-in bounded beam search across supplied future GWs, including rolling free transfers (up to five), one transfer per GW, bank, hits, legal lineups and captains. The search is **approximate**, does not model chips, future prices, actual FPL selling-price appreciation, multiple transfers per week or uncertainty, and must not be represented as a globally optimal plan.

Next requirements: ingest genuinely independent position-specific minutes/xG/xA/clean-sheet/defensive contribution forecasts, backtest against the predeadline historical data, expand solver to multiple transfers and chips, validate production CI and report realized performance. The collector still generates the conservative one-GW lineup screen by default; the rolling solver is deliberately opt-in until independently sourced projections and verified live finances exist.

## Practical provider comparison (November 2026)

Prioritize existing external projections over training a new points model from a short season sample. Candidate providers and permitted-access checks:
- FPL Form: https://fplform.com/export-fpl-form-data — explicitly offers predicted-points CSV for personal use; honor attribution, copyright and restrictions on publication.
- FPL Review: https://docs.fplreview.com/the-model/planner-interface/export_projections/ — documented per-GW CSV with FPL IDs, xPts and xMins; may require membership and authorized manual export.
- FPL Alpha: https://fplalpha.com/ — public GW-specific projections; confirm permission for automated collection before implementing any fetch.
- FPL Toolkit: https://www.fpltoolkit.co.uk/projections — six-week distributions; confirm permitted export/collection.
- Onside: https://onsidearena.com/data — published graded predeadline forecast dataset under CC-BY-4.0; useful as an external historical benchmark, not proof that other providers perform similarly.
- Official FPL ep_next — baseline from already-authorized public FPL API.

`source_benchmark.py` compares providers **only** on the identical player-GW sample with forecasts timestamped before deadline. Each authorized normalized CSV requires `player_id,gw,expected_points,source,as_of_utc`; run `python source_benchmark.py exports/*.csv --deadlines deadlines.json --actual actual.json`. For each GW, archive a predeadline immutable export; do not replace it with a later revision. Match all player IDs to official FPL IDs. Never redistribute third-party copyrighted exports. No paid-provider credentials or access bypasses in GitHub. Report MAE, RMSE and bias, plus coverage, by source; don't select a winner from small samples. Once enough comparable GWs accumulate, evaluate a lagged weighted ensemble out of sample rather than picking whichever provider just won last week.

The benchmarking script and provider registry are implemented; **provider-specific ingestion, authorization, automated data capture and sufficient actual benchmark samples are not yet verified**.

## Non-negotiable budget

**$0 for subscriptions, paid APIs, and projection datasets.** Official FPL API is the guaranteed baseline. Evaluate free downloadable exports from FPL Form and other independent providers only where access is free and reuse/collection permitted. No FPL Review premium dependency, no paid trials, no credentials, and no manual weekly user upload as the default workflow. Each source must record access method, terms, coverage, timestamp, and collection health. If independent free sources are unavailable, continue with the labeled official baseline rather than invent forecasts or violating terms.
