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
            # yfinance returns ZERO rows instead of raising when its cache
            # folder cannot host SQLite. Make sure it can before asking.
            try:
                from data_sources.yf_cache import ensure_yf_cache
                ensure_yf_cache()
            except Exception:
                pass
            return yf.Ticker(symbol + ".NS").history(
                start=start, auto_adjust=True)

        return self._execute(download)


def register_adapters(registry: SourceRegistry):
    registry.register(YahooPriceHistoryAdapter())
