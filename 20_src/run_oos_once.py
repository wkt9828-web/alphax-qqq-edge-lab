"""
run_oos_once.py -- FINAL OUT-OF-SAMPLE run of the frozen candidate (00_rules/FROZEN_CONFIG_OOS.json). RUNS ONCE.
  python run_oos_once.py                      -> real run on 2025-12-01..2026-11-12; needs hashes + data check; writes a lock
  python run_oos_once.py --dryrun --bars <csv> --start 2023-11-13 --end 2025-06-30 --out <dir>
        -> plumbing/regression check on ALREADY-SEEN data; writes nothing to the project, no lock, no counter row.
Reports the frozen candidate (base + F3), buy-and-hold, by quarter, 2x cost, top-3 share. Nothing is tuned here.
"""
import argparse, sys, json, hashlib, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E

ap = argparse.ArgumentParser()
ap.add_argument("--dryrun", action="store_true"); ap.add_argument("--bars"); ap.add_argument("--start"); ap.add_argument("--end"); ap.add_argument("--out")
a = ap.parse_args()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
CFG_PATH = root / "00_rules/FROZEN_CONFIG_OOS.json"; CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
R = CFG["rule"]; N, K, H = R["N_bars"], R["k_drop"], R["H_bars"]
assert (N, K, H) == (7, 0.012, 21) and R["unit_usd"] == 100000 and R["fee_per_side"] == 0.001 == E.FEE and E.STOP == R["stop_close_below_entry"]
EVENT_RULES = [("eq" if k == "equals" else "sw", s) for k, s in CFG["F3_event_rules"]]
HAND = {pd.Timestamp(x["date"]) for x in CFG["hand_added_event_days_et"]}
if a.dryrun:
    assert a.bars and a.start and a.end and a.out, "--dryrun needs --bars --start --end --out"
    START, END, BARS, OUT = a.start, a.end, Path(a.bars), Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
else:
    START, END = CFG["window"]["start"], CFG["window"]["end"]; BARS = root / "10_data/ibkr_hourly_oos/QQQ_1h_RTH_oos.csv"; OUT = root / "40_results"
    lock = root / "90_logs/OOS_RUN.lock"; assert not lock.exists(), f"final window already run once ({lock.read_text()[:60]!r}); a second pass must be labelled EXPLORATORY by hand"
    hf = root / "90_logs/FROZEN_CONFIG_OOS.sha256"; assert hf.exists(), "hash the frozen config first (90_logs/FROZEN_CONFIG_OOS.sha256)"
    assert hf.read_text().split()[0].lower() == sha(CFG_PATH), "frozen config changed after hashing"
    cf = root / "90_logs/oos_code_20261117.sha256"; assert cf.exists(), "record the code hashes first (90_logs/oos_code_20261117.sha256)"
    rec = {l.split()[1]: l.split()[0].lower() for l in cf.read_text().splitlines() if len(l.split()) == 2}
    for name, p in (("alphax_engine_v2.py", root / "20_src/alphax_engine_v2.py"), ("run_oos_once.py", Path(__file__)), ("check_oos_data.py", root / "20_src/check_oos_data.py")):
        assert rec.get(name) == sha(p), f"code hash mismatch for {name}: edited after hashing?"
    chk = root / "90_logs/hourly_data_check_oos.txt"; assert chk.exists() and "ALL PASS" in chk.read_text(), "run check_oos_data.py first (must say ALL PASS)"
print("engine_v2 sha256:", sha(root / "20_src/alphax_engine_v2.py")); print("runner   sha256:", sha(__file__)); print("frozen   sha256:", sha(CFG_PATH))

