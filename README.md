# Alpha X QQQ intraday submission: notes for reviewers (Edge Lab, Group 6)

Start with the executed notebook `60_submission/AlphaX_QQQ_Intraday_Research_v4_final.ipynb` (an HTML copy is next to it). This file explains how the figures on the form were produced and where they depart from the form's wording.

## Strategy and candidates

Long-only dip buying on QQQ, 1-hour regular-session bars. Signal at the close of bar t: close[t] / close[t-7] - 1 <= -1.2%, previous-session VIX/VIX3M < 1, and no Fed rate decision, Non Farm Payrolls or Inflation Rate MoM release on the entry day (the F3 news-day filter). Entry at the open of bar t+1. Exit after H bars or when a bar closes 3% or more below entry.

- **C1** (lead, exploratory): H = 35 bars. Designed after the final window had been seen, so its final-window result is a second use, not a blind out-of-sample test.
- **F3** (earlier pick): H = 21 bars. Frozen before the final window and run once; it lost 2.6% there and also failed the 2020 to 2023 older-history test.

The form's backtest page reports C1.

## How the form figures were computed (C1, full span 2020-01-03 to 2026-11-12)

| Form field | Value | Definition |
|---|---|---|
| Total completed trades | 209 | one entry and its exit |
| Annualised return | 9.1% | simple, not compounded: net +62.4% of the USD 100k unit over 6.86 years. Compounded equivalent about 7.3% |
| Sharpe ratio | 0.51 | daily mark-to-market P&L (open positions valued at each bar close), flat days included, annualised with sqrt(252) |
| Maximum drawdown | 29.2% | peak to trough of USD 100k + cumulative mark-to-market P&L |
| Profit factor | 1.25 | gross profit / gross loss over completed trades |
| Average hold | 2 to 5 days | mean 31 hourly bars (about 4.4 sessions, 6.4 calendar days); maximum 35 bars |

Source files: `40_results/V4_results.csv`, `40_results/V4_trades.csv`, `40_results/V4_daily_pnl_full.csv`, and the ledgers `60_submission/C1_FULL_trade_ledger.csv` and `60_submission/F3_FULL_trade_ledger.csv`. The notebook recomputes everything and matches the stored ledgers to under 1e-12 USD.

## Departures from the form's wording

- **Position size.** The form asks for one share per entry. We use a fixed USD 100,000 notional per trade (units = 100,000 / entry price, so fractional shares), with no compounding. All percentages are of that fixed unit.
- **Costs.** 0.10% per side flat (the form's allowance for US ETFs, inclusive of commission, fees and slippage), applied throughout. A 0.20% per side stress is reported alongside.

## In-sample and out-of-sample blocks (C1, net of 0.10% per side)

| Block | Dates | Trades | Sharpe | Net |
|---|---|---|---|---|
| Older history | 2020-01-03 to 2023-11-10 | 128 | 0.47 | +35.8% |
| In-sample | 2023-11-13 to 2025-06-30 | 40 | 0.82 | +17.5% |
| Selection | 2025-07-01 to 2025-11-30 | 9 | 1.26 | +5.9% |
| Final window | 2025-12-01 to 2026-11-12 | 32 | 0.18 | +3.2% (-3.2% at 2x cost) |

Sharpe degradation from in-sample (0.82) to the final window (0.18) is far larger than the form's 10% guideline. The final window is a second use for C1; F3 was the strategy frozen and run once there.

## Evidence strength, stated plainly

Full-span Sharpe 0.51 against a pre-registered bar of 0.5; t-statistic about 1.3; approximate deflated Sharpe about 13% after 25 configurations (range 10% to 68% depending on the assumed spread of tried Sharpes); a -35% year in 2022; +62% against +222% for buy and hold QQQ. DIA and IWM checks failed. Every failed test and every configuration tried is in the notebook.

## Reproducibility

Pre-registration hashes, run-once lock files and engine fingerprints are in `00_rules`, `90_logs` and the notebook's first section. Code is in `20_src`. Raw data (`10_data`: IBKR hourly bars and a snapshot of Flywheel files) is not hosted; `20_src/fetch_ibkr_hourly.py` and `20_src/fetch_r2_snapshot.py` show how it was obtained.

## Paper trading

No IBKR paper orders were placed. A read-only forward shadow watcher (`20_src/paper_shadow_watch.py`, configuration `00_rules/FROZEN_CONFIG_C1_SHADOW.json`) was tested on 16 and 17 Nov 2026 and recorded no signals. It was not running continuously from the official start date of 18 Nov because of a market-data session conflict, so there is no forward record and no brokerage statement. The strategy trades about 3 times a month, so a 10-trade paper record was not reachable by the deadline.
