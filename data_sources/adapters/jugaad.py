"""Adapter for the PyPI package ``jugaad-data`` (import ``jugaad_data``).

WHY THIS MODULE EXISTS
----------------------
``jugaad-data`` is a long-lived, widely used NSE/BSE downloader.  Its NSE
history helper returns one tidy DataFrame per symbol, and its archives helper
already knows how to walk NSE's format change (legacy ``cm...bhav.csv.zip``
before 2024-07-08, UDiFF afterwards), including a fallback to NSE's daily
reports API.  That makes it a useful independent route to the SAME official
data, so a change on one path does not blind the system.

WHAT IT RETURNS
---------------
* ``prices.daily_history`` -- yahoo_finance-shaped DataFrame (DatetimeIndex +
  Open/High/Low/Close/Volume).  ``stock_df`` calls its columns
  ``DATE/OPEN/HIGH/LOW/CLOSE/VOLUME``; the shared normaliser maps them.
* ``prices.bhavcopy_daily`` -- canonical records from ``bhavcopy_raw``.

Note: ``jugaad_data.nse.bhavcopy_save(dt, dest)`` is the file-writing sibling
of ``bhavcopy_raw``; we use the raw-text helper because the rest of this
package works from text and never needs a download folder.

CACHE FOLDER FIX (why we set an environment variable)
----------------------------------------------------
jugaad-data pickles every history call into a cache folder.  Its default on
Windows is ``%LOCALAPPDATA%\\nsehistory-stock`` -- outside this project, and on
some machines that folder is not writable, so ``stock_df`` died with
``PermissionError: [WinError 5]`` before it ever reached the network.  jugaad
honours the ``J_CACHE_DIR`` environment variable, so :func:`use_local_cache_dir`
points it at a folder chosen by :func:`nse_archives.cache_directory` (per-user
cache folder, with a project fallback).  An operator who has already set
``J_CACHE_DIR`` keeps their value.

GOLDEN RULE 7
-------------
``jugaad_data`` is imported lazily inside the seams below, so a missing package
cannot break the app.

COST WARNING
------------
``stock_df`` issues one HTTP request per ~100-day chunk.  Keep date ranges
short and let the adapter's 20 calls/minute budget do its job.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from data_sources.adapters.nse_archives import (
    cache_directory,
    parse_bhavcopy_text,
    records_to_yahoo_frame,
)
from data_sources.core import BaseSourceAdapter, SourceRegistry


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def use_local_cache_dir() -> str:
    """Point jugaad-data's disk cache at a writable folder WE chose.

    Returns the cache directory that will be used ("" when none is writable).
    Safe to call repeatedly: an operator-provided ``J_CACHE_DIR`` always wins.
    """
    configured = os.environ.get("J_CACHE_DIR")
    if configured:
        return configured
    folder = cache_directory("jugaad_data")
    if folder:
        os.environ["J_CACHE_DIR"] = folder
    return folder


def fetch_symbol_history(symbol: str, start: Any, end: Any = None,
                         series: str = "EQ"):
    """SEAM -- tests monkeypatch this instead of downloading anything."""
    use_local_cache_dir()
    try:
        from jugaad_data.nse import stock_df
    except ImportError as exc:
        raise RuntimeError(
            "the 'jugaad-data' package is not installed; "
            "run: pip install jugaad-data"
        ) from exc

    start_date = _as_date(start)
    end_date = _as_date(end) if end is not None else date.today()
    # Keyword arguments on purpose: jugaad has renamed these before.
    return stock_df(symbol=symbol, from_date=start_date,
                    to_date=end_date, series=series)


def fetch_bhavcopy_text(day: Any) -> str:
    """SEAM -- raw CSV text of one trading day's bhavcopy."""
    try:
        from jugaad_data.nse import bhavcopy_raw
    except ImportError as exc:
        raise RuntimeError(
            "the 'jugaad-data' package is not installed; "
            "run: pip install jugaad-data"
        ) from exc
    return bhavcopy_raw(_as_date(day))


class JugaadPriceHistoryAdapter(BaseSourceAdapter):
    """One symbol's daily history, via jugaad-data."""

    name = "jugaad_data"
    datasets = ("prices.daily_history",)

    def __init__(self):
        # Lower than the file-based feeds: one call fans out to several
        # chunked HTTP requests inside the library.
        super().__init__(max_calls=20, window_seconds=60)

    def fetch(self, symbol: str, start: Any, end: Any = None):
        def run():
            frame = fetch_symbol_history(symbol, start, end)
            if frame is None or len(frame) == 0:
                raise ValueError(f"jugaad-data returned no history for {symbol}")
            return records_to_yahoo_frame(frame, default_symbol=symbol)

        return self._execute(run)


class JugaadBhavcopyAdapter(BaseSourceAdapter):
    """Whole-market bhavcopy, via jugaad-data's archive walker."""

    name = "jugaad_data_bhavcopy"
    datasets = ("prices.bhavcopy_daily",)

    def __init__(self):
        super().__init__(max_calls=30, window_seconds=60)

    def fetch(self, day: Any):
        target = _as_date(day)

        def run():
            rows = parse_bhavcopy_text(
                fetch_bhavcopy_text(target), default_date=target)
            if not rows:
                raise ValueError(
                    f"jugaad-data returned 0 usable equity rows for {target}")
            return rows

        return self._execute(run)


def register_adapters(registry: SourceRegistry):
    registry.register(JugaadPriceHistoryAdapter())
    registry.register(JugaadBhavcopyAdapter())
