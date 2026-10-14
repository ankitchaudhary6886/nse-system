"""Ingest NSE's own historical price archives (bhavcopy) into prices_daily.

WHY THIS EXISTS
---------------
Until now every price row in this system arrived through Yahoo.  Yahoo is a
third party with its own adjustment rules, its own outages and its own idea of
when a symbol exists.  NSE publishes the same information itself, as a
downloadable end-of-day "bhavcopy" file, and that file is the authoritative
record.  This script walks those archives day by day and upserts the OHLCV
numbers into the existing ``prices_daily`` table, so the system gains a second,
independent source for its most important table.

HOW IT DOWNLOADS
----------------
Downloads are NOT implemented here.  They go through the adapter registry
(``data_sources``), so this script automatically benefits from provider
fallback and health tracking:

    nse_archives  ->  nselib  ->  nsemine  ->  jugaad_data_bhavcopy
                  ->  nse_india_api_bhavcopy

If one library or one URL fails, the next provider is tried.  Whichever one
worked is printed per date, so the run is auditable.

SAFETY RULES OBEYED
-------------------
* We only ever CREATE TABLE IF NOT EXISTS and upsert with INSERT OR REPLACE
  (golden rule 8).  Nothing is ever dropped.
* Network is the enemy of a shared laptop: the default run downloads at most
  5 dates, one every 1.5 seconds, and skips weekends.  Use --limit/--sleep to
  change that deliberately, not accidentally.
* Dates already present in the database are skipped (--force overrides).
* Only symbols the database already tracks are written by default, so a
  bhavcopy's ~2000 rows cannot quietly flood ``prices_daily`` with instruments
  the rest of the system has never heard of.  --symbols all reverses that.

USAGE
-----
    .\\env\\Scripts\\python.exe nse_archive_ingest.py probe
    .\\env\\Scripts\\python.exe nse_archive_ingest.py date 2026-10-13
    .\\env\\Scripts\\python.exe nse_archive_ingest.py backfill --days 30 --limit 5
    .\\env\\Scripts\\python.exe nse_archive_ingest.py range 2026-10-01 2026-10-13
    .\\env\\Scripts\\python.exe nse_archive_ingest.py month 2023-01
    .\\env\\Scripts\\python.exe nse_archive_ingest.py status

Every subcommand accepts --dry-run (download + parse, write nothing),
--symbols existing|stocks|all and --providers a,b,c.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import db
from data_sources import get_registry
from data_sources.core import ProviderFetchError

# Providers are tried in this order for a whole-market bhavcopy download.
# The first is our own parser of NSE's archive file (the most direct route to
# the authoritative data); the rest are independent packages.
DEFAULT_PROVIDERS: Tuple[str, ...] = (
    "nse_archives",
    "nselib",
    "nsemine",
    "jugaad_data_bhavcopy",
    "nse_india_api_bhavcopy",
)

# A date needs at least this many rows before we treat it as "already loaded".
# 50 is far below a real session (hundreds of tracked symbols) but far above a
# half-written crash, so a partial run is retried instead of trusted.
ENOUGH_ROWS_FOR_A_DATE = 50

# Default politeness settings.  NSE blocks scrapers that hammer it.
DEFAULT_SLEEP_SECONDS = 1.5
DEFAULT_LIMIT = 5
INSERT_SQL = ("INSERT OR REPLACE INTO prices_daily "
              "(symbol, date, open, high, low, close, volume) "
              "VALUES (?, ?, ?, ?, ?, ?, ?)")


# ------------------------------------------------------------------ database

def prepare_connection(conn) -> None:
    """Keep SQLite's scratch space in memory.

    WHY: some queries in this script (``SELECT DISTINCT symbol``, ``GROUP BY
    date``) need a sorter.  By default SQLite spills that sorter into a temp
    FILE, and on this shared machine the temp folder is not reliably usable by
    a long-running process -- the query then dies with the very confusing error
    "unable to open database file" even though the database itself is fine.
    Asking SQLite to sort in memory removes that failure mode.  The sets here
    are small (a few thousand symbols), so the memory cost is trivial.

    This only touches the connection this script opened; nothing global.
    """
    try:
        conn.execute("PRAGMA temp_store=MEMORY")
    except Exception:
        # An old SQLite without the pragma is still perfectly usable.
        pass


def ensure_tables(conn) -> None:
    """Create the two tables we touch if they are missing.  Never drops."""
    prepare_connection(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS prices_daily (
        symbol TEXT, date TEXT, open REAL, high REAL, low REAL,
        close REAL, volume REAL,
        PRIMARY KEY (symbol, date))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS price_meta (
        symbol TEXT PRIMARY KEY, last_date TEXT, rows INTEGER,
        updated_at TEXT)""")
    conn.commit()


