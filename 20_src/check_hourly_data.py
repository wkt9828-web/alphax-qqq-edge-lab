"""Data-quality check for IBKR hourly RTH files vs R2 daily closes (read-only; writes a report to 90_logs)."""
import sys, pandas as pd, numpy as np
from pathlib import Path
root = Path(__file__).resolve().parents[1]
rep = []
for sym in ("QQQ", "IWM"):
    f = root / "10_data" / "ibkr_hourly" / f"{sym}_1h_RTH.csv"
    if not f.exists(): rep.append(f"{sym}: FILE MISSING"); continue
    d = pd.read_csv(f); d["et"] = pd.to_datetime(d["date"], utc=True).dt.tz_convert("America/New_York")
    d["day"] = d["et"].dt.tz_localize(None).dt.normalize()
    r2 = pd.read_csv(root / "10_data" / "r2_snapshot" / "market_data" / "daily" / f"{sym}.csv"); r2["date"] = pd.to_datetime(r2["date"])
    r2 = r2.set_index("date")["close"]
    per = d.groupby("day").size()
    last_close = d.sort_values("et").groupby("day")["close"].last()
    j = pd.concat([last_close.rename("ibkr"), r2.rename("r2")], axis=1, join="inner")
    j["diff_pct"] = (j["ibkr"] / j["r2"] - 1) * 100
    win = j[j.index >= "2023-11-13"]
    exp_days = r2[r2.index >= "2023-11-13"].index
    missing = sorted(set(exp_days) - set(d["day"]))
    rep += [f"== {sym}: {len(d)} bars, {d['et'].min()} -> {d['et'].max()}",
            f"   bars/day: mode={per.mode().iloc[0]}, counts={per.value_counts().sort_index().to_dict()}",
            f"   trading days in R2 since 2023-11-13: {len(exp_days)} | missing in IBKR: {len(missing)} {missing[:8]}",
            f"   IBKR last-bar close vs R2 daily close: n={len(win)}, |diff|>0.05%: {(win['diff_pct'].abs() > 0.05).sum()}, max |diff|={win['diff_pct'].abs().max():.3f}%",
            f"   duplicate bars: {d['et'].duplicated().sum()}, NaN OHLC: {int(d[['open','high','low','close']].isna().sum().sum())}",
            f"   last 3 days bars: {per.tail(3).to_dict()}"]
out = "\n".join(rep); print(out)
(root / "90_logs" / "hourly_data_check.txt").write_text(out, encoding="utf-8")
