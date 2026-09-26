"""TradingView India scanner adapter for the existing fundamentals fetcher."""

import requests

from data_sources.core import BaseSourceAdapter, SourceRegistry


class TradingViewFundamentalsAdapter(BaseSourceAdapter):
    name = "tradingview"
    datasets = ("fundamentals.tv_batch",)
    url = "https://scanner.tradingview.com/india/scan"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    def __init__(self):
        super().__init__(max_calls=60, window_seconds=60)

    def fetch(self, tickers, columns):
        body = {"symbols": {"tickers": tickers}, "columns": columns}

        def request():
            response = requests.post(
                self.url, headers=self.headers, json=body, timeout=30)
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data")
            if not isinstance(rows, list):
                raise ValueError("TradingView response has no data list")
            return rows

        return self._execute(request)


def register_adapters(registry: SourceRegistry):
    registry.register(TradingViewFundamentalsAdapter())
