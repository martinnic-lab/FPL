# Evidence-gated research engine (staged delivery)

The public collector is unchanged. Cumbres collection/reporting is unchanged and
is never loaded by the new engine. No FPL write endpoint, login or transfer execution
exists in this implementation. All decisions remain **research-informed provisional**.

## Run

Python 3.12, standard library only:

```
python -m unittest discover -s tests -v
python collector.py
python summary.py
python research_runner.py
```

Without independent source-backed forecasts, this writes `blocked_missing_sources`,
not heuristic player rankings. Invalid/stale public evidence exits 2. The collector
workflow now publishes this status instead of the legacy `ep_next` heuristic. The
legacy `engine.py` API remains for compatibility and tests; it is not calibrated.
The read-only research workflow runs offline tests on PRs and refreshes public
evidence hourly/manual, uploading only a public status artifact. Actions can be
delayed; this is monitoring, not a guaranteed deadline notification service.

## Forecast contract and calibration

`forecasting.validate_rows` accepts only the exact fields in `FIELDS`; components
must match `COMPONENTS` and sum to the supplied xPts. Negative points are legal.
Every row has season, player, GW, model, HTTPS source and published/retrieved/deadline
UTC timestamps, minutes and start probability. Supply full GW totals (double GWs
aggregated, blanks explicitly sourced as zero). Missing values never become zero.
One model and horizon is used per solve; no arbitrary ensemble weights exist.

`walk_forward(records, min_train=20)` evaluates expanding-window additive bias
correction against raw forecasts, returning held-out MAE/RMSE, training counts,
fold-level predictions and input hash. Records add `actual` and
`actual_available_at` to forecast provenance. Only results finalized strictly before
the test deadline can train the correction, including across season boundaries.
It does not claim component/uncertainty calibration or automatically promote a model.
No actual forecast archive has been supplied, so no real calibration score is claimed.

## Conditional planning interface

`rolling_planner.solve` performs exhaustive dynamic programming within the supplied
candidate universe and weekly transfer cap (default two; configurable up to 15).
It includes zero transfers every GW, future FT banking to five, four-point hits,
purchase-price-dependent selling values and explicit conditional price paths.
The output includes top alternatives plus roll-now/optimize-later as a comparator.
The difference includes the in-horizon value of saved FTs, without inventing a
terminal FT price. It is not an unrestricted full-player-pool or season optimum.
The state limit aborts instead of publishing a partial optimum. Full-pool search
is combinatorial and requires a future scalable solver before production use.

Each GW supplies joint scenarios: probability, points and played boolean for every
candidate. The exact lineup search enumerates legal formations, GK, ordered bench
and captain/vice. Scenario scoring includes simultaneous absence substitutions,
formation constraints, GK replacement, captain fallback, BB and TC. Bench order
in outputs is three outfield substitutes followed by reserve GK.
Scenario extrema are sensitivity bounds, not confidence intervals. All components,
minutes and fixture/news effects must come from the sourced forecasts; the engine
does not manufacture a joint distribution from marginal means.

Chips are opt-in search actions. WC enumerates permanent legal squads; FH enumerates
temporary squads and restores original holdings/bank next week. Chip inventory
resets in GW20, expires after GW19, allows one chip per GW, forbids consecutive FH
including GW19/20, and retains FT counts on WC/FH (no additional accrual).
All four chips can be searched, including second-half inventory, within six GWs.
Beyond-horizon chip opportunity costs, injury/price recourse, dynamic player club
changes, and the special first deadline of a late-joining manager are **not modeled**.
There is no automatic expiring-chip commitment or claim of complete season planning.

## Private integration

```
python research_runner.py --research-input private-research.json --output data/private-research.json
python research_runner.py --history work/forecast-history.json
```

The strict input contract is documented by `research_runner.research` and exercised
by tests. Top-level fields: forecasts, scenarios, prices, live, news, chips, weights,
max_transfers. Forecast rows use `forecasting.FIELDS`. The full next six deadlines
(or remaining season) are required. Scenarios are keyed by GW, with source_url,
published_at, retrieved_at, values. Values contain probability, points and played
maps by player ID; scenario means must reconcile to source xPts. Prices are explicit
GW/player integer-tenths conditional market paths; initial prices match official data.

Live fields: verified_at, squad_ids, bank, ft, purchase_prices, selling_prices,
used_chips (`[[GW, name], ...]`), confirmed=true. These must be current editable
details independently confirmed within four hours, not reconstructed public picks.
The solver assumes the state is before any moves for the coming GW; **already-made
transfers, spent FTs, incurred hits or active chips require reconciliation outside
this version**. Do not use it for those states. News rows (player, source_url,
reviewed_at) are required for all candidates within 24h; the review is a human/source
attestation, not automated fact verification. Public snapshot/endpoint freshness is
12h, forecast retrieval 24h. Published timestamps/hashes establish recorded lineage,
not source authenticity. Rule/news refresh remains a prerequisite to actionable use.

Private outputs contain squad/finances. They are gitignored and never passed to
Actions. Do not commit private files, independent licensed data or credentials.
Pre-deadline decision archives should be stored privately and immutably by the caller;
hashes alone do not prove historical existence.

## Walk-forward decision audit and remaining acceptance work

`decision_audit.evaluate` accepts archived deadline frames with forecast availability,
archive time, final outcome availability, players, actual points/played maps and
three policies: rolling, roll, naive. Each policy supplies xi, bench, captain, vice,
chip, hit. It scores each first-week decision against the same realized outcomes,
including substitutions and hit costs. This paired walk-forward audit is not a
continuous stateful season replay, and validates chronology rather than authenticity.

Still required for A–C policy acceptance:

- Licensed/available point-in-time xG/xA, minutes, defensive-contribution, clean-sheet,
  bonus/injury and independent forecast archives with real outcomes.
- Empirical component/uncertainty calibration, ensemble selection by time split,
  and held-out model promotion thresholds.
- Continuous season replay with independent roll/naive policy states and price/news
  vintages; scalability benchmarks and an independent small-instance solver oracle.
- Beyond-six-GW chip opportunity costs, mandatory expiry comparisons and full-season
  sequencing. Never equate finite-window optimality with season optimality.
- Verified live state and rule refresh before any real recommendation.

## Rule provenance

Checked 2026-11-06 against official sources:

- https://fantasy.premierleague.com/help/faqs (FT cap, chip retention, selling prices,
  captain fallback, substitutions, FH restoration/adjacency).
- https://www.premierleague.com/en/news/4679879/whats-happening-with-fpl-chips-in-202627
  (two chip sets, GW19 expiry/GW20 reset, one chip/GW).

Official help/article calendar dates currently differ, so code uses event IDs and
fresh bootstrap deadlines, never hard-coded calendar dates. Rules are versioned
for 2026/27; automatic future-season reuse is blocked by the runner.
