"""regress_v2.py -- must pass BEFORE any filter result is read (PRE_REGISTRATION_v2 section 5)."""
import sys, io, contextlib
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E, flywheel_filters as FF
STAGES = {"IS": ("2023-11-13", "2025-06-30"), "SELECTION": ("2025-07-01", "2025-11-30")}
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
v1 = {"IS": pd.read_csv(root / "40_results/IS_results_v1_QQQ.csv"), "SELECTION": pd.read_csv(root / "40_results/SELECTION_results_v1_QQQ.csv")}
ok_all = True
for st, (a, b) in STAGES.items():
    bars = E.load_bars(root / "10_data/ibkr_hourly/QQQ_1h_RTH.csv", b)
    T, d, pnl = E.backtest(bars, ratio, 7, 0.012, 21, a); m = E.metrics(T, d)
    ref = v1[st][(v1[st].N == 7) & (v1[st].k == 0.012) & (v1[st].H == 21)].iloc[0]
    same = all(abs(m[k] - ref[k]) < 1e-9 for k in ("sharpe", "net_pct", "max_dd_pct")) and m["trades"] == ref["trades"]
    print(f"[{'PASS' if same else 'FAIL'}] v2 engine reproduces v1 {st}: trades {m['trades']}, sharpe {m['sharpe']:.6f}, net {m['net_pct']:.6f}"); ok_all &= same
    if st == "IS":
        Tg, dg, pg = E.backtest(bars, ratio, 7, 0.012, 21, a, gate_on=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): okg = E.selfchecks(bars, ratio, (7, 0.012, 21), a, Tg, dg, pg, gate_on=False)
        print(f"[{'PASS' if okg else 'FAIL'}] gate-OFF IS selfchecks pass on engine v2"); ok_all &= okg
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): okb = E.selfchecks(bars, ratio, (7, 0.012, 21), a, T, d, pnl)
        print(f"[{'PASS' if okb else 'FAIL'}] base IS selfchecks pass on engine v2"); ok_all &= okb
    masks, info = FF.build_masks(bars, root / "10_data/r2_snapshot", b)
    day_ok = bars[bars["day"] >= pd.Timestamp(a)]["day"]
    for k, v in masks.items():
        v = pd.Series(v, index=bars.index)[bars["day"] >= pd.Timestamp(a)]
        print(f"   mask {k:9s} {st}: allowed bars {v.mean():.3f} | {info.get(k, '')}")
    # all-True mask must equal no mask
    T2, d2, _ = E.backtest(bars, ratio, 7, 0.012, 21, a, extra_ok=np.ones(len(bars), bool))
    print(f"[{'PASS' if abs(d2.sum() - d.sum()) < 1e-9 else 'FAIL'}] all-True extra mask == no mask")
print("REGRESSION", "PASS" if ok_all else "FAIL")
