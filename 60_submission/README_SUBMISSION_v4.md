# Alpha X Oct-Nov 2026 - Group 6 - submission package (v4, 17 Nov 2026)

Submitted side by side: **C1** (QQQ, F3 news-day filter, hold 35 bars; exploratory, marginal) and **F3** (hold 21 bars; failed the older-history test and the final window). Every failed test is in the record.

## Step 1. Open PowerShell in the project folder
```powershell
cd C:\Users\User\Desktop\Quant\AlphaX_Intraday_Nov2026
```

## Step 2. Check the fingerprints of the v4 pre-registration (compare with 90_logs\PRE_REGISTRATION_v4.sha256)
```powershell
(Get-FileHash 00_rules\PRE_REGISTRATION_v4_NEW_CANDIDATES.md -Algorithm SHA256).Hash.ToLower()
```
```powershell
Get-Content 90_logs\PRE_REGISTRATION_v4.sha256
```

## Step 3. Check the v4 code and engine (compare with 90_logs\v4_code_20261117.sha256)
```powershell
Get-FileHash 20_src\run_v4_candidates.py, 20_src\alphax_engine_v2.py, 20_src\check_dia_data.py -Algorithm SHA256 | Format-Table Hash, Path
```
```powershell
Get-Content 90_logs\v4_code_20261117.sha256
```

## Step 4. Check the frozen final-window config and runner (compare with 90_logs\FROZEN_CONFIG_OOS.sha256 and oos_code_20261117.sha256)
```powershell
Get-FileHash 00_rules\FROZEN_CONFIG_OOS.json, 20_src\run_oos_once.py -Algorithm SHA256 | Format-Table Hash, Path
```

## Step 5. Re-execute the notebook (reads stored results, rechecks all fingerprints, re-derives the full-span PnL with the frozen engine; it does NOT re-run the run-once studies)
```powershell
cd 60_submission
```
```powershell
jupyter nbconvert --to notebook --execute --output AlphaX_QQQ_Intraday_Research_v4_final_rerun.ipynb AlphaX_QQQ_Intraday_Research_v4_final.ipynb
```

## Files
- `AlphaX_QQQ_Intraday_Research_v4_final.ipynb` / `.html`: executed notebook (fingerprints, record of every stage, equity curves, drawdowns, calendar years, blocks incl. 2x cost, t-stat and deflated-Sharpe range, trade facts, DIA failure, trial ledger, limits).
- `C1_FULL_trade_ledger.csv`, `F3_FULL_trade_ledger.csv`: every trade of the full span 3 Jan 2020 to 12 Nov 2026.
- Earlier stage notebooks: `AlphaX_QQQ_Intraday_Research_v1.*`, `..._v2_filters.*`.
- Pre-registrations: `00_rules\`. Results: `40_results\`. Hashes, locks, data checks, trial counter: `90_logs\`.

## Run-once rule
`run_oos_once.py`, `run_prewindow_v21.py`, `run_v3_screen.py` and `run_v4_candidates.py` write a lock file and refuse to run twice; a second pass must be labelled exploratory by hand.
