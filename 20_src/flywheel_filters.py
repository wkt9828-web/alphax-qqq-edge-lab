"""
flywheel_filters.py -- builds bar-aligned boolean ALLOW masks for PRE_REGISTRATION_v2 filters F1..F4.
All inputs are truncated to <= end_date (the stage end) BEFORE use, so later (OOS) rows can never influence a mask.
Definitions are exactly those in 00_rules/PRE_REGISTRATION_v2.md. Missing data -> False (no entry), except F3 after calendar end (no event assumed).
"""
import glob
from pathlib import Path
import numpy as np, pandas as pd
EVENT_RULES = [("eq", "Fed Interest Rate Decision"), ("sw", "Non Farm Payrolls"), ("sw", "Inflation Rate MoM")]

def _by_session(bars, allow_by_day):
    return bars["day"].map(allow_by_day).fillna(False).astype(bool).values

def build_masks(bars, snap, end_date):
    end = pd.Timestamp(end_date); days = list(pd.Series(bars["day"].unique()).sort_values())
    pos = {d: i for i, d in enumerate(days)}
    prev = {d: (days[i - 1] if i >= 1 else None) for d, i in pos.items()}
    lag2 = {d: (days[i - 2] if i >= 2 else None) for d, i in pos.items()}
    out, info = {}, {}
    # F1 GEX sign of previous session's snapshot
    tot = {}
    for f in sorted(glob.glob(str(snap / "historical_gex/QQQ/*/QQQ_gex_table.csv"))):
        name = Path(f).parent.name; d = pd.Timestamp(name.split("_exp")[0]); ex = pd.Timestamp(name.split("_exp")[1])
        if d > end: continue
        if d not in tot or ex < tot[d][0]: tot[d] = (ex, float(pd.read_csv(f)["net_gex"].sum()))
    g = {d: (tot[prev[d]][1] > 0 if prev[d] in tot else False) for d in days if prev[d] is not None}
    out["F1_GEX"] = _by_session(bars, g); info["F1_GEX"] = f"sessions with prev snapshot: {sum(prev[d] in tot for d in days if prev[d] is not None)}/{len(days)}"
    # F2 HY spread not widening over 20 observations (lag-2)
    def fred(name):
        s = pd.read_parquet(snap / f"market_data/fred/observations/{name}.parquet")[["date", "value"]].dropna()
        s["date"] = pd.to_datetime(s["date"]); return s[s["date"] <= end].sort_values("date").reset_index(drop=True)
    hy = fred("BAMLH0A0HYM2"); hd = hy["date"].values; hv = hy["value"].values
    h = {}
    for d in days:
        L = lag2[d]
        if L is None: h[d] = False; continue
        p = np.searchsorted(hd, np.datetime64(L), side="right") - 1
        h[d] = bool(p >= 20 and (hv[p] - hv[p - 20]) <= 0)
    out["F2_HY"] = _by_session(bars, h); info["F2_HY"] = f"first obs {hy['date'].min().date()}"
    # F4 rates shock: |5-obs change in DGS10| <= trailing-252 90th pct of |change| (strictly prior)
    r = fred("DGS10"); r["d5"] = r["value"] - r["value"].shift(5); r["p90"] = r["d5"].abs().shift(1).rolling(252).quantile(0.9)
    rd = r["date"].values; rr = {}
    for d in days:
        L = lag2[d]
        if L is None: rr[d] = False; continue
        p = np.searchsorted(rd, np.datetime64(L), side="right") - 1
        rr[d] = bool(p >= 0 and pd.notna(r["p90"].iloc[p]) and abs(r["d5"].iloc[p]) <= r["p90"].iloc[p])
    out["F4_RATES"] = _by_session(bars, rr)
    # F3 event day on ENTRY day (date of bar t+1): calendar fact, schedule only
    cal = pd.read_csv(snap / "news/economic_calendar.csv", usecols=["date", "country", "event"], low_memory=False)
    cal = cal[cal["country"] == "US"].copy(); cal["dt"] = pd.to_datetime(cal["date"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    cal["day"] = cal["dt"].dt.tz_localize(None).dt.normalize(); cal = cal[cal["day"] <= end]
    m = np.zeros(len(cal), bool)
    for kind, s in EVENT_RULES: m |= (cal["event"] == s).values if kind == "eq" else cal["event"].str.startswith(s).values
    ev = set(cal.loc[m, "day"]); d_arr = bars["day"].values
    entry_day = np.where(np.append(d_arr[1:] != d_arr[:-1], True), np.append(d_arr[1:], d_arr[-1]), d_arr)   # last bar of a session -> next session (calendar label), else same day
    out["F3_EVENT"] = np.array([pd.Timestamp(x) not in ev for x in entry_day]); info["F3_EVENT"] = f"event days <= end: {len(ev)}"
    return out, info
