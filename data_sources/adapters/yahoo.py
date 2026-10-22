"""Yahoo Finance adapters for NSE price history and non-price ticker fields.

Every direct ``yfinance`` call in the app routes through this module (F-15 /
ID52), so the ``.NS`` suffix rule, the tz-cache repair, the call budget and the
health record live in exactly ONE place.
"""

from data_sources.core import BaseSourceAdapter, SourceRegistry


def yahoo_ticker(symbol):
    """Project symbol -> Yahoo ticker.

    Project symbols are bare (``RELIANCE``) and get the ``.NS`` suffix; index
    and already-qualified symbols (``^NSEI``, ``NIFTY_SMALLCAP_100.NS``) pass
    through unchanged. Non-Yahoo providers want the bare project symbol, so the
    suffix is added HERE rather than by the callers.
    """
    if symbol.startswith("^") or symbol.endswith(".NS"):
        return symbol
    return symbol + ".NS"


def _ensure_cache():
    """yfinance returns ZERO rows instead of raising when its cache folder
    cannot host SQLite. Make sure it can before asking. Guarded: a repair
    failure must never break a fetch that would otherwise work."""
    try:
        from data_sources.yf_cache import ensure_yf_cache
        ensure_yf_cache()
    except Exception:
        pass


class YahooPriceHistoryAdapter(BaseSourceAdapter):
    name = "yahoo_finance"
    datasets = ("prices.daily_history",)

    def __init__(self):
        super().__init__(max_calls=120, window_seconds=60)

    def fetch(self, symbol, start, end=None):
        def download():
            import yfinance as yf
            _ensure_cache()
            return yf.Ticker(yahoo_ticker(symbol)).history(
                start=start, end=end, auto_adjust=True)

        return self._execute(download)


class YahooFieldAdapter(BaseSourceAdapter):
    """One non-price ``Ticker`` field: ``info``, ``financials``,
    ``balance_sheet``, ``cashflow``, ``splits``, ``dividends``, ``actions``,
    ``earnings_dates``, ... Callers ask for a single field per request so a
    failure on one field never hides the others (same isolation the old
    per-attribute ``try/except`` blocks gave them)."""

    name = "yahoo_finance_fields"
    datasets = ("yahoo.ticker_field",)

    def __init__(self):
        # Generous: these callers pace themselves with sleeps and the harvest
        # runs in a worker thread, so the budget must never be the thing that
        # silently skips a symbol.
        super().__init__(max_calls=600, window_seconds=60)

    def fetch(self, symbol, field):
        def read():
            import yfinance as yf
            _ensure_cache()
            return getattr(yf.Ticker(yahoo_ticker(symbol)), field)

        return self._execute(read)


def register_adapters(registry: SourceRegistry):
    registry.register(YahooPriceHistoryAdapter())
    registry.register(YahooFieldAdapter())