def existing_symbols(conn) -> Set[str]:
    """Symbols already present in prices_daily -- the default write filter."""
    try:
        return {row[0] for row in conn.execute(
            "SELECT DISTINCT symbol FROM prices_daily")}
    except Exception:
        return set()


def tracked_stock_symbols(conn) -> Set[str]:
    """Symbols in the `stocks` table that are still marked active."""
    try:
        return {row[0] for row in conn.execute(
            "SELECT symbol FROM stocks WHERE active=1")}
    except Exception:
        return set()


def resolve_symbols(conn, mode: str) -> Optional[Set[str]]:
    """Turn --symbols into a set, or None meaning 'accept everything'."""
    if mode == "all":
        return None
    if mode == "stocks":
        return tracked_stock_symbols(conn)
    return existing_symbols(conn)


def rows_on_date(conn, day: str) -> int:
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE date=?", (day,)).fetchone()[0]
    except Exception:
        return 0


def upsert_ohlcv(conn, rows: Iterable[Dict[str, Any]],
                 symbols: Optional[Set[str]] = None) -> int:
    """Write canonical records into prices_daily.  Returns rows sent to SQLite.

    INSERT OR REPLACE means re-running the same day simply rewrites the same
    rows: no duplicates, and a corrected price overwrites the old one.  Because
    a replace is stored internally as delete+insert, this count is "rows
    upserted", not "brand new rows"; the row total is reported separately.
    """
    payload: List[Tuple] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        if symbols is not None and symbol not in symbols:
            continue
        day = str(row.get("date") or "")[:10]
        if not day:
            continue
        try:
            payload.append((
                symbol, day,
                float(row["open"]), float(row["high"]),
                float(row["low"]), float(row["close"]),
                float(row.get("volume") or 0.0),
            ))
        except (KeyError, TypeError, ValueError):
            # A junk row is skipped, never guessed at.
            continue
    if not payload:
        return 0
    conn.executemany(INSERT_SQL, payload)
    conn.commit()
    return len(payload)


def refresh_price_meta(conn, symbols: Iterable[str]) -> int:
    """Recompute price_meta for the symbols we just touched.

    price_meta is what incremental updaters read to decide where to resume, so
    it must never be left stale after a backfill.
    """
    now = dt.datetime.now().isoformat(timespec="seconds")
    touched = sorted({symbol for symbol in symbols if symbol})
    for symbol in touched:
        row = conn.execute(
            "SELECT MAX(date), COUNT(*) FROM prices_daily WHERE symbol=?",
            (symbol,)).fetchone()
        if row and row[0]:
            conn.execute(
                "INSERT OR REPLACE INTO price_meta "
                "(symbol, last_date, rows, updated_at) VALUES (?, ?, ?, ?)",
                (symbol, row[0], row[1], now))
    conn.commit()
    return len(touched)


# ------------------------------------------------------------------- fetching

def fetch_bhavcopy(day: dt.date, providers: Sequence[str] = DEFAULT_PROVIDERS
                   ) -> Tuple[List[Dict[str, Any]], str]:
    """SEAM -- tests monkeypatch this instead of downloading anything.

    Returns (canonical rows, provider name that answered).  Raises
    ProviderFetchError when no provider could deliver.
    """
    result = get_registry().fetch("prices.bhavcopy_daily", providers, day)
    return list(result.data or []), result.provider


def _fetch_with_retry(day: dt.date, providers: Sequence[str],
                      sleep_seconds: float, attempts: int = 3
                      ) -> Tuple[List[Dict[str, Any]], str]:
    """Retry only on the local rate-limit wall, with a growing pause.

    NSE being busy is not retried here on purpose: a real 404 means "holiday or
    not published yet" and hammering it helps nobody.
    """
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return fetch_bhavcopy(day, providers)
        except ProviderFetchError as exc:
            last_error = exc
            if "rate limit" not in str(exc).lower() or attempt == attempts:
                raise
            pause = max(sleep_seconds, 1.0) * 4 * attempt
            print(f"    local rate limit hit; waiting {pause:.1f}s")
            time.sleep(pause)
    raise last_error if last_error else RuntimeError("bhavcopy fetch failed")


