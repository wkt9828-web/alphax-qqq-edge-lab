# Forward shadow log for C1 and F3 (read-only, no orders)

`20_src\paper_shadow_watch.py` watches QQQ hourly bars on the existing IBKR session (port 4003, read-only, its own clientId 9201) and writes what the frozen rules WOULD do from 18 Nov 2026: every dip signal with the reason it was or was not traded, every hypothetical entry (open of the next bar) and every exit. It places no orders and contains no order code.

Tested before delivery: a replay over the stored hourly file reproduced all 16 entries and 16 exits of C1 and F3 since 9 Sep 2026 exactly (same times, prices and exit reasons). It has NOT been run against live TWS yet.

## Step 1. Open PowerShell in the project folder
```powershell
cd C:\Users\User\Desktop\Quant\AlphaX_Intraday_Nov2026
```

## Step 2. Fingerprint the C1 shadow config (the watcher refuses to run until this file exists and matches)
```powershell
$h = (Get-FileHash 00_rules\FROZEN_CONFIG_C1_SHADOW.json -Algorithm SHA256).Hash.ToLower(); "$h  00_rules/FROZEN_CONFIG_C1_SHADOW.json" | Out-File -Encoding ascii 90_logs\FROZEN_CONFIG_C1_SHADOW.sha256
```
```powershell
Get-Content 90_logs\FROZEN_CONFIG_C1_SHADOW.sha256
```

## Step 3. One test pass (TWS/Gateway must be open and logged in on port 4003; no orders are possible)
```powershell
python 20_src\paper_shadow_watch.py --port 4003
```
Check the output: `connected read-only`, a `last complete bar` time, and the lines for C1_QQQ_H35_F3 and F3_QQQ_H21. If it says `IBKR VIX/VIX3M not available`, that is expected on some accounts: the gate then comes from the R2 snapshot, which ends 11 Nov, so you must fill `50_paper\vix_manual.csv` (Step 5) or new dips will be logged as `gate data missing`.

## Step 4. Keep it running during US market hours (22:30 to 05:00 Malaysia time in winter), one pass every 5 minutes
```powershell
python 20_src\paper_shadow_watch.py --port 4003 --loop
```

## Step 5. Every trading day before the open, check the gate and the calendar
```powershell
Get-Content 50_paper\shadow_status.json
```
Look at `gate_series_last_date` (must be the previous session) and `events_verified_through` (currently 2026-12-10: official Fed/BLS dates checked on 17 Nov). If the gate date is old, append the previous session's closes to `50_paper\vix_manual.csv` as `YYYY-MM-DD,vix,vix3m`. Entries after the verified date are logged `UNVERIFIED_CALENDAR`, never hidden.

## Step 6. Read the log
```powershell
Import-Csv 50_paper\shadow_log.csv | Format-Table logged_at_utc, variant, event, signal_time_et, entry_px, detail -AutoSize
```
Files in `50_paper\`: `shadow_log.csv` (append-only evidence), `shadow_runs.log` (one heartbeat line per pass, which proves the watcher was running when "no signal" is claimed), `shadow_status.json` (open positions, data sources), `snapshots\` (bars at each hypothetical entry), `events_manual.csv`, `events_verified_through.txt`, `vix_manual.csv`.

## What this is and is not
It is a forward, time-stamped record of what C1 and F3 would have done, from rules hashed before the first day. It is not IBKR paper evidence: there are no orders, fills or statement. Real paper orders on the new account (port 4004) would be a separate step that needs your explicit approval.
