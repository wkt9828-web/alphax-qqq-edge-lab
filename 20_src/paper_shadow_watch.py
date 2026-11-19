"""
paper_shadow_watch.py -- READ-ONLY forward shadow log for C1 (QQQ, F3 filter, hold 35 bars) and F3 (hold 21 bars).
NO ORDERS are ever placed: the IBKR connection is read-only and this file contains no order code.

What it does on each run (state is derived from the data, nothing is remembered between runs except the append-only log):
  1. verifies the hashes of the frozen configs and the engine (refuses to run if they changed),
  2. downloads the last ~30 days of QQQ 1h regular-hours bars (IBKR, port 4003 by default),
  3. re-runs the frozen engine (alphax_engine_v2.py) from the shadow start date over those bars,
  4. appends to 50_paper/shadow_log.csv every dip signal (with the reason it was or was not traded), every hypothetical entry and every exit,
  5. writes 50_paper/shadow_status.json (open positions, last bar, data sources) and appends a heartbeat line to 50_paper/shadow_runs.log.

  python 20_src\\paper_shadow_watch.py --port 4003              one pass (run it hourly, a couple of minutes after each hour)
  python 20_src\\paper_shadow_watch.py --port 4003 --loop       keeps running, one pass every 5 minutes

Replay test (no IBKR; uses a stored bars file and writes to a scratch folder):
  python 20_src\\paper_shadow_watch.py --replay-bars <csv> --asof "2026-11-12 16:00" --start 2026-09-01 --out-dir <scratch> --no-hash-check
"""
import argparse, sys, json, hashlib, time, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root / "20_src"))
import alphax_engine_v2 as E

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=4003); ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--client-id", type=int, default=9201)
ap.add_argument("--loop", action="store_true"); ap.add_argument("--poll-seconds", type=int, default=300)
ap.add_argument("--replay-bars"); ap.add_argument("--asof"); ap.add_argument("--start"); ap.add_argument("--out-dir"); ap.add_argument("--no-hash-check", action="store_true")
a = ap.parse_args()
REPLAY = bool(a.replay_bars)
if REPLAY: assert a.asof and a.out_dir and a.start, "replay needs --asof, --start and --out-dir"
if a.no_hash_check: assert REPLAY, "--no-hash-check is only allowed in replay mode"
if a.out_dir is None: OUT = root / "50_paper"
else: OUT = Path(a.out_dir)
assert REPLAY or OUT == root / "50_paper"
OUT.mkdir(parents=True, exist_ok=True); (OUT / "snapshots").mkdir(exist_ok=True)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
ET = "America/New_York"; N, K = 7, 0.012

C1_CFG_P, OOS_CFG_P = root / "00_rules/FROZEN_CONFIG_C1_SHADOW.json", root / "00_rules/FROZEN_CONFIG_OOS.json"
C1 = json.loads(C1_CFG_P.read_text(encoding="utf-8")); OOS = json.loads(OOS_CFG_P.read_text(encoding="utf-8"))
if not a.no_hash_check:
    for cfgp, logp in ((C1_CFG_P, root / "90_logs/FROZEN_CONFIG_C1_SHADOW.sha256"), (OOS_CFG_P, root / "90_logs/FROZEN_CONFIG_OOS.sha256")):
        assert logp.exists(), f"hash {cfgp.name} first and store it in {logp.name}"
        assert logp.read_text().split()[0].lower() == sha(cfgp), f"{cfgp.name} changed after hashing"
    assert sha(root / "20_src/alphax_engine_v2.py") == C1["references"]["alphax_engine_v2_sha256"], "engine changed"
SHA_CFG, SHA_ENG, SHA_SELF = sha(C1_CFG_P)[:12], sha(root / "20_src/alphax_engine_v2.py")[:12], sha(__file__)[:12]
START = pd.Timestamp(a.start or C1["shadow"]["start_date_et"])
VARIANTS = [("C1_QQQ_H35_F3", C1["rule"]["H_bars"]), ("F3_QQQ_H21", OOS["rule"]["H_bars"])]
assert C1["rule"]["N_bars"] == OOS["rule"]["N_bars"] == N and abs(C1["rule"]["k_drop"] - K) < 1e-12 and C1["F3_event_rules"] == OOS["F3_event_rules"]
RULES = [("eq" if k == "equals" else "sw", s) for k, s in C1["F3_event_rules"]]

