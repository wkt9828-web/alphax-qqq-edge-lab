"""
run_v3_screen.py -- PRE_REGISTRATION_v3 runner: volume-profile filters (P1, P2), trend guard (T1) and combinations (C1, C2) on the frozen base.
RUNS ONCE. Never loads data after 2025-11-30 (OOS is untouched).
  python run_v3_screen.py                                  real run (needs the hashed pre-registration; writes a lock)
  python run_v3_screen.py --dryrun --profiles <csv> --out <dir>    plumbing check on synthetic/seen data; no lock, no counter, numbers not for use
"""
import argparse, sys, io, contextlib, hashlib, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E

ap = argparse.ArgumentParser(); ap.add_argument("--dryrun", action="store_true"); ap.add_argument("--profiles"); ap.add_argument("--out"); ap.add_argument("--bars")
a = ap.parse_args()
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
PROF = Path(a.profiles) if a.profiles else root / "10_data/profiles_daily_QQQ.csv"
BARS = Path(a.bars) if a.bars else root / "10_data/ibkr_hourly/QQQ_1h_RTH.csv"
OUT = Path(a.out) if a.out else root / "40_results"; OUT.mkdir(parents=True, exist_ok=True)
if not a.dryrun:
    lock = root / "90_logs/V3_RUN.lock"; assert not lock.exists(), "v3 screen already run once; a second pass must be labelled EXPLORATORY by hand"
    hf = root / "90_logs/PRE_REGISTRATION_v3.sha256"; assert hf.exists(), "hash the v3 pre-registration first"
    assert hf.read_text().split()[0].lower() == sha(root / "00_rules/PRE_REGISTRATION_v3_PROFILE_TREND.md"), "pre-registration changed after hashing"
print("engine_v2 sha256:", sha(root / "20_src/alphax_engine_v2.py")); print("runner   sha256:", sha(__file__))
N, K, H = 7, 0.012, 21
STAGES = {"IS": ("2023-11-13", "2025-06-30"), "SELECTION": ("2025-07-01", "2025-11-30")}; POOL = ("2023-11-13", "2025-11-30")
BASE = {"IS": dict(sharpe=0.8368351852593853, dd=-11.389812146068582), "SELECTION": dict(sharpe=0.6813291639485024)}
EVENT_RULES = [("eq", "Fed Interest Rate Decision"), ("sw", "Non Farm Payrolls"), ("sw", "Inflation Rate MoM")]
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
prof = pd.read_csv(PROF, parse_dates=["date"]).set_index("date").sort_index()
prof["imb"] = prof["net_delta"] / prof["contracts"]
q = pd.read_csv(root / "10_data/r2_snapshot/market_data/daily/QQQ.csv", parse_dates=["date"]).set_index("date")["close"].sort_index()

def session_map(bars, fn):
    days = list(pd.Series(bars["day"].unique()).sort_values()); prev = {d: (days[i - 1] if i else None) for i, d in enumerate(days)}
    return bars["day"].map({d: fn(prev[d]) for d in days}), prev, days

def build_masks(bars, end):
    qq = q[q.index <= pd.Timestamp(end)]; sma = qq.rolling(200).mean()
    m = {}
    t1 = lambda p: bool(p is not None and p in qq.index and pd.notna(sma.get(p)) and qq[p] > sma[p])
    m["T1_TREND"] = session_map(bars, t1)[0].fillna(False).astype(bool).values
    p1 = lambda p: bool(p is not None and p in prof.index and pd.notna(prof.at[p, "imb"]) and prof.at[p, "imb"] < 0)
    m["P1_FLOW"] = session_map(bars, p1)[0].fillna(False).astype(bool).values
    valmap, prev, days = session_map(bars, lambda p: float(prof.at[p, "val"]) if (p is not None and p in prof.index and pd.notna(prof.at[p, "val"])) else np.nan)
    m["P2_VALUE"] = (bars["close"].values < valmap.values.astype(float))            # NaN -> False
    cov = np.mean([(prev[d] is not None) and (prev[d] in prof.index) for d in days if d >= pd.Timestamp(STAGES["IS"][0])])
    cal = pd.read_csv(root / "10_data/r2_snapshot/news/economic_calendar.csv", usecols=["date", "country", "event"], low_memory=False)
    cal = cal[cal["country"] == "US"].copy(); cal["dt"] = pd.to_datetime(cal["date"]).dt.tz_localize("UTC").dt.tz_convert("America/New_York")
    cal["day"] = cal["dt"].dt.tz_localize(None).dt.normalize(); cal = cal[cal["day"] <= pd.Timestamp(end)]
    mm = np.zeros(len(cal), bool)
    for kind, s in EVENT_RULES: mm |= (cal["event"] == s).values if kind == "eq" else cal["event"].str.startswith(s).values
    ev = set(cal.loc[mm, "day"]); d_arr = bars["day"].values
    entry_day = np.where(np.append(d_arr[1:] != d_arr[:-1], True), np.append(d_arr[1:], d_arr[-1]), d_arr)
    m["F3_EVENT"] = np.array([pd.Timestamp(x) not in ev for x in entry_day])
    return m, cov

