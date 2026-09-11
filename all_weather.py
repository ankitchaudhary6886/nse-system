"""
All-Weather Swing Mode — high-conviction setups during DEFENSIVE regime.
Authorized 2026-09-12.

When Nifty is below its EMA10, the main swing scan holds new entries.
But downturns are when quality names get cheap. This module finds a
strict subset:
  - Fundamental score >= 70 (quality)
  - Price >= 25% below 52-week high (deep discount)
  - Price within 10% of 52-week low (capitulation zone)
  - Reversal candle today: hammer OR bullish engulfing
  - Risk (entry-stop)/entry <= 5% (same rule as main system)

Entry  = today's high + tick
Stop   = min(today low, yesterday low) * 0.99
Target = 2R

Signals are stored in swing_signals with mode='ALL_WEATHER'.
Position size must be HALVED (owner rule).
"""
import sys
import datetime as dt
import numpy as np
import pandas as pd
import db

FUND_MIN = 70
BELOW_52W_MIN = 0.25       # >= 25% below 52w high
NEAR_LOW_MAX = 0.10        # within 10% of 52w low
MAX_RISK_PCT = 0.05
TARGET_R = 2.0
TICK = 0.05


def _fund_scores(conn):
    """symbol -> fundamental_score from latest scan."""
    out = {}
    try:
        rows = conn.execute(
            "SELECT symbol, fundamental_score FROM scan_results "
            "WHERE scan_date=(SELECT MAX(scan_date) FROM scan_results) "
            "AND fundamental_score IS NOT NULL").fetchall()
        for s, sc in rows:
            out[s] = sc
    except Exception:
        pass
    return out


def _candle_pattern(o, h, l, c, po, pc):
    """Return 'HAMMER' | 'BULLISH_ENGULFING' | None for latest bar."""
    body = abs(c - o)
    rng = h - l
    if rng <= 0:
        return None
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)

    # Hammer: small body, long lower wick, small upper wick
    if (body / rng < 0.35 and lower_wick / rng > 0.55
            and upper_wick / rng < 0.15):
        return "HAMMER"

    # Bullish engulfing: prev red, current green, current engulfs prev
    if pc < po and c > o and c >= po and o <= pc:
        return "BULLISH_ENGULFING"

    return None


def candidates(conn, limit=600):
    """Stocks with fund>=70 AND >=25% below 52w high AND near 52w low."""
    fund = _fund_scores(conn)
    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM universe_broad "
        "WHERE mcap_cr BETWEEN 1000 AND 8000 "
        "AND symbol NOT LIKE '%$%' AND symbol NOT LIKE '% %' "
        "ORDER BY mcap_cr DESC LIMIT ?", (limit,)).fetchall()]
    out = []
    for sym in syms:
        if fund.get(sym, 0) < FUND_MIN:
            continue
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume "
            "FROM prices_daily WHERE symbol=? "
            "ORDER BY date DESC LIMIT 260", (sym,)).fetchall()
        if len(rows) < 200:
            continue
        rows = list(reversed(rows))
        highs = [r[2] for r in rows if r[2] is not None]
        lows = [r[3] for r in rows if r[3] is not None]
        if len(highs) < 200 or len(lows) < 200:
            continue
        hi52 = max(highs[-252:])
        lo52 = min(lows[-252:])
        last = rows[-1][4]
        if hi52 <= 0 or last is None:
            continue
        below = (hi52 - last) / hi52
        if below < BELOW_52W_MIN:
            continue
        near_low = (last - lo52) / max(lo52, 1e-9)
        if near_low > NEAR_LOW_MAX:
            continue
        df = pd.DataFrame(rows,
                          columns=["date", "Open", "High", "Low",
                                   "Close", "Volume"]).set_index("date")
        out.append((sym, df, fund.get(sym)))
    return out


def detect(sym, df, fund_score=None):
    """Return dict(entry, stop, target, pattern, ...) or None."""
    if len(df) < 60:
        return None
    o = df["Open"].values
    h = df["High"].values
    l = df["Low"].values
    c = df["Close"].values

    pat = _candle_pattern(o[-1], h[-1], l[-1], c[-1], o[-2], c[-2])
    if not pat:
        return None

    entry = float(h[-1]) + TICK
    stop = min(float(l[-1]), float(l[-2])) * 0.99
    if stop >= entry:
        return None
    risk_pct = (entry - stop) / entry
    if risk_pct > MAX_RISK_PCT:
        return None
    target = entry + TARGET_R * (entry - stop)

    hi52 = float(np.max(h[-252:])) if len(h) >= 252 else float(np.max(h))
    pb_depth = (hi52 - c[-1]) / hi52 if hi52 > 0 else 0
    return {
        "symbol": sym,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "pattern": pat,
        "risk_pct": round(risk_pct, 4),
        "pb_depth": round(pb_depth, 3),
        "impulse": 0.0,
        "fund_score": fund_score,
    }


def scan(conn=None):
    """Top-level scan. Returns list of setups."""
    own = conn is None
    if own:
        conn = db.get_conn()
    setups = []
    for sym, df, fs in candidates(conn):
        s = detect(sym, df, fs)
        if s:
            s["fund_score"] = fs
            setups.append(s)
    if own:
        conn.close()
    return setups


if __name__ == "__main__":
    rows = scan()
    print(f"[AW] {len(rows)} all-weather setups")
    for s in rows:
        print(f"  {s['symbol']:<12} {s['pattern']:<18} "
              f"entry {s['entry']} stop {s['stop']} "
              f"target {s['target']} risk {s['risk_pct']*100:.1f}% "
              f"fund {s['fund_score']}")