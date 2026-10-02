import sys
import datetime as dt
import pandas as pd
import db
from fundamentals_store import merge

NUMERIC = ["current_price", "market_cap_cr", "pe", "pb", "roe", "roce",
           "debt_to_equity", "interest_coverage", "operating_margin",
           "net_profit_margin", "sales_growth_3y", "profit_growth_3y",
           "promoter_holding", "pledge_pct", "fii_holding", "dividend_yield"]

def load(path):
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "symbol" not in df.columns:
        print("CSV must have a 'symbol' column")
        return
    for c in NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    conn = db.get_conn()
    now = "csv:" + dt.datetime.now().isoformat()
    n = 0
    for _, r in df.iterrows():
        sym = str(r["symbol"]).strip().upper()
        for suffix in (".NS", ".NSE", ".BO", ".BSE"):
            if sym.endswith(suffix):
                sym = sym[:-len(suffix)]
                break
        if not sym:
            continue
        values = {"symbol": sym, "data_quality_flags": ["csv_import"]}
        for col in NUMERIC:
            if col in df.columns and pd.notna(r.get(col)):
                values[col] = r.get(col)
        for col in ("name", "sector"):
            if col in df.columns and pd.notna(r.get(col)):
                values[col] = str(r.get(col)).strip()
        if "cfo_positive" in df.columns and pd.notna(r.get("cfo_positive")):
            values["cfo_positive"] = int(float(r.get("cfo_positive")) != 0)
        merge(conn, values, source=f"csv:{path}", observed_at=now)
        n += 1
    conn.commit()
    print(f"Fundamentals CSV loaded: {n} stocks (non-null fields merged)")
    conn.close()

if len(sys.argv) > 1:
    load(sys.argv[1])
