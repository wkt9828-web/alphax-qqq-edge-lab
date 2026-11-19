"""
check_oos_data.py -- data-quality checks on the FINAL-WINDOW hourly file BEFORE the strategy is run. No strategy, signal or return is computed.
Writes 90_logs/hourly_data_check_oos.txt and prints PASS/FAIL lines.   python check_oos_data.py
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]
NEW = root / "10_data/ibkr_hourly_oos/QQQ_1h_RTH_oos.csv"
OLD = root / "10_data/ibkr_hourly/QQQ_1h_RTH.csv"
R2 = root / "10_data/r2_snapshot/market_data/daily/QQQ.csv"
WSTART, WEND = pd.Timestamp("2025-12-01"), pd.Timestamp("2026-11-12")
lines = []
def say(s): print(s); lines.append(s)
def load(p):
    d = pd.read_csv(p); d["et"] = pd.to_datetime(d["date"], utc=True).dt.tz_convert("America/New_York")
    d["day"] = d["et"].dt.tz_localize(None).dt.normalize(); return d.sort_values("et").reset_index(drop=True)
d = load(NEW); r2 = pd.read_csv(R2); r2["date"] = pd.to_datetime(r2["date"]); ok = {}
say(f"OOS file: {len(d)} bars {d['et'].min()} -> {d['et'].max()}")
ok["no_data_after_window_end"] = bool(d["day"].max() <= WEND)
ok["last_session_is_window_end"] = bool(d["day"].max() == WEND)
ok["starts_by_2025_11_05"] = bool(d["day"].min() <= pd.Timestamp("2025-11-05"))
cnt = d.groupby("day").size(); say(f"bars/day: mode={cnt.mode().iloc[0]} counts={cnt.value_counts().to_dict()}")
ok["no_duplicate_bars"] = bool(not d["et"].duplicated().any()); ok["no_nan_ohlc"] = bool(not d[["open", "high", "low", "close"]].isna().any().any())
r2_last = r2["date"].max(); exp = r2[(r2["date"] >= "2025-11-03") & (r2["date"] <= min(WEND, r2_last))]["date"]
miss = sorted(set(exp) - set(d["day"])); say(f"sessions in R2 daily 2025-11-03..{min(WEND, r2_last).date()}: {len(exp)} | missing in IBKR: {len(miss)} {[str(x.date()) for x in miss[:20]]}")
ok["no_missing_sessions"] = bool(len(miss) == 0)
after = sorted(set(d["day"][d["day"] > r2_last])); say(f"sessions after the last R2 daily row ({r2_last.date()}): {[str(x.date()) for x in after]} (cannot be cross-checked against R2)")
extra = sorted(set(d["day"][d["day"] >= "2025-11-03"]) - set(exp) - set(after)); say(f"IBKR sessions not in R2 daily: {len(extra)} {[str(x.date()) for x in extra[:10]]}")
g = d.groupby("day").agg(o=("open", "first"), c=("close", "last")).join(r2.set_index("date")[["open", "close"]], how="inner", rsuffix="_r2")
do = (g["o"] / g["open"] - 1).abs(); dc = (g["c"] / g["close"] - 1).abs()
say(f"open vs R2 open: n={len(g)} |diff|>0.1%: {(do > 0.001).sum()} max={do.max():.4%}")
say(f"close vs R2 close: n={len(g)} |diff|>0.05%: {(dc > 0.0005).sum()} max={dc.max():.4%}  (closing-auction prints differ slightly; entries/exits use opens)")
ok["opens_match_R2_0.1pct"] = bool((do > 0.001).sum() <= max(3, int(0.005 * len(g))))
old = load(OLD); ov = d.merge(old, on="et", suffixes=("_p", "_o"))
if len(ov):
    mx = max((ov[f"{c}_p"] / ov[f"{c}_o"] - 1).abs().max() for c in ("open", "high", "low", "close"))
    say(f"overlap with the IS/Selection file: {len(ov)} bars, max |diff| any OHLC = {mx:.4%}"); ok["overlap_identical_0.01pct"] = bool(mx < 1e-4)
else: say("overlap with the IS/Selection file: none (nothing to compare)")
first = d.groupby("day")["et"].first().dt.strftime("%H:%M").value_counts().to_dict(); say(f"first-bar start times: {first}")
w = d[d["day"] >= WSTART]; say(f"window sessions {WSTART.date()}..{WEND.date()}: {w['day'].nunique()}")
say("")
for k, v in ok.items(): say(f"  [{'PASS' if v else 'FAIL'}] {k}")
say("ALL PASS" if all(ok.values()) else "SOME FAIL -- do NOT run the strategy; report the lines above")
(root / "90_logs/hourly_data_check_oos.txt").write_text("\n".join(lines), encoding="utf-8")
sys.exit(0 if all(ok.values()) else 1)
