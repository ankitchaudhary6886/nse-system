"""Yahoo Finance adapter for incremental NSE price-history ingestion."""

from data_sources.core import BaseSourceAdapter, SourceRegistry


class YahooPriceHistoryAdapter(BaseSourceAdapter):
    name = "yahoo_finance"
    datasets = ("prices.daily_history",)

    def __init__(self):
        super().__init__(max_calls=120, window_seconds=60)

    def fetch(self, symbol, start):
        def download():
            import yfinance as yf
            return yf.Ticker(symbol + ".NS").history(
                start=start, auto_adjust=True)

        return self._execute(download)


def register_adapters(registry: SourceRegistry):
    registry.register(YahooPriceHistoryAdapter())
