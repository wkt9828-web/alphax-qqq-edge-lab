"""
alphax_engine.py -- hourly long-only backtest engine for PRE_REGISTRATION_v1.
Rules implemented exactly as registered:
  signal at close of bar t: close[t]/close[t-N]-1 <= -k  AND  VIX/VIX3M close of the PREVIOUS session < 1.0
  entry  = OPEN of bar t+1 ; exit = OPEN of the bar after (held H bars) or (bar close <= entry*(1-3%))
  fixed notional USD 100,000 per entry, one position at a time, no compounding, fee 0.10% per transaction (entry and exit notional)
  open position at the end of a stage is force-closed at the last bar CLOSE (flagged forced=True)
Look-ahead protection: only positive shifts; data is loaded only up to the stage end date (OOS never loaded for IS runs).
"""
import json, hashlib
from pathlib import Path
import numpy as np, pandas as pd

CAPITAL, FEE, STOP = 100_000.0, 0.001, 0.03

def load_bars(path, end_date):
    d = pd.read_csv(path)
    d["et"] = pd.to_datetime(d["date"], utc=True).dt.tz_convert("America/New_York")
    d = d.sort_values("et").drop_duplicates("et").reset_index(drop=True)
    d["day"] = d["et"].dt.tz_localize(None).dt.normalize()
    d = d[d["day"] <= pd.Timestamp(end_date)].reset_index(drop=True)
    assert d["day"].max() <= pd.Timestamp(end_date), "data beyond stage end loaded"
    return d[["et", "day", "open", "high", "low", "close"]]

def load_gate(vix_csv, vix3m_csv):
    a = pd.read_csv(vix_csv); b = pd.read_csv(vix3m_csv)
    a["date"] = pd.to_datetime(a["date"]); b["date"] = pd.to_datetime(b["date"])
    r = (a.set_index("date")["close"] / b.set_index("date")["close"]).dropna().sort_index()
    return r   # index = session date, value = ratio at that session's close

def gate_prev_session(days, ratio):
    """ratio of the last session STRICTLY BEFORE each bar's date (1-day lag)."""
    idx = ratio.index.values
    pos = np.searchsorted(idx, days.values.astype("datetime64[ns]"), side="left") - 1
    out = np.full(len(days), np.nan)
    ok = pos >= 0
    out[ok] = ratio.values[pos[ok]]
    return out

def backtest(bars, ratio, N, k, H, trade_start, gate_on=True, fee=FEE, stop=STOP):
    o = bars["open"].values; c = bars["close"].values; n = len(bars)
    day = bars["day"].values
    drop = np.full(n, np.nan); drop[N:] = c[N:] / c[:-N] - 1.0            # positive shift only
    g = gate_prev_session(bars["day"], ratio)
    gate_ok = (g < 1.0) if gate_on else np.ones(n, bool)                  # NaN -> False
    sig = (drop <= -k) & gate_ok & (day >= np.datetime64(pd.Timestamp(trade_start)))
    pnl = np.zeros(n); trades = []
    pos = False; pend_entry = False; pend_exit = False
    sig_i = entry_i = None; units = entry_px = last = 0.0; reason = ""
    for i in range(n):
        if pend_exit:                                           # exit at OPEN of bar i
            px = o[i]; xc = units * px * fee
            pnl[i] += units * (px - last) - xc
            trades.append(dict(signal_i=sig_i, entry_i=entry_i, exit_i=i, entry_px=entry_px, exit_px=px,
                               reason=reason, forced=False, exit_cost=xc, entry_cost=CAPITAL * fee))
            pos = False; pend_exit = False
        elif pend_entry:                                        # entry at OPEN of bar i
            entry_px = o[i]; units = CAPITAL / entry_px; entry_i = i
            pnl[i] -= CAPITAL * fee; last = entry_px; pos = True; pend_entry = False
        if pos:
            pnl[i] += units * (c[i] - last); last = c[i]
            held = i - entry_i + 1
            if i == n - 1:                                      # forced close at last bar close
                xc = units * c[i] * fee; pnl[i] -= xc
                trades.append(dict(signal_i=sig_i, entry_i=entry_i, exit_i=i, entry_px=entry_px, exit_px=c[i],
                                   reason="forced_end", forced=True, exit_cost=xc, entry_cost=CAPITAL * fee))
                pos = False
            elif held >= H:
                pend_exit = True; reason = "time"
            elif c[i] <= entry_px * (1 - stop):
                pend_exit = True; reason = "stop"
        elif sig[i] and i < n - 1 and not pend_entry:
            pend_entry = True; sig_i = i
    T = pd.DataFrame(trades)
    if len(T):
        T["units"] = CAPITAL / T["entry_px"]
        T["pnl_usd"] = T["units"] * (T["exit_px"] - T["entry_px"]) - T["entry_cost"] - T["exit_cost"]
        T["ret_net"] = T["pnl_usd"] / CAPITAL
        for col, idx in (("signal_time", "signal_i"), ("entry_time", "entry_i"), ("exit_time", "exit_i")):
            T[col] = bars["et"].values[T[idx].values]
    daily = pd.Series(pnl, index=bars["day"].values).groupby(level=0).sum()
    daily = daily[daily.index >= pd.Timestamp(trade_start)]
    return T, daily, pnl

