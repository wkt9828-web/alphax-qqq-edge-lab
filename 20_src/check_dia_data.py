"""
check_dia_data.py -- data-quality checks on the DIA hourly file BEFORE any v4 strategy is run (PRE_REGISTRATION_v4 section 4).
No strategy, signal or backtest return is computed. Writes 90_logs/dia_data_check.txt and prints PASS/FAIL lines.   python check_dia_data.py
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]
DIA = root / "10_data/ibkr_hourly_dia/DIA_1h_RTH.csv"
QQQ_FILES = [root / "10_data/ibkr_hourly_prewindow/QQQ_1h_RTH_pre.csv", root / "10_data/ibkr_hourly/QQQ_1h_RTH.csv", root / "10_data/ibkr_hourly_oos/QQQ_1h_RTH_oos.csv"]
WEND = pd.Timestamp("2026-11-12"); lines = []
def say(s): print(s); lines.append(s)
def load(p):
    d = pd.read_csv(p); d["et"] = pd.to_datetime(d["date"], utc=True).dt.tz_convert("America/New_York")
    d["day"] = d["et"].dt.tz_localize(None).dt.normalize(); return d.sort_values("et").drop_duplicates("et").reset_index(drop=True)
d = load(DIA); q = pd.concat([load(p) for p in QQQ_FILES]).sort_values("et").drop_duplicates("et").reset_index(drop=True); q = q[q["day"] <= WEND]
ok = {}; say(f"DIA file: {len(d)} bars {d['et'].min()} -> {d['et'].max()} | QQQ calendar: {q['day'].nunique()} sessions {q['day'].min().date()} -> {q['day'].max().date()}")
ok["no_data_after_window_end"] = bool(d["day"].max() <= WEND); ok["last_session_is_window_end"] = bool(d["day"].max() == WEND)
ok["starts_by_2019_12_10"] = bool(d["day"].min() <= pd.Timestamp("2019-12-10"))
cnt = d.groupby("day").size(); say(f"bars/day: mode={cnt.mode().iloc[0]} counts={cnt.value_counts().to_dict()}")
ok["no_duplicate_bars"] = bool(not d["et"].duplicated().any()); ok["no_nan_ohlc"] = bool(not d[["open", "high", "low", "close"]].isna().any().any())
ok["high_ge_low"] = bool((d["high"] >= d["low"]).all())
sq, sd = set(q["day"]), set(d["day"]); miss = sorted(x for x in sq - sd if x >= pd.Timestamp("2020-01-02")); extra = sorted(x for x in sd - sq if x >= pd.Timestamp("2020-01-02"))
say(f"sessions QQQ has but DIA lacks (from 2020-01-02): {len(miss)} {[str(x.date()) for x in miss[:20]]}"); say(f"sessions DIA has but QQQ lacks: {len(extra)} {[str(x.date()) for x in extra[:10]]}")
ok["no_missing_sessions_vs_QQQ"] = bool(len(miss) == 0); ok["no_extra_sessions_vs_QQQ"] = bool(len(extra) == 0)
bq = q.groupby("day").size(); bd = cnt.reindex(bq.index); diff = int((bq != bd).sum()); say(f"sessions whose bar count differs from QQQ: {diff}")
ok["bar_counts_match_QQQ"] = bool(diff <= max(3, int(0.005 * len(bq))))
first = d.groupby("day")["et"].first().dt.strftime("%H:%M").value_counts().to_dict(); say(f"first-bar start times: {first}")
# instrument/timestamp sanity: intraday-daily moves of DIA and QQQ should be highly correlated (no strategy return is computed)
def dmove(x): g = x.groupby("day").agg(o=("open", "first"), c=("close", "last")); return (g["c"] / g["o"] - 1)
j = pd.concat([dmove(d), dmove(q)], axis=1, keys=["dia", "qqq"]).dropna(); r = float(j["dia"].corr(j["qqq"])); say(f"correlation of daily open-to-close moves DIA vs QQQ: {r:.3f} over {len(j)} sessions")
ok["dia_qqq_daily_corr_gt_0.7"] = bool(r > 0.7)
say(""); [say(f"  [{'PASS' if v else 'FAIL'}] {k}") for k, v in ok.items()]
say("ALL PASS" if all(ok.values()) else "SOME FAIL -- do NOT run the strategy; report the lines above")
(root / "90_logs/dia_data_check.txt").write_text("\n".join(lines), encoding="utf-8"); sys.exit(0 if all(ok.values()) else 1)
