"""
fetch_ibkr_gapfill.py -- READ-ONLY. Fills single missing sessions (found by comparing with R2 daily dates) in the hourly RTH files.
Cause of the gap: monthly chunk boundary in fetch_ibkr_hourly.py (first-of-month sessions dropped). No orders are placed.
  python fetch_ibkr_gapfill.py --port 4003
"""
import argparse, time
from pathlib import Path
import pandas as pd
from ib_insync import IB, Stock, util

ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, required=True)
ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--client-id", type=int, default=9102)
a = ap.parse_args()
root = Path(__file__).resolve().parents[1]; OUT = root / "10_data" / "ibkr_hourly"
ib = IB(); ib.connect(a.host, a.port, clientId=a.client_id, readonly=True, timeout=20)
for sym in ("QQQ", "IWM"):
    main = pd.read_csv(OUT / f"{sym}_1h_RTH.csv")
    have = set(pd.to_datetime(main["date"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize())
    r2 = pd.read_csv(root / "10_data" / "r2_snapshot" / "market_data" / "daily" / f"{sym}.csv"); r2["date"] = pd.to_datetime(r2["date"])
    need = sorted(d for d in r2["date"] if d >= pd.Timestamp("2023-07-03") and d not in have)
    print(sym, "missing sessions:", [str(d.date()) for d in need])
    c = Stock(sym, "SMART", "USD"); ib.qualifyContracts(c)
    for d in need:
        end = (d + pd.Timedelta(days=1)).tz_localize("UTC")          # 00:00 UTC next day = evening of session day in New York
        bars = ib.reqHistoricalData(c, endDateTime=end.to_pydatetime(), durationStr="2 D", barSizeSetting="1 hour",
                                    whatToShow="TRADES", useRTH=True, formatDate=2)
        df = util.df(bars) if bars else pd.DataFrame()
        if len(df):
            et = pd.to_datetime(df["date"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None).dt.normalize()
            df = df[et == d]
        df.to_csv(OUT / "chunks" / f"{sym}_gap_{d:%Y%m%d}.csv", index=False)
        print(sym, d.date(), len(df), "bars"); time.sleep(11)
    parts = [pd.read_csv(p) for p in sorted((OUT / "chunks").glob(f"{sym}_*.csv")) if p.stat().st_size > 5]
    m = pd.concat(parts, ignore_index=True); m["date"] = pd.to_datetime(m["date"], utc=True)
    m = m.drop_duplicates("date").sort_values("date"); m["et"] = m["date"].dt.tz_convert("America/New_York")
    m.to_csv(OUT / f"{sym}_1h_RTH.csv", index=False); print(sym, "merged rows:", len(m))
ib.disconnect(); print("done")
