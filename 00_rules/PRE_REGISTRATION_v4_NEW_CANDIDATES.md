# PRE-REGISTRATION v4 -- two new candidates, exploratory, run once across all four blocks
Written: 2026-11-17 (SGT), DRAFT until hashed; to be hashed BEFORE any v4 result is computed. v1, v2, v2.1, v3 and the frozen F3 config stay in force unchanged.
Owner: kt (Group 6). Deadline: 20 Nov 2026 23:59 SGT. Chosen by the owner on 17 Nov: "both candidates".

## 1. Context, stated plainly
- F3 (QQQ, hold 21 bars, news-day filter) passed IS and Selection, failed the 2020-2023 older-history test and then lost 2.6% net (Sharpe -0.19, -10.4% at 2x cost) in the final window 1 Dec 2025 .. 12 Nov 2026, run once on 17 Nov. That result stands and is the first thing the submission reports.
- The final window is therefore OPENED: we know how F3 and QQQ did in it. Both candidates below were chosen AFTER seeing that result, so the window is a "second-use window", not a sealed out-of-sample test. Every result is labelled exploratory and none is used to pick between the candidates.
- Neither candidate has been run on any data. No H=35 result and no DIA result has been computed or seen by anyone before this file is hashed.

## 2. Candidates (one definition each; no variants; no tuning)
Common rule (unchanged from v1/F3): signal at close of bar t if close[t]/close[t-7]-1 <= -1.2% AND previous-session VIX/VIX3M < 1; entry at open of bar t+1; exit after H bars or when a bar closes <= entry*(1-3%); one position at a time; USD 100,000 per entry, no compounding; 0.10% per side (2x = 0.20%); forced close at the end of each tested window; 1h regular-hours bars; engine alphax_engine_v2.py unchanged. F3 = skip entries whose entry day (ET) has a Fed rate decision, Non Farm Payrolls or Inflation Rate MoM (same definition and same hand-added 6 and 10 Nov 2026 dates as FROZEN_CONFIG_OOS.json).
- C1_QQQ_H35_F3: QQQ, H = 35 bars (5 sessions), with F3. Reason (from in-sample evidence only): in the v1 grid every one of the four dip settings improved as the hold grew from 7 to 14 to 21 bars, and 21 was the largest hold tested, so the next step on that trend is untested.
- C2_DIA_F3: the exact frozen F3 rule (N=7, k=1.2%, H=21) on DIA (Dow Jones ETF), no re-tuning. Reason: the fund prefers non-SPX ideas and this is an instrument the rule was never fitted on. Known prior: the same rule failed in-sample on IWM (Sharpe -0.85), so a low chance of success is expected.
- Comparator, not a candidate: C2b_DIA_base (DIA without F3) to show with/without the filter. It counts as a trial.
- Reference rows (already measured configs, not new trials): QQQ F3 (H=21) and QQQ base re-run on the same blocks for comparison.
Trial budget: 3 new configs (C1, C2, C2b). Distinct configs so far 22; after v4: 25 (above the BP3.4 warning level of 20; the submission says so).

## 3. Blocks (each run separately, positions do not carry across blocks) plus one continuous run
PRE 2020-01-03..2023-11-10 | IS 2023-11-13..2025-06-30 | SELECTION 2025-07-01..2025-11-30 | FINAL (second-use) 2025-12-01..2026-11-12 | FULL 2020-01-03..2026-11-12 as one continuous backtest. Bars before a block's start are used only as lookback; no signal before the start.
DISCLOSURE: IS, Selection and the older window were already seen for QQQ; for DIA no window has ever been loaded.

## 4. Data
QQQ: IBKR 1h RTH, the pre-window file and the main hourly file merged on timestamp (identical on their overlap). DIA: IBKR 1h RTH fetched 17 Nov, 2019-12 .. 2026-11-12, checked by check_dia_data.py (must say ALL PASS): every session that QQQ has must exist, 7 bars on a normal day, first bar 09:30, no duplicates or NaN, nothing after 2026-11-12, and a sanity check that DIA and QQQ intraday-daily moves are highly correlated (instrument and timestamps right; no strategy return is computed). Gate: VIX/VIX3M from the R2 snapshot (ends 11 Nov; the 12 Nov session uses 11 Nov, as before).

## 5. Criteria (decided now; informational labels, not a selection rule)
A candidate is labelled SUPPORTED only if, on the FULL continuous run: trades >= 50; net > 0; net at 2x cost > 0; Sharpe >= 0.5; (ex-top-3 profit > 0 or top-3 share < 50%); all self-checks pass; AND net > 0 in at least 3 of the 4 blocks.
C1 additionally must beat QQQ F3 (H=21) on FULL: Sharpe at least 0.10 higher and max drawdown no worse.
C2 is additionally compared with C2b: "the news-day filter helps on DIA" if FULL Sharpe is at least 0.10 higher with F3.
Anything else is labelled NOT SUPPORTED and reported in full. Both candidates are reported whatever they show; the final-window block is never used to choose between them or to change them.
Always reported per block: trades, Sharpe, net, net at 2x, max drawdown, win rate, profit factor, top-3 share, ex-top-3 profit, same-unit buy-and-hold, by-year table, and the FULL equity curve.

## 6. Run-once rule
run_v4_candidates.py verifies this file's hash, the code hashes and the DIA data check before running, writes a lock after the real run and refuses a second pass. A plumbing dry run prints no performance numbers.
