"""Adapter for the PyPI package ``nselib`` (import ``nselib``).

WHY THIS MODULE EXISTS
----------------------
``nselib`` is a pure-downloader library (no fancy objects) whose
``capital_market`` module can hand back the current NSE bhavcopy and the
official security-wise price + volume + DELIVERABLE-position history.  The
delivery figure matters to this system: it is the "did real investors take
delivery, or was it day-trading churn?" number that Top Picks already weighs.

It is the closest thing to a no-frills second opinion on NSE's own files, so
if our hand-rolled archive parser ever trips over a format change, this feed
still works.

WHAT IT RETURNS
---------------
* ``prices.bhavcopy_daily`` -- canonical records (see nse_archives.py).
* ``prices.price_volume_delivery`` -- a DataFrame exactly as nselib returns it
  (columns ``Date, Symbol, Series, OpenPrice, ClosePrice, TotalTradedQuantity,
  DeliverableQty, ...``).  It is deliberately NOT reshaped: callers that want
  delivery data need the extra columns, and the column names are documented
  here so nobody has to guess.

GOLDEN RULE 7
-------------
``nselib`` is imported lazily inside the seams, so the app is unaffected when
the package is absent.

GOTCHA
------
``nselib`` swallows HTTP errors and can return an EMPTY DataFrame instead of
raising.  Empty results are turned into an explicit error below so the
registry can fall through to the next provider instead of caching "no data".
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from data_sources.adapters.nse_archives import normalize_price_records
from data_sources.core import BaseSourceAdapter, SourceRegistry


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _nse_date(value: Any) -> str:
    """nselib wants text dates in ``dd-mm-YYYY`` form."""
    return _as_date(value).strftime("%d-%m-%Y")


def fetch_bhavcopy(day: Any):
    """SEAM -- returns nselib's raw bhavcopy DataFrame (UDiFF columns)."""
    try:
        from nselib import capital_market
    except ImportError as exc:
        raise RuntimeError(
            "the 'nselib' package is not installed; run: pip install nselib"
        ) from exc
    return capital_market.bhav_copy_equities(_nse_date(day))


def fetch_symbol_delivery(symbol: str, start: Any, end: Any = None):
    """SEAM -- price + volume + deliverable-position history for one symbol."""
    try:
        from nselib import capital_market
    except ImportError as exc:
        raise RuntimeError(
            "the 'nselib' package is not installed; run: pip install nselib"
        ) from exc
    end_date = end if end is not None else date.today()
    return capital_market.price_volume_and_deliverable_position_data(
        symbol, from_date=_nse_date(start), to_date=_nse_date(end_date))


class NselibBhavcopyAdapter(BaseSourceAdapter):
    """Whole-market bhavcopy via nselib."""

    name = "nselib"
    datasets = ("prices.bhavcopy_daily",)

    def __init__(self):
        super().__init__(max_calls=30, window_seconds=60)

    def fetch(self, day: Any):
        target = _as_date(day)

        def run():
            frame = fetch_bhavcopy(target)
            if frame is None or len(frame) == 0:
                raise ValueError(f"nselib returned no bhavcopy for {target}")
            # The shared normaliser understands DataFrames as well as CSV text
            # and uses the same alias table, so nselib's UDiFF column names
            # (TckrSymb / ClsPric / ...) are read by one piece of code only.
            rows = normalize_price_records(frame, default_date=target)
            if not rows:
                raise ValueError(
                    f"nselib bhavcopy for {target} had no usable equity rows")
            return rows

        return self._execute(run)


class NselibDeliveryAdapter(BaseSourceAdapter):
    """Price + volume + deliverable-position history via nselib."""

    name = "nselib_delivery"
    datasets = ("prices.price_volume_delivery",)

    def __init__(self):
        super().__init__(max_calls=20, window_seconds=60)

    def fetch(self, symbol: str, start: Any, end: Any = None):
        def run():
            frame = fetch_symbol_delivery(symbol, start, end)
            if frame is None or len(frame) == 0:
                raise ValueError(
                    f"nselib returned no delivery history for {symbol}")
            return frame

        return self._execute(run)


def register_adapters(registry: SourceRegistry):
    registry.register(NselibBhavcopyAdapter())
    registry.register(NselibDeliveryAdapter())
