"""Adapter for the PyPI package ``nse`` (import name ``nse``, class ``NSE``).

WHY THIS MODULE EXISTS
----------------------
``nse`` is the maintained home of the old "NseIndiaApi" project.  It speaks
NSE's own JSON endpoints with the cookie dance and throttling already handled,
which makes it a good second opinion next to Yahoo.  It gives us two things we
want:

  * per-symbol daily OHLCV history (NSE's getHistoricalTradeData endpoint), and
  * the official daily bhavcopy file, saved to disk.

NAME TRAP: the PyPI package is ``nse``, NOT ``nseindiaapi``.  There is no
``nseindiaapi`` package on PyPI, so ``from nse import NSE`` is the correct
import.  (``indianstockmarketapi`` is GitHub-only, not on PyPI.)

WHAT IT RETURNS
---------------
* ``prices.daily_history`` -- a DataFrame shaped exactly like the yahoo_finance
  adapter (DatetimeIndex + Open/High/Low/Close/Volume), so it is a drop-in
  fallback for the existing price ingester.
* ``prices.bhavcopy_daily`` -- canonical records, the same shape every
  bhavcopy provider in this package returns.

GOLDEN RULE 7
-------------
``nse`` is imported lazily inside the fetch helpers, so a missing package can
never break the app: this module still imports in microseconds and the adapter
simply reports "unavailable" when called.

RATE LIMITS
-----------
The adapter allows 30 calls per minute.  ``NSE()`` keeps its cookies in a cache
folder under the OS temp directory so we do not write anything into the repo.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from data_sources.adapters.nse_archives import (
    cache_directory,
    parse_bhavcopy_text,
    records_to_yahoo_frame,
)
from data_sources.core import BaseSourceAdapter, SourceRegistry


def _as_date(value: Any) -> date:
    """Accept a string or a real date; the ``nse`` package wants date objects."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def cache_dir() -> str:
    """Folder ``NSE()`` needs for its cookie store and downloads.

    Chosen by :func:`nse_archives.cache_directory`, which prefers the per-user
    cache folder and falls back to ``data/caches/nse_api`` when the user folder
    is not writable.  We deliberately do NOT let the library pick, because its
    default can be a denied path on locked-down machines.
    """
    folder = cache_directory("nse_api")
    if not folder:
        raise RuntimeError(
            "no writable cache folder for the 'nse' package; set "
            "NSE_ADAPTER_CACHE_DIR to a writable directory")
    return folder


def fetch_symbol_history(symbol: str, start: Any, end: Any = None,
                         series: str = "eq"):
    """SEAM -- tests monkeypatch THIS function instead of hitting the network.

    Returns the list of per-day dictionaries the ``nse`` package produces
    (keys such as ``CH_TIMESTAMP``, ``CH_CLOSING_PRICE``).  The caller turns
    them into canonical records, so this layer stays vendor-shaped on purpose.
    """
    try:
        from nse import NSE
    except ImportError as exc:
        raise RuntimeError(
            "the 'nse' package is not installed; run: pip install nse"
        ) from exc

    start_date = _as_date(start)
    end_date = _as_date(end) if end is not None else date.today()
    with NSE(download_folder=cache_dir()) as client:
        return client.fetch_equity_historical_data(
            symbol, from_date=start_date, to_date=end_date, series=series)


def fetch_bhavcopy_text(day: Any) -> str:
    """SEAM -- download one official daily bhavcopy CSV through ``nse``.

    ``NSE.equity_bhavcopy`` picks the right archive URL for the date (legacy
    or UDiFF) and unzips it, so we get a plain CSV path back.
    """
    try:
        from nse import NSE
    except ImportError as exc:
        raise RuntimeError(
            "the 'nse' package is not installed; run: pip install nse"
        ) from exc

    with NSE(download_folder=cache_dir()) as client:
        path = client.equity_bhavcopy(_as_date(day))
    if path is None:
        raise FileNotFoundError(f"nse package returned no bhavcopy for {day}")
    return Path(path).read_text(encoding="utf-8", errors="ignore")


class NseApiPriceHistoryAdapter(BaseSourceAdapter):
    """Per-symbol daily OHLCV from NSE's own JSON history endpoint."""

    name = "nse_india_api"
    datasets = ("prices.daily_history",)

    def __init__(self):
        super().__init__(max_calls=30, window_seconds=60)

    def fetch(self, symbol: str, start: Any, end: Any = None):
        def run():
            rows = fetch_symbol_history(symbol, start, end)
            if not rows:
                raise ValueError(f"nse package returned no history for {symbol}")
            return records_to_yahoo_frame(rows, default_symbol=symbol)

        return self._execute(run)


class NseApiBhavcopyAdapter(BaseSourceAdapter):
    """Official whole-market bhavcopy downloaded through the ``nse`` package."""

    name = "nse_india_api_bhavcopy"
    datasets = ("prices.bhavcopy_daily",)

    def __init__(self):
        super().__init__(max_calls=30, window_seconds=60)

    def fetch(self, day: Any) -> list:
        target = _as_date(day)

        def run():
            rows = parse_bhavcopy_text(
                fetch_bhavcopy_text(target), default_date=target)
            if not rows:
                raise ValueError(
                    f"nse package returned 0 usable equity rows for {target}")
            return rows

        return self._execute(run)


def register_adapters(registry: SourceRegistry):
    registry.register(NseApiPriceHistoryAdapter())
    registry.register(NseApiBhavcopyAdapter())