def benchmark_daily(bars, trade_start, fee=FEE):
    b = bars[bars["day"] >= pd.Timestamp(trade_start)].reset_index(drop=True)
    u = CAPITAL / b["open"].iloc[0]; c = b["close"].values; o0 = b["open"].iloc[0]
    p = np.zeros(len(b)); p[0] = u * (c[0] - o0) - CAPITAL * fee
    p[1:] = u * np.diff(c); p[-1] -= u * c[-1] * fee
    return pd.Series(p, index=b["day"].values).groupby(level=0).sum()

def metrics(T, daily):
    r = daily / CAPITAL
    sd = r.std(ddof=1)
    sharpe = float(np.sqrt(252) * r.mean() / sd) if sd > 0 else float("nan")
    eq = CAPITAL + daily.cumsum(); peak = eq.cummax(); mdd = float(((eq - peak) / peak).min())
    out = dict(sharpe=sharpe, net_pct=float(daily.sum() / CAPITAL * 100), max_dd_pct=mdd * 100, trades=int(len(T)))
    if len(T):
        w = T["pnl_usd"] > 0
        gp = T.loc[w, "pnl_usd"].sum(); gl = -T.loc[~w, "pnl_usd"].sum()
        top3 = T["pnl_usd"].nlargest(3).sum(); tot = T["pnl_usd"].sum()
        out.update(win_rate=float(w.mean()), profit_factor=float(gp / gl) if gl > 0 else float("inf"),
                   worst_trade_pct=float(T["ret_net"].min() * 100), mean_trade_pct=float(T["ret_net"].mean() * 100),
                   top3_share=float(top3 / tot) if tot > 0 else float("nan"),
                   pnl_ex_top3=float(tot - top3))
    return out

def selfchecks(bars, ratio, params, trade_start, T, daily, pnl):
    """prints PASS/FAIL list; returns True only if all pass"""
    N, k, H = params; res = {}
    res["fills_after_signal"] = bool(len(T) == 0 or (T["entry_i"] > T["signal_i"]).all())
    res["no_overlap"] = bool(len(T) == 0 or (T["entry_i"].values[1:] > T["exit_i"].values[:-1]).all())
    res["pnl_reconciles"] = bool(abs(T["pnl_usd"].sum() - pnl.sum()) < 0.01 if len(T) else abs(pnl.sum()) < 0.01)
    res["daily_equals_bar_sum"] = bool(abs(daily.sum() - pnl[bars["day"].values >= np.datetime64(pd.Timestamp(trade_start))].sum()) < 0.01)
    res["fixed_notional_entries"] = bool(len(T) == 0 or np.allclose(T["units"] * T["entry_px"], CAPITAL))
    # truncation test: cut data at ~60%, trades fully closed before the cut must be identical
    cut = int(len(bars) * 0.6); b2 = bars.iloc[:cut].reset_index(drop=True)
    T2, _, _ = backtest(b2, ratio, N, k, H, trade_start)
    a = T[(T["exit_i"] < cut - 1)][["signal_i", "entry_i", "exit_i", "entry_px", "exit_px"]].reset_index(drop=True)
    b = T2[(~T2["forced"]) & (T2["exit_i"] < cut - 1)][["signal_i", "entry_i", "exit_i", "entry_px", "exit_px"]].reset_index(drop=True) if len(T2) else T2
    res["truncation_test"] = bool(a.equals(b) or (len(a) == 0 and len(b) == 0))
    # future-perturbation test: scramble prices after cut, earlier trades must not change
    b3 = bars.copy(); rng = np.random.default_rng(1)
    for col in ("open", "high", "low", "close"):
        b3.loc[cut:, col] = b3.loc[cut:, col].values * (1 + rng.normal(0, 0.05, len(b3) - cut))
    T3, _, _ = backtest(b3, ratio, N, k, H, trade_start)
    d = T3[T3["exit_i"] < cut - 1][["signal_i", "entry_i", "exit_i"]].reset_index(drop=True) if len(T3) else T3
    e = T[T["exit_i"] < cut - 1][["signal_i", "entry_i", "exit_i"]].reset_index(drop=True)
    res["future_perturbation_test"] = bool(e.equals(d) or (len(e) == 0 and len(d) == 0))
    # 2x cost run must be lower or equal
    T4, d4, _ = backtest(bars, ratio, N, k, H, trade_start, fee=FEE * 2)
    res["cost_monotonic"] = bool(d4.sum() <= daily.sum() + 1e-6)
    for kx, v in res.items(): print(f"  [{'PASS' if v else 'FAIL'}] {kx}")
    return all(res.values())

def file_sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
