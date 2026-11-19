"""
build_profile_daily.py -- flattens the downloaded Flywheel profile JSON files into ONE small CSV per symbol (data preparation only:
no returns, no signals, no backtest). Run on Windows (Lara) after fetch_r2_profiles.py.

  python 20_src\\build_profile_daily.py
Reads  10_data/r2_snapshot/profiles/{QQQ,SPXW}/*_profile.json
Writes 10_data/profiles_daily_QQQ.csv and 10_data/profiles_daily_SPXW.csv (one row per profile date) and prints coverage counts per year.
"""
import json
from pathlib import Path
import pandas as pd
root = Path(__file__).resolve().parents[1]
KEEP = ["symbol", "date", "tick", "rows", "contracts", "n_buckets", "vpoc", "tpo_poc", "vah", "val", "tpo_vah", "tpo_val",
        "net_delta", "n_brackets", "session_open", "price_min", "price_max"]
for sym in ("QQQ", "SPXW"):
    rows = []
    for f in sorted((root / "10_data/r2_snapshot/profiles" / sym).glob("*_profile.json")):
        j = json.loads(f.read_text(encoding="utf-8")); rows.append({k: j.get(k) for k in KEEP})
    d = pd.DataFrame(rows); d["date"] = pd.to_datetime(d["date"]); d = d.sort_values("date").drop_duplicates("date")
    out = root / "10_data" / f"profiles_daily_{sym}.csv"; d.to_csv(out, index=False)
    print(sym, len(d), "dates", d["date"].min().date(), "->", d["date"].max().date(), "| nulls in vpoc/val/vah/net_delta/contracts:",
          int(d[["vpoc", "val", "vah", "net_delta", "contracts"]].isna().any(axis=1).sum()), "| saved", out)
    print("  dates per year:", d.groupby(d["date"].dt.year).size().to_dict())
