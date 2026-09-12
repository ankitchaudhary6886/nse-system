"""
Trend-Regime Scanner — stocks above BOTH EMA50 and EMA200.
Authorized 2026-09-12 (BACKLOG ID8).

Purpose:
- Stock-level complement to the market-level regime spectrum
- Cut noise for downstream scanners (only consider confirmed trends)
- Serve as a pre-filter for swing / positional / value layers

Definition of "trend confirmed":
  current close > EMA50  AND  current close > EMA200

Strength score (0-100) rewards:
  - EMA50 > EMA200 (golden-cross structure)   +30
  - EMA50 > EMA50(t-20)  (medium trend rising) +20
  - EMA200 > EMA200(t-20) (long trend rising)  +20
  - Distance above EMA200 (mildly extended)    +15
  - Fresh break (crossed within 20 bars)       +15

Stored in trend_candidates. Runs daily after daily_update.
Telegram alert only if the count swings by >20% vs prior day.
"""
import sys
import datetime as dt
import db
from log_utils import get_logger
from universe_helper import combined_universe

log = get_logger("trend")

MIN_HISTORY = 220
EMA50_SPAN = 50
EMA200_SPAN = 200


def _ensure(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS trend_candidates(
        date TEXT, symbol TEXT, close REAL,
        ema50 REAL, ema200 REAL,
        above_50 INTEGER, above_200 INTEGER,
        score REAL, notes TEXT,
        PRIMARY KEY(date, symbol)
    )
    """)


def _ema(values, span):
    if not values:
        return None
    k = 2.0 / (span + 1.0)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def _score(close, e50, e200, e50_prev, e200_prev,
           crossed_50_recent, crossed_200_recent):
    score = 0
    notes = []
    if e50 is not None and e200 is not None and e50 > e200:
        score += 30
        notes.append("EMA50>EMA200")
    if e50 is not None and e50_prev is not None and e50 > e50_prev:
        score += 20
        notes.append("EMA50 rising")
    if e200 is not None and e200_prev is not None and e200 > e200_prev:
        score += 20
        notes.append("EMA200 rising")
    if e200 and e200 > 0:
        dist = (close / e200 - 1) * 100
        if 0 <= dist <= 30:
            score += 15
            notes.append(f"+{dist:.0f}% above EMA200")
    if crossed_50_recent or crossed_200_recent:
        score += 15
        notes.append("fresh cross")
    return min(100, score), notes


def compute(conn=None, limit=1500):
    own = conn is None
    if own:
        conn = db.get_conn()
    _ensure(conn)
    today = dt.date.today().isoformat()
    syms = combined_universe(conn, band_limit=limit)

    rows_out = []
    for sym in syms:
        prows = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol=? "
            "ORDER BY date DESC LIMIT ?", (sym, MIN_HISTORY)).fetchall()
        if len(prows) < MIN_HISTORY:
            continue
        closes = [r[0] for r in reversed(prows) if r[0] is not None]
        if len(closes) < MIN_HISTORY:
            continue

        close = closes[-1]
        e50 = _ema(closes, EMA50_SPAN)
        e200 = _ema(closes, EMA200_SPAN)
        e50_prev = _ema(closes[:-20], EMA50_SPAN) if len(closes) > 20 else None
        e200_prev = _ema(closes[:-20], EMA200_SPAN) if len(closes) > 20 else None

        if e50 is None or e200 is None:
            continue
        if not (close > e50 and close > e200):
            continue

        # fresh cross detection (within last 20 bars)
        crossed_50 = False
        crossed_200 = False
        if len(closes) > 21:
            c20 = closes[-21]
            e50_20 = _ema(closes[:-20], EMA50_SPAN)
            e200_20 = _ema(closes[:-20], EMA200_SPAN)
            if e50_20 and c20 <= e50_20:
                crossed_50 = True
            if e200_20 and c20 <= e200_20:
                crossed_200 = True

        s, notes = _score(close, e50, e200, e50_prev, e200_prev,
                          crossed_50, crossed_200)
        rows_out.append({
            "date": today, "symbol": sym, "close": round(close, 2),
            "ema50": round(e50, 2), "ema200": round(e200, 2),
            "above_50": 1, "above_200": 1,
            "score": s, "notes": " | ".join(notes),
        })

    rows_out.sort(key=lambda r: -r["score"])
    conn.execute("DELETE FROM trend_candidates WHERE date=?", (today,))
    for r in rows_out:
        conn.execute(
            "INSERT OR REPLACE INTO trend_candidates VALUES "
            "(?,?,?,?,?,?,?,?,?)",
            (r["date"], r["symbol"], r["close"], r["ema50"], r["ema200"],
             r["above_50"], r["above_200"], r["score"], r["notes"]))
    conn.commit()

    # day-over-day swing alert
    try:
        prev = conn.execute(
            "SELECT COUNT(*) FROM trend_candidates WHERE date < ? "
            "ORDER BY date DESC LIMIT 1", (today,)).fetchone()
        prev_n = prev[0] if prev else 0
        cur_n = len(rows_out)
        if prev_n > 0:
            change = abs(cur_n - prev_n) / prev_n
            if change >= 0.20:
                try:
                    from alerts import send
                    arrow = "▲" if cur_n > prev_n else "▼"
                    send(f"📈 TREND pool {arrow}  "
                         f"{prev_n} → {cur_n} "
                         f"({change*100:.0f}% change)")
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"swing alert skipped: {e}")

    if own:
        conn.close()
    log.info(f"trend candidates: {len(rows_out)}")
    return rows_out


def top(n=25):
    conn = db.get_conn()
    _ensure(conn)
    today = conn.execute(
        "SELECT MAX(date) FROM trend_candidates").fetchone()[0]
    if not today:
        conn.close()
        return []
    rows = conn.execute(
        "SELECT symbol, close, ema50, ema200, score, notes "
        "FROM trend_candidates WHERE date=? "
        "ORDER BY score DESC LIMIT ?", (today, n)).fetchall()
    conn.close()
    return [{"symbol": r[0], "close": r[1], "ema50": r[2],
             "ema200": r[3], "score": r[4], "notes": r[5]}
            for r in rows]


def report(n=25, send_tg=False):
    rows = top(n)
    print("=" * 60)
    print("TREND CANDIDATES (price > EMA50 AND price > EMA200)")
    print("=" * 60)
    if not rows:
        print("(none)")
    for r in rows:
        print(f"{r['symbol']:<12} "
              f"₹{r['close']:>8.2f}  "
              f"EMA50 ₹{r['ema50']:>8.2f}  "
              f"EMA200 ₹{r['ema200']:>8.2f}  "
              f"score {r['score']:>3}  {r['notes']}")
    if send_tg and rows:
        try:
            from alerts import send
            lines = [f"📈 TREND CANDIDATES — {len(rows)} stocks",
                     "top 8:"]
            for r in rows[:8]:
                lines.append(f"  {r['symbol']}  ₹{r['close']}  "
                             f"score {r['score']}")
            send("\n".join(lines))
        except Exception as e:
            print(f"[TREND] telegram skipped: {e}")
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        compute()
        report()
    elif cmd == "top":
        report(n=int(sys.argv[2]) if len(sys.argv) > 2 else 25)
    elif cmd == "alert":
        report(send_tg=True)
    else:
        report()