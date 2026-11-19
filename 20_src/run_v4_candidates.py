"""
run_v4_candidates.py -- PRE_REGISTRATION_v4: C1 (QQQ, hold 35 bars, F3), C2 (DIA, frozen F3 rule), comparator C2b (DIA base) plus QQQ reference rows,
each over the blocks PRE / IS / SELECTION / FINAL(second-use) and one continuous FULL run. RUNS ONCE.
  python run_v4_candidates.py                      -> real run; needs the hashed pre-registration, code hashes, DIA data check ALL PASS; writes a lock
  python run_v4_candidates.py --dryrun --qqq-bars <csv> --out <dir>
        -> plumbing check with a SYNTHETIC stand-in for DIA; prints NO performance numbers; writes nothing to the project, no lock, no counter rows.
"""
import argparse, sys, json, hashlib, io, contextlib, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E

ap = argparse.ArgumentParser(); ap.add_argument("--dryrun", action="store_true"); ap.add_argument("--qqq-bars"); ap.add_argument("--out")
a = ap.parse_args()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
CFG = json.loads((root / "00_rules/FROZEN_CONFIG_OOS.json").read_text(encoding="utf-8"))
EVENT_RULES = [("eq" if k == "equals" else "sw", s) for k, s in CFG["F3_event_rules"]]; HAND = {pd.Timestamp(x["date"]) for x in CFG["hand_added_event_days_et"]}
BLOCKS = [("PRE", "2020-01-03", "2023-11-10"), ("IS", "2023-11-13", "2025-06-30"), ("SEL", "2025-07-01", "2025-11-30"), ("FINAL", "2025-12-01", "2026-11-12"), ("FULL", "2020-01-03", "2026-11-12")]
VARIANTS = [("QQQ_F3_H21_ref", "QQQ", 21, True), ("QQQ_base_H21_ref", "QQQ", 21, False), ("C1_QQQ_H35_F3", "QQQ", 35, True), ("C2_DIA_F3", "DIA", 21, True), ("C2b_DIA_base", "DIA", 21, False)]
N, K = 7, 0.012
if a.dryrun:
    assert a.qqq_bars and a.out, "--dryrun needs --qqq-bars and --out"; OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
    q = pd.read_csv(a.qqq_bars); rng = np.random.default_rng(7); d = q.copy()
    for c in ("open", "high", "low", "close"): d[c] = q[c] * 0.45 * (1 + rng.normal(0, 0.001, len(q)))
    QQ, DD = OUT / "_qqq.csv", OUT / "_dia_synthetic.csv"; q.to_csv(QQ, index=False); d.to_csv(DD, index=False)
else:
    OUT = root / "40_results"; lock = root / "90_logs/V4_RUN.lock"; assert not lock.exists(), f"v4 already run once ({lock.read_text()[:60]!r}); a second pass must be labelled EXPLORATORY by hand"
    hf = root / "90_logs/PRE_REGISTRATION_v4.sha256"; assert hf.exists(), "hash the v4 pre-registration first"
    assert hf.read_text().split()[0].lower() == sha(root / "00_rules/PRE_REGISTRATION_v4_NEW_CANDIDATES.md"), "pre-registration changed after hashing"
    cf = root / "90_logs/v4_code_20261117.sha256"; assert cf.exists(), "record the code hashes first (90_logs/v4_code_20261117.sha256)"
    rec = {l.split()[1]: l.split()[0].lower() for l in cf.read_text().splitlines() if len(l.split()) == 2}
    for name, p in (("alphax_engine_v2.py", root / "20_src/alphax_engine_v2.py"), ("run_v4_candidates.py", Path(__file__)), ("check_dia_data.py", root / "20_src/check_dia_data.py")):
        assert rec.get(name) == sha(p), f"code hash mismatch for {name}: edited after hashing?"
    chk = root / "90_logs/dia_data_check.txt"; assert chk.exists() and "ALL PASS" in chk.read_text(), "run check_dia_data.py first (must say ALL PASS)"
    pre = pd.read_csv(root / "10_data/ibkr_hourly_prewindow/QQQ_1h_RTH_pre.csv"); main = pd.read_csv(root / "10_data/ibkr_hourly/QQQ_1h_RTH.csv")
    m = pd.concat([pre, main]); m["_t"] = pd.to_datetime(m["date"], utc=True); m = m.sort_values("_t").drop_duplicates("_t").drop(columns="_t")
    (root / "10_data/ibkr_hourly_merged").mkdir(exist_ok=True); QQ = root / "10_data/ibkr_hourly_merged/QQQ_1h_RTH_merged.csv"; m.to_csv(QQ, index=False)
    DD = root / "10_data/ibkr_hourly_dia/DIA_1h_RTH.csv"