# ---------- events (F3) ----------
def load_events():
    cal = pd.read_csv(root / "10_data/r2_snapshot/news/economic_calendar.csv", usecols=["date", "country", "event"], low_memory=False)
    cal = cal[cal["country"] == "US"].copy(); cal["dt"] = pd.to_datetime(cal["date"]).dt.tz_localize("UTC").dt.tz_convert(ET)
    cal["day"] = cal["dt"].dt.tz_localize(None).dt.normalize(); cal_max = cal["day"].max()
    mm = np.zeros(len(cal), bool)
    for kind, s in RULES: mm |= (cal["event"] == s).values if kind == "eq" else cal["event"].str.startswith(s).values
    ev = {d: e for d, e in zip(cal.loc[mm, "day"], cal.loc[mm, "event"])}
    for h in C1["hand_added_event_days_et"]: ev[pd.Timestamp(h["date"])] = h["event"]
    man = OUT / "events_manual.csv"
    if man.exists():
        m = pd.read_csv(man, comment="#")
        for _, r in m.dropna(subset=["date"]).iterrows(): ev[pd.Timestamp(r["date"])] = str(r["event"])
    vt = OUT / "events_verified_through.txt"; vthru = pd.Timestamp(vt.read_text().split()[0]) if vt.exists() else pd.Timestamp("2026-11-12")
    return ev, max(cal_max, vthru)

# ---------- VIX / VIX3M gate ----------
def load_ratio(ib):
    src = {}; d = root / "10_data/r2_snapshot/market_data/daily"
    v = pd.read_csv(d / "_VIX.csv"); w = pd.read_csv(d / "_VIX3M.csv")
    for x in (v, w): x["date"] = pd.to_datetime(x["date"])
    r = (v.set_index("date")["close"] / w.set_index("date")["close"]).dropna(); src.update({k: "R2 snapshot" for k in r.index})
    man = OUT / "vix_manual.csv"
    if man.exists():
        m = pd.read_csv(man, comment="#"); m["date"] = pd.to_datetime(m["date"])
        for _, x in m.dropna().iterrows(): r.loc[x["date"]] = float(x["vix"]) / float(x["vix3m"]); src[x["date"]] = "manual file"
    if ib is not None:
        try:
            from ib_insync import Index, util
            got = {}
            for sym in ("VIX", "VIX3M"):
                c = Index(sym, "CBOE"); ib.qualifyContracts(c)
                bars = ib.reqHistoricalData(c, endDateTime="", durationStr="20 D", barSizeSetting="1 day", whatToShow="TRADES", useRTH=True, formatDate=1)
                df = util.df(bars); df["date"] = pd.to_datetime(df["date"]); got[sym] = df.set_index("date")["close"]
            rr = (got["VIX"] / got["VIX3M"]).dropna()
            for k, val in rr.items(): r.loc[pd.Timestamp(k)] = float(val); src[pd.Timestamp(k)] = "IBKR index bars"
        except Exception as e: print("  (IBKR VIX/VIX3M not available -> R2 snapshot / manual file:", repr(e)[:90], ")")
    return r.sort_index(), src

# ---------- bars ----------
def clean(df):
    d = df.copy(); d["et"] = pd.to_datetime(d["date"], utc=True).dt.tz_convert(ET)
    d = d.sort_values("et").drop_duplicates("et").reset_index(drop=True); d["day"] = d["et"].dt.tz_localize(None).dt.normalize()
    return d[["et", "day", "open", "high", "low", "close"]]
def get_bars(ib):
    if REPLAY:
        asof = pd.Timestamp(a.asof, tz=ET); d = clean(pd.read_csv(a.replay_bars)); d = d[d["et"] <= asof].reset_index(drop=True); return d, asof, "replay:" + Path(a.replay_bars).name
    from ib_insync import Stock, util
    c = Stock("QQQ", "SMART", "USD"); ib.qualifyContracts(c)
    bars = ib.reqHistoricalData(c, endDateTime="", durationStr="30 D", barSizeSetting="1 hour", whatToShow="TRADES", useRTH=True, formatDate=2)
    assert bars, "no bars returned (market data?)"
    return clean(util.df(bars)), pd.Timestamp.now(tz=ET), f"IBKR port {a.port} (read-only)"
