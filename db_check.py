import pandas as pd
import db

conn = db.get_conn()

print("DATABASE sectors:")
for sym in ["MUTHOOTFIN", "BBTC", "DIXON", "RELIANCE", "HDFCBANK", "SBIN"]:
    r = conn.execute(
        "SELECT symbol, sector FROM stocks WHERE symbol=?", (sym,)).fetchone()
    print("  ", r)

print("distinct sectors in DB:",
      conn.execute("SELECT COUNT(DISTINCT sector) FROM stocks").fetchone()[0])

print("CSV columns and rows:")
df = pd.read_csv("data/nifty500_constituents.csv")
print("  columns:", df.columns.tolist())
print(df[df["Symbol"].isin(["MUTHOOTFIN", "BBTC", "DIXON"])].to_string())