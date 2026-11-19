"""
run_prewindow_v21.py -- PRE_REGISTRATION_v2_1 runner: frozen v2 rule (base, base+F3_EVENT) on the PRE-WINDOW. RUNS ONCE.
  python run_prewindow_v21.py                      -> real run (2020-01-03..2023-11-10); needs the hashed pre-registration; writes a lock
  python run_prewindow_v21.py --dryrun --bars <csv> --start 2023-11-13 --end 2025-06-30 --out <dir>
        -> regression/plumbing check on ALREADY-SEEN data; writes nothing to the project, no lock, no counter row.
Never loads data after --end. Never touches the OOS window (hard stop at 2025-11-30).
"""
import argparse, sys, hashlib, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E

ap = argparse.ArgumentParser()
ap.add_argument("--dryrun", action="store_true"); ap.add_argument("--bars"); ap.add_argument("--start"); ap.add_argument("--end"); ap.add_argument("--out")
ap.add_argument("--placebo-n", type=int, default=500)
a = ap.parse_args()
N, K, H = 7, 0.012, 21                                   # frozen (v1 chosen base)
EVENT_RULES = [("eq", "Fed Interest Rate Decision"), ("sw", "Non Farm Payrolls"), ("sw", "Inflation Rate MoM")]   # = flywheel_filters.EVENT_RULES
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
if a.dryrun:
    assert a.bars and a.start and a.end and a.out, "--dryrun needs --bars --start --end --out"
    START, END, BARS, OUT = a.start, a.end, Path(a.bars), Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
else:
    START, END = "2020-01-03", "2023-11-10"; BARS = root / "10_data/ibkr_hourly_prewindow/QQQ_1h_RTH_pre.csv"; OUT = root / "40_results"
    lock = root / "90_logs/PREWINDOW_RUN.lock"
    assert not lock.exists(), f"PRE-WINDOW already run once ({lock.read_text()[:60]!r}); a second pass must be labelled EXPLORATORY by hand"
    hf = root / "90_logs/PRE_REGISTRATION_v2_1.sha256"; assert hf.exists(), "hash the pre-registration first (90_logs/PRE_REGISTRATION_v2_1.sha256)"
    want = hf.read_text().split()[0].lower(); got = sha(root / "00_rules/PRE_REGISTRATION_v2_1_PREWINDOW.md")
    assert want == got, f"pre-registration hash mismatch: recorded {want[:12]} vs file {got[:12]} -- edited after hashing?"
    chk = root / "90_logs/hourly_data_check_prewindow.txt"; assert chk.exists() and "ALL PASS" in chk.read_text(), "run check_prewindow_data.py first (must say ALL PASS)"
assert pd.Timestamp(END) <= pd.Timestamp("2025-11-30"), "OOS (2025-12-01+) is never loaded here"
print("engine_v2 sha256:", sha(root / "20_src/alphax_engine_v2.py")); print("runner   sha256:", sha(__file__))

