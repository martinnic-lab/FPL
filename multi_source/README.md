# Independent multi-source FPL audit (pilot)

Entry 1580840. This system is research infrastructure, NOT a calibrated optimizer. Binding policy: ../DECISION_POLICY.md.

## Architecture
1. Official collector: read existing data/latest-summary.json and validate timestamp, published picks, current GW finished flag, deadline. Public squad is not editable squad; never infer live bank, FT or selling prices.
2. Four source adapters: Solio, FPL Toolkit, Lineup Optimizer, RotoWire. Each adapter stores dated URL, source category, published player xPts, minutes, horizon, model provenance and caveats. Do not scrape paywalls, bypass authentication or fabricate unavailable data. Editorial opinions are not numerical xPts.
3. Central auditor: normalize FPL player ID and horizon, flag stale sources, independent agreement and outliers, preserve missingness. Do not average overlapping sources as independent votes. Forecast weights require out-of-sample calibration.
4. Decision layer: compare legal no-chip XI and GW12/GW14 Free Hit *incremental* gains, captaincy and 6-GW opportunity cost; keep TC and BB for later weeks. No automated transfers.

## Current status
The pilot includes a strict source registry and an auditable aggregation script. Live adapters and multiweek legal-squad optimizer are not implemented. A numeric consensus requires independently collected, dated player-level records. Reports must explicitly label missing inputs and must not claim optimization.

## Run
`python3 multi_source/audit.py --inputs multi_source/samples/example.json --output reports/source-audit.json`
Example is illustrative only, not a real forecast. Supply actual sourced records for live decisions.

## Next milestones
- Verify access and usage terms for each source and implement compliant collectors.
- Store frozen pre-deadline forecasts and actual FPL outcomes for time-split calibration.
- Add a tested legal 15-player Free Hit builder, price caps, club quotas, captaincy, bench and rolling GW12–19 opportunity-cost solver.
- Wire outputs into existing Monday and deadline tasks after quality gates pass.
