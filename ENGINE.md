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
- Conservative *uncalibrated* official `ep_next` baseline, fixture-strength adjustment and discounting. This is a screening heuristic, not an empirically validated xPts forecast.
- Exact legal XI search over formations, goalkeeper, captain, vice and ordered substitutes; 15-player squad validation and maximum three per club.
- Compare rolling with zero/one/two legal transfers; affordability from verified selling prices and bank; four-point hits for transfers beyond free transfers.
- Static first-half Bench Boost and Triple Captain opportunity screen; mutually exclusive gameweeks and explicit first-half expiry warning.
- Explicit **no live finance → no transfer recommendations** gate.
- Cumbres data deliberately excluded from the engine's inputs. Its collector and reports remain separate.
- Unit tests for legality, lineup, missing live details, transfers and chips.

## Not yet implemented (do not overclaim)

- Calibrated player minutes, xG/xA, clean-sheet, defensive contribution, bonus and injury probability projections with time-split backtests.
- A proper sequential solver with future transfers, price uncertainty, auto-sub distributions, free-transfer roll value and multiweek chip effects.
- Free Hit temporary-squad optimizer, complete second-half Wildcard/chip strategy and exact chip rule-state tests.
- Full squad optimization (rather than bounded candidate screening), ensemble calibration and out-of-sample decision auditing.
- Authenticated live team, live bank/FT/selling prices. **Public data alone cannot provide them.**

The default scheduled output `data/latest-engine.json` is **lineup-only** unless verified live data is explicitly provided. Never treat the heuristic output as sufficient evidence to execute transfers.

## Safety and separation

No credentials are collected. Never commit `private-live.json` or personal auth tokens. Price-watch alerts are independent of Cumbres ownership. Cumbres standings, rivals and captaincy can be viewed for entertainment, but must not enter feature engineering or decisions.
