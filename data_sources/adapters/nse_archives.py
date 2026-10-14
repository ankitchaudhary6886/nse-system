"""NSE historical-report archive adapter -- the authoritative bhavcopy feed.

WHY THIS MODULE EXISTS
----------------------
Every price in this system comes from somebody else.  Yahoo (the existing
``yahoo_finance`` adapter) is convenient, but it is a third party that can
change its mind, rate-limit us, or hand back adjusted numbers.  NSE itself
publishes an end-of-day "bhavcopy" (literally "copy of the day's trades") as a
public download in its archives.  That file is the AUTHORITATIVE record of what
NSE printed for that session, so this module reads it directly.

WHERE THE DATA COMES FROM
-------------------------
NSE moved its archive host to ``nsearchives.nseindia.com``.  The older
``archives.nseindia.com`` name still answers for some paths, so both are tried.
The file FORMAT changed on 2024-07-08, and there are four URLs per date:

  1. UDiFF daily bhavcopy  (2024-07-08 onward) -- new short column names
     /content/cm/BhavCopy_NSE_CM_0_0_0_{YYYYMMDD}_F_0000.csv.zip
  2. Legacy daily bhavcopy (before 2024-07-08) -- old long column names
     /content/historical/EQUITIES/{YYYY}/{MMM}/cm{DDMMMYYYY}bhav.csv.zip
  3. Legacy monthly bhavcopy -- historically ONE file per calendar month with
     every trading day of that month inside it
     /content/historical/EQUITIES/{YYYY}/{MMM}/cm{MMMYYYY}bhav.csv.zip
     HONEST STATUS (verified 2026-10-15): NSE no longer serves this file.  Both
     hosts return 404 for every month tried (2019, 2021, 2022, 2023, 2024 and
     the current month).  The parser and adapter are kept because the format is
     real and may return, but treat the monthly feed as best-effort: the daily
     URLs above are the reliable route, and nse_archive_ingest.py falls back to
     day-by-day automatically when the monthly download fails.
  4. sec_bhavdata_full_{DDMMYYYY}.csv -- plain CSV (no zip) with OHLC + traded
     quantity.  Last-resort fallback; it is the same file delivery.py reads.

All four are parsed by ONE parser, because column names are matched by alias
(``TckrSymb`` == ``SYMBOL`` == ``CH_SYMBOL``) instead of by position.

THE TWO CANONICAL SHAPES (the contract for every feed in this package)
---------------------------------------------------------------------
* Bhavcopy providers return a plain list of dictionaries:

      {"symbol": "RELIANCE", "date": "2024-07-08", "open": 2500.0,
       "high": 2550.0, "low": 2490.0, "close": 2540.0, "volume": 5000000.0}

* Symbol-history providers return a pandas DataFrame shaped EXACTLY like the
  yahoo_finance adapter (a DatetimeIndex plus Open/High/Low/Close/Volume), so
  ingest_prices.py can add these provider names to its fallback tuple without
  any code change.  ``records_to_yahoo_frame`` does that conversion.

Both normalising helpers live here and are shared by the sibling adapters, so
there is exactly one place where NSE's many spellings of "close price" are
understood.

GOLDEN RULE 7 (the UI must never blank)
---------------------------------------
``requests`` and ``pandas`` are imported lazily INSIDE the functions that need
them.  Importing this module is therefore free and safe; if a package is
missing, the adapter reports "unavailable" through the normal health path
instead of taking the app down.

RATE LIMITS
-----------
NSE throttles and blocks scrapers.  The adapter defaults to 45 calls per
60 seconds and does one download per date; nse_archive_ingest.py additionally
sleeps between dates.  Never call this in a tight loop.
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

from data_sources.core import BaseSourceAdapter, SourceRegistry

# ---------------------------------------------------------------- constants

# India Standard Time.  NSE trading dates are IST dates, and several vendor
# libraries hand back an INSTANT (a UTC timestamp of IST midnight) instead of a
# plain date, so this offset is what turns "2026-10-12 18:30" back into the
# correct trading date 2026-10-13.  Getting this wrong shifts every row by one
# day, which is the kind of silent error that ruins a backtest.
IST = timezone(timedelta(hours=5, minutes=30))

# NSE serves the archives from here.  Both hosts are tried; the first is the
# current one and the second keeps working for a few legacy paths.
ARCHIVE_HOSTS = (
    "https://nsearchives.nseindia.com",
    "https://archives.nseindia.com",
)

# 2024-07-08 is the day NSE switched the bhavcopy to the new "UDiFF" format.
UDIFF_SWITCH_DATE = date(2024, 7, 8)

# Only these trading series belong in a price database.  "EQ" is the normal
# rolling-settlement series; BE/BZ are trade-for-trade series of the same
# companies.  Everything else (bonds, ETFs-only series, derivatives) is skipped.
EQUITY_SERIES = ("EQ", "BE", "BZ")

# UDiFF marks ordinary stocks with FinInstrmTp = STK.
EQUITY_INSTRUMENT_TYPE = "STK"

REQUEST_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


# --------------------------------------------------- shared machine-local cache

# Cache folders are remembered for the life of the process so we only run the
# write probe once per feed.
_CACHE_DIRS: Dict[str, str] = {}


def _is_writable(path: str) -> bool:
    """Create the folder and write+delete a probe file.  Never raises."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".write_probe")
        with open(probe, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


def cache_directory(name: str) -> str:
    """Return a writable, machine-local cache folder for one feed.

    WHY THIS EXISTS: two of the packages we wrap insist on a cache folder
    (``nse`` stores its NSE cookies there, jugaad-data pickles every history
    call).  Their defaults live under the per-user app-data folder, which is
    normally right -- but on a locked-down machine that folder can be denied,
    and the package then fails with a raw PermissionError.  Vendors are also
    not allowed to decide where OUR files go, so we choose:

      1. ``$NSE_ADAPTER_CACHE_DIR/<name>`` if the operator set that variable,
      2. the per-user cache folder (``%LOCALAPPDATA%`` / ``~/.cache``),
      3. ``<project>/data/caches/<name>`` as a last resort for restricted
         environments (that folder is machine-local and regenerable).

    Returns "" when nothing is writable, so the caller can raise a clear error
    instead of letting a confusing permission traceback escape.
    """
    if name in _CACHE_DIRS:
        return _CACHE_DIRS[name]

    candidates: List[str] = []
    override = os.environ.get("NSE_ADAPTER_CACHE_DIR")
    if override:
        candidates.append(os.path.join(override, name))
    home_cache = (os.environ.get("LOCALAPPDATA")
                  or os.environ.get("XDG_CACHE_HOME")
                  or os.path.join(os.path.expanduser("~"), ".cache"))
    candidates.append(os.path.join(home_cache, "nse_system", name))
    project_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    candidates.append(os.path.join(project_root, "data", "caches", name))

    for candidate in candidates:
        if _is_writable(candidate):
            _CACHE_DIRS[name] = candidate
            return candidate
    _CACHE_DIRS[name] = ""
    return ""


# ------------------------------------------------------- small text helpers

def _key(name: Any) -> str:
    """Column name -> a comparable key: lowercase, letters and digits only.

    NSE pads header cells with spaces (" SYMBOL"), mixes case and uses both
    ``DATE1`` and ``TradDt`` for the same idea.  Stripping everything except
    letters and digits makes those spellings comparable.
    """
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


# Field name -> every vendor spelling we have seen for it.  Exact matching on
# the cleaned key (no substring guessing, which could confuse LASTPric with
# ClsPric).
_ALIASES: Dict[str, Sequence[str]] = {
    "symbol": ("tckrsymb", "symbol", "chsymbol", "symbolname"),
    "date": ("traddt", "date1", "timestamp", "chtimestamp", "mtimestamp",
             "date", "datetime"),
    "open": ("opnpric", "open", "openprice", "chopeningprice"),
    "high": ("hghpric", "high", "highprice", "chtradehighprice"),
    "low": ("lwpric", "low", "lowprice", "chtradelowprice"),
    "close": ("clspric", "close", "closeprice", "chclosingprice"),
    "volume": ("ttltradgvol", "tottrdqty", "ttltrdqnty", "chtottradedqty",
               "volume", "totaltradedquantity"),
    "series": ("sctysrs", "series", "chseries"),
    "instrument_type": ("fininstrmtp", "instrumenttype"),
}

_DATE_FORMATS = (
    "%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y", "%d%b%Y", "%d%b%y",
    "%d-%m-%Y", "%d/%m/%Y", "%d-%B-%Y", "%Y/%m/%d", "%Y%m%d",
)

# Full timestamp spellings some vendors return when a value carries a time.
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%Y/%m/%d %H:%M:%S",
)