def run(bars, mask, start, label, full=True):
    T, d, pnl = E.backtest(bars, ratio, N, K, H, start, extra_ok=mask)
    out = E.metrics(T, d); out.update(variant=label)
    if full:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): ok = E.selfchecks(bars, ratio, (N, K, H), start, T, d, pnl, extra_ok=mask)
        _, d2, _ = E.backtest(bars, ratio, N, K, H, start, fee=E.FEE * 2, extra_ok=mask)
        out.update(selfchecks_pass=ok, net_pct_2x_cost=float(d2.sum() / E.CAPITAL * 100))
    return T, d, out

def std_is(m): return bool(m["trades"] >= 30 and m["net_pct"] > 0 and m["net_pct_2x_cost"] > 0 and m["sharpe"] >= BASE["IS"]["sharpe"] + 0.10
                           and m["max_dd_pct"] >= BASE["IS"]["dd"] and (m.get("pnl_ex_top3", -1) > 0 or m.get("top3_share", 1) < 0.5) and m["selfchecks_pass"])
def std_sel(m): return bool(m["trades"] >= 6 and m["net_pct"] > 0 and m["sharpe"] >= BASE["SELECTION"]["sharpe"])
def guard_is(m): return bool(m["trades"] >= 30 and m["net_pct"] > 0 and m["net_pct_2x_cost"] > 0 and m["sharpe"] >= BASE["IS"]["sharpe"] - 0.10 and m["max_dd_pct"] >= BASE["IS"]["dd"] and m["selfchecks_pass"])
def guard_sel(m): return bool(m["trades"] >= 6 and m["net_pct"] > 0 and m["sharpe"] >= BASE["SELECTION"]["sharpe"] - 0.10)

bars_by = {s: E.load_bars(BARS, STAGES[s][1]) for s in STAGES}; barsP = E.load_bars(BARS, POOL[1]); assert barsP["day"].max() <= pd.Timestamp("2025-11-30")
masks_by, covs = {}, {}
for s in STAGES: masks_by[s], covs[s] = build_masks(bars_by[s], STAGES[s][1])
masksP, covP = build_masks(barsP, POOL[1])
print(f"profile coverage (share of IS-onward sessions with a usable previous-session profile): {covP:.3f}")
rows, trades = [], []
def stage_run(name, comb, stage):
    mask = np.ones(len(bars_by[stage]), bool)
    for c in comb: mask &= masks_by[stage][c]
    T, d, m = run(bars_by[stage], mask, STAGES[stage][0], name); m.update(stage=stage, blocked_bars=int((~mask).sum()))
    rows.append(m)
    if len(T): trades.append(T.assign(variant=name, stage=stage))
    return m
singles = {"P1_FLOW": ["P1_FLOW"], "P2_VALUE": ["P2_VALUE"], "T1_TREND": ["T1_TREND"], "C1_F3+T1": ["F3_EVENT", "T1_TREND"]}
IS = {n: stage_run(n, c, "IS") for n, c in singles.items()}
for n, m in IS.items(): m["IS_PASS"] = guard_is(m) if n == "T1_TREND" else std_is(m)
SEL = {}
for n, c in singles.items():
    if IS[n]["IS_PASS"]:
        SEL[n] = stage_run(n, c, "SELECTION"); SEL[n]["SEL_PASS"] = guard_sel(SEL[n]) if n == "T1_TREND" else std_sel(SEL[n])