print("engine_v2 sha256:", sha(root / "20_src/alphax_engine_v2.py")); print("runner   sha256:", sha(__file__))
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
CAL = root / "10_data/r2_snapshot/news/economic_calendar.csv"
def f3_mask(bars, end):
    cal = pd.read_csv(CAL, usecols=["date", "country", "event"], low_memory=False)
    cal = cal[cal["country"] == "US"].copy(); cal["dt"] = pd.to_datetime(cal["date"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    cal["day"] = cal["dt"].dt.tz_localize(None).dt.normalize(); cal = cal[cal["day"] <= pd.Timestamp(end)]
    mm = np.zeros(len(cal), bool)
    for kind, s in EVENT_RULES: mm |= (cal["event"] == s).values if kind == "eq" else cal["event"].str.startswith(s).values
    ev = set(cal.loc[mm, "day"]) | {h for h in HAND if h <= pd.Timestamp(end)}
    d_arr = bars["day"].values; entry_day = np.where(np.append(d_arr[1:] != d_arr[:-1], True), np.append(d_arr[1:], d_arr[-1]), d_arr)
    return np.array([pd.Timestamp(x) not in ev for x in entry_day])
def one(bars, mask, H, start):
    T, d, pnl = E.backtest(bars, ratio, N, K, H, start, extra_ok=mask)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): ok = E.selfchecks(bars, ratio, (N, K, H), start, T, d, pnl, extra_ok=mask)
    m = E.metrics(T, d); _, d2, _ = E.backtest(bars, ratio, N, K, H, start, fee=E.FEE * 2, extra_ok=mask)
    m.update(selfchecks_pass=ok, net_pct_2x_cost=float(d2.sum() / E.CAPITAL * 100)); return T, d, m
files = {"QQQ": QQ, "DIA": DD}; rows, trades, daily_full = [], [], {}; all_ok = True
for blk, start, end in BLOCKS:
    if a.dryrun and pd.Timestamp(start) < pd.Timestamp(pd.read_csv(QQ)["date"].iloc[0][:10]) + pd.Timedelta(days=15): continue   # dry run: only blocks inside the stand-in data
    bars = {s: E.load_bars(files[s], end) for s in files}
    for s in bars: assert bars[s]["day"].max() <= pd.Timestamp(end)
    masks = {s: f3_mask(bars[s], end) for s in bars}
    for name, sym, H, useF3 in VARIANTS:
        T, d, m = one(bars[sym], masks[sym] if useF3 else None, H, start); all_ok &= bool(m["selfchecks_pass"])
        m.update(variant=name, block=blk, symbol=sym, H=H, F3=useF3, start=start, end=end); rows.append(m)
        if len(T): trades.append(T.assign(variant=name, block=blk))
        if blk == "FULL": daily_full[name] = d
    for sym in bars:
        bm = E.metrics(pd.DataFrame(), E.benchmark_daily(bars[sym], start)); bm.update(variant=f"buy_and_hold_{sym}", block=blk, symbol=sym, start=start, end=end); rows.append(bm)
        if blk == "FULL": daily_full[f"buy_and_hold_{sym}"] = E.benchmark_daily(bars[sym], start)
R = pd.DataFrame(rows)
if a.dryrun:
    print(f"DRYRUN OK: {len(R)} result rows, {len(trades)} trade tables, selfchecks all pass: {all_ok}. Performance numbers are deliberately NOT printed in a dry run."); sys.exit(0)

# verdicts (PRE_REGISTRATION_v4 section 5)
V = []
for name in ("C1_QQQ_H35_F3", "C2_DIA_F3"):
    full = R[(R.variant == name) & (R.block == "FULL")].iloc[0]; blocks = R[(R.variant == name) & (R.block.isin(["PRE", "IS", "SEL", "FINAL"]))]
    pos = int((blocks["net_pct"] > 0).sum())
    std = bool(full["trades"] >= 50 and full["net_pct"] > 0 and full["net_pct_2x_cost"] > 0 and full["sharpe"] >= 0.5
               and (full.get("pnl_ex_top3", -1) > 0 or full.get("top3_share", 1) < 0.5) and full["selfchecks_pass"] and pos >= 3)
    if name == "C1_QQQ_H35_F3":
        ref = R[(R.variant == "QQQ_F3_H21_ref") & (R.block == "FULL")].iloc[0]; extra = bool(full["sharpe"] >= ref["sharpe"] + 0.10 and full["max_dd_pct"] >= ref["max_dd_pct"]); lab = "beats QQQ F3 H21 by Sharpe +0.10 and drawdown no worse"
    else:
        ref = R[(R.variant == "C2b_DIA_base") & (R.block == "FULL")].iloc[0]; extra = bool(full["sharpe"] >= ref["sharpe"] + 0.10); lab = "news-day filter helps on DIA (Sharpe +0.10 over DIA base)"
    V.append(dict(candidate=name, standard_checks_and_3_of_4_blocks_positive=std, blocks_positive_of_4=pos, extra_condition=lab, extra_met=extra, LABEL="SUPPORTED" if (std and extra) else "NOT SUPPORTED"))
VD = pd.DataFrame(V); pd.set_option("display.width", 250, "display.max_columns", 40)
cols = ["variant", "block", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share", "pnl_ex_top3", "selfchecks_pass"]
print(R[[c for c in cols if c in R.columns]].round(3).to_string(index=False)); print("\nVERDICTS:\n", VD.to_string(index=False))
def yr(d, label): y = d.groupby(pd.DatetimeIndex(d.index).year).sum() / E.CAPITAL * 100; return pd.DataFrame({"variant": label, "year": y.index, "net_pct": y.values})
BY = pd.concat([yr(d, n) for n, d in daily_full.items()]); print("\nFULL run by year:\n", BY.round(2).to_string(index=False))
R.to_csv(OUT / "V4_results.csv", index=False); VD.to_csv(OUT / "V4_verdicts.csv", index=False); BY.to_csv(OUT / "V4_by_year_full.csv", index=False)
pd.concat(trades).to_csv(OUT / "V4_trades.csv", index=False); pd.DataFrame(daily_full).to_csv(OUT / "V4_daily_pnl_full.csv")
with open(root / "90_logs/config_counter.csv", "a") as f:
    for n in ("QQQ_N7_k0.012_H35_F3_EVENT", "DIA_N7_k0.012_H21_F3_EVENT", "DIA_N7_k0.012_H21"): f.write(f"{n},ALL_BLOCKS,{dt.datetime.now():%Y-%m-%d %H:%M},v4_exploratory_second_use_window\n")
(root / "90_logs/V4_RUN.lock").write_text(f"run {dt.datetime.now().isoformat()}"); print("\nsaved to", OUT, "| lock written: second pass is not allowed")
