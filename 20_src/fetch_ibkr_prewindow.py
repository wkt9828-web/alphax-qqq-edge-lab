"""
fetch_ibkr_prewindow.py -- READ-ONLY IBKR download of QQQ 1-hour REGULAR-HOURS bars for the PRE-WINDOW (PRE_REGISTRATION_v2_1).
No orders are ever placed. Run on Windows (Lara) with TWS/Gateway open. Writes ONLY to 10_data/ibkr_hourly_prewindow.

  python fetch_ibkr_prewindow.py --port 4003

Differences from fetch_ibkr_hourly.py (fixes its first-of-month defect):
  * each request ends at 00:00 UTC of the NEXT day (so the session of the mark date is included) and asks for 35 D, so neighbouring
    chunks overlap by ~5 days; duplicates are dropped on merge;
  * after merging, sessions missing versus R2 QQQ daily are re-requested one by one (same method as fetch_ibkr_gapfill.py).
Resumable: finished chunks are cached; rerun after any pacing error. Own clientId 9103 (no collision with AQ100 / P12 / 9101 / 9102).
Final file keeps only sessions <= 2023-11-10 so no IS data can be mixed in.
"""
import argparse, time
from pathlib import Path
import pandas as pd
from ib_insync import IB, Stock, util

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--client-id", type=int, default=9103)
ap.add_argument("--start", default="2019-12-02")
ap.add_argument("--end", default="2023-11-10")          # last session to keep
ap.add_argument("--sleep", type=float, default=11.0)    # pacing (seconds) between requests
a = ap.parse_args()
root = Path(__file__).resolve().parents[1]
OUT = root / "10_data" / "ibkr_hourly_prewindow"; (OUT / "chunks").mkdir(parents=True, exist_ok=True)
R2_DAILY = root / "10_data" / "r2_snapshot" / "market_data" / "daily" / "QQQ.csv"
END = pd.Timestamp(a.end)

def to_et_day(s):
    return pd.to_datetime(s, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()

def merge():
    parts = [pd.read_csv(p) for p in sorted((OUT / "chunks").glob("QQQ_*.csv")) if p.stat().st_size > 5]
    d = pd.concat(parts, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"], utc=True)
    d = d.drop_duplicates("date").sort_values("date")
    d["et"] = d["date"].dt.tz_convert("America/New_York")
    d = d[d["et"].dt.tz_localize(None).dt.normalize() <= END]          # never keep anything after the window end
    d.to_csv(OUT / "QQQ_1h_RTH_pre.csv", index=False)
    return d

ib = IB(); ib.connect(a.host, a.port, clientId=a.client_id, readonly=True, timeout=20)
print("connected (read-only), serverVersion", ib.client.serverVersion())
c = Stock("QQQ", "SMART", "USD"); ib.qualifyContracts(c)

# 1) overlapping chunks: marks every 30 days, each request = 35 days ending 00:00 UTC of the day AFTER the mark
marks = []; m = pd.Timestamp(a.start, tz="UTC") + pd.Timedelta(days=35)
while True:
    marks.append(m)
    if m >= pd.Timestamp(a.end, tz="UTC") + pd.Timedelta(days=1): break
    m += pd.Timedelta(days=30)
for m in marks:
    f = OUT / "chunks" / f"QQQ_pre_{m:%Y%m%d}.csv"
    if f.exists(): continue
    bars = ib.reqHistoricalData(c, endDateTime=m.to_pydatetime(), durationStr="35 D", barSizeSetting="1 hour",
                                whatToShow="TRADES", useRTH=True, formatDate=2)
    df = util.df(bars) if bars else pd.DataFrame()
    if len(df): df.to_csv(f, index=False)
    print(m.date(), len(df), "bars" + ("" if len(df) else "  <-- EMPTY, not cached, rerun later"))
    time.sleep(a.sleep)
d = merge(); print("merged bars:", len(d), d["et"].min(), "->", d["et"].max())

# 2) gap-fill sessions missing versus R2 daily (window start .. end)
r2 = pd.read_csv(R2_DAILY); r2["date"] = pd.to_datetime(r2["date"])
have = set(to_et_day(d["date"]))
need = sorted(x for x in r2["date"] if pd.Timestamp("2020-01-02") <= x <= END and x not in have)
print("sessions missing vs R2 daily:", [str(x.date()) for x in need])
for day in need:
    end = (day + pd.Timedelta(days=1)).tz_localize("UTC")
    bars = ib.reqHistoricalData(c, endDateTime=end.to_pydatetime(), durationStr="2 D", barSizeSetting="1 hour",
                                whatToShow="TRADES", useRTH=True, formatDate=2)
    df = util.df(bars) if bars else pd.DataFrame()
    if len(df): df = df[to_et_day(df["date"]) == day]
    if len(df): df.to_csv(OUT / "chunks" / f"QQQ_gap_{day:%Y%m%d}.csv", index=False)
    print("gap", day.date(), len(df), "bars"); time.sleep(a.sleep)
if need: d = merge()
per_day = d.groupby(d["et"].dt.date).size()
print(f"QQQ: {len(d)} bars {d['et'].min()} -> {d['et'].max()} | bars/day mode={per_day.mode().iloc[0]} | file: {OUT / 'QQQ_1h_RTH_pre.csv'}")
ib.disconnect(); print("done")