bars = E.load_bars(BARS, END); assert bars["day"].max() <= pd.Timestamp(END)
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
def f3_mask(bars, cal_csv, end):                          # same definition as flywheel_filters.build_masks()["F3_EVENT"]
    cal = pd.read_csv(cal_csv, usecols=["date", "country", "event"], low_memory=False)
    cal = cal[cal["country"] == "US"].copy(); cal["dt"] = pd.to_datetime(cal["date"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    cal["day"] = cal["dt"].dt.tz_localize(None).dt.normalize(); cal = cal[cal["day"] <= pd.Timestamp(end)]
    m = np.zeros(len(cal), bool)
    for kind, s in EVENT_RULES: m |= (cal["event"] == s).values if kind == "eq" else cal["event"].str.startswith(s).values
    ev = set(cal.loc[m, "day"]); d_arr = bars["day"].values
    entry_day = np.where(np.append(d_arr[1:] != d_arr[:-1], True), np.append(d_arr[1:], d_arr[-1]), d_arr)
    return np.array([pd.Timestamp(x) not in ev for x in entry_day]), ev
CAL = root / "10_data/r2_snapshot/news/economic_calendar.csv"
maskB, ev = f3_mask(bars, CAL, END)
print(f"bars {len(bars)} | {bars['day'].min().date()} -> {bars['day'].max().date()} | event days <= end: {len(ev)} | bars blocked by F3: {(~maskB).sum()}")
if a.dryrun and (root / "10_data/r2_snapshot/market_data/fred/observations/DGS10.parquet").exists():    # plumbing: identical to the v2 filter module
    import flywheel_filters as FF
    mm, _ = FF.build_masks(bars, root / "10_data/r2_snapshot", END); print("F3 mask identical to flywheel_filters.build_masks:", bool((mm["F3_EVENT"] == maskB).all()))

def run(name, mask):
    T, d, pnl = E.backtest(bars, ratio, N, K, H, START, extra_ok=mask)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): ok = E.selfchecks(bars, ratio, (N, K, H), START, T, d, pnl, extra_ok=mask)
    m = E.metrics(T, d); _, d2, _ = E.backtest(bars, ratio, N, K, H, START, fee=E.FEE * 2, extra_ok=mask)
    m.update(variant=name, selfchecks_pass=ok, net_pct_2x_cost=float(d2.sum() / E.CAPITAL * 100))
    print(f"[{name}] self-checks {'PASS' if ok else 'FAIL'}"); return T, d, m
TA, dA, mA = run("A_base", None); TB, dB, mB = run("B_base+F3", maskB)
bench = E.benchmark_daily(bars, START); mBH = E.metrics(pd.DataFrame(), bench); mBH.update(variant="buy_and_hold_QQQ")

def supported(m):
    return bool(m["trades"] >= 30 and m["net_pct"] > 0 and m["net_pct_2x_cost"] > 0 and m["sharpe"] >= 0.5
                and (m.get("pnl_ex_top3", -1) > 0 or m.get("top3_share", 1) < 0.5) and m["selfchecks_pass"])
mA["A_SUPPORTED"] = supported(mA)
mB["B_MEETS_CHECKS"] = supported(mB)
mB["B_IMPROVES"] = bool(mB["B_MEETS_CHECKS"] and mB["sharpe"] >= mA["sharpe"] + 0.10 and mB["max_dd_pct"] >= mA["max_dd_pct"])
# trades in A that F3 removed
keyA = set(map(str, TA["entry_time"])) if len(TA) else set(); keyB = set(map(str, TB["entry_time"])) if len(TB) else set()
blocked = TA[[str(x) not in keyB for x in TA["entry_time"]]] if len(TA) else TA
# random-day-blocking placebo (descriptive)
rng = np.random.default_rng(20261115); sess = np.array(sorted(bars.loc[bars["day"] >= pd.Timestamp(START), "day"].unique()))
n_block = len({pd.Timestamp(x) for x in np.where(np.append(bars["day"].values[1:] != bars["day"].values[:-1], True), np.append(bars["day"].values[1:], bars["day"].values[-1]), bars["day"].values) if pd.Timestamp(x) in ev and pd.Timestamp(x) >= pd.Timestamp(START)})
ent = np.where(np.append(bars["day"].values[1:] != bars["day"].values[:-1], True), np.append(bars["day"].values[1:], bars["day"].values[-1]), bars["day"].values)
sh = []
for _ in range(a.placebo_n):
    blk = set(rng.choice(sess, size=min(n_block, len(sess)), replace=False)); mk = np.array([x not in blk for x in ent])
    _, dd, _ = E.backtest(bars, ratio, N, K, H, START, extra_ok=mk); sh.append(E.metrics(pd.DataFrame(), dd)["sharpe"])
sh = np.array(sh); placebo = dict(n_draws=len(sh), event_days_blocked_in_window=n_block, F3_sharpe=mB["sharpe"],
                                   placebo_median_sharpe=float(np.nanmedian(sh)), share_of_draws_with_sharpe_ge_F3=float(np.mean(sh >= mB["sharpe"])))
# by-year
def yr(daily, T, label):
    y = daily.groupby(daily.index.year).sum() / E.CAPITAL * 100
    n = T.groupby(pd.to_datetime(T["entry_time"], utc=True).dt.year).size() if len(T) else pd.Series(dtype=int)
    return pd.DataFrame({"variant": label, "year": y.index, "net_pct": y.values, "trades": [int(n.get(i, 0)) for i in y.index]})
BY = pd.concat([yr(dA, TA, "A_base"), yr(dB, TB, "B_base+F3"), yr(bench, pd.DataFrame(), "buy_and_hold_QQQ")])
R = pd.DataFrame([mA, mB, mBH]); pd.set_option("display.width", 250)
cols = ["variant", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share", "pnl_ex_top3", "selfchecks_pass", "A_SUPPORTED", "B_MEETS_CHECKS", "B_IMPROVES"]
print(R[[c for c in cols if c in R.columns]].round(3).to_string(index=False)); print("\nby year:\n", BY.round(2).to_string(index=False))
print("\nblocked-by-F3 trades:", len(blocked), "| their net PnL USD:", round(float(blocked["pnl_usd"].sum()), 2) if len(blocked) else 0); print("placebo:", placebo)
tag = "_dryrun" if a.dryrun else ""
R.to_csv(OUT / f"PRE_results_v21{tag}.csv", index=False); BY.to_csv(OUT / f"PRE_by_year_v21{tag}.csv", index=False)
pd.concat([TA.assign(variant="A_base"), TB.assign(variant="B_base+F3")]).to_csv(OUT / f"PRE_trades_v21{tag}.csv", index=False)
pd.DataFrame({"A_base": dA, "B_base+F3": dB, "buy_and_hold": bench}).to_csv(OUT / f"PRE_daily_pnl_usd_v21{tag}.csv")
blocked.to_csv(OUT / f"PRE_blocked_by_F3_v21{tag}.csv", index=False); pd.DataFrame([placebo]).to_csv(OUT / f"PRE_placebo_F3_v21{tag}.csv", index=False)
if not a.dryrun:
    with open(root / "90_logs/config_counter.csv", "a") as f:
        for n in ("QQQ_N7_k0.012_H21", "QQQ_N7_k0.012_H21_F3_EVENT"): f.write(f"{n},PREWINDOW,{dt.datetime.now():%Y-%m-%d %H:%M},v2_1_frozen_rule_older_history\n")
    (root / "90_logs/PREWINDOW_RUN.lock").write_text(f"run {dt.datetime.now().isoformat()} window {START}..{END}")
    print("\nVERDICT (rules in PRE_REGISTRATION_v2_1 sec.5): A_SUPPORTED=%s  B_IMPROVES=%s" % (mA["A_SUPPORTED"], mB["B_IMPROVES"]))
    print("saved to", OUT, "| lock written: second pass is not allowed")
