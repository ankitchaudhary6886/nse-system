"""Adapter for the PyPI package ``nsemine`` (import ``nsemine``).

WHY THIS MODULE EXISTS
----------------------
``nsemine`` scrapes NSE both ways: it can read the official daily bhavcopy
(including the delivery columns) AND it can pull a symbol's daily candles from
NSE's charting feed.  Two properties make it worth having in the fallback
chain:

  * its bhavcopy loader already returns clean, renamed columns
    (``date, symbol, series, open, high, low, close, volume, delivery_pct``),
    so it is a quick cross-check against our own parser, and
  * its chart history comes from a different NSE endpoint than the ``nse``
    package's history API, so the two fail independently.

WHAT IT RETURNS
---------------
* ``prices.bhavcopy_daily`` -- canonical records.
* ``prices.daily_history`` -- yahoo_finance-shaped DataFrame.

GOLDEN RULE 7
-------------
``nsemine`` is imported lazily inside the seams; importing this module costs
nothing and a missing package only marks the adapter unavailable.

GOTCHA
------
Every nsemine function prints a traceback and returns ``None`` when something
goes wrong instead of raising.  We convert ``None``/empty into a real error so
the registry falls through to the next provider and the health panel shows an
honest failure instead of a silent "no data".
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from data_sources.adapters.nse_archives import (
    normalize_price_records,
    records_to_yahoo_frame,
)
from data_sources.core import BaseSourceAdapter, SourceRegistry


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value: Any) -> datetime:
    """nsemine's history helpers want datetime, not date, objects."""
    if isinstance(value, datetime):
        return value
    return datetime.combine(_as_date(value), datetime.min.time())


def fetch_bhavcopy(day: Any, series: str = "EQ"):
    """SEAM -- nsemine's clean bhavcopy + delivery DataFrame for one day."""
    try:
        from nsemine.archives import get_daily_bhavcopy_and_deliverables_data
    except ImportError as exc:
        raise RuntimeError(
            "the 'nsemine' package is not installed; run: pip install nsemine"
        ) from exc
    return get_daily_bhavcopy_and_deliverables_data(
        series=series, trade_date=_as_date(day))


def fetch_symbol_history(symbol: str, start: Any, end: Any = None,
                         interval: str = "D"):
    """SEAM -- nsemine daily candles from NSE's charting feed."""
    try:
        from nsemine.historical import get_stock_historical_data
    except ImportError as exc:
        raise RuntimeError(
            "the 'nsemine' package is not installed; run: pip install nsemine"
        ) from exc
    return get_stock_historical_data(
        stock_symbol=symbol,
        start_datetime=_as_datetime(start),
        end_datetime=_as_datetime(end) if end is not None else datetime.now(),
        interval=interval)


class NsemineBhavcopyAdapter(BaseSourceAdapter):
    """Whole-market bhavcopy (with delivery columns) via nsemine."""

    name = "nsemine"
    datasets = ("prices.bhavcopy_daily",)

    def __init__(self):
        super().__init__(max_calls=30, window_seconds=60)

    def fetch(self, day: Any):
        target = _as_date(day)

        def run():
            frame = fetch_bhavcopy(target)
            if frame is None or len(frame) == 0:
                raise ValueError(f"nsemine returned no bhavcopy for {target}")
            rows = normalize_price_records(frame, default_date=target)
            if not rows:
                raise ValueError(
                    f"nsemine bhavcopy for {target} had no usable equity rows")
            return rows

        return self._execute(run)


class NseminePriceHistoryAdapter(BaseSourceAdapter):
    """Daily candles for one symbol via nsemine's chart feed."""

    name = "nsemine_history"
    datasets = ("prices.daily_history",)

    def __init__(self):
        super().__init__(max_calls=20, window_seconds=60)

    def fetch(self, symbol: str, start: Any, end: Any = None):
        def run():
            frame = fetch_symbol_history(symbol, start, end)
            if frame is None or len(frame) == 0:
                raise ValueError(f"nsemine returned no history for {symbol}")
            return records_to_yahoo_frame(frame, default_symbol=symbol)

        return self._execute(run)


def register_adapters(registry: SourceRegistry):
    registry.register(NsemineBhavcopyAdapter())
    registry.register(NseminePriceHistoryAdapter())
