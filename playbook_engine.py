"""Playbook engine — scan, tag, search, and walk-forward backtest.

This is the C10/C11 bridge between ``playbook.py`` (pure rules) and the
terminal. It owns every database read/write and the two long-running jobs:

  scan      — evaluate every live rule on the current universe, persist one
              row per (as_of, symbol, strategy). Those rows ARE the strategy
              tags the search engine reads.
  backtest  — walk the same rules forward bar by bar, enter at the next open,
              simulate stop/target/time exit, subtract round-trip costs, and
              persist win rate / expectancy / profit factor per strategy.

HONESTY RULES
-------------
* Entry is the NEXT bar's open, never the signal bar's close. A signal is
  computed after the close, so a same-bar fill is look-ahead.
* If the next open gaps more than 5% past the trigger, the trade is skipped.
* If a bar touches both stop and target, the stop is assumed first.
* Costs are 30 bps round trip (STT + exchange + GST + stamp + slippage).
* Shape rules are evaluated every ``step`` bars in the backtest to stay
  inside the free Oracle VM's CPU budget. That is disclosed in the payload.
"""

from __future__ import annotations

import datetime as dt
import json
import threading

import numpy as np

import db
import playbook


COST_BPS = 30.0
CHASE_LIMIT = 0.05
DEFAULT_SCAN_LIMIT = 900
DEFAULT_BACKTEST_LIMIT = 150
DEFAULT_BACKTEST_YEARS = 3
DEFAULT_STEP = 1


# ============================================================
# Job state (one scan + one backtest at a time)
# ============================================================
_LOCK = threading.Lock()

_SCAN = {
    "running": False, "status": "idle", "message": "No scan yet.",
    "as_of": None, "scanned": 0, "total": 0, "signals": 0,
    "started_at": None, "finished_at": None,
}

_BT = {
    "running": False, "status": "idle", "message": "No backtest yet.",
    "strategy": None, "done": 0, "total": 0,
    "run_at": None, "started_at": None, "finished_at": None,
}


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def scan_status():
    with _LOCK:
        return dict(_SCAN)


def backtest_status():
    with _LOCK:
        return dict(_BT)


def _set_scan(**kw):
    with _LOCK:
        _SCAN.update(kw)


def _set_bt(**kw):
    with _LOCK:
        _BT.update(kw)


def start_scan(limit=DEFAULT_SCAN_LIMIT, symbols=None):
    """Queue a whole-universe scan. One at a time, same as the backtest."""
    with _LOCK:
        if _SCAN["running"]:
            return {"started": False, "already_running": True}
        _SCAN.update(running=True, status="running", message="Queued.",
                     as_of=None, scanned=0, total=0, signals=0,
                     started_at=_now(), finished_at=None)
    t = threading.Thread(target=scan, kwargs={"limit": limit,
                                              "symbols": symbols},
                         daemon=True, name="playbook-scan")
    t.start()
    return {"started": True}


