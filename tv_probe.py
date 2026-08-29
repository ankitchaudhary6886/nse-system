import requests

URL = "https://scanner.tradingview.com/india/scan"
CANDIDATES = [
    "name", "close", "market_cap_basic", "price_earnings_ttm",
    "price_to_book_fq", "return_on_equity_fq",
    "return_on_invested_capital_fq", "debt_to_equity_fq",
    "interest_coverage_fq", "operating_margin_fq", "net_margin_fq",
    "gross_margin_fq", "revenue_growth_fy", "net_income_growth_fy",
    "dividend_yield_recent", "operating_cash_flow_fq",
    "free_cash_flow_fq", "total_debt_fq", "book_value_per_share_fq",
    "price_to_sales_ttm", "ev_to_ebitda_fq", "sector", "industry",
]

body = {"symbols": {"tickers": ["NSE:RELIANCE"]}, "columns": CANDIDATES}
r = requests.post(URL, headers={"User-Agent": "Mozilla/5.0"}, json=body, timeout=30)
print("status:", r.status_code)
if r.status_code != 200:
    print(r.text[:2000])
else:
    data = r.json().get("data", [])
    if data:
        vals = dict(zip(CANDIDATES, data[0]["d"]))
        print("HAS VALUE:")
        for k, v in vals.items():
            if v is not None:
                print(f"  {k} = {v}")
        print("NULL:", [k for k, v in vals.items() if v is None])