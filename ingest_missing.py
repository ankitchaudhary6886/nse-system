"""One-time: download history for tracked symbols missing recent data."""
import datetime as dt
import time
import yfinance as yf
import db
import data_quality

def main():
    conn = db.get_conn()
    r = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()
    latest = data_quality._parse_date(r[0])
    cutoff = (latest - dt.timedelta(days=10)).isoformat()
    recent = set(x[0] for x in conn.execute(
        "SELECT DISTINCT symbol FROM prices_daily WHERE date>=?",
        (cutoff,)))
    tracked = data_quality._get_universe_symbols(conn)
    missing = [s for s in tracked if s not in recent]
    conn.close()
    print(f"missing symbols: {len(missing)}")

    conn = db.get_conn()
    done = 0
    for sym in missing:
        try:
            d = yf.Ticker(sym + ".NS").history(period="5y",
                                               auto_adjust=True)
        except Exception:
            continue
        if d is None or len(d) < 200:
            continue
        rows = []
        for idx, row in d.iterrows():
            rows.append((sym, str(idx.date())[:10],
                         float(row["Open"]), float(row["High"]),
                         float(row["Low"]), float(row["Close"]),
                         float(row["Volume"])))
        conn.executemany(
            "INSERT OR REPLACE INTO prices_daily "
            "(symbol, date, open, high, low, close, volume) "
            "VALUES (?,?,?,?,?,?,?)", rows)
        conn.commit()
        done += 1
        if done % 25 == 0:
            print(f"  ...{done}/{len(missing)}")
        time.sleep(0.2)
    conn.close()
    print(f"ingested {done} symbols")

if __name__ == "__main__":
    main()