def mark_partial(d, now):
    dur = np.where(d["et"].dt.strftime("%H:%M") == "09:30", 30, 60); end = d["et"] + pd.to_timedelta(dur, unit="m")
    complete = (end <= now).values; d = d.copy()
    for i in np.where(~complete)[0]:                  # an in-progress bar: only its OPEN is known; never use its partial high/low/close
        for col in ("high", "low", "close"): d.loc[i, col] = d.loc[i, "open"]
    return d, int(complete.sum())

def f3_mask(bars, ev):
    d = bars["day"].values; entry_day = np.where(np.append(d[1:] != d[:-1], True), np.append(d[1:], d[-1]), d)
    return np.array([pd.Timestamp(x) not in ev for x in entry_day])

def next_weekday(day):
    x = pd.Timestamp(day) + pd.Timedelta(days=1)
    while x.weekday() >= 5: x += pd.Timedelta(days=1)
    return x

LOG, COLS = OUT / "shadow_log.csv", ["key", "logged_at_utc", "variant", "event", "signal_time_et", "entry_time_et", "entry_px", "exit_time_et", "exit_px", "reason", "pnl_usd_hypothetical", "gate_ratio", "gate_source", "event_status", "detail", "data_source", "config_sha12", "engine_sha12", "script_sha12"]
def seen_keys(): return set(pd.read_csv(LOG)["key"]) if LOG.exists() else set()
def append(rows):
    if not rows: return
    df = pd.DataFrame(rows)[COLS]; df.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)

