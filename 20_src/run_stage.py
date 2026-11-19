"""
run_stage.py -- runs the 12 pre-registered configs for stage IS or SELECTION (never OOS).
  python run_stage.py IS            -> 40_results/IS_results_v1.csv  (+ gate flags)
  python run_stage.py SELECTION     -> only configs that passed the IS gate
Data is loaded only up to the stage end date. Every config run is appended to 90_logs/config_counter.csv.
"""
import sys, io, contextlib, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); import alphax_engine as E
root = Path(__file__).resolve().parents[1]
GRID = [(N, k, H) for N in (4, 7) for k in (0.008, 0.012) for H in (7, 14, 21)]
STAGES = {"IS": ("2023-11-13", "2025-06-30"), "SELECTION": ("2025-07-01", "2025-11-30")}
stage = sys.argv[1].upper(); assert stage in STAGES, "OOS is run only by run_oos_once.py"
sym = sys.argv[2].upper() if len(sys.argv) > 2 else "QQQ"
start, end = STAGES[stage]
bars = E.load_bars(root / "10_data/ibkr_hourly" / f"{sym}_1h_RTH.csv", end)
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
cfgs = GRID
if stage == "SELECTION":
    prev = pd.read_csv(root / "40_results" / f"IS_results_v1_{sym}.csv"); keep = prev[prev["IS_GATE_PASS"]]
    cfgs = [(int(r.N), float(r.k), int(r.H)) for r in keep.itertuples()]
    print("configs passing IS gate:", len(cfgs))
bench = E.metrics(pd.DataFrame(), E.benchmark_daily(bars, start)); rows, alltr = [], []
for (N, k, H) in cfgs:
    T, daily, pnl = E.backtest(bars, ratio, N, k, H, start)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): ok = E.selfchecks(bars, ratio, (N, k, H), start, T, daily, pnl)
    m = E.metrics(T, daily); _, d2, _ = E.backtest(bars, ratio, N, k, H, start, fee=E.FEE * 2)
    m.update(N=N, k=k, H=H, stage=stage, symbol=sym, selfchecks_pass=ok, net_pct_2x_cost=float(d2.sum() / E.CAPITAL * 100))
    gate = (m["trades"] >= 30 and m["sharpe"] >= 0.8 and m["net_pct"] > 0 and m["net_pct_2x_cost"] > 0
            and (m.get("pnl_ex_top3", -1) > 0 or m.get("top3_share", 1) < 0.5) and ok) if stage == "IS" else None
    if stage == "IS": m["IS_GATE_PASS"] = bool(gate)
    rows.append(m)
    if len(T): T = T.assign(N=N, k=k, H=H); alltr.append(T)
R = pd.DataFrame(rows).sort_values(["stage", "N", "k", "H"])
out = root / "40_results" / f"{stage}_results_v1_{sym}.csv"; R.to_csv(out, index=False)
if alltr: pd.concat(alltr).to_csv(root / "40_results" / f"{stage}_trades_v1_{sym}.csv", index=False)
with open(root / "90_logs/config_counter.csv", "a") as f:
    for (N, k, H) in cfgs: f.write(f"{sym}_N{N}_k{k}_H{H},{stage},{dt.datetime.now():%Y-%m-%d %H:%M},engine_v1\n")
pd.set_option("display.width", 250)
cols = ["N", "k", "H", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share", "selfchecks_pass"] + (["IS_GATE_PASS"] if stage == "IS" else [])
print(R[cols].round(3).to_string(index=False))
print(f"\nBENCHMARK buy&hold {sym} {stage}: sharpe={bench['sharpe']:.3f} net={bench['net_pct']:.2f}% maxDD={bench['max_dd_pct']:.1f}%")
print("saved:", out)