# ============================================================
# Loading
# ============================================================
def _safe_float(x, default=0.0):
    try:
        v = float(x)
        if not np.isfinite(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def load_arrays(conn, symbol, limit=None):
    """Return one symbol's bars + indicators, or None if history is short."""
    sql = ("SELECT date, open, high, low, close, volume FROM prices_daily "
           "WHERE symbol=? ORDER BY date")
    params = [symbol]
    if limit:
        sql += " DESC LIMIT ?"
        params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    if limit:
        rows = list(reversed(rows))
    if len(rows) < playbook.DEFAULT_MIN_BARS:
        return None
    dates = [str(r[0])[:10] for r in rows]
    o = np.array([_safe_float(r[1]) for r in rows], dtype=float)
    h = np.array([_safe_float(r[2]) for r in rows], dtype=float)
    l = np.array([_safe_float(r[3]) for r in rows], dtype=float)
    c = np.array([_safe_float(r[4]) for r in rows], dtype=float)
    v = np.array([_safe_float(r[5]) for r in rows], dtype=float)
    # The stored series is raw bhavdata, so a split shows up as a cliff. The
    # corporate_actions table has the ex-date and the yfinance split factor
    # (2.0 = 2-for-1). Back-adjust every bar strictly before the ex-date so the
    # whole window is on today's share basis; volume is scaled the other way.
    splits = conn.execute(
        "SELECT ex_date, ratio FROM corporate_actions "
        "WHERE symbol=? AND kind='split' AND ratio>1 ORDER BY ex_date",
        (symbol,)).fetchall()
    if splits:
        factor = np.ones(len(dates), dtype=float)
        for ex_date, ratio in splits:
            ex = str(ex_date)[:10]
            factor[np.array([d < ex for d in dates])] *= float(ratio)
        o, h, l, c = o / factor, h / factor, l / factor, c / factor
        v = v * factor
    if c[-1] < playbook.DEFAULT_MIN_PRICE:
        return None
    # A >45% single-session move is a split/bonus seam, not a trade. The repo
    # already tracks price_basis for exactly this reason; until the series is
    # rebuilt on one basis, the only honest action is to exclude the symbol.
    if len(c) > 2:
        base = np.where(c[:-1] > 0, c[:-1], np.nan)
        step = np.abs(np.diff(c) / base)
        if np.nanmax(step) > 0.45:
            return None
    ind = playbook.build_indicators(o, h, l, c, v)
    return {"symbol": symbol, "date": dates, "o": o, "h": h, "l": l,
            "c": c, "v": v, "ind": ind, "n": len(c)}


def _universe(conn, limit):
    from universe_helper import band_universe
    try:
        return list(band_universe(conn, limit=int(limit or 1000)))
    except Exception:
        rows = conn.execute(
            "SELECT DISTINCT symbol FROM prices_daily "
            "WHERE symbol NOT LIKE '^%' ORDER BY symbol LIMIT ?",
            (int(limit or 1000),)).fetchall()
        return [r[0] for r in rows]


def _pct_rank(values: dict) -> dict:
    """Percentile rank in [0, 1], where 0 is the lowest value and 1 the highest.

    Callers must read the direction: top-decile momentum is rank >= 0.90;
    bottom-half volatility is vol_rank <= 0.50.
    """
    if not values:
        return {}
    keys = list(values)
    arr = np.array([values[k] for k in keys], dtype=float)
    order = arr.argsort()
    ranks = np.empty(len(arr), dtype=float)
    ranks[order] = np.arange(len(arr))
    denom = max(1, len(arr) - 1)
    return {k: float(ranks[j] / denom) for j, k in enumerate(keys)}


def _momentum(bars):
    c = bars["c"]
    if len(c) < 253:
        return None
    prior = c[-22]
    base = c[-253]
    if prior <= 0 or base <= 0:
        return None
    return float(prior / base - 1.0)


def _volatility(bars, window=60):
    c = bars["c"]
    if len(c) < window + 1:
        return None
    base = c[-(window + 1):-1]
    diff = np.diff(c[-(window + 1):])
    ret = np.divide(diff, base, out=np.zeros_like(diff, dtype=float),
                    where=base > 0)
    if not np.all(np.isfinite(ret)):
        return None
    return float(np.std(ret))


# ============================================================
# Scan
# ============================================================
def scan(conn=None, limit=800, symbols=None, as_of=None):
    """Evaluate every live rule and persist the tag rows.

    Returns a summary dict. Safe to call twice: the second call replaces the
    same ``as_of`` rows rather than duplicating them.
    """
    own = conn is None
    if own:
        conn = db.get_conn()
    try:
        syms = (list(symbols) if isinstance(symbols, (list, tuple, set))
                else [symbols]) if symbols else _universe(conn, limit)
        _set_scan(running=True, status="running", total=len(syms),
                  scanned=0, signals=0, as_of=as_of,
                  message=f"Loading {len(syms)} companies.", started_at=_now(),
                  finished_at=None)

        loaded = {}
        for n, sym in enumerate(syms, 1):
            try:
                bars = load_arrays(conn, sym)
            except Exception:
                bars = None
            if bars:
                loaded[sym] = bars
            if n % 50 == 0:
                _set_scan(scanned=n,
                          message=f"Loaded {n}/{len(syms)} companies.")

        # A tag may only be stamped with a date the stock actually traded on.
        # Without this, a symbol 40 days stale would inherit today's as_of and
        # look like a fresh signal on the search screen.
        if not loaded:
            _set_scan(running=False, status="empty", scanned=0, signals=0,
                      as_of=as_of, finished_at=_now(),
                      message="No company had enough clean history.")
            return {"as_of": as_of, "scanned": 0, "signals": 0,
                    "by_strategy": {}}
        latest = max(b["date"][-1] for b in loaded.values())
        stale = [s for s, b in loaded.items() if b["date"][-1] != latest]
        for s in stale:
            loaded.pop(s, None)
        day = latest

        # Cross-sectional ranks: only names with a full 12-month window.
        moms, vols = {}, {}
        for sym, bars in loaded.items():
            m = _momentum(bars)
            if m is not None:
                moms[sym] = m
            vv = _volatility(bars)
            if vv is not None:
                vols[sym] = vv
        mom_rank = _pct_rank(moms)
        vol_rank = _pct_rank(vols)

        rows, n_sig = [], 0
        for sym, bars in loaded.items():
            i = bars["n"] - 1
            ctx = {
                "sym": sym, "date": bars["date"], "o": bars["o"],
                "h": bars["h"], "l": bars["l"], "c": bars["c"],
                "v": bars["v"], "ind": bars["ind"], "i": i,
                "rs_pct": mom_rank.get(sym),
                "mom_12_1": moms.get(sym),
                "mom_rank": mom_rank.get(sym),
                "vol_rank": vol_rank.get(sym),
            }
            signals = playbook.detect_all(ctx)
            signals.extend(playbook.detect_warnings(ctx))
            for s in signals:
                rows.append(_row_from_signal(s, day))
                n_sig += 1

        if not rows:
            _set_scan(running=False, status="empty", scanned=len(loaded),
                      signals=0, as_of=day, finished_at=_now(),
                      message="No strategy matched on the latest bar.")
            return {"as_of": day, "scanned": len(loaded), "signals": 0,
                    "by_strategy": {},
                    "skipped": len(syms) - len(loaded)}

        persist(conn, day, rows)
        by = {}
        for r in rows:
            by[r["strategy"]] = by.get(r["strategy"], 0) + 1
        _set_scan(running=False, status="complete", scanned=len(loaded),
                  signals=len(rows), as_of=day, finished_at=_now(),
                  message=f"{len(rows)} tags across {len(by)} strategies "
                          f"on {day}.")
        return {"as_of": day, "scanned": len(loaded),
                "signals": len(rows), "by_strategy": by,
                "skipped": len(syms) - len(loaded)}
    except Exception as exc:
        _set_scan(running=False, status="error", message=str(exc),
                  finished_at=_now())
        raise
    finally:
        if own:
            conn.close()


def _row_from_signal(sig, as_of):
    return {
        "as_of": as_of,
        "symbol": sig["symbol"],
        "strategy": sig["method"],
        "direction": sig["direction"],
        "status": sig.get("signal_type", "BREAKOUT"),
        "confidence": sig.get("confidence"),
        "entry": sig.get("entry"),
        "stop": sig.get("stop"),
        "target": sig.get("target"),
        "rr": sig.get("rr"),
        "risk_pct": sig.get("risk_pct"),
        "hold": sig.get("hold"),
        "tags": json.dumps(sig.get("tags") or []),
        "notes": sig.get("notes"),
        "params": json.dumps((sig.get("raw") or {}).get("params") or {}),
        "indicators": json.dumps(
            (sig.get("raw") or {}).get("indicators") or {}),
        "exits": json.dumps((sig.get("raw") or {}).get("exits") or {}),
        "overlaps": json.dumps((sig.get("raw") or {}).get("overlaps_with") or []),
        "created_at": _now(),
    }


_INSERT_COLS = ("as_of", "symbol", "strategy", "direction", "status",
                "confidence", "entry", "stop", "target", "rr", "risk_pct",
                "hold", "tags", "notes", "params", "indicators", "exits",
                "overlaps", "created_at")


def persist(conn, as_of, rows):
    """Replace this as_of's rows. Never DROP; delete only the same snapshot."""
    conn.execute("DELETE FROM strategy_signals WHERE as_of=?", (as_of,))
    placeholders = ",".join("?" for _ in _INSERT_COLS)
    conn.executemany(
        f"INSERT OR REPLACE INTO strategy_signals({','.join(_INSERT_COLS)}) "
        f"VALUES({placeholders})",
        [tuple(r.get(c) for c in _INSERT_COLS) for r in rows])
    conn.commit()


# ============================================================
# Read APIs
# ============================================================
def latest_as_of(conn):
    try:
        return conn.execute(
            "SELECT MAX(as_of) FROM strategy_signals").fetchone()[0]
    except Exception:
        return None


def signals(conn, strategy=None, symbol=None, as_of=None, direction=None,
            limit=500):
    as_of = as_of or latest_as_of(conn)
    if not as_of:
        return []
    where = ["as_of=?"]
    args = [as_of]
    if strategy:
        where.append("strategy=?")
        args.append(strategy)
    if symbol:
        where.append("symbol=?")
        args.append(symbol.upper())
    if direction:
        where.append("direction=?")
        args.append(direction)
    sql = ("SELECT as_of, symbol, strategy, direction, status, confidence, "
           "entry, stop, target, rr, risk_pct, hold, tags, notes, params, "
           "indicators, exits, overlaps FROM strategy_signals WHERE "
           + " AND ".join(where)
           + " ORDER BY (rr IS NULL), rr DESC, symbol LIMIT ?")
    args.append(int(limit))
    out = []
    for r in conn.execute(sql, args):
        out.append({
            "as_of": r[0], "symbol": r[1], "strategy": r[2],
            "direction": r[3], "status": r[4], "confidence": r[5],
            "entry": r[6], "stop": r[7], "target": r[8], "rr": r[9],
            "risk_pct": r[10], "hold": r[11],
            "tags": _json(r[12], []), "notes": r[13],
            "params": _json(r[14], {}), "indicators": _json(r[15], {}),
            "exits": _json(r[16], {}),
            "overlaps": _json(r[17], []),
        })
    return out


def _json(raw, default):
    try:
        return json.loads(raw) if raw else default
    except (TypeError, ValueError):
        return default


def symbol_tags(conn, symbol):
    as_of = latest_as_of(conn)
    if not as_of:
        return {"symbol": symbol.upper(), "as_of": None, "tags": []}
    rows = signals(conn, symbol=symbol, as_of=as_of, limit=100)
    return {"symbol": symbol.upper(), "as_of": as_of, "tags": rows,
            "count": len(rows),
            "strategies": sorted({r["strategy"] for r in rows})}


def _latest_backtests(conn):
    """Latest backtest row per strategy."""
    out = {}
    try:
        rows = conn.execute(
            "SELECT b.* FROM strategy_backtests b JOIN ("
            "  SELECT strategy, MAX(run_at) AS run_at FROM strategy_backtests"
            "  GROUP BY strategy) x "
            "ON b.strategy=x.strategy AND b.run_at=x.run_at").fetchall()
        cols = [d[0] for d in conn.execute(
            "SELECT * FROM strategy_backtests LIMIT 0").description]
    except Exception:
        return out
    for r in rows:
        d = dict(zip(cols, r))
        out[d["strategy"]] = d
    return out


def is_backtestable(sid: str) -> bool:
    """A rule is walk-forward testable only if it is symbol-local and live."""
    meta = playbook.STRATEGY_BY_ID.get(sid, {})
    return bool(meta.get("backtestable", meta.get("status") == "live"))


def strategies_with_stats(conn):
    as_of = latest_as_of(conn)
    counts = {}
    if as_of:
        for r in conn.execute(
                "SELECT strategy, "
                "SUM(CASE WHEN direction='LONG_ENTRY' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN direction='TOP_WARNING' THEN 1 ELSE 0 END) "
                "FROM strategy_signals WHERE as_of=? GROUP BY strategy",
                (as_of,)):
            entries = r[1] or 0
            warns = r[2] or 0
            counts[r[0]] = {"matches": entries, "warnings": warns,
                           "total": entries + warns}
    stats = _latest_backtests(conn)
    out = []
    for meta in playbook.STRATEGIES:
        sid = meta["id"]
        item = dict(meta)
        item["matches"] = counts.get(sid, {}).get("matches", 0)
        item["warnings"] = counts.get(sid, {}).get("warnings", 0)
        item["total_tags"] = counts.get(sid, {}).get("total", 0)
        item["exit_text"] = playbook._EXIT_TEXT.get(sid, {})
        item["backtestable"] = is_backtestable(sid)
        # A scan-only rule may still have a stale row from an older engine
        # version. Never show it as if it had been walk-forward tested.
        bt = stats.get(sid) if item["backtestable"] else None
        item["backtest"] = ({
            "run_at": bt.get("run_at"), "signals": bt.get("signals"),
            "wins": bt.get("wins"), "losses": bt.get("losses"),
            "win_rate": bt.get("win_rate"),
            "avg_win_r": bt.get("avg_win_r"),
            "avg_loss_r": bt.get("avg_loss_r"),
            "expectancy_r": bt.get("expectancy_r"),
            "profit_factor": bt.get("profit_factor"),
            "max_dd_r": bt.get("max_dd_r"), "years": bt.get("years"),
            "universe_n": bt.get("universe_n"),
            "median_hold": bt.get("median_hold"),
            "best_r": bt.get("best_r"), "worst_r": bt.get("worst_r"),
            "step_bars": bt.get("step_bars"), "cost_bps": bt.get("cost_bps"),
        } if bt else None)
        out.append(item)
    return {"as_of": as_of, "strategies": out,
            "scan": scan_status(), "backtest": backtest_status()}


# ============================================================
# Backtest
# ============================================================
def start_backtest(limit=DEFAULT_BACKTEST_LIMIT,
                   years=DEFAULT_BACKTEST_YEARS,
                   strategies=None, step=DEFAULT_STEP):
    with _LOCK:
        if _BT["running"]:
            return {"started": False, "already_running": True}
        _BT.update(running=True, status="running", message="Queued.",
                   strategy=None, done=0, total=0, run_at=None,
                   started_at=_now(), finished_at=None)
    t = threading.Thread(target=_run_backtest,
                         args=(limit, years, strategies, step),
                         daemon=True, name="playbook-backtest")
    t.start()
    return {"started": True}


def _candidates(bars, sid, step):
    """Indices worth evaluating. Cheap pre-filter, then the real rule."""
    n = bars["n"]
    c, h = bars["c"], bars["h"]
    last = n - 2
    if last < 260:
        return []
    if sid == "donchian_20":
        hh = bars["ind"]["hh20"]
        idx = np.where(c[:last + 1] > hh[:last + 1])[0]
        return [int(i) for i in idx if i >= 21]
    if sid == "high_52w":
        hh = bars["ind"]["hh252"]
        idx = np.where(c[:last + 1] > hh[:last + 1])[0]
        return [int(i) for i in idx if i >= 253]
    if sid == "ma_50_200":
        s50, s200 = bars["ind"]["sma50"], bars["ind"]["sma200"]
        out = []
        for i in range(202, last + 1):
            if (np.isfinite(s50[i]) and np.isfinite(s200[i])
                    and s50[i - 1] <= s200[i - 1] and s50[i] > s200[i]):
                # The rule confirms up to 20 bars AFTER the cross, so those
                # bars must be candidates too — the cross bar itself can never
                # pass the 1% buffer.
                out.extend(range(i, min(i + 21, last + 1)))
        return sorted(set(out))
    # Shape rules are sampled every `step` bars (default 1 = every bar).
    out = []
    for i in range(260, last + 1, max(1, int(step))):
        lo = max(0, i - 60)
        if c[i] >= 0.97 * float(np.max(h[lo:i + 1])):
            out.append(i)
    return out


def _run_backtest(limit, years, strategies, step):
    conn = None
    try:
        conn = db.get_conn()
        syms = _universe(conn, limit)
        ids = [s for s in (strategies or playbook.LIVE_IDS)
               if s in playbook.DETECTORS and is_backtestable(s)]
        if not ids:
            raise RuntimeError("no backtestable strategies selected")
        _set_bt(message=f"Loading {len(syms)} companies.", total=len(syms))
        loaded = []
        for n, sym in enumerate(syms, 1):
            try:
                bars = load_arrays(conn, sym)
            except Exception:
                bars = None
            if bars:
                bars["_start"] = max(260, bars["n"] - int(years * 252))
                loaded.append(bars)
            if n % 25 == 0:
                _set_bt(done=n, message=f"Loaded {n}/{len(syms)}.")
        trades = {sid: [] for sid in ids}
        total_work = max(1, len(loaded) * len(ids))
        done = 0
        for bars in loaded:
            for sid in ids:
                fn = playbook.DETECTORS[sid]
                # One open trade per symbol per strategy. Without this, every
                # new 20-day high while a position is open counts again and
                # the sample becomes pseudo-replicated.
                blocked_until = -1
                for i in _candidates(bars, sid, step):
                    if i < bars["_start"] or i < blocked_until:
                        continue
                    ctx = {"sym": bars["symbol"], "date": bars["date"],
                           "o": bars["o"], "h": bars["h"], "l": bars["l"],
                           "c": bars["c"], "v": bars["v"],
                           "ind": bars["ind"], "i": i}
                    try:
                        sig = fn(ctx)
                    except Exception:
                        sig = None
                    if not sig or sig.get("direction") != "LONG_ENTRY":
                        continue
                    trade = _simulate(bars, i, sig)
                    if trade:
                        trades[sid].append(trade)
                        blocked_until = i + trade["hold"] + 1
                done += 1
                _set_bt(done=done, total=total_work, strategy=sid,
                        message=f"{sid}: {len(trades[sid])} trades.")
        run_at = _now()
        rows = []
        for sid, tr in trades.items():
            rows.append(_stats_row(run_at, sid, tr, years,
                                   len(loaded), step))
        conn.execute("DELETE FROM strategy_backtests WHERE run_at=?", (run_at,))
        for r in rows:
            cols = list(r)
            conn.execute(
                f"INSERT OR REPLACE INTO strategy_backtests"
                f"({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",
                tuple(r[c] for c in cols))
        conn.commit()
        _set_bt(running=False, status="complete", finished_at=_now(),
                run_at=run_at,
                message=f"Backtested {len(rows)} strategies on "
                        f"{len(loaded)} companies "
                        f"({len(syms) - len(loaded)} skipped for short "
                        f"history or an unadjusted split seam).")
    except Exception as exc:
        _set_bt(running=False, status="error", message=str(exc),
                finished_at=_now())
    finally:
        if conn is not None:
            conn.close()


def _simulate(bars, i, sig):
    """Next-open entry, conservative stop-first simulation."""
    n = bars["n"]
    j = i + 1
    if j >= n:
        return None
    entry = float(bars["o"][j])
    stop = float(sig["stop"])
    target = float(sig["target"])
    if entry <= 0 or stop >= entry:
        return None
    if entry > float(sig["entry"]) * (1 + CHASE_LIMIT):
        return None
    if entry <= stop:
        return None
    mode = (sig.get("raw") or {}).get("exit_mode")
    # Entering on a gap already through the research target is not a trade:
    # the same open would book an instant, untradeable profit.
    if mode is None and entry >= target:
        return None
    risk = entry - stop
    hold = int(sig.get("hold") or 40)
    last = min(n - 1, j + hold - 1)
    exit_px = float(bars["c"][last])
    exit_j = last
    ind = bars.get("ind") or {}
    for k in range(j, last + 1):
        # A gap through either level fills at the open, not at the level.
        if float(bars["o"][k]) <= stop:
            exit_px, exit_j = float(bars["o"][k]), k
            break
        if mode is None and float(bars["o"][k]) >= target:
            exit_px, exit_j = float(bars["o"][k]), k
            break
        if float(bars["l"][k]) <= stop:
            exit_px, exit_j = stop, k
            break
        if mode is None and float(bars["h"][k]) >= target:
            exit_px, exit_j = target, k
            break
        if mode == "ll10":
            lo = max(0, k - 10)
            channel = float(np.min(bars["l"][lo:k]))
            if k > lo and float(bars["c"][k]) < channel:
                exit_px, exit_j = float(bars["c"][k]), k
                break
        elif mode == "reverse_cross":
            s50 = ind.get("sma50", [None])[k]
            s200 = ind.get("sma200", [None])[k]
            if (s50 is not None and s200 is not None
                    and np.isfinite(s50) and np.isfinite(s200)
                    and s50 < s200):
                exit_px, exit_j = float(bars["c"][k]), k
                break
    r = (exit_px - entry) / risk - (COST_BPS / 10000.0) * entry / risk
    return {"r": float(r), "hold": int(exit_j - j + 1),
            "entry": entry, "exit": exit_px,
            "entry_date": bars["date"][j], "exit_date": bars["date"][exit_j]}


def _stats_row(run_at, sid, trades, years, universe_n, step):
    meta = playbook.STRATEGY_BY_ID.get(sid, {})
    n = len(trades)
    rs = [t["r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    win_rate = (len(wins) / n) if n else None
    avg_win = float(np.mean(wins)) if wins else None
    avg_loss = float(np.mean(losses)) if losses else None
    expectancy = float(np.mean(rs)) if rs else None
    gross_win = float(sum(wins)) if wins else 0.0
    gross_loss = abs(float(sum(losses))) if losses else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else None
    # Max drawdown in R on the closed-trade equity curve, ordered by exit
    # date (realization order). Trades from different symbols overlap, so this
    # is still a closed-trade approximation, not a portfolio margin curve.
    peak = dd = 0.0
    eq = 0.0
    ordered = sorted(trades, key=lambda t: (t.get("exit_date") or "",
                                            t.get("entry_date") or ""))
    for t in ordered:
        eq += t["r"]
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    holds = [t["hold"] for t in trades]
    return {
        "run_at": run_at, "strategy": sid,
        "years": float(years), "universe_n": int(universe_n),
        "signals": n, "wins": len(wins), "losses": len(losses),
        "win_rate": round(win_rate, 4) if win_rate is not None else None,
        "avg_win_r": round(avg_win, 3) if avg_win is not None else None,
        "avg_loss_r": round(avg_loss, 3) if avg_loss is not None else None,
        "expectancy_r": round(expectancy, 3) if expectancy is not None else None,
        "profit_factor": round(pf, 3) if pf is not None else None,
        "max_dd_r": round(dd, 3),
        "median_hold": int(np.median(holds)) if holds else None,
        "best_r": round(max(rs), 3) if rs else None,
        "worst_r": round(min(rs), 3) if rs else None,
        "cost_bps": COST_BPS,
        "step_bars": int(step),
        "params": json.dumps(meta.get("params") or {}),
        "created_at": _now(),
    }


def backtests(conn, strategy=None, limit=50):
    sql = "SELECT * FROM strategy_backtests"
    args = []
    if strategy:
        sql += " WHERE strategy=?"
        args.append(strategy)
    sql += " ORDER BY run_at DESC, strategy LIMIT ?"
    args.append(int(limit))
    cur = conn.execute(sql, args)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]
