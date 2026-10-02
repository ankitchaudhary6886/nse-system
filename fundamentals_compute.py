import sys
import time
import datetime as dt
import yfinance as yf
import db
from fundamentals_store import merge

def series(df, label):
    if df is None or label not in df.index:
        return None
    s = df.loc[label].dropna()
    return s if len(s) > 0 else None

def latest(s):
    return float(s.iloc[0])

def cagr(s, max_years=3):
    vals = s.iloc[:max_years + 1].dropna()
    if len(vals) < 2:
        return None
    first, last = float(vals.iloc[-1]), float(vals.iloc[0])
    years = len(vals) - 1
    if first <= 0 or last <= 0:
        return None
    return ((last / first) ** (1.0 / years) - 1.0) * 100.0

def fetch_one(conn, sym, name, sector):
    tk = yf.Ticker(sym + ".NS")
    info = tk.info or {}
    fin = tk.financials
    bs = tk.balance_sheet
    cf = tk.cashflow

    op = series(fin, "Operating Income")
    ni = series(fin, "Net Income")
    rev = series(fin, "Total Revenue")
    ie = series(fin, "Interest Expense")
    eq = series(bs, "Stockholders Equity")
    debt = series(bs, "Total Debt")
    cash = series(bs, "Cash And Cash Equivalents")
    ocf = series(cf, "Operating Cash Flow")

    roce = None
    if op is not None and eq is not None and debt is not None:
        capital = latest(eq) + latest(debt) - (latest(cash) if cash is not None else 0.0)
        if capital > 0:
            roce = latest(op) / capital * 100.0

    de = None
    if debt is not None and eq is not None and latest(eq) > 0:
        de = latest(debt) / latest(eq)

    ic = None
    if op is not None and ie is not None and latest(ie) != 0:
        ic = latest(op) / abs(latest(ie))

    om = None
    if op is not None and rev is not None and latest(rev) > 0:
        om = latest(op) / latest(rev) * 100.0
    nm = None
    if ni is not None and rev is not None and latest(rev) > 0:
        nm = latest(ni) / latest(rev) * 100.0
    roe = None
    if ni is not None and eq is not None and latest(eq) > 0:
        roe = latest(ni) / latest(eq) * 100.0

    mcap = info.get("marketCap")
    values = {
        "symbol": sym, "name": name, "sector": sector,
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap_cr": None if mcap is None else mcap / 1e7,
        "pe": info.get("trailingPE"), "pb": info.get("priceToBook"),
        "roe": roe, "roce": roce, "debt_to_equity": de,
        "interest_coverage": ic, "operating_margin": om,
        "net_profit_margin": nm,
        "sales_growth_3y": cagr(rev) if rev is not None else None,
        "profit_growth_3y": cagr(ni) if ni is not None else None,
        "dividend_yield": (None if info.get("dividendYield") is None
                           else info.get("dividendYield") * 100.0),
        "cfo_positive": (1 if (ocf is not None and latest(ocf) > 0)
                         else (0 if ocf is not None else None)),
    }
    merge(conn, values, source="yahoo_financials",
          observed_at="calc:" + dt.datetime.now().isoformat())
    conn.commit()
    return True

def run(force=False):
    conn = db.get_conn()
    have = {r[0] for r in conn.execute(
        "SELECT symbol FROM fundamentals WHERE uploaded_at LIKE 'calc:%'")}
    stocks = conn.execute(
        "SELECT symbol,name,sector FROM stocks WHERE active=1 ORDER BY symbol").fetchall()
    total = len(stocks)
    failed = []
    for i, (sym, name, sector) in enumerate(stocks, 1):
        if sym in have and not force:
            continue
        ok = False
        for attempt in range(3):
            try:
                fetch_one(conn, sym, name, sector)
                print(f"[{i}/{total}] {sym}: computed")
                ok = True
                break
            except Exception as e:
                print(f"[{i}/{total}] {sym} attempt {attempt+1} failed: {type(e).__name__}")
                time.sleep(5 * (attempt + 1))
        if not ok:
            failed.append(sym)
        time.sleep(0.5)
    print("FAILED:", failed if failed else "none")
    n = conn.execute(
        "SELECT COUNT(*) FROM fundamentals WHERE uploaded_at LIKE 'calc:%'").fetchone()[0]
    print(f"Computed fundamentals stored: {n} stocks")
    conn.close()

if len(sys.argv) > 1 and sys.argv[1] == "run":
    run()
