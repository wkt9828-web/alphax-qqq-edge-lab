"""
run_v2_filters.py -- PRE_REGISTRATION_v2 runner. Refuses OOS.
  python run_v2_filters.py IS                -> F1..F4 on IS (base fixed N7,k1.2%,H21)
  python run_v2_filters.py SELECTION         -> only filters that passed the IS criteria
  python run_v2_filters.py COMBO_IS|COMBO_SELECTION   -> intersection of filters that passed BOTH stages (>=2 needed)
Each distinct variant is appended to 90_logs/config_counter.csv once per stage run.
"""
import sys, io, contextlib, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E, flywheel_filters as FF
STAGES = {"IS": ("2023-11-13", "2025-06-30"), "SELECTION": ("2025-07-01", "2025-11-30")}
BASE = {"IS": dict(sharpe=0.8368351852593853, dd=-11.389812146068582), "SELECTION": dict(sharpe=0.6813291639485024)}
N, K, H = 7, 0.012, 21
mode = sys.argv[1].upper(); assert mode in ("IS", "SELECTION", "COMBO_IS", "COMBO_SELECTION"), "OOS is never run here"
stage = "IS" if mode.endswith("IS") else "SELECTION"; a, b = STAGES[stage]
ratio = E.load_gate(root / "10_data/r2_snapshot/market_data/daily/_VIX.csv", root / "10_data/r2_snapshot/market_data/daily/_VIX3M.csv")
bars = E.load_bars(root / "10_data/ibkr_hourly/QQQ_1h_RTH.csv", b); assert bars["day"].max() <= pd.Timestamp(b)
masks, info = FF.build_masks(bars, root / "10_data/r2_snapshot", b)
res_dir = root / "40_results"
if mode in ("IS", "SELECTION"):
    names = ["F1_GEX", "F2_HY", "F3_EVENT", "F4_RATES"]
    if mode == "SELECTION":
        prev = pd.read_csv(res_dir / "IS_results_v2_filters.csv"); names = prev[prev["IS_PASS"]]["variant"].tolist(); print("IS passers:", names)
    variants = {n: masks[n] for n in names}
else:
    p1 = pd.read_csv(res_dir / "IS_results_v2_filters.csv"); p2 = pd.read_csv(res_dir / "SELECTION_results_v2_filters.csv")
    both = [v for v in p1[p1["IS_PASS"]]["variant"] if bool(p2[p2["variant"] == v]["SEL_PASS"].iloc[0])]
    assert len(both) >= 2, f"combo needs >=2 filters passing both stages; have {both}"
    m = np.ones(len(bars), bool)
    for v in both: m &= masks[v]
    variants = {"F5_COMBO(" + "+".join(both) + ")": m}
rows, alltr = [], []
for name, mask in variants.items():
    T, d, pnl = E.backtest(bars, ratio, N, K, H, a, extra_ok=mask)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): ok = E.selfchecks(bars, ratio, (N, K, H), a, T, d, pnl, extra_ok=mask)
    m_ = E.metrics(T, d); _, d2, _ = E.backtest(bars, ratio, N, K, H, a, fee=E.FEE * 2, extra_ok=mask)
    m_.update(variant=name, stage=stage, selfchecks_pass=ok, net_pct_2x_cost=float(d2.sum() / E.CAPITAL * 100))
    if stage == "IS":
        m_["IS_PASS"] = bool(m_["trades"] >= 30 and m_["net_pct"] > 0 and m_["net_pct_2x_cost"] > 0 and m_["sharpe"] >= BASE["IS"]["sharpe"] + 0.10
                             and m_["max_dd_pct"] >= BASE["IS"]["dd"] and (m_.get("pnl_ex_top3", -1) > 0 or m_.get("top3_share", 1) < 0.5) and ok)
    else:
        m_["SEL_PASS"] = bool(m_["trades"] >= 6 and m_["net_pct"] > 0 and m_["sharpe"] >= BASE["SELECTION"]["sharpe"])
    rows.append(m_)
    if len(T): alltr.append(T.assign(variant=name, stage=stage))
R = pd.DataFrame(rows); tag = "_combo" if mode.startswith("COMBO") else ""
out = res_dir / f"{stage}_results_v2_filters{tag}.csv"; R.to_csv(out, index=False)
if alltr: pd.concat(alltr).to_csv(res_dir / f"{stage}_trades_v2_filters{tag}.csv", index=False)
with open(root / "90_logs/config_counter.csv", "a") as f:
    for n in variants: f.write(f"QQQ_N7_k0.012_H21_{n},{stage},{dt.datetime.now():%Y-%m-%d %H:%M},v2_filter_engine_v2\n")
pd.set_option("display.width", 250)
cols = ["variant", "trades", "sharpe", "net_pct", "net_pct_2x_cost", "max_dd_pct", "win_rate", "profit_factor", "top3_share", "pnl_ex_top3", "selfchecks_pass"] + (["IS_PASS"] if stage == "IS" else ["SEL_PASS"])
print(R[cols].round(3).to_string(index=False)); print("saved:", out)
