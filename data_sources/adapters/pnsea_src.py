"""Adapter for the PyPI package ``pnsea`` (import ``pnsea``).

WHY THIS MODULE EXISTS
----------------------
``pnsea`` is a small "nsepy-style" wrapper: one object tree
(``NSE().equity``) over NSE's website endpoints, with a stealth HTTP session
that fetches the cookies NSE demands.  It reaches NSE's
``getHistoricalTradeData`` endpoint -- the same authoritative source the
``nse`` package uses but through a completely separate implementation -- which
makes it a genuinely independent fallback rather than a rewrap.

It can also pull price + volume + DELIVERABLE-position history
(``equity.delivery_history``), which is the delivery-conviction data Top Picks
uses.  That call is exposed here as a dataset too.

WHAT IT RETURNS
---------------
* ``prices.daily_history`` -- yahoo_finance-shaped DataFrame.
* ``prices.price_volume_delivery`` -- pnsea's own renamed frame
  (``Date, Open, High, Low, Close, Volume, Delivery_Qty, Delivery_Pct, VWAP``).

GOLDEN RULE 7
-------------
``pnsea`` (and its ``stealthkit`` dependency) is imported lazily inside the
seams.  If either is missing the adapter simply reports unavailable.

DATE FORMAT WARNING
-------------------
pnsea passes dates straight into query strings and its own helpers expect
``dd-mm-YYYY`` text.  We convert here so the rest of the system can keep using
plain ``date`` objects and ISO strings.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from data_sources.adapters.nse_archives import records_to_yahoo_frame
from data_sources.core import BaseSourceAdapter, SourceRegistry


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _nse_date(value: Any) -> str:
    """pnsea wants ``dd-mm-YYYY`` text, not ISO."""
    return _as_date(value).strftime("%d-%m-%Y")


def _client():
    """Build a pnsea NSE client (lazy import; also used by the tests' seam)."""
    try:
        from pnsea import NSE
    except ImportError as exc:
        raise RuntimeError(
            "the 'pnsea' package is not installed; run: pip install pnsea"
        ) from exc
    return NSE()


def fetch_symbol_history(symbol: str, start: Any, end: Any = None,
                         series: str = "EQ"):
    """SEAM -- pnsea historical trade data for one symbol."""
    end_date = end if end is not None else date.today()
    client = _client()
    return client.equity.history(
        symbol, from_date=_nse_date(start), to_date=_nse_date(end_date),
        series=series)


def fetch_symbol_delivery(symbol: str, start: Any, end: Any = None,
                          series: str = "EQ"):
    """SEAM -- pnsea price + volume + deliverable position history."""
    end_date = end if end is not None else date.today()
    client = _client()
    return client.equity.delivery_history(
        symbol, from_date=_nse_date(start), to_date=_nse_date(end_date),
        series=series)


class PnseaPriceHistoryAdapter(BaseSourceAdapter):
    """Daily history for one symbol via pnsea."""

    name = "pnsea"
    datasets = ("prices.daily_history",)

    def __init__(self):
        # pnsea/NSE are cookie-hungry; keep the budget modest.
        super().__init__(max_calls=20, window_seconds=60)

    def fetch(self, symbol: str, start: Any, end: Any = None):
        def run():
            frame = fetch_symbol_history(symbol, start, end)
            if frame is None or len(frame) == 0:
                raise ValueError(f"pnsea returned no history for {symbol}")
            return records_to_yahoo_frame(frame, default_symbol=symbol)

        return self._execute(run)


class PnseaDeliveryAdapter(BaseSourceAdapter):
    """Price + volume + delivery history for one symbol via pnsea."""

    name = "pnsea_delivery"
    datasets = ("prices.price_volume_delivery",)

    def __init__(self):
        super().__init__(max_calls=20, window_seconds=60)

    def fetch(self, symbol: str, start: Any, end: Any = None):
        def run():
            frame = fetch_symbol_delivery(symbol, start, end)
            if frame is None or len(frame) == 0:
                raise ValueError(
                    f"pnsea returned no delivery history for {symbol}")
            return frame

        return self._execute(run)


def register_adapters(registry: SourceRegistry):
    registry.register(PnseaPriceHistoryAdapter())
    registry.register(PnseaDeliveryAdapter())
