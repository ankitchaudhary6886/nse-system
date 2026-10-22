"""Shared data-source adapters and fallback orchestration."""

from datetime import date

from .core import (
    FetchResult,
    ProviderFetchError,
    SourceAdapter,
    SourceHealth,
    SourceRegistry,
    get_registry,
)

# The ONE price-history fallback chain (F-15 / ID52). Call sites that used to
# import yfinance directly go through this list, so a Yahoo outage degrades to
# the NSE-backed providers instead of failing outright.
PRICE_HISTORY_PROVIDERS = ("yahoo_finance", "nse_india_api", "jugaad_data",
                           "nsemine_history", "pnsea")


def _period_to_start(period):
    """Translate a yfinance-style period (``5y``, ``2y``, ``1mo``) into the ISO
    start date that opens the same window. Only the Yahoo adapter understands
    periods, so the chain always receives a concrete ``start``."""
    text = str(period).lower()
    for suffix, unit in (("mo", "months"), ("wk", "weeks"),
                         ("y", "years"), ("d", "days")):
        if text.endswith(suffix):
            from dateutil.relativedelta import relativedelta
            return (date.today()
                    - relativedelta(**{unit: int(text[:-len(suffix)])})
                    ).isoformat()
    raise ValueError(f"unsupported period: {period!r}")


def fetch_price_history(symbol, start=None, end=None, period=None):
    """Daily OHLCV bars for one symbol through the shared provider chain.

    Returns the DataFrame the winning provider produced — the same shape as
    ``yf.Ticker(...).history()`` (tz-aware DatetimeIndex, auto-adjusted).
    Raises ``ProviderFetchError`` when no provider can serve the symbol.
    """
    if period is not None:
        start = _period_to_start(period)
    return get_registry().fetch(
        "prices.daily_history", PRICE_HISTORY_PROVIDERS,
        symbol=symbol, start=start, end=end).data


def fetch_yahoo_field(symbol, field):
    """One non-price Yahoo ``Ticker`` field (``info``, ``splits``,
    ``dividends``, ``actions``, ``earnings_dates``, ``financials``, ...).

    Requesting one field per call keeps the old per-attribute failure
    isolation: a field that errors raises here and never hides the others.
    """
    return get_registry().fetch(
        "yahoo.ticker_field", ("yahoo_finance_fields",),
        symbol=symbol, field=field).data


__all__ = [
    "FetchResult",
    "PRICE_HISTORY_PROVIDERS",
    "ProviderFetchError",
    "SourceAdapter",
    "SourceHealth",
    "SourceRegistry",
    "fetch_price_history",
    "fetch_yahoo_field",
    "get_registry",
]