def _field(record: Dict[str, Any], name: str) -> Any:
    """Read one logical field from a vendor row using the alias table."""
    wanted = _ALIASES[name]
    for raw_key, value in record.items():
        if _key(raw_key) in wanted:
            return value
    return None


def _trading_date_from_instant(value: Any) -> str:
    """An instant (datetime) -> the IST trading date it belongs to.

    Vendors disagree about how to store a trading date: some give a plain date,
    some give an IST-midnight instant expressed in UTC (jugaad-data returns
    ``2026-10-12 18:30`` for the session of 2026-10-13), and nsemine gives epoch
    milliseconds.  Converting to IST first makes all of them agree.
    """
    if getattr(value, "tzinfo", None) is not None:
        try:
            return value.astimezone(IST).date().isoformat()
        except Exception:
            pass
    return (value + timedelta(hours=5, minutes=30)).date().isoformat()


def _parse_datetime_text(text: str) -> Optional[datetime]:
    """Parse a ``date time`` string, downsizing nanosecond precision first."""
    candidates = [text]
    if len(text) > 26:
        candidates.append(text[:26])       # numpy prints 9-digit nanoseconds
    for candidate in candidates:
        for fmt in _DATETIME_FORMATS:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def parse_nse_date(value: Any) -> Optional[str]:
    """Turn any NSE date spelling into an ISO ``YYYY-MM-DD`` string.

    Handles plain dates (``2024-07-08``, ``08-JUL-2024``, ``02-Jan-2023``,
    ``02JAN2023``) and full instants (datetime objects, pandas Timestamps,
    ``2026-10-12 18:30:00``).  Instants are converted to IST before the date is
    taken, because a UTC instant of IST midnight belongs to the NEXT day.

    Returns None when the value cannot be understood -- the caller then decides
    what to do; nothing is ever guessed.
    """
    if value is None:
        return None
    if isinstance(value, datetime):          # includes pandas Timestamp
        return _trading_date_from_instant(value)
    if isinstance(value, date):
        return value.isoformat()
    # numpy datetime64 and similar objects: try .date() where it exists.
    if hasattr(value, "date") and not isinstance(value, str):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    text = str(value).strip()
    if not text or text.lower() in ("nan", "nat", "none", "-"):
        return None

    # A value carrying a TIME is an instant -> shift to IST.  A value without a
    # time is already the trading date, so it is used exactly as printed.
    body = text.replace("T", " ").strip()
    head, _, tail = body.partition(" ")
    if tail.strip():
        stamp = _parse_datetime_text(body)
        if stamp is not None:
            return _trading_date_from_instant(stamp)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(head, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> Optional[float]:
    """NSE numbers arrive as text with thousands separators, or as '-'."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        out = float(value)
        return out if out == out else None          # NaN check without numpy
    text = str(value).strip().replace(",", "")
    if not text or text in ("-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean_symbol(value: Any) -> Optional[str]:
    """Normalise a ticker; drop the junk rows the universe also filters out."""
    if value is None:
        return None
    symbol = str(value).strip().upper()
    if not symbol or symbol in ("NAN", "NONE", "-"):
        return None
    # Same rule as the existing delivery.py scanner: NSE pads some rows with a
    # trailing '$' or an embedded space for special instruments.
    if "$" in symbol or " " in symbol:
        return None
    return symbol


def _as_records(records: Any) -> List[Dict[str, Any]]:
    """Accept a DataFrame, a single dict, or a list of dicts uniformly."""
    if records is None:
        return []
    if hasattr(records, "to_dict"):                 # pandas DataFrame
        try:
            return list(records.to_dict("records"))
        except Exception:
            return []
    if isinstance(records, dict):
        return [records]
    return [row for row in records if isinstance(row, dict)]


# --------------------------------------------------------------- normalising

def normalize_price_records(
    records: Any,
    default_date: Any = None,
    series: Optional[Sequence[str]] = EQUITY_SERIES,
    default_symbol: Any = None,
) -> List[Dict[str, Any]]:
    """Vendor rows -> the canonical OHLCV record list.

    This is the single place where all the NSE column spellings are untangled,
    so every adapter (nselib, nsemine, jugaad, pnsea, the ``nse`` package)
    goes through it and the ingest CLI only ever sees one shape.

    ``default_date`` is used by files that carry the date once in the filename
    (for example the daily sec_bhavdata_full CSV) rather than in every row, and
    ``default_symbol`` by single-symbol history feeds whose frames do not repeat
    the ticker in every row (nsemine's chart feed is one of those).

    Rows whose date, symbol or prices cannot be read are skipped, never
    invented.  Duplicate (symbol, date) pairs keep the LAST row seen.
    """
    out: Dict[tuple, Dict[str, Any]] = {}
    for record in _as_records(records):
        symbol = _clean_symbol(_field(record, "symbol"))
        if symbol is None:
            symbol = _clean_symbol(default_symbol)
        if symbol is None:
            continue

        if series is not None:
            row_series = _field(record, "series")
            if row_series is not None:
                row_series = str(row_series).strip().upper()
                if row_series and row_series not in tuple(series):
                    continue

        instrument = _field(record, "instrument_type")
        if instrument is not None:
            instrument = str(instrument).strip().upper()
            if instrument and instrument != EQUITY_INSTRUMENT_TYPE:
                continue

        day = parse_nse_date(_field(record, "date"))
        if day is None:
            day = parse_nse_date(default_date)
        if day is None:
            continue

        open_ = _to_float(_field(record, "open"))
        high = _to_float(_field(record, "high"))
        low = _to_float(_field(record, "low"))
        close = _to_float(_field(record, "close"))
        volume = _to_float(_field(record, "volume"))
        if close is None or open_ is None or high is None or low is None:
            continue

        out[(symbol, day)] = {
            "symbol": symbol,
            "date": day,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 0.0 if volume is None else volume,
        }
    return sorted(out.values(), key=lambda row: (row["date"], row["symbol"]))


def records_to_yahoo_frame(records: Any, default_symbol: Any = None):
    """Canonical records -> the exact DataFrame shape yahoo_finance returns.

    ingest_prices.py reads ``df.index`` plus the columns ``Open``, ``High``,
    ``Low``, ``Close``, ``Volume``.  Producing that same shape here means any
    provider in this package can be dropped into the existing fallback tuple
    with no consumer-side change.  pandas is imported lazily (golden rule 7).

    ``default_symbol`` fills in the ticker for single-symbol vendor frames that
    do not repeat it in every row.
    """
    try:
        import pandas as pd
    except ImportError as exc:                      # pragma: no cover - guarded
        raise RuntimeError(
            "pandas is required to build a price frame; install pandas"
        ) from exc

    raw_rows = _as_records(records)
    rows = normalize_price_records(records, default_symbol=default_symbol)
    if not rows:
        if raw_rows:
            # The vendor DID send rows but none carried a usable symbol, date
            # and price.  Returning an empty frame would look like success and
            # the registry would stop trying other providers, so fail loudly.
            raise ValueError(
                "vendor returned rows but none contained a usable "
                "symbol/date/price combination")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    frame = pd.DataFrame(rows)
    frame = frame.rename(columns={"open": "Open", "high": "High",
                                  "low": "Low", "close": "Close",
                                  "volume": "Volume"})
    frame.index = pd.to_datetime(frame["date"])
    frame.index.name = "Date"
    return frame[["Open", "High", "Low", "Close", "Volume"]].sort_index()


# ------------------------------------------------------------------- parsing

def parse_bhavcopy_text(
    text: str,
    default_date: Any = None,
    series: Optional[Sequence[str]] = EQUITY_SERIES,
) -> List[Dict[str, Any]]:
    """Parse the CSV body of ANY NSE bhavcopy flavour into canonical records.

    Format is detected from the header through the alias table, so the same
    function handles UDiFF, the legacy ``cm...bhav.csv`` file and
    ``sec_bhavdata_full``.  Returns an empty list for empty/garbage input
    instead of raising, because NSE sometimes serves a HTML error page.
    """
    if not text or not text.strip():
        return []
    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    try:
        rows = list(reader)
    except csv.Error:
        return []
    return normalize_price_records(rows, default_date=default_date, series=series)


def decode_archive(content: bytes) -> str:
    """Turn downloaded bytes into text, unzipping when the body is a zip.

    NSE serves bhavcopy as a zip and sec_bhavdata_full as plain CSV, and both
    arrive with the same ``.csv``-ish name, so sniff the magic bytes instead of
    trusting the URL.
    """
    if content[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = [name for name in archive.namelist()
                     if name.lower().endswith(".csv")]
            if not names:
                names = archive.namelist()
            if not names:
                raise ValueError("zip archive contains no files")
            return archive.read(names[0]).decode("utf-8", errors="ignore")
    return content.decode("utf-8", errors="ignore")


def _require_requests():
    """Lazy import so a missing package can never break the app (rule 7)."""
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError(
            "requests is not installed, so NSE archives cannot be downloaded; "
            "run: pip install requests"
        ) from exc
    return requests


def download(url: str, timeout: int = 30) -> bytes:
    """Fetch one archive URL.  Scripts/tests monkeypatch THIS function."""
    requests = _require_requests()
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    if response.status_code == 404:
        # Normal and expected on weekends/holidays and before NSE publishes.
        raise FileNotFoundError(f"{url} -> 404 (holiday or not published yet)")
    response.raise_for_status()
    if not response.content:
        raise ValueError(f"{url} returned an empty body")
    return response.content


def _as_date(value: Any) -> date:
    """Coerce a str/date/datetime into a ``date`` for URL building."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_nse_date(value)
    if parsed is None:
        raise ValueError(f"not a date: {value!r}")
    return date.fromisoformat(parsed)


# ------------------------------------------------------------- URL building

def daily_bhavcopy_urls(day: date, hosts: Sequence[str] = ARCHIVE_HOSTS
                        ) -> List[str]:
    """Every URL worth trying for one trading day, in preference order."""
    day = _as_date(day)
    urls: List[str] = []
    if day >= UDIFF_SWITCH_DATE:
        name = f"BhavCopy_NSE_CM_0_0_0_{day.strftime('%Y%m%d')}_F_0000.csv.zip"
        for host in hosts:
            urls.append(f"{host}/content/cm/{name}")
    else:
        stamp = day.strftime("%d%b%Y").upper()       # e.g. 02JAN2023
        month = stamp[2:5]                           # e.g. JAN
        name = f"cm{stamp}bhav.csv.zip"
        for host in hosts:
            urls.append(
                f"{host}/content/historical/EQUITIES/{day.year}/{month}/{name}")
    # The plain-CSV delivery file also carries OHLCV and needs no unzip.
    for host in hosts:
        urls.append(f"{host}/products/content/"
                    f"sec_bhavdata_full_{day.strftime('%d%m%Y')}.csv")
    return urls


def monthly_bhavcopy_urls(year: int, month: int,
                          hosts: Sequence[str] = ARCHIVE_HOSTS) -> List[str]:
    """Every URL worth trying for one calendar month of legacy bhavcopy."""
    month_name = date(year, month, 1).strftime("%b").upper()
    name = f"cm{month_name}{year}bhav.csv.zip"
    return [f"{host}/content/historical/EQUITIES/{year}/{month_name}/{name}"
            for host in hosts]


# ------------------------------------------------------------------- fetching

def _first_working_rows(urls: Iterable[str], parser, timeout: int,
                        opener=download) -> List[Dict[str, Any]]:
    """Try each URL until one yields rows; report every failure honestly."""
    errors: List[str] = []
    for url in urls:
        try:
            text = decode_archive(opener(url, timeout))
        except Exception as exc:
            errors.append(f"{url} -> {type(exc).__name__}: {exc}")
            continue
        rows = parser(text)
        if rows:
            return rows
        errors.append(f"{url} -> downloaded but parsed 0 equity rows")
    detail = "; ".join(errors[-4:]) if errors else "no URLs were tried"
    raise RuntimeError(f"no usable NSE archive ({detail})")


def fetch_bhavcopy_day(day: Any, hosts: Sequence[str] = ARCHIVE_HOSTS,
                       timeout: int = 30, opener=None
                       ) -> List[Dict[str, Any]]:
    """Download and parse one trading day's whole-market bhavcopy.

    Raises RuntimeError when no URL works, so the registry can fall through to
    the next provider.  Rows are filtered to the requested date: if NSE serves
    a file for a different day (which happens after rule changes) we would
    rather fail loudly than write mis-dated prices.

    ``opener`` defaults to :func:`download` resolved at call time, so tests can
    replace the network with an in-memory function.
    """
    day = _as_date(day)
    wanted = day.isoformat()
    opener = opener or download

    def parse(text: str) -> List[Dict[str, Any]]:
        return parse_bhavcopy_text(text, default_date=day)

    rows = _first_working_rows(
        daily_bhavcopy_urls(day, hosts), parse, timeout, opener)
    matching = [row for row in rows if row["date"] == wanted]
    if not matching:
        seen = sorted({row["date"] for row in rows})[:3]
        raise RuntimeError(
            f"{wanted}: downloaded archive carried dates {seen}, not {wanted}")
    return matching


def fetch_bhavcopy_month(year: int, month: int,
                         hosts: Sequence[str] = ARCHIVE_HOSTS,
                         timeout: int = 60, opener=None
                         ) -> List[Dict[str, Any]]:
    """Download one legacy monthly bhavcopy (many sessions in a single file).

    Monthly files only ever existed for the legacy era, and as of 2026-10-15
    NSE returns 404 for every month we probed, so this is a best-effort route:
    callers should fall back to day-by-day downloads (nse_archive_ingest.py's
    ``month`` command does exactly that).
    """
    opener = opener or download

    def parse(text: str) -> List[Dict[str, Any]]:
        return parse_bhavcopy_text(text)

    return _first_working_rows(
        monthly_bhavcopy_urls(year, month, hosts), parse, timeout, opener)


def probe_day(day: Any, hosts: Sequence[str] = ARCHIVE_HOSTS,
              timeout: int = 20, opener=None) -> List[Dict[str, Any]]:
    """Try EVERY archive URL for one date and report what each one did.

    Used by ``nse_archive_ingest.py probe`` to answer the honest question
    "is this feed actually reachable from this machine right now?" without
    writing anything.  Each entry is::

        {"url": ..., "ok": bool, "rows": int, "detail": str}
    """
    day = _as_date(day)
    opener = opener or download
    report: List[Dict[str, Any]] = []
    for url in daily_bhavcopy_urls(day, hosts):
        entry: Dict[str, Any] = {"url": url, "ok": False, "rows": 0,
                                 "detail": ""}
        try:
            text = decode_archive(opener(url, timeout))
            rows = parse_bhavcopy_text(text, default_date=day)
            entry["rows"] = len(rows)
            entry["ok"] = bool(rows)
            entry["detail"] = "parsed OK" if rows else "parsed 0 equity rows"
        except Exception as exc:
            entry["detail"] = f"{type(exc).__name__}: {exc}"
        report.append(entry)
    return report


# ------------------------------------------------------------------ adapters

class NseArchiveBhavcopyAdapter(BaseSourceAdapter):
    """Daily whole-market bhavcopy straight from NSE's own archive."""

    name = "nse_archives"
    datasets = ("prices.bhavcopy_daily",)

    def __init__(self):
        # 45 downloads a minute is already aggressive for NSE; the ingest CLI
        # also sleeps between dates.  Do not raise this casually.
        super().__init__(max_calls=45, window_seconds=60)

    def fetch(self, day, hosts=None, timeout=30, opener=None):
        target = _as_date(day)
        return self._execute(lambda: fetch_bhavcopy_day(
            target, hosts=hosts or ARCHIVE_HOSTS, timeout=timeout,
            opener=opener))


class NseArchiveMonthlyBhavcopyAdapter(BaseSourceAdapter):
    """Legacy monthly bhavcopy: one download would cover ~20 sessions.

    Kept registered even though NSE currently 404s every monthly URL we probed
    (see the module docstring): the health panel then shows the failure
    honestly, and the ingest CLI falls back to day-by-day downloads.
    """

    name = "nse_archives_monthly"
    datasets = ("prices.bhavcopy_monthly",)

    def __init__(self):
        super().__init__(max_calls=15, window_seconds=60)

    def fetch(self, year, month, hosts=None, timeout=60, opener=None):
        return self._execute(lambda: fetch_bhavcopy_month(
            int(year), int(month), hosts=hosts or ARCHIVE_HOSTS,
            timeout=timeout, opener=opener))


def register_adapters(registry: SourceRegistry):
    registry.register(NseArchiveBhavcopyAdapter())
    registry.register(NseArchiveMonthlyBhavcopyAdapter())