# ------------------------------------------------------------------- commands

def ingest_day(conn, day: dt.date, symbols: Optional[Set[str]] = None,
               providers: Sequence[str] = DEFAULT_PROVIDERS,
               dry_run: bool = False, sleep_seconds: float = DEFAULT_SLEEP_SECONDS
               ) -> Dict[str, Any]:
    """Download one date and upsert it.  Returns a small report dictionary."""
    report = {"date": day.isoformat(), "provider": None, "fetched": 0,
              "kept": 0, "upserted": 0, "dry_run": dry_run, "error": None}
    try:
        rows, provider = _fetch_with_retry(day, providers, sleep_seconds)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report
    report["provider"] = provider
    report["fetched"] = len(rows)
    kept = [row for row in rows
            if symbols is None or row.get("symbol") in symbols]
    report["kept"] = len(kept)
    if dry_run or not kept:
        return report
    report["upserted"] = upsert_ohlcv(conn, kept, symbols=None)  # already filtered
    refresh_price_meta(conn, (row["symbol"] for row in kept))
    return report


def _print_report(report: Dict[str, Any]) -> None:
    if report["error"]:
        print(f"  {report['date']}  SKIPPED/FAILED: {report['error']}")
        return
    tag = " (dry run)" if report["dry_run"] else ""
    print(f"  {report['date']}  provider={report['provider']}  "
          f"bhavcopy rows={report['fetched']}  tracked={report['kept']}  "
          f"upserted={report['upserted']}{tag}")


def _is_loaded(conn, day: dt.date) -> bool:
    return rows_on_date(conn, day.isoformat()) >= ENOUGH_ROWS_FOR_A_DATE


def _weekdays(start: dt.date, end: dt.date) -> List[dt.date]:
    days, cursor = [], start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += dt.timedelta(days=1)
    return days


def _run_dates(conn, days: Sequence[dt.date], symbols, providers, dry_run,
               sleep_seconds, limit: Optional[int], force: bool,
               status: Dict[str, int], max_failures: int = 3) -> None:
    """Shared loop: skip loaded dates, respect the limit, sleep politely.

    ``max_failures`` stops the run after that many dates fail IN A ROW.  Without
    it, a blocked or offline NSE would make us try every date in the range and
    every URL for each one -- slow for us and rude to NSE.
    """
    done = 0
    consecutive_failures = 0
    for day in days:
        if limit is not None and done >= limit:
            print(f"  ...download limit ({limit}) reached; stopping")
            break
        if not force and _is_loaded(conn, day):
            status["skipped"] += 1
            continue
        report = ingest_day(conn, day, symbols=symbols, providers=providers,
                            dry_run=dry_run, sleep_seconds=sleep_seconds)
        _print_report(report)
        if report["error"] is None:
            done += 1
            consecutive_failures = 0
            status["dates"] += 1
            status["fetched"] += report["fetched"]
            status["upserted"] += report["upserted"]
        else:
            status["failed"] += 1
            consecutive_failures += 1
            if max_failures and consecutive_failures >= max_failures:
                print(f"  ...{consecutive_failures} dates failed in a row; "
                      "stopping (NSE is probably blocking us or offline)")
                break
        time.sleep(max(0.0, sleep_seconds))


def command_date(conn, args, symbols, providers) -> int:
    status = {"dates": 0, "fetched": 0, "upserted": 0, "skipped": 0, "failed": 0}
    days = []
    for text in args.days:
        days.append(dt.date.fromisoformat(text))
    days = [d for d in days if _weekday_ok(d, args.include_weekends)]
    _run_dates(conn, days, symbols, providers, args.dry_run, args.sleep,
               args.limit, args.force, status, args.max_failures)
    return _summarise(conn, status, args)


def command_range(conn, args, symbols, providers) -> int:
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    if end < start:
        start, end = end, start
    days = _weekdays(start, end)
    if args.include_weekends:
        days = [start + dt.timedelta(days=i)
                for i in range((end - start).days + 1)]
    status = {"dates": 0, "fetched": 0, "upserted": 0, "skipped": 0, "failed": 0}
    _run_dates(conn, days, symbols, providers, args.dry_run, args.sleep,
               args.limit, args.force, status, args.max_failures)
    return _summarise(conn, status, args)


