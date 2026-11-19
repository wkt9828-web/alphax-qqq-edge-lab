# PRE-REGISTRATION v2.1 -- Older-history (PRE-WINDOW) test of the frozen v2 rule
Written: 2026-11-15 (SGT), BEFORE any pre-2023-11-13 hourly bar was downloaded or looked at. Adds to v1 (hash 7f02cd45...) and v2 (hash 776d4321...); changes neither.
Owner: kt (Group 6). Deadline: 20 Nov 2026 23:59 SGT.

## 1. Purpose
The v1/v2 research used only the 3 most recent years (IS 2023-11-13..2025-06-30, SELECTION 2025-07-01..2025-11-30). The base signal and the event-day filter were found/kept on those windows. This test runs the SAME frozen rules, once, on EARLIER data that no code has loaded: QQQ hourly bars from 2020-01-03 to 2023-11-10 (PRE-WINDOW, about 3.85 years, includes the Mar-2020 crash, the 2021 melt-up and the 2022 bear market).
It is an out-of-time check. It does NOT replace IS / SELECTION / OOS, does not touch the OOS window (2025-12-01 onward), and nothing in it may be used to retune any parameter.

## 2. What is frozen (identical to v2; no parameter is changed)
- QQQ, IBKR 1h regular-hours bars (TRADES, useRTH=1), long only, USD 100,000 per entry, one position at a time, no compounding, 0.10% per side (2x = 0.20% per side), t -> t+1 execution.
- Signal: close[t]/close[t-7] - 1 <= -1.2%; gate: VIX/VIX3M of the PREVIOUS session < 1.0; exit after 21 bars or bar close <= entry x (1 - 3%), filled at the next bar open. Forced exit at the last bar of the window.
- Variant A = base. Variant B = base + F3_EVENT (skip entries whose ENTRY day has a US Fed Interest Rate Decision, Non Farm Payrolls, or Inflation Rate MoM event; calendar = news/economic_calendar.csv, US rows, UTC converted to New York date, schedule only). Exactly these two variants. F1/F2/F4 are NOT run (GEX starts Nov 2023, HY spread starts Nov 2023, and they already failed in v2).
- Code: alphax_engine_v2.py (unchanged), the F3 logic copied from flywheel_filters.py, run by run_prewindow_v21.py. Their SHA-256 values are recorded in 90_logs before the run.

## 3. Window and data
- Test window (trades allowed): 2020-01-03 .. 2023-11-10. Reason for the start: VIX3M begins 2020-01-02 and the gate needs the previous session's value. Warm-up bars from 2019-12-02 are used only for the 7-bar lookback.
- The window ends 2023-11-10 so that it cannot overlap the IS start (2023-11-13).
- Price source: new IBKR pull, QQQ 1h RTH, 2019-12-02 .. 2023-11-10, with overlapping request chunks (fixes the first-of-month gap defect of the v1 download) and an automatic gap-fill. Checks before any strategy run: session count vs R2 QQQ daily (missing sessions must be 0 after gap-fill), bars/day structure, duplicate/NaN, opens vs R2 daily opens (tolerance 0.1%), and bar-for-bar agreement with the existing file on the overlap 2023-07-03..2023-11-10.
- Disclosure: the owner already knows broad market history for 2020-2023 (COVID crash, 2022 bear market). The test is rule-blind (rules and thresholds fixed before data) but not market-blind.

## 4. Decided now: what counts as support
Variant A (base) "SUPPORTED" if ALL: trades >= 30; net PnL > 0; net PnL > 0 at 2x cost; net Sharpe >= 0.5 (lower than the 0.8 IS gate because out-of-time degradation is expected); (PnL ex-top-3 trades > 0 OR top-3 share < 50%); all engine self-checks PASS.
Variant B (base + F3) "IMPROVES" if ALL: B meets the same checks as A; Sharpe(B) >= Sharpe(A) + 0.10 (the v2 IS rule); max drawdown(B) no worse than max drawdown(A).
Always reported (not pass/fail): buy-and-hold QQQ over the same window and same unit; by-year table; trades blocked by F3 and their PnL; a random-day-blocking placebo for F3 (500 draws, seed 20261115, same number of blocked days).

## 5. What happens next (decided now, so the result cannot be spun)
1. A SUPPORTED and B IMPROVES -> freeze base + F3 as the submitted strategy (OOS one pass only on the owner's go).
2. A SUPPORTED but B does not improve -> F3 is dropped as a non-generalising filter; freeze base only; the report says the Flywheel filter did not hold up out-of-time. Whether to submit a base-only strategy is the owner's decision.
3. A not supported -> the v1 edge is not confirmed out-of-time. Rules are NOT loosened; no re-tuning on this window. Move to the volume-profile screen (separate pre-registration v3) and/or no submission; owner decides.
Any second look at this window with a changed rule is labelled EXPLORATORY and cannot be the basis of a submitted strategy.

## 6. Trial budget
No new parameter configuration is introduced (same two variants already counted: base and base+F3). Two stage rows (stage = PREWINDOW) are appended to 90_logs/config_counter.csv for traceability. Distinct configs stay at 18. The follow-up volume-profile screen (v3) is capped at 2 new configs so the total cannot exceed 20 (the BP3.4 warning is for more than 20).

## 7. Run-once rule
run_prewindow_v21.py verifies this file's hash against 90_logs/PRE_REGISTRATION_v2_1.sha256 before running, writes a lock file after the first real run and refuses to run again. A dry run on already-seen IS data (--dryrun) is used only to prove the code reproduces the v1/v2 IS numbers.

## 8. Note on the seal (IS / SELECTION / OOS)
PRE-WINDOW is a fourth, earlier slice. It is older than IS, shares no dates with IS, SELECTION or OOS, and is read only after the rules and pass criteria above are hashed. It does not spend or reveal the OOS. It is not "tuning" because no output of it can change a parameter.
