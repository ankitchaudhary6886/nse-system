"""
Swing Desk engine (live, no execution).
EOD: regime gate + breadth gate + sector gate -> signals -> Telegram.
Daily: grade pending signals WIN / LOSS / EXPIRED / TIMEOUT.
"""
import datetime as dt
import pandas as pd
import db
from scanner import Screener
from setup import SetupDetector
from regime import MarketRegime
import sector_gate
import breadth

def universe(conn):
    rows = conn.execute(
        "SELECT symbol FROM universe_broad "
        "WHERE mcap_cr BETWEEN 1000 AND 8000 "
        "AND symbol NOT LIKE '%$%' AND symbol NOT LIKE '% %' "
        "ORDER BY mcap_cr DESC LIMIT 1000").fetchall()
    core = [r[0] for r in conn.execute(
        "SELECT symbol FROM stocks WHERE active=1")]
    return sorted(set([r[0] for r in rows]) | set(core))

def ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS swing_signals(
        signal_date TEXT, symbol TEXT, entry_trigger REAL,
        stop REAL, target REAL, risk_pct REAL, pullback REAL,
        impulse REAL, ema_zone TEXT, outcome TEXT,
        updated_at TEXT)""")

def scan():
    conn = db.get_conn()
    ensure(conn)
    reg = MarketRegime.compute()
    today = dt.date.today().isoformat()
    print(f"regime: {'BULLISH' if reg.is_bullish else 'DEFENSIVE'} "
          f"({reg.symbol})")
    conn.execute("DELETE FROM swing_signals WHERE signal_date=?",
                 (today,))
    if not reg.is_bullish:
        conn.commit()
        conn.close()
        print("defensive regime -> no new signals today")
        return

    try:
        bok = breadth.breadth_ok(conn)
    except Exception:
        bok = True
    if not bok:
        conn.commit()
        conn.close()
        print("breadth weak -> no new signals today")
        return

    allowed = sector_gate.allowed_sectors()
    print(f"sector gate (top-{len(allowed)}): "
          f"{', '.join(sorted(allowed)) or 'n/a'}")

    n = 0
    for sym in universe(conn):
        if not sector_gate.passes(sym, allowed):
            continue
        rows = conn.execute(
            "SELECT date, close, high, low, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        if len(rows) < 280:
            continue
        df = pd.DataFrame(list(rows), columns=["date", "Close",
                          "High", "Low", "Volume"]).set_index("date")
        df.index = pd.to_datetime(df.index)
        sc = Screener.evaluate(df, sym)
        if not sc.passed:
            continue
        st = SetupDetector.detect(df, sym)
        if not st.triggered:
            continue
        risk_pct = (st.entry_price - st.stop_loss) / st.entry_price
        conn.execute(
            "INSERT INTO swing_signals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (today, sym, st.entry_price, st.stop_loss,
             st.target_price, round(risk_pct * 100, 2),
             st.pullback_depth, st.impulse_pct, st.ema_proximity,
             "PENDING", dt.datetime.now().isoformat()))
        n += 1
        print(f"  ✅ {sym} trigger ₹{st.entry_price}  "
              f"SL ₹{st.stop_loss}  TGT ₹{st.target_price}  "
              f"risk {risk_pct:.1%}  zone {st.ema_proximity}")
        try:
            import swing_alerts
            swing_alerts.notify_setup(st)
        except Exception as e:
            print(f"  alert skipped: {e}")
    conn.commit()
    conn.close()
    print(f"swing signals today: {n}")

def update_outcomes():
    conn = db.get_conn()
    ensure(conn)
    pend = conn.execute(
        "SELECT rowid, signal_date, symbol, entry_trigger, stop, "
        "target FROM swing_signals WHERE outcome IN "
        "('PENDING','OPEN')").fetchall()
    for rowid, sd, sym, trig, stop, target in pend:
        rows = conn.execute(
            "SELECT date, high, low FROM prices_daily "
            "WHERE symbol=? AND date>? ORDER BY date LIMIT 35",
            (sym, sd)).fetchall()
        trig_day = None
        for i in range(min(3, len(rows))):
            if rows[i][1] >= trig:
                trig_day = i
                break
        if trig_day is None:
            if len(rows) >= 3:
                conn.execute(
                    "UPDATE swing_signals SET outcome='EXPIRED', "
                    "updated_at=? WHERE rowid=?",
                    (dt.datetime.now().isoformat(), rowid))
            continue
        out = "OPEN"
        for d, h, l in rows[trig_day:]:
            if l <= stop:
                out = "LOSS"
                break
            if h >= target:
                out = "WIN"
                break
        if out == "OPEN" and len(rows) >= 30:
            out = "TIMEOUT"
        if out != "OPEN":
            conn.execute(
                "UPDATE swing_signals SET outcome=?, updated_at=? "
                "WHERE rowid=?",
                (out, dt.datetime.now().isoformat(), rowid))
    conn.commit()
    conn.close()

def report():
    conn = db.get_conn()
    ensure(conn)
    print("SWING SCORECARD:")
    for r in conn.execute(
            "SELECT outcome, COUNT(*) FROM swing_signals "
            "GROUP BY outcome ORDER BY outcome"):
        print(f"   {r[0]:<8} {r[1]}")
    conn.close()

def backfill(step=10, max_stocks=600):
    conn = db.get_conn()
    ensure(conn)
    syms = universe(conn)[:max_stocks]
    conn.close()
    n = 0
    for sym in syms:
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT date, close, high, low, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        conn.close()
        if len(rows) < 300:
            continue
        df = pd.DataFrame(list(rows), columns=["date", "Close",
                          "High", "Low", "Volume"]).set_index("date")
        df.index = pd.to_datetime(df.index)
        conn = db.get_conn()
        for i in range(280, len(df), step):
            hist = df.iloc[:i]
            d = str(hist.index[-1])[:10]
            if conn.execute(
                    "SELECT 1 FROM swing_signals WHERE symbol=? "
                    "AND signal_date=?", (sym, d)).fetchone():
                continue
            sc = Screener.evaluate(hist, sym)
            if not sc.passed:
                continue
            st = SetupDetector.detect(hist, sym)
            if not st.triggered:
                continue
            risk_pct = (st.entry_price - st.stop_loss) / st.entry_price
            conn.execute(
                "INSERT INTO swing_signals VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?)",
                (d, sym, st.entry_price, st.stop_loss,
                 st.target_price, round(risk_pct * 100, 2),
                 st.pullback_depth, st.impulse_pct,
                 st.ema_proximity, "PENDING",
                 dt.datetime.now().isoformat()))
            n += 1
        conn.commit()
        conn.close()
    print(f"backfilled signals: {n}")
    update_outcomes()
    report()

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "backfill":
        backfill()
    else:
        update_outcomes()
        scan()
        report()