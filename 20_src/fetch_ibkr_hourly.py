"""
fetch_ibkr_hourly.py  --  READ-ONLY IBKR historical download of 1-hour REGULAR-HOURS bars (QQQ, IWM).
No orders are ever placed. Run on Windows (Lara) with TWS/Gateway open. Writes ONLY to 10_data/ibkr_hourly.

  python fetch_ibkr_hourly.py --port <TWS_PORT> --start 2023-08-01
Uses its own clientId (default 9101) so it cannot collide with AQ100 / P12 clients.
Resumable: finished chunks are cached; rerun after any pacing error.
"""
import argparse, time
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from ib_insync import IB, Stock, util

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--host", default="127.0.0.1")
ap.add_argument("--client-id", type=int, default=9101)
ap.add_argument("--start", default="2023-08-01")
ap.add_argument("--symbols", default="QQQ,IWM")
ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "10_data" / "ibkr_hourly"))
a = ap.parse_args()
OUT = Path(a.out); (OUT / "chunks").mkdir(parents=True, exist_ok=True)

ib = IB(); ib.connect(a.host, a.port, clientId=a.client_id, readonly=True, timeout=20)
print("connected (read-only), serverVersion", ib.client.serverVersion())
start = pd.Timestamp(a.start, tz="UTC")
end_marks = pd.date_range(end=pd.Timestamp.now(tz="UTC").ceil("D"), start=start, freq="MS", tz="UTC")
end_marks = list(end_marks) + [pd.Timestamp.now(tz="UTC").ceil("D")]
for sym in a.symbols.split(","):
    c = Stock(sym, "SMART", "USD"); ib.qualifyContracts(c)
    for em in sorted(set(end_marks)):
        f = OUT / "chunks" / f"{sym}_{em:%Y%m%d}.csv"
        if f.exists(): continue
        bars = ib.reqHistoricalData(c, endDateTime=em.to_pydatetime(), durationStr="1 M", barSizeSetting="1 hour",
                                    whatToShow="TRADES", useRTH=True, formatDate=2)
        df = util.df(bars) if bars else pd.DataFrame()
        df.to_csv(f, index=False); print(sym, em.date(), len(df), "bars"); time.sleep(11)   # pacing
    parts = [pd.read_csv(p) for p in sorted((OUT / "chunks").glob(f"{sym}_*.csv")) if p.stat().st_size > 5]
    d = pd.concat(parts, ignore_index=True)
    d["date"] = pd.to_datetime(d["date"], utc=True)
    d = d.drop_duplicates("date").sort_values("date")
    d["et"] = d["date"].dt.tz_convert("America/New_York")
    d.to_csv(OUT / f"{sym}_1h_RTH.csv", index=False)
    per_day = d.groupby(d["et"].dt.date).size()
    print(f"{sym}: {len(d)} bars {d['et'].min()} -> {d['et'].max()} | bars/day mode={per_day.mode().iloc[0]}")
ib.disconnect(); print("done")
