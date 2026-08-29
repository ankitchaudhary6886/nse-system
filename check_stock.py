import sys
import db
import scoring

sym = sys.argv[2] if len(sys.argv) > 2 else "DIXON"
conn = db.get_conn()
cols = [c[1] for c in conn.execute("PRAGMA table_info(fundamentals)")]
row = conn.execute(
    "SELECT * FROM fundamentals WHERE symbol=?", (sym,)).fetchone()
if row is None:
    print("no fundamentals for", sym)
    sys.exit()
m = dict(zip(cols, row))

print("RAW FUNDAMENTALS:", sym)
for k in ["pe", "roe", "roce", "debt_to_equity",
          "sales_growth_3y", "profit_growth_3y",
          "cfo_positive", "market_cap_cr"]:
    print(f"  {k} = {m.get(k)}")

med = scoring.sector_pe_medians(conn)
r = scoring.score_stock(conn, sym, med)
print("sector:", r["sector"],
      "| sector median PE:", med.get(r["sector"]))
print("roce_s:", r["roce_s"], "| growth_s:", r["growth_s"],
      "| val_s:", r["val_s"], "| composite:", r["composite"])
print("GATES:")
for g in r["gates"]:
    print("  ", g[0], "| passed:", g[1], "|", g[4])