prof_pass = [n for n in ("P1_FLOW", "P2_VALUE") if IS[n]["IS_PASS"] and n in SEL and SEL[n]["SEL_PASS"]]
c2 = None
if prof_pass:
    c2 = "C2_F3+" + "+".join(prof_pass); comb = ["F3_EVENT"] + prof_pass; singles[c2] = comb
    IS[c2] = stage_run(c2, comb, "IS"); IS[c2]["IS_PASS"] = std_is(IS[c2])
    if IS[c2]["IS_PASS"]: SEL[c2] = stage_run(c2, comb, "SELECTION"); SEL[c2]["SEL_PASS"] = std_sel(SEL[c2])
cand = [n for n in singles if n != "T1_TREND" and IS[n]["IS_PASS"] and n in SEL and SEL[n]["SEL_PASS"]]
# F3 (v2) is eligible by construction; pooled run for every eligible variant
pooled, dailyP = [], {}
for n in ["F3_EVENT (v2)"] + cand:
    comb = ["F3_EVENT"] if n.startswith("F3_EVENT") else singles[n]
    mask = np.ones(len(barsP), bool)
    for c in comb: mask &= masksP[c]
    T, d, m = run(barsP, mask, POOL[0], n); m["filters"] = len(comb); pooled.append(m); dailyP[n] = d
    if len(T): trades.append(T.assign(variant=n, stage="POOLED"))
bm = barsP; bench = E.benchmark_daily(bm, POOL[0]); mb = E.metrics(pd.DataFrame(), bench); mb.update(variant="buy_and_hold_QQQ", filters=0); pooled.append(mb)
P = pd.DataFrame(pooled); elig = P[P["variant"] != "buy_and_hold_QQQ"].sort_values(["sharpe", "filters"], ascending=[False, True])
pick = elig.iloc[0]["variant"]
R = pd.DataFrame(rows); pd.set_option("display.width", 260)
cols = ["variant", "stage", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share", "pnl_ex_top3", "blocked_bars", "selfchecks_pass", "IS_PASS"]
if a.dryrun:
    print(f"\nDRYRUN OK: {len(R)} stage rows, {len(P)} pooled rows, selfchecks all pass: {bool(R['selfchecks_pass'].all())}. Performance numbers are deliberately NOT printed in a dry run.")
else:
    print("\nSTAGE RESULTS\n", R[[c for c in cols if c in R.columns]].round(3).to_string(index=False))
    print("\nSEL pass flags:", {n: bool(m["SEL_PASS"]) for n, m in SEL.items()})
    print("\nPOOLED (2023-11-13..2025-11-30)\n", P[["variant", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share"]].round(3).to_string(index=False))
    print("\nRULE'S PICK (highest pooled Sharpe among eligible):", pick, "| default; owner may choose another eligible variant")
R.to_csv(OUT / ("V3_results_dryrun.csv" if a.dryrun else "V3_results.csv"), index=False); P.to_csv(OUT / ("V3_pooled_dryrun.csv" if a.dryrun else "V3_pooled.csv"), index=False)
if trades: pd.concat(trades).to_csv(OUT / ("V3_trades_dryrun.csv" if a.dryrun else "V3_trades.csv"), index=False)
pd.DataFrame({**dailyP, "buy_and_hold": bench}).to_csv(OUT / ("V3_daily_pnl_pooled_dryrun.csv" if a.dryrun else "V3_daily_pnl_pooled.csv"))
if not a.dryrun:
    with open(root / "90_logs/config_counter.csv", "a") as f:
        for n in singles:
            for s in ("IS", "SELECTION"):
                if (s == "IS") or n in SEL: f.write(f"QQQ_N7_k0.012_H21_{n},{s},{dt.datetime.now():%Y-%m-%d %H:%M},v3_screen\n")
    (root / "90_logs/V3_RUN.lock").write_text(f"run {dt.datetime.now().isoformat()}"); print("lock written; second pass not allowed")
