"""
Research Cockpit — historical behaviour of setups similar to today's.

Entry points:
  analyze_symbol(sym)          — full per-symbol analysis (cached 7d)
  analyze_universe(limit)      — today's setups + their cached stats
  warm_cache()                 — compute + cache stats for today's symbols
  sector_aggregate()           — pool setups across symbols, by sector

Cache table: research_cache(symbol, computed_at, payload_json)
Payload carries CACHE_VERSION; a version mismatch invalidates the row.
"""
import sys
import time
import json
import datetime as dt
import numpy as np
import pandas as pd
import db
from setup import SetupDetector


CACHE_VERSION = 2
HISTORY_DAYS = 5 * 365
STEP = 5
MIN_BARS = 280
HOLD_BARS = 30
CACHE_TTL_DAYS = 7


# ============================================================
# Cache
# ============================================================
def _ensure_cache(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS research_cache(
        symbol TEXT PRIMARY KEY,
        computed_at TEXT,
        payload TEXT
    )
    """)


def _get_cached(conn, sym, max_age_days=CACHE_TTL_DAYS):
    try:
        row = conn.execute(
            "SELECT computed_at, payload FROM research_cache "
            "WHERE symbol=?", (sym,)).fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        d = dt.date.fromisoformat(str(row[0])[:10])
        if (dt.date.today() - d).days > max_age_days:
            return None
        payload = json.loads(row[1])
        if payload.get("cache_version") != CACHE_VERSION:
            return None
        return payload
    except Exception:
        return None


def _put_cache(conn, sym, payload):
    _ensure_cache(conn)
    payload["cache_version"] = CACHE_VERSION
    conn.execute(
        "INSERT OR REPLACE INTO research_cache VALUES (?,?,?)",
        (sym, dt.date.today().isoformat(),
         json.dumps(payload, default=str)))


def _clear_cache(conn, sym=None):
    _ensure_cache(conn)
    if sym:
        conn.execute("DELETE FROM research_cache WHERE symbol=?", (sym,))
    else:
        conn.execute("DELETE FROM research_cache")
    conn.commit()


# ============================================================
# Core simulation
# ============================================================
def _simulate_forward(df, signal_i, trigger, stop):
    n = len(df)
    h = df["High"].values
    l = df["Low"].values

    risk = trigger - stop
    if risk <= 0:
        return None

    trig_bar = None
    for j in range(signal_i + 1, min(signal_i + 4, n)):
        if h[j] >= trigger:
            trig_bar = j
            break
    if trig_bar is None:
        return {
            "triggered": False, "outcome": "EXPIRED",
            "mfe_r": 0.0, "mae_r": 0.0,
            "hit_1r": False, "hit_2r": False,
            "hit_3r": False, "hit_4r": False,
            "bars_to_1r": None, "bars_to_2r": None,
            "bars_to_3r": None, "bars_to_4r": None,
        }

    end_bar = min(trig_bar + HOLD_BARS, n)
    mfe = 0.0
    mae = 0.0
    hit_1r = hit_2r = hit_3r = hit_4r = False
    b_1r = b_2r = b_3r = b_4r = None
    outcome = "TIMEOUT"

    for k in range(trig_bar, end_bar):
        up_r = (h[k] - trigger) / risk
        dn_r = (l[k] - trigger) / risk
        if up_r > mfe:
            mfe = up_r
        if dn_r < mae:
            mae = dn_r
        bars_since = k - trig_bar
        if not hit_1r and up_r >= 1.0:
            hit_1r = True; b_1r = bars_since
        if not hit_2r and up_r >= 2.0:
            hit_2r = True; b_2r = bars_since
        if not hit_3r and up_r >= 3.0:
            hit_3r = True; b_3r = bars_since
        if not hit_4r and up_r >= 4.0:
            hit_4r = True; b_4r = bars_since
        if l[k] <= stop:
            outcome = "LOSS"
            break

    if outcome != "LOSS" and not hit_1r:
        outcome = "TIMEOUT"

    return {
        "triggered": True, "outcome": outcome,
        "mfe_r": round(float(mfe), 2), "mae_r": round(float(mae), 2),
        "hit_1r": hit_1r, "hit_2r": hit_2r,
        "hit_3r": hit_3r, "hit_4r": hit_4r,
        "bars_to_1r": b_1r, "bars_to_2r": b_2r,
        "bars_to_3r": b_3r, "bars_to_4r": b_4r,
    }


def _load_df(conn, sym, years=5):
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume "
        "FROM prices_daily WHERE symbol=? ORDER BY date",
        (sym,)).fetchall()
    if not rows or len(rows) < MIN_BARS:
        return None
    df = pd.DataFrame(list(rows),
                      columns=["date", "Open", "High", "Low",
                               "Close", "Volume"]).set_index("date")
    df.index = pd.to_datetime(df.index)
    cutoff = df.index[-1] - pd.Timedelta(days=365 * years)
    return df[df.index >= cutoff]


def _historical_setups(df):
    setups = []
    for i in range(MIN_BARS, len(df) - 1, STEP):
        slice_df = df.iloc[:i + 1]
        st = SetupDetector.detect(slice_df, "X")
        if not st.triggered:
            continue
        sim = _simulate_forward(df, i, st.entry_price, st.stop_loss)
        if sim is None:
            continue
        setups.append({
            "signal_date": str(slice_df.index[-1].date()),
            "entry": st.entry_price,
            "stop": st.stop_loss,
            "risk_pct": round((st.entry_price - st.stop_loss) /
                              st.entry_price * 100, 2),
            "pullback_pct": round(st.pullback_depth * 100, 1),
            "pullback_days": int(st.pullback_days),
            "impulse_pct": round(st.impulse_pct * 100, 1),
            "ema_zone": st.ema_proximity,
            "shape_score": int(st.shape_score),
            **sim,
        })
    return setups


def _aggregate(setups):
    if not setups:
        return {"n_setups": 0, "n_triggered": 0,
                "p_trigger": None, "p_1r_given_trigger": None,
                "p_2r_given_trigger": None, "p_3r_given_trigger": None,
                "p_4r_given_trigger": None,
                "median_bars_to_1r": None, "median_bars_to_2r": None,
                "median_bars_to_3r": None, "median_bars_to_4r": None,
                "median_mfe_r": None, "median_mae_r": None,
                "p5_mfe_r": None, "p95_mfe_r": None,
                "p5_mae_r": None, "p95_mae_r": None,
                "outcome_mix": {}}

    n = len(setups)
    triggered = [s for s in setups if s["triggered"]]
    nt = len(triggered)

    def _hitrate(level):
        if not nt:
            return None
        key = f"hit_{level}r"
        return round(sum(1 for s in triggered if s[key]) / nt, 3)

    def _median_bars(level):
        key = f"bars_to_{level}r"
        arr = [s[key] for s in triggered if s[key] is not None]
        return round(float(np.median(arr)), 1) if arr else None

    mfes = [s["mfe_r"] for s in triggered]
    maes = [s["mae_r"] for s in triggered]
    outcome_mix = {}
    for s in setups:
        outcome_mix[s["outcome"]] = outcome_mix.get(s["outcome"], 0) + 1

    def _pct(arr, q):
        return round(float(np.percentile(arr, q)), 2) if arr else None

    return {
        "n_setups": n, "n_triggered": nt,
        "p_trigger": round(nt / n, 3) if n else None,
        "p_1r_given_trigger": _hitrate(1),
        "p_2r_given_trigger": _hitrate(2),
        "p_3r_given_trigger": _hitrate(3),
        "p_4r_given_trigger": _hitrate(4),
        "median_bars_to_1r": _median_bars(1),
        "median_bars_to_2r": _median_bars(2),
        "median_bars_to_3r": _median_bars(3),
        "median_bars_to_4r": _median_bars(4),
        "median_mfe_r": _pct(mfes, 50),
        "median_mae_r": _pct(maes, 50),
        "p5_mfe_r": _pct(mfes, 5),
        "p95_mfe_r": _pct(mfes, 95),
        "p5_mae_r": _pct(maes, 5),
        "p95_mae_r": _pct(maes, 95),
        "outcome_mix": outcome_mix,
    }


def analyze_symbol(sym, use_cache=True):
    sym = sym.upper()
    conn = db.get_conn()

    if use_cache:
        cached = _get_cached(conn, sym)
        if cached is not None:
            conn.close()
            return cached

    df = _load_df(conn, sym, years=5)
    if df is None:
        conn.close()
        return {"symbol": sym, "error": "insufficient history"}

    current_setup = None
    st = SetupDetector.detect(df, sym)
    if st.triggered:
        current_setup = {
            "signal_date": st.signal_date,
            "entry": st.entry_price, "stop": st.stop_loss,
            "target_3r": round(st.entry_price +
                               3.0 * (st.entry_price - st.stop_loss), 2),
            "risk_pct": round((st.entry_price - st.stop_loss) /
                              st.entry_price * 100, 2),
            "pullback_pct": round(st.pullback_depth * 100, 1),
            "pullback_days": int(st.pullback_days),
            "impulse_pct": round(st.impulse_pct * 100, 1),
            "ema_zone": st.ema_proximity,
            "shape_score": int(st.shape_score),
        }

    latest_close = float(df["Close"].iloc[-1])
    high_52w = float(df["High"].tail(252).max())
    low_52w = float(df["Low"].tail(252).min())

    setups = _historical_setups(df)
    agg = _aggregate(setups)
    recent = sorted(setups, key=lambda s: s["signal_date"],
                    reverse=True)[:5]

    sector = None
    row = conn.execute(
        "SELECT sector FROM stocks WHERE symbol=?", (sym,)).fetchone()
    if row:
        sector = row[0]

    result = {
        "symbol": sym, "sector": sector,
        "as_of": str(df.index[-1].date()),
        "latest_close": latest_close,
        "high_52w": high_52w, "low_52w": low_52w,
        "pct_from_52w_high": round((high_52w - latest_close) /
                                    high_52w * 100, 1),
        "pct_from_52w_low": round((latest_close - low_52w) /
                                   low_52w * 100, 1),
        "current_setup": current_setup,
        "historical": agg, "recent_setups": recent,
        "raw_setups": setups,
        "history_bars_tested": len(df),
        "history_years": 5, "step": STEP,
    }

    if use_cache:
        _put_cache(conn, sym, result)
        conn.commit()

    conn.close()
    return result


# ============================================================
# Universe view
# ============================================================
def _today_symbols(conn, trend_limit=50):
    today = dt.date.today().isoformat()
    rows = conn.execute(
        "SELECT DISTINCT symbol, mode FROM swing_signals "
        "WHERE signal_date=?", (today,)).fetchall()
    symbols = {r[0]: r[1] for r in rows}
    try:
        trows = conn.execute(
            "SELECT symbol FROM trend_candidates WHERE date=? "
            "ORDER BY score DESC LIMIT ?",
            (today, trend_limit)).fetchall()
        for r in trows:
            symbols.setdefault(r[0], "TREND")
    except Exception:
        pass
    return symbols


def analyze_universe(today_only=True, max_symbols=200,
                     compute_missing=False):
    conn = db.get_conn()
    today = dt.date.today().isoformat()
    symbols = _today_symbols(conn)

    out = []
    for sym, src in list(symbols.items())[:max_symbols]:
        cached = _get_cached(conn, sym)
        if cached is None:
            if compute_missing:
                cached = analyze_symbol(sym, use_cache=True)
            else:
                cached = {"symbol": sym, "error": "not cached"}
        h = cached.get("historical", {})
        out.append({
            "symbol": sym,
            "source": src,
            "sector": cached.get("sector"),
            "latest_close": cached.get("latest_close"),
            "pct_from_52w_high": cached.get("pct_from_52w_high"),
            "pct_from_52w_low": cached.get("pct_from_52w_low"),
            "n_setups": h.get("n_setups"),
            "n_triggered": h.get("n_triggered"),
            "p_trigger": h.get("p_trigger"),
            "p_1r": h.get("p_1r_given_trigger"),
            "p_2r": h.get("p_2r_given_trigger"),
            "p_3r": h.get("p_3r_given_trigger"),
            "p_4r": h.get("p_4r_given_trigger"),
            "median_mfe_r": h.get("median_mfe_r"),
            "median_mae_r": h.get("median_mae_r"),
            "p95_mfe_r": h.get("p95_mfe_r"),
            "p5_mae_r": h.get("p5_mae_r"),
            "current_setup": cached.get("current_setup"),
        })

    conn.close()
    return {"date": today, "n_setups": len(out), "rows": out}


# ============================================================
# Sector aggregation
# ============================================================
def sector_aggregate(max_symbols=200):
    """
    Roll up the day's universe by sector. Pools raw setups from every
    cached symbol in the sector, then recomputes stats on the pool.
    """
    conn = db.get_conn()
    today = dt.date.today().isoformat()
    symbols = _today_symbols(conn)

    buckets = {}
    missing = []
    for sym in list(symbols.keys())[:max_symbols]:
        cached = _get_cached(conn, sym)
        if cached is None or "error" in cached:
            missing.append(sym)
            continue
        sector = cached.get("sector") or "Unknown"
        buckets.setdefault(sector, []).append(cached)
    conn.close()

    out = []
    for sector, cached_list in buckets.items():
        pooled_setups = []
        for c in cached_list:
            pooled_setups.extend(c.get("raw_setups", []))
        agg = _aggregate(pooled_setups)
        out.append({
            "sector": sector,
            "n_symbols": len(cached_list),
            "symbols": [c.get("symbol") for c in cached_list],
            **agg,
        })

    out.sort(key=lambda r: -(r["n_setups"] or 0))

    return {
        "date": today,
        "n_sectors": len(out),
        "n_symbols_cached": sum(len(v) for v in buckets.values()),
        "n_symbols_missing": len(missing),
        "missing": missing[:30],
        "sectors": out,
    }


# ============================================================
# Warm cache for today's symbols
# ============================================================
def warm_cache(max_symbols=200, force=False):
    conn = db.get_conn()
    _ensure_cache(conn)
    symbols = _today_symbols(conn, trend_limit=50)

    todo = []
    for sym in list(symbols.keys())[:max_symbols]:
        if not force and _get_cached(conn, sym) is not None:
            continue
        todo.append(sym)

    conn.close()

    if not todo:
        print(f"[WARM] all {len(symbols)} symbols already cached")
        return 0

    print(f"[WARM] computing {len(todo)} of {len(symbols)} symbols "
          f"(force={force})")
    t0 = time.time()
    done = 0
    failed = 0
    for i, sym in enumerate(todo, 1):
        try:
            # When force=True, bypass cache entirely so we recompute + store
            r = analyze_symbol(sym, use_cache=not force)
            if "error" in r:
                failed += 1
                print(f"  [{i}/{len(todo)}] {sym}: {r['error']}")
            else:
                done += 1
                if i % 5 == 0 or i == len(todo):
                    elapsed = time.time() - t0
                    rate = i / elapsed if elapsed else 0
                    eta = (len(todo) - i) / rate if rate else 0
                    print(f"  [{i}/{len(todo)}] {sym} ok "
                          f"({elapsed:.0f}s, ETA {eta:.0f}s)")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(todo)}] {sym}: exception {e}")

    print(f"[WARM] done: {done} computed, {failed} failed, "
          f"{time.time() - t0:.0f}s total")
    return done


def clear_cache(sym=None):
    conn = db.get_conn()
    _clear_cache(conn, sym)
    conn.close()


# ============================================================
# CLI output
# ============================================================
def _print_symbol(result):
    print("=" * 70)
    print(f"RESEARCH COCKPIT — {result['symbol']}")
    print("=" * 70)
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return
    print(f"  Sector: {result['sector']}")
    print(f"  As of: {result['as_of']}  close: {result['latest_close']}")
    print(f"  {result['pct_from_52w_high']}% from 52w high  |  "
          f"{result['pct_from_52w_low']}% from 52w low")
    print()
    if result["current_setup"]:
        cs = result["current_setup"]
        print("  CURRENT SETUP:")
        print(f"    signal {cs['signal_date']}  entry {cs['entry']}  "
              f"stop {cs['stop']}  target3R {cs['target_3r']}")
    else:
        print("  CURRENT SETUP: none triggered today")
    print()
    h = result["historical"]
    print(f"  HISTORICAL ({h['n_setups']} setups over 5y):")
    print(f"    triggered: {h['n_triggered']} (P={h['p_trigger']})")
    print(f"    P(+1R): {h['p_1r_given_trigger']}  "
          f"P(+2R): {h['p_2r_given_trigger']}  "
          f"P(+3R): {h['p_3r_given_trigger']}  "
          f"P(+4R): {h['p_4r_given_trigger']}")
    print(f"    MFE R: p5={h['p5_mfe_r']}  p50={h['median_mfe_r']}  "
          f"p95={h['p95_mfe_r']}")
    print(f"    MAE R: p5={h['p5_mae_r']}  p50={h['median_mae_r']}  "
          f"p95={h['p95_mae_r']}")
    print(f"    outcomes: {h['outcome_mix']}")


def _print_universe(out):
    print("=" * 100)
    print(f"RESEARCH UNIVERSE — {out['date']}  ({out['n_setups']} setups)")
    print("=" * 100)
    print(f"{'SYM':<12} {'SRC':<12} {'n':<4} {'trig':<5} "
          f"{'P1R':<6} {'P2R':<6} {'P3R':<6} "
          f"{'MFE':<6} {'MAE':<6} {'52wHi%':<7}")
    for r in out["rows"]:
        def _f(v, dp=2):
            if v is None:
                return "—"
            return f"{v:.{dp}f}"
        def _p(v):
            if v is None:
                return "—"
            return f"{v*100:.0f}%"
        print(f"{r['symbol']:<12} {r['source']:<12} "
              f"{(r['n_setups'] or 0):<4} "
              f"{(r['n_triggered'] or 0):<5} "
              f"{_p(r['p_1r']):<6} {_p(r['p_2r']):<6} {_p(r['p_3r']):<6} "
              f"{_f(r['median_mfe_r']):<6} {_f(r['median_mae_r']):<6} "
              f"{_f(r['pct_from_52w_high'], 1):<7}")


def _print_sector(out):
    print("=" * 100)
    print(f"RESEARCH SECTORS — {out['date']}")
    print(f"  {out['n_sectors']} sectors · {out['n_symbols_cached']} "
          f"symbols cached · {out['n_symbols_missing']} missing")
    print("=" * 100)
    print(f"{'SECTOR':<22} {'syms':<5} {'n':<5} {'trig':<5} "
          f"{'P1R':<6} {'P2R':<6} {'P3R':<6} "
          f"{'MFE':<6} {'MAE':<6}")
    for r in out["sectors"]:
        def _f(v, dp=2):
            if v is None:
                return "—"
            return f"{v:.{dp}f}"
        def _p(v):
            if v is None:
                return "—"
            return f"{v*100:.0f}%"
        print(f"{(r['sector'] or 'Unknown'):<22} "
              f"{r['n_symbols']:<5} "
              f"{(r['n_setups'] or 0):<5} "
              f"{(r['n_triggered'] or 0):<5} "
              f"{_p(r['p_1r_given_trigger']):<6} "
              f"{_p(r['p_2r_given_trigger']):<6} "
              f"{_p(r['p_3r_given_trigger']):<6} "
              f"{_f(r['median_mfe_r']):<6} "
              f"{_f(r['median_mae_r']):<6}")


if __name__ == "__main__":
    argv = sys.argv[1:]

    if "--clear-cache" in argv:
        clear_cache()
        print("cache cleared")
        sys.exit(0)

    if "--warm" in argv:
        force = "--force" in argv
        limit = 200
        for a in argv:
            if a.startswith("--limit="):
                try:
                    limit = int(a.split("=", 1)[1])
                except Exception:
                    pass
        warm_cache(max_symbols=limit, force=force)
        sys.exit(0)

    if "--sector" in argv or "-s" in argv:
        want_json = "--json" in argv
        out = sector_aggregate()
        if want_json:
            print(json.dumps(out, indent=2, default=str))
        else:
            _print_sector(out)
        sys.exit(0)

    if "--universe" in argv or "-u" in argv:
        want_json = "--json" in argv
        want_compute = "--compute-missing" in argv
        out = analyze_universe(compute_missing=want_compute)
        if want_json:
            print(json.dumps(out, indent=2, default=str))
        else:
            _print_universe(out)
        sys.exit(0)

    want_json = "--json" in argv
    want_refresh = "--refresh" in argv
    positional = [a for a in argv
                  if not a.startswith("--") and not a.startswith("-")]
    sym = positional[0] if positional else "RELIANCE"

    result = analyze_symbol(sym, use_cache=not want_refresh)
    if want_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_symbol(result)