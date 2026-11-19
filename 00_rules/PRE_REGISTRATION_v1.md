# PRE-REGISTRATION v1 — Alpha X Oct–Nov 2026 — Intraday project (independent of any running strategy)
Written: 2026-11-13 (SGT) BEFORE any strategy backtest. Any change after the first backtest = new labelled version (v2…), logged in 90_logs.
Owner: kt (Group 6). Deadline: 20 Nov 2026 23:59 SGT. Submission = ONE quality alpha. If nothing passes the gates, the outcome is "no submission" — rules are NOT loosened.

## 1. Hypothesis (one sentence)
After a sharp multi-hour selloff in QQQ during a NON-inverted volatility term structure (VIX/VIX3M < 1), forced/liquidity-driven selling partly reverses over the next 1–3 sessions by more than the 0.20% round-trip cost.

## 2. Instrument, bars, sizing
- Primary: QQQ, 1-hour REGULAR-HOURS bars (IBKR TRADES, useRTH=1). Long only. IWM = same rule, NO retuning, reported as robustness check only (not a second alpha).
- Sizing: 1 fixed unit = USD 100,000 notional per entry, no compounding, no stacking (one position at a time). Cumulative return = Σ USD PnL / 100,000 (never cumprod).
- Costs: 0.10% per transaction (entry and exit each) on notional. Sensitivity run at 0.20%/side (2x). No other slippage assumed (liquid ETF, market orders at bar open) — stated limitation.

## 3. Signal (all at bar close t; uses only data <= close of t)
- DROP: close[t] / close[t-N bars] - 1 <= -k   (rolling over regular-hours bars; overnight gaps included)
- REGIME GATE (daily, lagged 1 day): VIX_close[D-1] / VIX3M_close[D-1] < 1.0, where D is the date of bar t. Always on (not tunable). Source: R2 market_data/daily/_VIX.csv, _VIX3M.csv.
- Entry: BUY at OPEN of the next bar (t+1) — never at the signal bar's close. No P&L on the signal bar.
- Exit: SELL at the OPEN of the bar after the first of: (a) H hourly bars held, (b) bar close <= entry*(1-3%) protective stop (fixed, not tuned). Fill at next bar open.
- Flat required to enter. No re-entry at the same bar as an exit.

## 4. Parameter grid (ONLY these; 12 selectable configs)
N ∈ {4, 7} bars; k ∈ {0.8%, 1.2%}; H ∈ {7, 14, 21} bars (~1, 2, 3 sessions).
Also reported (NOT selectable): gate OFF ablation of the chosen config; IWM check; 2x-cost run.
Total configs tested counter is kept in 90_logs/config_counter.csv; >20 would require a deflated-Sharpe warning (BP3.4).

## 5. Data and splits (chronological; dates fixed now)
- Backtest window = 3 most recent years: 2023-11-13 → last complete session available at data freeze (expected 2026-11-11/12). Warm-up bars before 2023-11-13 are used only for lookbacks.
- IS: 2023-11-13 → 2025-06-30. SELECTION: 2025-07-01 → 2025-11-30. OOS: 2025-12-01 → data end. (IS+SELECTION ≈ 68% of window, OOS ≈ 32%.)
- Tuning on IS only; variant choice on SELECTION only; OOS run ONCE after config freeze (hash recorded). Nothing changes after OOS is viewed; otherwise it is relabelled SELECTION.
- OOS disclosure: the owner has seen daily QQQ/IWM behaviour through Nov 2026 in earlier, separate daily-strategy research. The OOS here is "frozen-rule single-pass" but not market-blind; forward paper trading is the blind evidence.
- Price source: IBKR hourly RTH (research + paper). R2 daily QQQ/IWM close used to cross-check IBKR session closes (tolerance 0.05%; mismatches listed). R2 gate data lagged one day (also protects against batch-publication lag).
- Not used: GEX, profiles, option volume (short/PIT-unconfirmed); may appear only as clearly-labelled exploratory notes, never in the submitted rule.

## 6. Gates (decided before testing)
IS gate (per config): ≥30 trades; net Sharpe ≥ 0.8; net PnL > 0; net PnL stays > 0 after removing the 3 best trades OR top-3 trades < 50% of total net profit; PnL > 0 at 2x cost.
SELECTION rule: among configs passing the IS gate, choose the best SELECTION net Sharpe with SELECTION net PnL > 0 and ≥8 trades; ties → shorter H, then larger k. None qualifies → STOP, no alpha.
OOS pass: net PnL > 0 and ≥10 trades; preferred (not required): Sharpe degradation IS→OOS ≤ 10%. Report win rate; >80% needs explanation.
Always report: trade counts per stage, by-year, worst trade, max DD (on capital, cumsum), profit factor, benchmark (buy&hold QQQ same period, same unit), top-3 trade share.

## 7. Mandatory self-checks (PASS/FAIL printed with every result)
Truncation test; fill strictly after signal; no shift(-k) features, no centered windows; PnL reconciliation Σ trade = Σ daily = final − start (±$0.01); fixed-notional return method; costs on entry and exit; no look-ahead in daily gate (D-1 only).

## 8. Paper trading
Separate NEW paper account (pending IBKR approval, details from owner). Same rules/config hash; signals from IBKR hourly bars; data source noted in the paper log; no orders without explicit owner approval; infrequent signals are NOT forced.

## 9. Gate-0 observation recorded before testing (IS only, descriptive)
QQQ RTH-hour bars (10:00–15:00 starts), IS: mean |open→close| 0.254% vs 0.20% round-trip cost (ratio 1.27) → holds of 1–3 hours are cost-dominated; hence H ≥ 7 bars. Mean 1/2/3-day forward return from the 15:00 close in IS: +0.10% / +0.20% / +0.31% (bullish drift: benchmark comparison is essential).
