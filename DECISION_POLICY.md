# FPL decision policy — v1 (2026/27)

## Mandate and separation
Entry 1580840 (Nicho11s). **Single strategy:** maximize expected season FPL points under the official rules, uncertainty, budget, chip inventory and future transfer options. Worldwide/Colombia ranks are performance benchmarks. Cumbres top-eight is a personal goal and **reporting-only**; never feed Cumbres rival squads, ownership, captaincy or standings into projections, optimization, risk preferences, transfer choices or captaincy. Continue collecting Cumbres data separately for optional retrospective inspection. Never create a parallel league-aware optimizer.

## Evidence and independence
Challenge user-suggested transfers and the model alike. A player name mentioned by the user does not confer priority. Compare every proposed move against all reasonable candidates, doing nothing and rolling an FT. Do not chase last week's returns, a price rise, a popular player, or a desire to spend cash. Distinguish proven facts, independent projections, model assumptions and qualitative judgment. Never manufacture xPts, selling prices, probabilities, or a claim of model completion. If independent projections are unavailable, report that limitation rather than inventing a ranking. Compare forecasts on the same horizon and within the same model; calibrate ensembles using time-split, out-of-sample error, not arbitrary weights.

## Mandatory freshness gate
Before each actionable report fetch data/latest-summary.json; verify collected_at_utc, current_gameweek, current_gameweek_finished, latest_public_squad_gameweek, next_deadline_utc. Confirm fixtures, official player statuses, dated team news, and prices. Public post-deadline picks are NOT the live editable squad. Do not assume current bank, free transfers, selling prices or transfers. Never call a gameweek finished unless official finished is true. Mark incomplete/stale data and block unconditional affordability claims.

## Optimization objective
Optimize legal squad-level expected points over a rolling 6-GW horizon, with longer chip planning to GW19 and beyond; discount distant uncertainty, model 0/1/2+ transfers, banked FT opportunity cost (up to official limit), hits, actual selling-price rules, club quotas, squad composition, starting XI/formation, bench order, captain/vice-captain, auto-subs and price changes. Money left in bank is neither a reward nor a penalty; judge marginal points and flexibility. Minutes/start probabilities, xG/xA, clean-sheet and defensive-contribution probabilities, bonus, fixtures, and injury uncertainty must inform forecasts. Quantify upside and downside; use uncertainty and scenario sensitivity, not fixed confidence claims. Prefer the highest credible expected-points strategy; ownership is not an input.

## Chips are first-class constraints
Verify official 2026/27 chip rules and remaining inventory before recommendations. First-half chips expire at GW19 deadline, second set begins GW20; only one chip per GW, special Free Hit adjacency restrictions and transfer-banking interactions must be tested against current official rules. GW5 first Wildcard is recorded used; remaining first-half Free Hit, Bench Boost and Triple Captain are provisional until refreshed official history. Optimize Triple Captain extra captain xPts, Bench Boost expected bench points net of setup costs, Free Hit one-week gain and opportunity cost, second-half Wildcard/chip sequencing. GW16 Haaland TC is a *candidate*, not a locked choice. Never waste an expiring chip or precommit without comparisons.

## Weekly reporting
1. Timestamp and data verification.
2. Actual 15-man squad, bank/FT/selling prices only if verified.
3. Best starting XI, captain, bench order and projected points with uncertainty.
4. Top three feasible transfer plans including roll, net 6-GW expected XI gain, hits, cash, FT value and future chip impacts.
5. Reasons to reject popular/user-proposed alternatives, material minutes/injury risks and price timing.
6. Chip inventory and next decision window.
7. Worldwide and Colombia rank, plus a **separate informational Cumbres standings section**. Never let the latter alter recommendations.
8. Store pre-deadline forecasts and decisions for hindsight-free review.

## Engineering and verification roadmap (NOT implemented merely by this policy)
A. Ingest official scoring and fixture data, independent xPts and minutes forecasts with provenance and timestamps; add defensive-contribution forecasts.
B. Implement legal lineup, bench, transfers, bank, chips and multiweek solver with rule-unit tests.
C. Backtest time-split forecast calibration, solver against roll/naive baselines, and pre-deadline decision logs.
D. Integrate actionable price monitoring with optimal shortlist, avoiding speculative alerts or premature transfers.
E. Keep public Cumbres collector intact, but strictly separate it from model features.

## Acceptance gate
Until A–C are implemented and tested, label all decisions as **research-informed provisional**, not mathematically optimized. Do not claim verified 6-GW point differences without a same-model source and time stamp. Never execute transfers automatically.
