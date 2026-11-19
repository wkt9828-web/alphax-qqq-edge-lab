# PRE-REGISTRATION v3 -- volume-profile filters and a trend-regime guard on the frozen v1 base
Written: 2026-11-16 (SGT), DRAFT until hashed; to be hashed BEFORE any v3 filter is backtested. v1 (7f02cd45...), v2 (776d4321...) and v2.1 (a97d0d21...) stay in force unchanged.
Owner: kt (Group 6). Deadline: 20 Nov 2026 23:59 SGT.

## 1. Context, stated plainly
- v2.1 (run once on 15 Nov, 2020-01-03..2023-11-10): the base was NOT supported (164 trades, Sharpe -0.12, net -8.6%, -41.4% at 2x cost, drawdown -52.9%; -61.8% in 2022) and base + F3 did not improve it (Sharpe 0.16, -20.4% at 2x cost).
- The owner has decided the project is submitted with its best-evidence result and a full, honest record. v3 looks for a better-evidenced candidate and a regime guard. It is NOT a rescue of a failed test: the v2.1 verdict stands and is reported in the submission.
- T1 below is designed AFTER seeing the 2022 loss. It is exploratory by construction. Its only independent evidence will be the OOS window and paper trading.

## 2. What is fixed (not re-tuned)
- BASE = QQQ, 1h RTH bars, N=7, k=1.2%, H=21, 3% stop, VIX/VIX3M(previous session)<1 gate, USD 100,000 one unit, 0.10% per side (2x = 0.20%), no compounding, t -> t+1 execution, forced exit at stage end (engine alphax_engine_v2.py, unchanged).
- Splits unchanged: IS 2023-11-13..2025-06-30, SELECTION 2025-07-01..2025-11-30. OOS 2025-12-01..2026-11-12: not loaded by any v3 code (hard stop at 2025-11-30).
- DISCLOSURE: IS and SELECTION were already seen in v1 and v2, so they are not fresh data for v3.

## 3. Data facts (checked on file layout only, before any return was computed)
- Profiles (R2 profiles/QQQ, one JSON + parquet per date) are built from OPTION trades (source: theta_trade_quote; side rule: price vs quote mid; volume is option volume bucketed by the underlying price). Fields used: vpoc, vah, val (volume value area, QQQ price units), net_delta (signed delta of aggressive option flow), contracts (option contracts traded).
- QQQ profiles are fully daily only from 2023 (about 250 dates a year); before that they are sparse (56 dates in 2020, 124 in 2021, 170 in 2022). Profile filters are therefore testable only inside IS/SELECTION/OOS, never on 2020-2022.
- Publication time of each historical profile is unknown (5,566 of 5,658 files carry a bulk R2 upload stamp of 2026-11-01). Every profile filter therefore uses the PREVIOUS session's profile only (one-session lag). Missing profile for the previous session -> no entry.

## 4. Candidates (each an extra condition ANDed onto the base entry signal; one definition each; no variants)
Session D = date of signal bar t. "prev" = the session before D.
- P1_FLOW: ALLOW entry only if net_delta[prev] / contracts[prev] < 0 (the previous session's aggressive option flow was net delta-selling: forced or fearful selling that tends to exhaust).
- P2_VALUE: ALLOW entry only if close[t] < val[prev] (the signal bar closes below the previous session's volume value-area low: price stretched below accepted value).
- T1_TREND (regime guard): ALLOW entry only if the previous session's QQQ daily close > its 200-session simple moving average (R2 market_data/daily/QQQ.csv, values up to prev only; fewer than 200 observations -> no entry). Aimed at the 2022-style bear market.
- C1 = F3_EVENT AND T1_TREND (F3 exactly as in v2: skip entries whose entry day has a Fed rate decision, Non Farm Payrolls or Inflation Rate MoM event). Always run.
- C2 = F3_EVENT AND every profile filter (P1, P2) that passes BOTH stages below. Run only if at least one profile filter passes both stages.
- Every variant also keeps the VIX/VIX3M gate.
Trial budget: at most 5 new configs (P1, P2, T1, C1, C2). Distinct configs so far 18; after v3 at most 23. This is ABOVE the BP3.4 warning level of 20: the submission will state it, and report a deflated-Sharpe estimate for the chosen candidate as a caveat (not a pass/fail test).

## 5. Criteria (decided now)
STANDARD criteria (as v2; used for P1, P2, C1, C2 and for F3 as already measured):
- IS: trades >= 30; net > 0; net at 2x cost > 0; Sharpe >= 0.9368 (base 0.8368 + 0.10); max drawdown no worse than -11.39%; (ex-top-3 profit > 0 or top-3 share < 50%); all self-checks pass.
- SELECTION (only IS passers): trades >= 6; net > 0; Sharpe >= 0.6813.
T1 alone is a GUARD, not a candidate: it is reported with the guard test (IS and SELECTION: net > 0, net at 2x > 0, Sharpe not more than 0.10 below base, drawdown no worse than base) for information; it can only enter the submission inside C1.
ELIGIBLE = passes both stages under the STANDARD criteria. F3 (already measured in v2) is eligible by construction.
CHOICE among eligible variants = highest POOLED Sharpe (one continuous backtest from 2023-11-13 to 2025-11-30, net of costs); ties -> fewer filters. Pooled Sharpe is used instead of Selection Sharpe because Selection has only about 10 trades. The rule's pick is the DEFAULT; the owner may choose another eligible variant, and the submission will then say so.
Always reported: trades per stage, by-year, drawdown, 2x cost, profit factor, top-3 share, benchmark buy-and-hold same unit, filter coverage (share of sessions with a usable prev profile), and the filter's blocked-day count.

## 6. What happens after (decided now)
1. The chosen variant is frozen with hashes (FROZEN_CONFIG) and run ONCE on OOS (1 Dec 2025 .. 12 Nov 2026) only on the owner's explicit go; reported as it comes out, including by-year, 2x cost, buy-and-hold and top-3 share. The 6 Nov and later event dates for F3 are added by hand from the official BLS and Fed calendars and recorded in the frozen config (the R2 calendar ends 5 Nov).
2. EXPLORATORY (clearly labelled, never used to choose): the chosen variant and T1/C1 are run once on the 2020-01-03..2023-11-10 pre-window (T1/C1 are computable there; profile filters are not). If a chosen variant contains no regime guard, the submission says its 2020-2023 behaviour is the failed v2.1 result.
3. If no new variant is eligible, F3 remains the default candidate, labelled "failed the older-history test".

## 8. Disclosure of an early look (added before hashing; no definition or criterion above was changed because of it)
On 16 Nov, before this file was hashed, a plumbing dry run of run_v3_screen.py on SYNTHETIC profile data printed the real in-sample (IS) results of T1_TREND and C1 (they do not depend on profile data) and the pooled F3 result: T1 IS Sharpe 0.50, +8.8%, drawdown -11.1%; C1 IS Sharpe 0.77, +13.5%, drawdown -6.0%; pooled F3 Sharpe 1.32. Under the criteria in section 5 this means T1 fails its guard test and C1 fails the standard IS bar (Sharpe below 0.9368). The runner was then changed so a dry run prints no performance numbers. The P1 and P2 results have NOT been seen: the profile CSV did not exist yet and the dry run used random numbers.

## 7. Run-once rule
run_v3_screen.py verifies this file's hash before running, never loads data after 2025-11-30, writes a lock file after the real run and refuses to run again. A plumbing/dry run uses synthetic profile data and prints no performance numbers of the real filters.