bars = E.load_bars(BARS, END); assert bars["day"].max() <= pd.Timestamp(END)
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
def f3_mask(bars, cal_csv, end, hand):
    cal = pd.read_csv(cal_csv, usecols=["date", "country", "event"], low_memory=False)
    cal = cal[cal["country"] == "US"].copy(); cal["dt"] = pd.to_datetime(cal["date"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    cal["day"] = cal["dt"].dt.tz_localize(None).dt.normalize(); last_cal = cal["day"].max(); cal = cal[cal["day"] <= pd.Timestamp(end)]
    m = np.zeros(len(cal), bool)
    for kind, s in EVENT_RULES: m |= (cal["event"] == s).values if kind == "eq" else cal["event"].str.startswith(s).values
    ev = set(cal.loc[m, "day"]) | {h for h in hand if h <= pd.Timestamp(end)}
    assert all(h > last_cal for h in hand), "hand-added days must lie after the calendar's last row (no double counting)"
    d_arr = bars["day"].values
    entry_day = np.where(np.append(d_arr[1:] != d_arr[:-1], True), np.append(d_arr[1:], d_arr[-1]), d_arr)
    return np.array([pd.Timestamp(x) not in ev for x in entry_day]), ev
maskB, ev = f3_mask(bars, root / "10_data/r2_snapshot/news/economic_calendar.csv", END, HAND)
inwin = sorted(x for x in ev if pd.Timestamp(START) <= x <= pd.Timestamp(END))
print(f"bars {len(bars)} | {bars['day'].min().date()} -> {bars['day'].max().date()} | event days in window: {len(inwin)} | bars blocked by F3: {(~maskB).sum()}")

def run(name, mask):
    T, d, pnl = E.backtest(bars, ratio, N, K, H, START, extra_ok=mask)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): ok = E.selfchecks(bars, ratio, (N, K, H), START, T, d, pnl, extra_ok=mask)
    m = E.metrics(T, d); _, d2, _ = E.backtest(bars, ratio, N, K, H, START, fee=E.FEE * 2, extra_ok=mask)
    m.update(variant=name, selfchecks_pass=ok, net_pct_2x_cost=float(d2.sum() / E.CAPITAL * 100))
    print(f"[{name}] self-checks {'PASS' if ok else 'FAIL'}"); return T, d, m
TA, dA, mA = run("A_base", None); TB, dB, mB = run("B_base+F3 (frozen candidate)", maskB)
bench = E.benchmark_daily(bars, START); mBH = E.metrics(pd.DataFrame(), bench); mBH.update(variant="buy_and_hold_QQQ")
for m in (mA, mB):   # informational only (v2.1 sec.5 thresholds); NOT a pass/fail gate for the final window
    m["info_net_pos_and_2x_pos_and_sharpe_ge_0.5"] = bool(m["net_pct"] > 0 and m["net_pct_2x_cost"] > 0 and m["sharpe"] >= 0.5)
keyB = set(map(str, TB["entry_time"])) if len(TB) else set()
blocked = TA[[str(x) not in keyB for x in TA["entry_time"]]] if len(TA) else TA
def per_q(daily, T, label):
    q = daily.groupby(pd.PeriodIndex(daily.index, freq="Q")).sum() / E.CAPITAL * 100
    n = T.groupby(pd.to_datetime(T["entry_time"], utc=True).dt.tz_localize(None).dt.to_period("Q")).size() if len(T) else pd.Series(dtype=int)
    return pd.DataFrame({"variant": label, "quarter": q.index.astype(str), "net_pct": q.values, "trades": [int(n.get(i, 0)) for i in q.index]})
BY = pd.concat([per_q(dA, TA, "A_base"), per_q(dB, TB, "B_base+F3"), per_q(bench, pd.DataFrame(), "buy_and_hold_QQQ")])
RES = pd.DataFrame([mA, mB, mBH]); pd.set_option("display.width", 250)
cols = ["variant", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share", "pnl_ex_top3", "selfchecks_pass"]
print(RES[[c for c in cols if c in RES.columns]].round(3).to_string(index=False)); print("\nby quarter:\n", BY.round(2).to_string(index=False))
print("\nblocked-by-F3 trades:", len(blocked), "| their net PnL USD:", round(float(blocked["pnl_usd"].sum()), 2) if len(blocked) else 0)
tag = "_dryrun" if a.dryrun else ""
RES.to_csv(OUT / f"OOS_results{tag}.csv", index=False); BY.to_csv(OUT / f"OOS_by_quarter{tag}.csv", index=False)
pd.concat([TA.assign(variant="A_base"), TB.assign(variant="B_base+F3")]).to_csv(OUT / f"OOS_trades{tag}.csv", index=False)
pd.DataFrame({"A_base": dA, "B_base+F3": dB, "buy_and_hold": bench}).to_csv(OUT / f"OOS_daily_pnl_usd{tag}.csv")
blocked.to_csv(OUT / f"OOS_blocked_by_F3{tag}.csv", index=False); pd.DataFrame({"event_day_in_window": [str(x.date()) for x in inwin]}).to_csv(OUT / f"OOS_event_days{tag}.csv", index=False)
if not a.dryrun:
    with open(root / "90_logs/config_counter.csv", "a") as f:
        for n in ("QQQ_N7_k0.012_H21", "QQQ_N7_k0.012_H21_F3_EVENT"): f.write(f"{n},OOS,{dt.datetime.now():%Y-%m-%d %H:%M},final_window_frozen_candidate\n")
    (root / "90_logs/OOS_RUN.lock").write_text(f"run {dt.datetime.now().isoformat()} window {START}..{END}")
    print("\nsaved to", OUT, "| lock written: second pass is not allowed")