def run_once(ib):
    now_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    bars_raw, now, source = get_bars(ib); bars, ncomp = mark_partial(bars_raw, now)
    ratio, gsrc = load_ratio(ib); ev, cov_end = load_events()
    g = E.gate_prev_session(bars["day"], ratio); close = bars["close"].values; n = len(bars)
    drop = np.full(n, np.nan); drop[N:] = close[N:] / close[:-N] - 1.0
    keys = seen_keys(); new = []; status = {"last_run_utc": now_utc, "now_et": str(now), "data_source": source, "last_complete_bar_start_et": str(bars["et"].iloc[ncomp - 1]) if ncomp else None, "in_progress_bar": bool(n > ncomp), "events_verified_through": str(cov_end.date()), "variants": {}}
    last_g_day = ratio.index.max(); status["gate_series_last_date"] = str(last_g_day.date()); status["gate_last_source"] = gsrc.get(last_g_day)
    base = dict(logged_at_utc=now_utc, data_source=source, config_sha12=SHA_CFG, engine_sha12=SHA_ENG, script_sha12=SHA_SELF)
    snap_needed = False
    for name, H in VARIANTS:
        mask = f3_mask(bars, ev); T, d_, pnl = E.backtest(bars, ratio, N, K, H, START, extra_ok=mask)
        open_pos = None
        for r in T.itertuples():
            ent = bars["et"].iloc[r.entry_i]
            row = dict(base, variant=name, signal_time_et=str(bars["et"].iloc[r.signal_i]), entry_time_et=str(ent), entry_px=r.entry_px, gate_ratio=round(float(g[r.signal_i]), 4), gate_source=gsrc.get(ratio.index[ratio.index < bars["day"].iloc[r.signal_i]].max()))
            ed = bars["day"].iloc[r.entry_i]; row["event_status"] = "VERIFIED" if ed <= cov_end else "UNVERIFIED_CALENDAR"
            k = f"ENTRY|{name}|{ent}"
            if k not in keys: new.append(dict(row, key=k, event="ENTRY (hypothetical fill = open of next bar)", detail=f"H={H}", **{c: "" for c in ("exit_time_et", "exit_px", "reason", "pnl_usd_hypothetical")})); snap_needed = True
            if r.forced: open_pos = dict(entry_time_et=str(ent), entry_px=float(r.entry_px), bars_held=int(n - 1 - r.entry_i + 1), last_price=float(bars_raw["close"].iloc[-1]), mark_pnl_usd=round(float(r.units * (bars_raw["close"].iloc[-1] - r.entry_px)), 0))
            else:
                ex = bars["et"].iloc[r.exit_i]; k = f"EXIT|{name}|{ex}"
                if k not in keys: new.append(dict(row, key=k, event="EXIT", exit_time_et=str(ex), exit_px=r.exit_px, reason=r.reason, pnl_usd_hypothetical=round(float(r.pnl_usd), 2), detail=f"net of 0.10%/side, H={H}"))
        # every raw dip since the start, with the reason it was or was not traded
        for i in range(ncomp):
            if not (bars["day"].iloc[i] >= START and drop[i] <= -K): continue
            sig_t = bars["et"].iloc[i]; gi = g[i]; taken = bool((T["signal_i"] == i).any()) if len(T) else False
            in_pos = bool(len(T) and ((T["entry_i"] <= i) & (T["exit_i"] > i)).any())
            if i + 1 < n: eday = bars["day"].iloc[i + 1]
            else: eday = next_weekday(bars["day"].iloc[i]) if sig_t.strftime("%H:%M") == "15:00" else bars["day"].iloc[i]
            es = "VERIFIED" if eday <= cov_end else "UNVERIFIED_CALENDAR"
            if np.isnan(gi): why = "NO ENTRY: gate data missing (no VIX/VIX3M for the previous session)"
            elif gi >= 1.0: why = f"NO ENTRY: gate closed (VIX/VIX3M {gi:.3f} >= 1)"
            elif pd.Timestamp(eday) in ev: why = f"NO ENTRY: blocked by F3 ({ev[pd.Timestamp(eday)]} on {pd.Timestamp(eday).date()})"
            elif taken: why = "TAKEN"
            elif i == ncomp - 1 and i + 1 >= n: why = "SIGNAL PENDING: entry at the open of the next bar unless a position is open" if not in_pos else "NO ENTRY: already in position"
            elif in_pos: why = "NO ENTRY: already in position"
            else: why = "NO ENTRY: other (see engine)"
            k = f"DIP|{sig_t}|{name}|{why[:24]}"
            if k not in keys: new.append(dict(base, key=k, variant=name, event="DIP SIGNAL", signal_time_et=str(sig_t), entry_time_et="", entry_px="", exit_time_et="", exit_px="", reason="", pnl_usd_hypothetical="", gate_ratio=("" if np.isnan(gi) else round(float(gi), 4)), gate_source="", event_status=es, detail=f"{why}; 7-bar drop {drop[i]*100:.2f}%; signal-bar close {close[i]:.2f}")); snap_needed = snap_needed or ("TAKEN" in why or "PENDING" in why)
        status["variants"][name] = dict(H_bars=H, closed_trades_since_start=int((~T["forced"]).sum()) if len(T) else 0, open_position=open_pos)
    if new and (snap_needed or REPLAY):
        bars_raw.to_csv(OUT / "snapshots" / f"bars_{now.strftime('%Y%m%d_%H%M')}.csv", index=False)
    append(new)
    (OUT / "shadow_status.json").write_text(json.dumps(status, indent=2, default=str))
    with open(OUT / "shadow_runs.log", "a") as f: f.write(f"{now_utc} | last complete bar {status['last_complete_bar_start_et']} | gate last {status['gate_series_last_date']} ({status['gate_last_source']}) | events verified through {status['events_verified_through']} | new rows {len(new)} | {source}\n")
    print(f"[{now_utc}] last complete bar {status['last_complete_bar_start_et']} | new log rows: {len(new)}")
    for r in new: print("   +", r["variant"], "|", r["event"], "|", r.get("detail", ""))
    for name, v in status["variants"].items(): print("  ", name, "| closed trades since start:", v["closed_trades_since_start"], "| open position:", v["open_position"])
    if status["events_verified_through"] < str(now.date()): print("   NOTE: event calendar verified only through", status["events_verified_through"], "- later entries are logged UNVERIFIED_CALENDAR until you check the Fed/BLS dates")
    return status

if __name__ == "__main__":
    ib = None
    if not REPLAY:
        from ib_insync import IB
        ib = IB(); cid = a.client_id
        for _ in range(5):
            try: ib.connect(a.host, a.port, clientId=cid, readonly=True, timeout=20); break
            except Exception as e:
                print("connect failed on clientId", cid, repr(e)[:80]); cid += 1
        assert ib.isConnected(), "could not connect (TWS/Gateway open? API enabled? port?)"
        print("connected read-only on port", a.port, "clientId", cid)
    try:
        while True:
            run_once(ib)
            if not a.loop or REPLAY: break
            time.sleep(a.poll_seconds)
    finally:
        if ib is not None: ib.disconnect()
