"""One-time: download 5y daily history for smallcap band (1000-8000 cr)."""
import math
import time
import yfinance as yf
import db

def run(limit=600, min_mcap=1000, max_mcap=8000):
    conn = db.get_conn()
    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM universe_broad "
        "WHERE mcap_cr BETWEEN ? AND ? "
        "ORDER BY mcap_cr DESC LIMIT ?",
        (min_mcap, max_mcap, limit))]
    print(f"ingesting {len(syms)} smallcaps...")
    done = 0
    for sym in syms:
        have = conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE symbol=?",
            (sym,)).fetchone()[0]
        if have >= 250:
            done += 1
            continue
        try:
            tk = yf.Ticker(sym + ".NS")
            df = tk.history(period="5y", auto_adjust=True)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        rows = []
        for idx, r in df.iterrows():
            o = float(r["Open"])
            h = float(r["High"])
            l = float(r["Low"])
            c = float(r["Close"])
            v = float(r["Volume"])
            if any(math.isnan(x) for x in (o, h, l, c, v)):
                continue
            rows.append((sym, str(idx.date()), o, h, l, c, v))
        conn.executemany(
            "INSERT OR REPLACE INTO prices_daily "
            "VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        done += 1
        print(f"[{done}/{len(syms)}] {sym}: {len(rows)} rows")
        time.sleep(0.2)
    print("smallcap history ingest complete")
    conn.close()

if __name__ == "__main__":
    run()