import db
import scoring

conn = db.get_conn()

print("DB SECTORS:")
for sym in ["MUTHOOTFIN", "BBTC", "DIXON"]:
    r = conn.execute(
        "SELECT sector FROM stocks WHERE symbol=?", (sym,)).fetchone()
    print("  ", sym, "->", r[0])

med = scoring.sector_pe_medians(conn)
cols = [c[1] for c in conn.execute("PRAGMA table_info(fundamentals)")]

for sym in ["MUTHOOTFIN", "BBTC", "DIXON"]:
    row = conn.execute(
        "SELECT * FROM fundamentals WHERE symbol=?", (sym,)).fetchone()
    m = dict(zip(cols, row))
    sec = conn.execute(
        "SELECT sector FROM stocks WHERE symbol=?", (sym,)).fetchone()[0]
    pe = m.get("pe")
    pg = m.get("profit_growth_3y")
    md = med.get(sec)
    ratio = None
    if pe and md:
        ratio = round(pe / md, 2)
    peg = None
    if pe and pg and pg > 0:
        peg = round(pe / pg, 2)
    print(sym,
          "| PE:", pe,
          "| sector:", sec,
          "| sector median PE:", md,
          "| PE ratio:", ratio,
          "| PEG:", peg,
          "| ROCE:", m.get("roce"),
          "| profit 3Y:", pg,
          "| sales 3Y:", m.get("sales_growth_3y"))