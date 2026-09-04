"""
A3 — FII/DII daily cash-flow macro layer.
Fetches NSE's official FII stats CSV, parses FII & DII net flows (in Crores),
and stores them for the terminal UI.
"""
import datetime as dt
import requests
import db
import io
import csv

def _ensure(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS macro_flow(
        date TEXT PRIMARY KEY, fii_net_cr REAL, dii_net_cr REAL)""")

def _fetch_nse():
    """Best-effort fetch of NSE FII stats CSV."""
    d = dt.date.today()
    url = f"https://archives.nseindia.com/content/fo/fii_stats_{d.strftime('%d%m%Y')}.csv"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        reader = csv.reader(io.StringIO(r.text))
        fii_net = 0.0
        dii_net = 0.0
        for row in reader:
            if not row or len(row) < 5:
                continue
            client = row[0].strip().upper()
            try:
                # NSE usually reports in Rupees. 1 Crore = 10,000,000
                net_val = float(row[4].replace(",", "").replace('"', "")) / 10000000
            except Exception:
                continue
            if "FII" in client or "FPI" in client:
                fii_net += net_val
            elif "DII" in client or "MUTUAL" in client:
                dii_net += net_val
        return fii_net, dii_net
    except Exception as e:
        print(f"[MACRO] NSE fetch failed: {e}")
        return None

def refresh():
    conn = db.get_conn()
    _ensure(conn)
    today = dt.date.today().isoformat()
    
    res = _fetch_nse()
    if res:
        fii, dii = res
        conn.execute("INSERT OR REPLACE INTO macro_flow(date, fii_net_cr, dii_net_cr) VALUES(?,?,?)",
                     (today, round(fii, 2), round(dii, 2)))
        conn.commit()
        print(f"[MACRO] Fetched: FII {fii:+.0f}Cr, DII {dii:+.0f}Cr")
    else:
        print("[MACRO] Skipped today (market closed or NSE blocked)")
    conn.close()

def latest():
    conn = db.get_conn()
    _ensure(conn)
    row = conn.execute(
        "SELECT date, fii_net_cr, dii_net_cr FROM macro_flow "
        "ORDER BY date DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None
    return {"date": row[0], "fii_net": row[1], "dii_net": row[2], 
            "net_flow": row[1] + row[2]}

if __name__ == "__main__":
    refresh()
    print(latest())