def command_backfill(conn, args, symbols, providers) -> int:
    """Walk backwards from today, downloading only dates we do not have."""
    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    start = end - dt.timedelta(days=max(1, args.days))
    days = list(reversed(_weekdays(start, end)))
    if args.include_weekends:
        days = [start + dt.timedelta(days=i)
                for i in range((end - start).days + 1)][::-1]
    status = {"dates": 0, "fetched": 0, "upserted": 0, "skipped": 0, "failed": 0}
    _run_dates(conn, days, symbols, providers, args.dry_run, args.sleep,
               args.limit, args.force, status, args.max_failures)
    return _summarise(conn, status, args)


def command_month(conn, args, symbols, providers) -> int:
    """Ingest one calendar month.

    Legacy months (before 2024-07-08) USED to come as one monthly zip, but NSE
    has retired that file (verified 2026-10-15: 404 for every month probed), so
    this normally falls straight through to walking the month's weekdays.
    """
    year, month = (int(part) for part in args.month.split("-"))
    first = dt.date(year, month, 1)
    next_month = (dt.date(year + (month == 12), (month % 12) + 1, 1))
    last = next_month - dt.timedelta(days=1)
    status = {"dates": 0, "fetched": 0, "upserted": 0, "skipped": 0, "failed": 0}

    if first < dt.date(2024, 7, 8):
        print(f"  trying the legacy monthly archive for {args.month} "
              "(one file covers the whole month)")
        try:
            result = get_registry().fetch(
                "prices.bhavcopy_monthly",
                ("nse_archives_monthly",), year, month)
            rows = [row for row in (result.data or [])
                    if symbols is None or row.get("symbol") in symbols]
            print(f"  provider={result.provider}  rows in file={len(result.data or [])}"
                  f"  tracked={len(rows)}")
            if rows and not args.dry_run:
                written = upsert_ohlcv(conn, rows)
                refresh_price_meta(conn, (row["symbol"] for row in rows))
                status["upserted"] += written
                status["dates"] = len({row["date"] for row in rows})
                status["fetched"] += len(result.data or [])
            if rows:
                return _summarise(conn, status, args)
            print("  monthly archive gave 0 usable rows; falling back to "
                  "day-by-day")
        except Exception as exc:
            print(f"  monthly archive unavailable "
                  f"({type(exc).__name__}: {exc}); falling back to day-by-day")

    days = _weekdays(first, last)
    _run_dates(conn, days, symbols, providers, args.dry_run, args.sleep,
               args.limit, args.force, status, args.max_failures)
    return _summarise(conn, status, args)


def command_probe(conn, args, symbols, providers) -> int:
    """Report, URL by URL, whether NSE's archive is reachable from this machine.

    This is the honest "is the feed alive?" check: it never writes to the
    database and it shows the exact URL and status of every attempt.
    """
    from data_sources.adapters import nse_archives

    days = [dt.date.fromisoformat(text) for text in args.days] if args.days else []
    if not days:
        cursor = dt.date.today()
        while cursor.weekday() >= 5:
            cursor -= dt.timedelta(days=1)
        days = [cursor]
    exit_code = 0
    for day in days:
        print(f"NSE archive probe for {day.isoformat()} ({day.strftime('%A')}):")
        report = nse_archives.probe_day(day)
        worked = False
        for entry in report:
            marker = "OK " if entry["ok"] else "-- "
            print(f"  {marker}{entry['url']}")
            print(f"      {entry['detail']}"
                  + (f" ({entry['rows']} rows)" if entry["rows"] else ""))
            worked = worked or entry["ok"]
        if not worked:
            print("  RESULT: no URL returned usable data for this date "
                  "(weekend/holiday, not published yet, or blocked).")
            exit_code = 1
        else:
            print("  RESULT: reachable.")
    return exit_code


def command_status(conn, args, symbols, providers) -> int:
    """Show what is in prices_daily right now (no network)."""
    ensure_tables(conn)
    total, symbols_n, first, last = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT symbol), MIN(date), MAX(date) "
        "FROM prices_daily").fetchone()
    print(f"prices_daily: {total:,} rows, {symbols_n:,} symbols, "
          f"{first} -> {last}")
    recent = conn.execute(
        "SELECT date, COUNT(*) FROM prices_daily "
        "GROUP BY date ORDER BY date DESC LIMIT 5").fetchall()
    for day, count in recent:
        print(f"  {day}: {count:,} rows")
    health = get_registry().health()
    print("registered price providers:")
    for item in health:
        if any(dataset.startswith("prices.")
               for dataset in item["datasets"]):
            print(f"  {item['provider']:<26} state={item['state']:<12} "
                  f"datasets={','.join(item['datasets'])}")
    return 0


