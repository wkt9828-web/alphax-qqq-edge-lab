# PRE-REGISTRATION v2 -- Flywheel-filter study on the frozen v1 base signal
Written: 2026-11-14 (SGT), BEFORE any filter was backtested. Supersedes nothing: v1 (hash 7f02cd45...) stays in force as the record; v2 only ADDS filters.
Reason for v2: the Alpha X guidelines ask for a strategy that improves with Flywheel data filters (GEX sign, credit-spread risk-off, event-day, rates regime), compared with and without. v1 used only the VIX/VIX3M gate.
Owner: kt (Group 6). Deadline: 20 Nov 2026 23:59 SGT.

## 1. What is fixed (not re-tuned)
- BASE = v1 chosen config: QQQ, 1h RTH bars, N=7 bars, k=1.2%, H=21 bars, 3% stop, VIX/VIX3M<1 gate (previous session), USD 100,000 one unit, 0.10% per side, no compounding. Chosen in v1 by its own rule; NOT re-gridded here.
- Splits unchanged: IS 2023-11-13..2025-06-30, SELECTION 2025-07-01..2025-11-30, OOS 2025-12-01..data end (2026-11-12), run once, not yet run, not loaded.
- DISCLOSURE: IS and SELECTION were already seen in v1, so v2 SELECTION is not fresh data. OOS remains unseen by any code.
- Baseline numbers to beat (from v1 results CSVs): IS Sharpe 0.8368, net +16.08%, max DD -11.39%, 52 trades; SELECTION Sharpe 0.6813, net +2.88%, 10 trades.

## 2. Filters (each = extra condition ANDed onto the base entry signal; one definition each, no variants; all use data lagged so nothing after the signal bar is used)
Session index D = date of signal bar t. "prev session" = the session before D; "lag-2" = two sessions before D.
- F1_GEX: take the QQQ GEX snapshot dated prev session (10_data/r2_snapshot/historical_gex/QQQ/<date>_exp*/QQQ_gex_table.csv; if two files share a date use the earliest expiry). total = sum(net_gex). ALLOW entry only if total > 0 (positive gamma = dampening regime, consistent with a mean-reversion thesis). Snapshot publication time is unproven, hence the one-session lag. Missing snapshot -> no entry.
- F2_HY: FRED BAMLH0A0HYM2 (HY option-adjusted spread). Take the last observation dated on or before lag-2; change = value - value 20 observations earlier. ALLOW only if change <= 0 (spread not widening). Lag-2 matches the observed R2 publication lag (R2 file uploaded 11 Nov held data to 9 Nov). Missing -> no entry.
- F3_EVENT: ALLOW only if the ENTRY day (date of bar t+1, a calendar fact) has no scheduled US event among: "Fed Interest Rate Decision", events starting "Non Farm Payrolls", events starting "Inflation Rate MoM" (US CPI), from news/economic_calendar.csv (country US; timestamps are UTC, converted to America/New_York date; schedule only, the actual/estimate columns are never read). The calendar ends 2026-11-05: later days are treated as no-event and this is disclosed.
- F4_RATES: FRED DGS10, last observation on or before lag-2; d5 = value - value 5 observations earlier. ALLOW only if |d5| <= the 90th percentile of |d5| over the previous 252 observations (strictly before the current one). Missing -> no entry.
- F5_COMBO: defined only AFTER the single-filter results: the intersection of every filter that individually passes BOTH stages below. Tested only if at least 2 pass.
Every variant also keeps the v1 VIX/VIX3M gate.

## 3. What "improves" means (decided now)
IS stage (per filter): trades >= 30; net > 0; net at 2x cost > 0; Sharpe >= 0.9368 (base 0.8368 + 0.10); max drawdown no worse than -11.39%; (ex-top-3 profit > 0 or top-3 share < 50%); all self-checks pass.
SELECTION stage (only for IS passers): trades >= 6; net > 0; Sharpe >= 0.6813 (not worse than base).
Choice: among variants passing both stages, best SELECTION Sharpe; ties -> fewer filters.
If NO variant passes: the finding is "no tested Flywheel filter improved the base"; the rules are not loosened; whether to submit the v1 base without a filter is then the owner's decision and is reported as such.
OOS (one pass, after freezing the chosen variant, only on owner's go): pass = net > 0 and >= 10 trades; preferred Sharpe within 10% of IS.

## 4. Trial budget
Distinct configs so far: 14 (12 v1 grid + 2 v1 extras). v2 adds at most 5 (F1..F5) = at most 19, under the 20-config warning level (BP3.4). Every run is appended to 90_logs/config_counter.csv.

## 5. Engine v2
alphax_engine_v2.py = v1 engine plus (a) an optional per-bar `extra_ok` mask, (b) selfchecks that pass gate_on/extra_ok through their re-runs (fixes the v1 harness slip found 2026-11-13). Regression test BEFORE any filter result is read: with no filter it must reproduce v1 IS and SELECTION numbers exactly, and gate-off IS self-checks must pass.
Paper-trading note: HY/rates/GEX can be refreshed nightly from R2 (lagged); the event calendar stops 2026-11-05, so F3 cannot be applied live without another source.
