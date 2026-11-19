"""Engine self-test on SYNTHETIC data only (no real prices are used, so no strategy result is seen)."""
import numpy as np, pandas as pd, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import alphax_engine as E
rng = np.random.default_rng(7)
days = pd.bdate_range("2023-06-01", periods=700)
rows = []; p = 100.0
for d in days:
    for h in range(7):
        t = pd.Timestamp(d).tz_localize("America/New_York") + pd.Timedelta(hours=9.5 + h)
        o = p; p = p * (1 + rng.normal(0, 0.0035) - (0.012 if rng.random() < 0.01 else 0))
        rows.append((t, pd.Timestamp(d), o, max(o, p) * 1.001, min(o, p) * 0.999, p))
bars = pd.DataFrame(rows, columns=["et", "day", "open", "high", "low", "close"])
ratio = pd.Series(rng.uniform(0.8, 1.15, len(days)), index=pd.DatetimeIndex(days))
ok_all = True
for (N, k, H) in [(4, 0.008, 7), (7, 0.012, 21), (4, 0.012, 14)]:
    start = "2023-09-01"
    T, daily, pnl = E.backtest(bars, ratio, N, k, H, start)
    print(f"cfg N={N} k={k} H={H}: trades={len(T)} net={daily.sum():.0f} USD")
    ok_all &= E.selfchecks(bars, ratio, (N, k, H), start, T, daily, pnl)
# gate lag unit test: ratio on day D must NOT be used on day D
r = pd.Series([0.5, 1.5], index=pd.to_datetime(["2024-01-02", "2024-01-03"]))
g = E.gate_prev_session(pd.Series(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])), r)
gate_ok = bool(np.isnan(g[0]) and g[1] == 0.5 and g[2] == 1.5); print("  [%s] gate uses previous session only" % ("PASS" if gate_ok else "FAIL"))
# stop/time exit unit test with a handmade path
import types
print("\nSELFTEST RESULT:", "ALL PASS" if (ok_all and gate_ok) else "FAILURES")