def _weekday_ok(day: dt.date, include_weekends: bool) -> bool:
    return include_weekends or day.weekday() < 5


def normalise_limit(value) -> Optional[int]:
    """``--limit 0`` means "no limit"; anything unusable also means no limit.

    Kept as a named function (instead of a lambda inside argparse) so the test
    suite can check the rule without opening a database.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _summarise(conn, status: Dict[str, int], args) -> int:
    print(f"  dates={status['dates']} fetched={status['fetched']} "
          f"upserted={status['upserted']} skipped_already_loaded="
          f"{status['skipped']} failed={status['failed']}")
    if not args.dry_run:
        total = conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
        print(f"  prices_daily now holds {total:,} rows")
    return 1 if status["failed"] and not status["dates"] else 0


# ----------------------------------------------------------------------- CLI

def add_common_options(parser: argparse.ArgumentParser) -> None:
    """Add the download-politeness options to one (sub)command parser.

    They live on every subcommand rather than on the top-level parser so the
    natural command order works: ``backfill --days 30 --limit 3``.
    """
    parser.add_argument("--symbols", choices=("existing", "stocks", "all"),
                        default="existing",
                        help="which bhavcopy symbols to write (default: only "
                             "symbols already in prices_daily)")
    parser.add_argument("--providers", default=",".join(DEFAULT_PROVIDERS),
                        help="comma-separated provider order for downloads")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS,
                        help="seconds to wait between downloads (default 1.5)")
    parser.add_argument("--limit", type=normalise_limit, default=DEFAULT_LIMIT,
                        help="maximum NEW dates to download this run "
                             "(default 5; use 0 for no limit)")
    parser.add_argument("--force", action="store_true",
                        help="re-download dates that already look loaded")
    parser.add_argument("--dry-run", action="store_true",
                        help="download and parse but write nothing")
    parser.add_argument("--include-weekends", action="store_true",
                        help="also try Saturday/Sunday (NSE rarely has data)")
    parser.add_argument("--max-failures", type=int, default=3,
                        help="stop after this many dates fail in a row "
                             "(0 = keep trying; default 3)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest NSE historical price archives (bhavcopy) into "
                    "prices_daily.")
    subs = parser.add_subparsers(dest="command")

    p_date = subs.add_parser("date", help="ingest one or more exact dates")
    add_common_options(p_date)
    p_date.add_argument("days", nargs="+", help="YYYY-MM-DD [YYYY-MM-DD ...]")

    p_range = subs.add_parser("range", help="ingest every weekday in a range")
    add_common_options(p_range)
    p_range.add_argument("start", help="YYYY-MM-DD")
    p_range.add_argument("end", help="YYYY-MM-DD")

    p_back = subs.add_parser(
        "backfill", help="walk back from today filling missing weekdays")
    add_common_options(p_back)
    p_back.add_argument("--days", type=int, default=30,
                        help="how many calendar days back to look (default 30)")
    p_back.add_argument("--end", default=None,
                        help="last date to consider (default today)")

    p_month = subs.add_parser("month", help="ingest one calendar month")
    add_common_options(p_month)
    p_month.add_argument("month", help="YYYY-MM")

    p_probe = subs.add_parser(
        "probe", help="check which NSE archive URLs are reachable")
    add_common_options(p_probe)
    p_probe.add_argument("days", nargs="*", help="YYYY-MM-DD (default: last "
                                                 "weekday)")

    p_status = subs.add_parser(
        "status", help="show prices_daily contents and providers")
    add_common_options(p_status)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    providers = tuple(part.strip() for part in args.providers.split(",")
                      if part.strip())

    conn = db.get_conn()          # creates any missing tables via db.SCHEMA
    ensure_tables(conn)
    try:
        if args.command == "status":
            return command_status(conn, args, None, providers)
        symbols = resolve_symbols(conn, args.symbols)
        if symbols is not None:
            print(f"symbol filter: {args.symbols} -> {len(symbols):,} symbols")
        if args.command == "probe":
            return command_probe(conn, args, symbols, providers)
        handlers = {
            "date": command_date,
            "range": command_range,
            "backfill": command_backfill,
            "month": command_month,
        }
        return handlers[args.command](conn, args, symbols, providers)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
