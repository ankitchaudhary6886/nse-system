"""
Swing Desk engine (live, no execution).
EOD: regime gate + breadth gate + sector gate + fund veto -> signals -> Telegram.
When regime is DEFENSIVE, falls back to ALL-WEATHER mode (stricter filters,
half position size).
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
    # safe migration: add 'mode' column if missing
    cols = [r[1] for r in conn.execute("PRAGMA table_info(swing_signals)")]
    if "mode" not in cols:
        try:
            conn.execute(
                "ALTER TABLE swing_signals "
                "ADD COLUMN mode TEXT DEFAULT 'SWING'")
        except Exception:
            pass


def _is_vetoed(sym, conn):
    try:
        import fund_veto
        return fund_veto.vetoed(sym, conn=conn)
    except Exception:
        return False, None


def _scan_all_weather(conn, today):
    """High-conviction setups during DEFENSIVE regime. Half size."""
    try:
        import all_weather
    except Exception as e:
        print(f"[AW] module missing: {e}")
        return 0

    # Relaxed breadth: only above50 >= 0.35
    try:
        b = breadth.compute(conn)
        if b["above50"] < 0.35:
            print(f"[AW] breadth too weak: above50={b['above50']:.2f} "
                  f"< 0.35 -> skip")
            return 0
        print(f"[AW] breadth ok for AW mode: above50={b['above50']:.2f}")
    except Exception as e:
        print(f"[AW] breadth check skipped: {e}")

    conn.execute(
        "DELETE FROM swing_signals WHERE signal_date=? "
        "AND mode='ALL_WEATHER'", (today,))

    cands = all_weather.candidates(conn)
    print(f"[AW] {len(cands)} candidates (fund>=70 & >=25% below 52w high)")

    n = 0
    for sym, df, fs in cands:
        st = all_weather.detect(sym, df, fs)
        if not st:
            continue
        bad, why = _is_vetoed(sym, conn)
        if bad:
            print(f"  [AW] {sym} vetoed: {why}")
            continue
        conn.execute(
            "INSERT INTO swing_signals(signal_date, symbol, entry_trigger, "
            "stop, target, risk_pct, pullback, impulse, ema_zone, outcome, "
            "updated_at, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (today, sym, st["entry"], st["stop"], st["target"],
             round(st["risk_pct"] * 100, 2), st["pb_depth"], st["impulse"],
             st["pattern"], "PENDING",
             dt.datetime.now().isoformat(), "ALL_WEATHER"))
        n += 1
        print(f"  [AW] {sym:<12} {st['pattern']:<18} entry {st['entry']} "
              f"stop {st['stop']} target {st['target']} fund {fs}")
        try:
            import swing_alerts
            swing_alerts.notify_all_weather(sym, st)
        except Exception as e:
            print(f"  [AW] alert skipped: {e}")
    print(f"[AW] all-weather signals stored: {n}")
    return n


def scan():
    conn = db.get_conn()
    ensure(conn)
    reg = MarketRegime.compute()
    today = dt.date.today().isoformat()
    print(f"regime: {'BULLISH' if reg.is_bullish else 'DEFENSIVE'} "
          f"({reg.symbol})")
    conn.execute(
        "DELETE FROM swing_signals WHERE signal_date=? AND mode='SWING'",
        (today,))

    if not reg.is_bullish:
        print("defensive regime -> running ALL-WEATHER scan")
        n_aw = _scan_all_weather(conn, today)
        conn.commit()
        conn.close()
        print(f"all-weather signals today: {n_aw}")
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
    veto_skipped = 0
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

        # Staleness check: only accept patterns completed on the last bar
        last_bar_date = str(df.index[-1].date())
        if st.signal_date != last_bar_date:
            continue

        bad, why = _is_vetoed(sym, conn)
        if bad:
            veto_skipped += 1
            print(f"  [VETO] {sym} skipped — {why}")
            continue

        risk_pct = (st.entry_price - st.stop_loss) / st.entry_price
        conn.execute(
            "INSERT INTO swing_signals(signal_date, symbol, entry_trigger, "
            "stop, target, risk_pct, pullback, impulse, ema_zone, outcome, "
            "updated_at, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (today, sym, st.entry_price, st.stop_loss,
             st.target_price, round(risk_pct * 100, 2),
             st.pullback_depth, st.impulse_pct, st.ema_proximity,
             "PENDING", dt.datetime.now().isoformat(), "SWING"))
        n += 1
        print(f"  OK {sym} trigger Rs {st.entry_price}  "
              f"SL Rs {st.stop_loss}  TGT Rs {st.target_price}  "
              f"risk {risk_pct:.1%}  zone {st.ema_proximity}")
        try:
            import swing_alerts
            swing_alerts.notify_setup(st)
        except Exception as e:
            print(f"  alert skipped: {e}")
    conn.commit()
    conn.close()
    print(f"swing signals today: {n}  (veto-skipped: {veto_skipped})")


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
    print("BY MODE:")
    for r in conn.execute(
            "SELECT mode, COUNT(*) FROM swing_signals "
            "GROUP BY mode ORDER BY mode"):
        print(f"   {r[0] or 'SWING':<12} {r[1]}")
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
                "INSERT INTO swing_signals(signal_date, symbol, "
                "entry_trigger, stop, target, risk_pct, pullback, "
                "impulse, ema_zone, outcome, updated_at, mode) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (d, sym, st.entry_price, st.stop_loss,
                 st.target_price, round(risk_pct * 100, 2),
                 st.pullback_depth, st.impulse_pct,
                 st.ema_proximity, "PENDING",
                 dt.datetime.now().isoformat(), "SWING"))
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
    elif mode == "aw":
        conn = db.get_conn()
        ensure(conn)
        today = dt.date.today().isoformat()
        n = _scan_all_weather(conn, today)
        conn.commit()
        conn.close()
        print(f"all-weather signals: {n}")
    else:
        update_outcomes()
        scan()
        report()