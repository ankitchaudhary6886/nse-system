import requests

COLS = ["close", "price_earnings_ttm", "return_on_equity_fq", "debt_to_equity_fq"]

tests = [
    ("https://scanner.tradingview.com/india/scan", "NSE:RELIANCE"),
    ("https://scanner.tradingview.com/america/scan", "NASDAQ:AAPL"),
]

for url, ticker in tests:
    body = {"symbols": {"tickers": [ticker]}, "columns": COLS}
    r = requests.post(url, headers={"User-Agent": "Mozilla/5.0"}, json=body, timeout=30)
    print(ticker, "->", r.status_code)
    if r.status_code == 200:
        d = r.json().get("data", [])
        print(dict(zip(COLS, d[0]["d"])) if d else "no data")