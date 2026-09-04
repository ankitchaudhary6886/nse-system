"""
Top Picks — daily shortlist fusing:
  50% ML P(WIN) + 30% institutional accumulation + 20% sector leadership
  + bonus for a live Gabani setup.
Computed once per day, cached in top_picks table.
"""
import datetime as dt
import pandas as pd
import db
import meta_model
import institutional
import sector_gate

def _ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS top_picks(
        date TEXT, symbol TEXT, p_win REAL, accum REAL,
        sector_rs REAL, sector TEXT, setup INTEGER,
        composite REAL)""")

def _detect_setup(conn, sym):
    try:
        from setup import SetupDetector
        rows = conn.execute(
            "SELECT date, close, high, low, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        if len(rows) < 280:
            return 0
        df = pd.DataFrame(list(rows),
                          columns=["date", "Close", "High", "Low",
                                   "Volume"]).set_index("date")
        df.index = pd.to_datetime(df.index)
        st = SetupDetector.detect(df, sym)
        return 1 if st.triggered else 0
    except Exception:
        return 0

def compute(force=False):
    conn = db.get_conn()
    _ensure(conn)
    today = dt.date.today().isoformat()
    if not force:
        n = conn.execute(
            "SELECT COUNT(*) FROM top_picks WHERE date=?",
            (today,)).fetchone()[0]
        if n > 0:
            conn.close()
            return

    conn.execute("DELETE FROM top_picks WHERE date=?", (today,))
    srs = sector_gate._sector_rs_map(conn)

    acc = {}
    try:
        for s, a in conn.execute(
                "SELECT symbol, accum FROM institutional "
                "WHERE date=(SELECT MAX(date) FROM institutional)"):
            acc[s] = a
    except Exception:
        pass

    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM universe_broad "
        "WHERE mcap_cr BETWEEN 1000 AND 8000 "
        "ORDER BY mcap_cr DESC LIMIT 600")]

    rows = []
    for sym in syms:
        r = meta_model.score_symbol(sym, use_yahoo=False)
        if not r or r.get("p_win") is None:
            continue
        p = r["p_win"]
        a = acc.get(sym)
        if a is None:
            a = institutional.accumulation_score(sym, conn)
            a = a if a is not None else 0.5
        sr = srs.get(sym, 0.5)
        sec = sector_gate.sector_of(sym)
        comp = 0.5 * p + 0.3 * a + 0.2 * sr
        rows.append([today, sym, p, a, sr, sec, 0, round(comp, 3)])

    rows.sort(key=lambda x: -x[7])
    top50 = rows[:50]

    # setup bonus only for the shortlist (keeps it fast)
    for row in top50:
        row[6] = _detect_setup(conn, row[1])
        row[7] = round(row[7] + (0.1 if row[6] else 0), 3)
    top50.sort(key=lambda x: -x[7])

    conn.executemany(
        "INSERT INTO top_picks VALUES (?,?,?,?,?,?,?,?)", top50)
    conn.commit()
    conn.close()
    print(f"[TOPPICKS] computed {len(rows)} -> stored top {len(top50)}")

def top(n=15):
    conn = db.get_conn()
    _ensure(conn)
    rows = conn.execute(
        "SELECT symbol, p_win, accum, sector, setup, composite "
        "FROM top_picks "
        "WHERE date=(SELECT MAX(date) FROM top_picks) "
        "ORDER BY composite DESC LIMIT ?", (n,)).fetchall()
    conn.close()
    return [{"symbol": s, "p_win": p, "accum": a, "sector": sec,
             "setup": bool(st), "composite": c}
            for s, p, a, sec, st, c in rows]

if __name__ == "__main__":
    compute(force=True)
    for r in top():
        tag = " 🏄" if r["setup"] else ""
        print(f"  {r['symbol']:<12} comp {r['composite']:.2f} "
              f"P(WIN) {r['p_win']:.0%} accum {r['accum']:.2f} "
              f"{r['sector'] or ''}{tag}")