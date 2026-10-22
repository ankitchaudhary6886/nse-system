"""Corporate actions: the free book behind every adjusted-vs-raw price seam.

WHY: stored history is yfinance ``auto_adjust=True`` (split/dividend adjusted)
while the Fyers feed is raw. The ingest guards can only block or flag a seam;
with a corporate-action record they can name the event and repair the series.
So the book is built from free sources only: a manual CSV (the one source
allowed to claim a fact), yfinance's split/dividend LISTS (its prices are
distrusted, the event list is still a useful candidate) and unexplained gaps in
our own stored closes.

A gap is a CANDIDATE, never a fact: -25% may be a demerger, a disclosure or a
data error, which is why an unmatched ratio becomes
``kind_guess='unknown_event'`` and only the CSV path writes 'confirmed_source'.

``ratio`` is the multiplier applied to HISTORY prices (1:10 split -> 10.0, 1:1
bonus -> 2.0); dividends carry ratio NULL and ``amount`` = rupees per share.
Status: confirmed_source | unconfirmed | rejected.
"""
import argparse
import csv
import datetime as dt
import json
import math
import re
import time
from typing import Any, Dict, List, Optional

from data_sources import fetch_yahoo_field

KINDS = ("split", "bonus", "dividend", "rights", "demerger")
RATIO_KINDS = ("split", "bonus", "rights")   # history prices *= ratio
COMMON_RATIOS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 20.0)
DEFAULT_MIN_GAP = 0.15        # the same 15% the ingest guards call a seam
CSV_COLUMNS = ("symbol", "ex_date", "kind", "ratio", "amount")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9&.\-]{0,19}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FIELDS = ("symbol", "ex_date", "kind", "ratio", "amount", "source", "status",
           "recorded_at", "raw")
_SELECT = "SELECT " + ", ".join(_FIELDS) + " FROM corporate_actions"
_INSERT = ("INSERT OR REPLACE INTO corporate_actions(" + ", ".join(_FIELDS) +
           ") VALUES (" + ",".join("?" * len(_FIELDS)) + ")")


def now_ist() -> str:
    """recorded_at is read in IST, so it is stored in IST."""
    return dt.datetime.now(IST).replace(microsecond=0).isoformat(sep=" ")


# --- validators: bad data becomes None, never an exception -----------------

def _clean_symbol(value: Any) -> Optional[str]:
    """Upper-case a ticker, or None when it could not be one (spaces, '$')."""
    text = str(value).strip().upper() if value is not None else ""
    return text if _SYMBOL_RE.match(text) else None


def _parse_date(value: Any) -> Optional[str]:
    """Strict YYYY-MM-DD only; anything else is a skip, never a guess."""
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value.isoformat()
    text = str(value).strip() if value is not None else ""
    if not _DATE_RE.match(text):
        return None
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _to_float(value: Any) -> Optional[float]:
    """float or None; blanks, NaN, inf, rupee signs and junk all become None."""
    text = str(value).replace(",", "").replace("\u20b9", "").strip() \
        if value is not None else ""
    try:
        number = float(text)
    except ValueError:
        return None
    return number if text and math.isfinite(number) else None


def _nearest_ratio(value: float) -> Optional[float]:
    """Nearest COMMON_RATIOS entry within 5% of `value`, else None."""
    if not value or not math.isfinite(value):
        return None
    best = min(COMMON_RATIOS, key=lambda ratio: abs(value - ratio))
    return best if abs(value - best) / best <= 0.05 else None


def _action_from_dict(action: Any) -> Optional[Dict[str, Any]]:
    """Normalise one action dict (from fetch, CSV or another script)."""
    if not isinstance(action, dict):
        return None
    symbol, ex_date = _clean_symbol(action.get("symbol")), _parse_date(
        action.get("ex_date"))
    kind = str(action.get("kind") or "").strip().lower()
    ratio, amount = _to_float(action.get("ratio")), _to_float(action.get("amount"))
    if not symbol or ex_date is None or kind not in KINDS:
        return None
    if kind in RATIO_KINDS and (ratio is None or ratio <= 0):
        return None      # a split/bonus/rights without a ratio is unusable
    if kind == "dividend":
        if amount is None or amount <= 0:
            return None  # a dividend without rupees-per-share is unusable
        ratio = None
    raw = action.get("raw")
    return {"symbol": symbol, "ex_date": ex_date, "kind": kind,
            "ratio": ratio if ratio is not None and ratio > 0 else None,
            "amount": amount if amount is not None and amount > 0 else None,
            "source": str(action.get("source") or "manual").strip(),
            "status": (str(action.get("status") or "unconfirmed").strip()
                       or "unconfirmed"),
            "recorded_at": action.get("recorded_at") or now_ist(),
            "raw": raw if raw is None or isinstance(raw, str)
            else json.dumps(raw, default=str)}


def _insert(conn, action: Dict[str, Any]) -> None:
    conn.execute(_INSERT, tuple(action[field] for field in _FIELDS))


# --- 1. manual CSV: the only source allowed to claim a fact ----------------

def import_csv(conn, path) -> dict:
    """Load a hand-maintained CSV; bad rows are skipped and counted.

    A missing header raises, because a file without the columns cannot be
    interpreted at all. Everything imported here is 'confirmed_source': a human
    read the ratio off the exchange filing, which is the one claim we act on.
    """
    path = str(path)
    out = {"file": path, "rows_seen": 0, "imported": 0, "skipped": 0,
           "by_kind": {}}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{path}: empty file; a header row is required")
        cols = {name.strip().lower(): i for i, name in enumerate(header)}
        missing = [column for column in CSV_COLUMNS if column not in cols]
        if missing:
            raise ValueError(f"{path}: missing column(s) {missing}; "
                             f"header must contain {list(CSV_COLUMNS)}")
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue                    # a blank line is not a row attempt
            out["rows_seen"] += 1
            values = {name: (row[i].strip() if i < len(row) else "")
                      for name, i in cols.items()}
            action = _action_from_dict({
                "symbol": values.get("symbol"), "ex_date": values.get("ex_date"),
                "kind": values.get("kind"), "ratio": values.get("ratio"),
                "amount": values.get("amount"), "source": "manual_csv",
                "status": "confirmed_source", "raw": ",".join(row)})
            if action is None:
                out["skipped"] += 1
                continue
            _insert(conn, action)
            out["imported"] += 1
            out["by_kind"][action["kind"]] = (
                out["by_kind"].get(action["kind"], 0) + 1)
    conn.commit()
    return out


# --- 2. yfinance event list: candidates, because prices are distrusted -----

def _series_items(series: Any) -> list:
    try:
        return list(series.items()) if series is not None and len(series) else []
    except Exception:
        return []


def _index_date(index: Any) -> Optional[str]:
    """yfinance indexes events by an IST-midnight Timestamp; take its date."""
    try:
        if hasattr(index, "date") and not isinstance(index, str):
            return index.date().isoformat()
    except Exception:
        pass
    return _parse_date(str(index)[:10])


def fetch_yfinance_actions(symbols, sleep_seconds=0.4) -> List[dict]:
    """Harvest yfinance split/dividend LISTS as 'unconfirmed' candidates.

    SPLIT SEMANTICS (verified against live data, 2026-10-20): the value in
    ``Ticker.splits`` IS already the history multiplier. HDFCBANK.NS shows 5.0
    for its 5:1 split (2011-07-14) and WIPRO.NS 2.0 for a 1:1 bonus
    (2024-12-03); Yahoo divides pre-event prices by that value. So
    ``ratio = float(value)`` -- storing its reciprocal would invent reverse
    splits. The fetch goes through data_sources (F-15/ID52), which imports
    yfinance lazily and repairs its tz cache first: importing this module
    never touches the network, one bad attribute is skipped rather than fatal,
    and a symbol with no events is still a valid empty result.
    """
    wanted: List[str] = []
    for raw in ([symbols] if isinstance(symbols, str) else (symbols or [])):
        symbol = _clean_symbol(raw)
        if symbol and symbol not in wanted:
            wanted.append(symbol)
    out: List[dict] = []
    for position, symbol in enumerate(wanted):
        ticker = symbol if symbol.endswith(".NS") else symbol + ".NS"
        for kind, attribute in (("split", "splits"), ("dividend", "dividends")):
            try:
                series = fetch_yahoo_field(symbol, attribute)
            except Exception:
                series = None
            for index, value in _series_items(series):
                ex_date, number = _index_date(index), _to_float(value)
                if not ex_date or number is None or number <= 0:
                    continue
                action = _action_from_dict({
                    "symbol": symbol, "ex_date": ex_date, "kind": kind,
                    "ratio": number if kind == "split" else None,
                    "amount": number if kind == "dividend" else None,
                    "source": "yfinance", "status": "unconfirmed",
                    "raw": json.dumps({"ticker": ticker, "series": attribute,
                                       "date": ex_date, "value": number})})
                if action is not None:
                    # The caller may hold these rows before merging; keep the
                    # documented field set and let merge_actions stamp _when_.
                    action.pop("recorded_at", None)
                    out.append(action)
        if sleep_seconds and position < len(wanted) - 1:
            time.sleep(float(sleep_seconds))
    return out


# --- 2b. chunked, resumable harvest (2026-10-18) ---------------------------
# The first full-universe harvest hung indefinitely on one symbol inside
# yfinance, which has no timeout of its own. A hung harvest is worse than a
# partial one: it silently blocks progress and leaves no record. This runner
# bounds every symbol with a wall-clock timeout, records per-symbol state in
# corporate_actions_fetch_state, merges each chunk as it goes, and resumes from
# the last recorded success instead of starting over.
FETCH_STATE_TABLE = "corporate_actions_fetch_state"


def ensure_fetch_state(conn) -> None:
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {FETCH_STATE_TABLE} ("
        "symbol TEXT PRIMARY KEY, fetched_at TEXT, status TEXT, "
        "actions INTEGER, error TEXT)")
    conn.commit()


def _fetch_one_with_timeout(symbol: str, timeout_seconds: float):
    """Return (actions, error). Executor is not joined, so a hung thread cannot
    stall the batch; the thread dies with the process."""
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FutureTimeout

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fetch_yfinance_actions, [symbol], 0.0)
    try:
        return future.result(timeout=max(1.0, float(timeout_seconds))), None
    except FutureTimeout:
        return [], "timeout"
    except Exception as exc:  # one bad ticker must not stop the harvest
        return [], f"{type(exc).__name__}: {exc}"
    finally:
        executor.shutdown(wait=False)


def fetch_all_resumable(conn, symbols, sleep_seconds: float = 0.2,
                        per_symbol_timeout: float = 20.0,
                        chunk_size: int = 50, force: bool = False,
                        progress: bool = True) -> dict:
    """Chunked, resumable yfinance corporate-action harvest.

    ``force`` re-fetches symbols already marked ok. Progress is persisted after
    every symbol, so a killed run resumes where it stopped. Returns counts by
    status, total merged actions and the chunk size actually used.
    """
    ensure_fetch_state(conn)
    done = set()
    if not force:
        done = {row[0] for row in conn.execute(
            f"SELECT symbol FROM {FETCH_STATE_TABLE} WHERE status='ok'")}
    todo = [s for s in symbols if s not in done]
    counts = {"symbols": len(symbols), "already_done": len(symbols) - len(todo),
              "fetched_symbols": 0, "inserted": 0, "updated": 0, "actions": 0,
              "timeouts": [], "errors": [], "chunk_size": int(chunk_size)}
    for position, symbol in enumerate(todo, 1):
        actions, error = _fetch_one_with_timeout(symbol, per_symbol_timeout)
        status = "error" if error else "ok"
        if error:
            counts["timeouts" if error == "timeout" else "errors"].append(symbol)
        else:
            merged = merge_actions(conn, actions)
            counts["inserted"] += merged["inserted"]
            counts["updated"] += merged["updated"]
            counts["actions"] += len(actions)
            counts["fetched_symbols"] += 1
        conn.execute(
            f"INSERT OR REPLACE INTO {FETCH_STATE_TABLE} "
            "(symbol, fetched_at, status, actions, error) VALUES (?,?,?,?,?)",
            (symbol, now_ist(), status, len(actions), error))
        conn.commit()
        if progress and (position % max(1, int(chunk_size)) == 0
                         or position == len(todo)):
            print(f"  [{position}/{len(todo)}] {symbol}: {status}, "
                  f"actions={counts['actions']}, "
                  f"timeouts={len(counts['timeouts'])}", flush=True)
        if sleep_seconds and position < len(todo):
            time.sleep(float(sleep_seconds))
    return counts


# --- 3. merge: provenance is the caller's decision -------------------------

def merge_actions(conn, actions) -> dict:
    """Upsert action dicts; returns {'inserted', 'updated'} by primary key.

    INSERT OR REPLACE keeps whatever source/status the caller passed: a fetch
    must not be able to overwrite a human-confirmed row, nor the reverse.
    """
    counts = {"inserted": 0, "updated": 0}
    for candidate in actions or []:
        action = _action_from_dict(candidate)
        if action is None:
            continue
        exists = conn.execute(
            "SELECT 1 FROM corporate_actions WHERE symbol=? AND ex_date=? "
            "AND kind=?", (action["symbol"], action["ex_date"],
                           action["kind"])).fetchone()
        _insert(conn, action)
        counts["updated" if exists else "inserted"] += 1
    conn.commit()
    return counts


# --- 4. gap detection: read-only candidates for a human to confirm ---------

def _scan_symbols(conn, symbols, limit) -> List[str]:
    """Symbols to walk: explicit, else all of prices_daily alphabetical, capped."""
    if isinstance(symbols, str):
        symbols = [symbols]
    if symbols:
        picked: List[str] = []
        for raw in symbols:
            symbol = _clean_symbol(raw)
            if symbol and symbol not in picked:
                picked.append(symbol)
    else:
        picked = [row[0] for row in conn.execute(
            "SELECT DISTINCT symbol FROM prices_daily ORDER BY symbol")
            if row[0]]
    return picked[:limit] if limit and limit > 0 else picked


def detect_price_gaps(conn, symbols=None, min_gap=0.15,
                      limit=500) -> List[dict]:
    """Find unexplained day-over-day jumps in STORED closes. Writes nothing.

    Why a ratio: a split divides the price without changing wealth, so
    prev_close/close is the multiplier that would explain the move (100 -> 10
    gives 10.0). A crash has no such ratio, hence 'unknown_event' -- the point
    is to never let a gap be silently read as a split.
    """
    threshold, out = abs(float(min_gap or 0)), []
    for symbol in _scan_symbols(conn, symbols, limit):
        rows = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol=? AND close IS "
            "NOT NULL AND close > 0 ORDER BY date", (symbol,)).fetchall()
        previous = None
        for date, close in rows:
            if previous is not None and previous > 0:
                move = close / previous - 1.0
                if abs(move) >= threshold:
                    implied = round(previous / close, 4)
                    match = _nearest_ratio(implied)
                    out.append({
                        "symbol": symbol, "date": date,
                        "prev_close": round(previous, 4),
                        "close": round(close, 4),
                        "move_pct": round(move * 100, 2),
                        "implied_ratio": implied, "ratio_match": match,
                        "direction": "down" if implied >= 1.0 else "up",
                        "kind_guess": ("split_or_bonus" if match is not None
                                       else "unknown_event")})
            previous = close
    return out


# --- 5. explain: what the ingest guards print when they refuse -------------

def explain(conn, symbol, date, window_days=10) -> dict:
    """Nearest recorded action (and stored closes) around one date.

    'rejected' rows are skipped on purpose: an action we do not believe must
    not be offered as the explanation for a gap.
    """
    symbol = _clean_symbol(symbol) or str(symbol or "").strip().upper()
    parsed = _parse_date(date)
    if parsed is None:
        raise ValueError(f"date must be YYYY-MM-DD, got {date!r}")
    day = dt.date.fromisoformat(parsed)
    window = max(0, int(window_days or 0))
    start = (day - dt.timedelta(days=window)).isoformat()
    end = (day + dt.timedelta(days=window)).isoformat()
    best, days_apart, action = None, None, None
    rows = conn.execute(
        _SELECT + " WHERE symbol=? AND ex_date BETWEEN ? AND ? AND "
        "COALESCE(status, '') <> 'rejected' ORDER BY ex_date",
        (symbol, start, end)).fetchall()
    for row in rows:
        ex_date = _parse_date(row[1])
        if ex_date is None:
            continue
        distance = abs((dt.date.fromisoformat(ex_date) - day).days)
        if best is None or (distance, ex_date) < best[0]:
            best = ((distance, ex_date), row)
    if best is not None:
        days_apart, row = best[0][0], best[1]
        action = dict(zip(_FIELDS, row))
    closes = [{"date": row[0], "close": row[1]} for row in conn.execute(
        "SELECT date, close FROM prices_daily WHERE symbol=? AND date BETWEEN "
        "? AND ? ORDER BY date", (symbol, start, end))]
    return {"symbol": symbol, "date": parsed, "action": action,
            "days_apart": days_apart, "closes": closes}


# --- 6. summary ------------------------------------------------------------

_GAP_SQL = ("WITH seq AS (SELECT symbol, date, close, LAG(close) OVER "
            "(PARTITION BY symbol ORDER BY date) AS prev_close "
            "FROM prices_daily) SELECT COUNT(*), COUNT(DISTINCT symbol) "
            "FROM seq WHERE date >= ? AND prev_close > 0 AND close > 0 "
            "AND ABS(close * 1.0 / prev_close - 1.0) >= ?")


def _gap_scan(conn, sessions=60, min_gap=DEFAULT_MIN_GAP) -> dict:
    """Cheap window-function count over the last N sessions (no Python loop).

    'method' tells the caller whether the number is exact ('window_sql') or a
    bounded symbol sample ('sample'), so a summary never implies more coverage
    than it had.
    """
    dates = [row[0] for row in conn.execute(
        "SELECT DISTINCT date FROM prices_daily WHERE date IS NOT NULL "
        "ORDER BY date DESC LIMIT ?", (sessions,)) if row[0]]
    scan = {"sessions": len(dates), "from": min(dates) if dates else None,
            "to": max(dates) if dates else None, "candidates": 0,
            "symbols_scanned": 0, "method": "no_prices"}
    if not dates:
        return scan
    try:
        count, symbols = conn.execute(
            _GAP_SQL, (min(dates), abs(float(min_gap)))).fetchone()
        scan.update(candidates=int(count or 0), symbols_scanned=int(symbols or 0),
                    method="window_sql")
    except Exception:
        sample = _scan_symbols(conn, None, 25)
        found = [gap for gap in detect_price_gaps(conn, sample, min_gap, 25)
                 if gap["date"] >= min(dates)]
        scan.update(candidates=len(found), symbols_scanned=len(sample),
                    method="sample")
    return scan


def summary(conn) -> dict:
    """Counts by source/status/kind, coverage, and recent gap candidates."""
    def grouped(column: str) -> Dict[str, int]:
        rows = conn.execute(f"SELECT {column}, COUNT(*) FROM corporate_actions "
                            f"GROUP BY {column}")
        return {(row[0] if row[0] is not None else ""): row[1] for row in rows}

    total, earliest, latest, symbols = conn.execute(
        "SELECT COUNT(*), MIN(ex_date), MAX(ex_date), COUNT(DISTINCT symbol) "
        "FROM corporate_actions").fetchone()
    gaps = _gap_scan(conn)
    return {"actions": total, "by_source": grouped("source"),
            "by_status": grouped("status"), "by_kind": grouped("kind"),
            "earliest_ex_date": earliest, "latest_ex_date": latest,
            "symbols": symbols, "gap_candidates_60s": gaps["candidates"],
            "gap_scan": gaps}


# --- CLI: db is imported here only, so the library stands alone ------------

def _split_symbols(text: str) -> List[str]:
    return [part.strip().upper() for part in (text or "").split(",")
            if part.strip()]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Corporate actions: candidates, never facts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    child = sub.add_parser("detect", help="read-only gap candidates")
    child.add_argument("--limit", type=int, default=500)
    child.add_argument("--min-gap", dest="min_gap", type=float,
                       default=DEFAULT_MIN_GAP)
    child.add_argument("--symbols", default=None)
    child = sub.add_parser("fetch", help="harvest yfinance split/dividends")
    child.add_argument("--symbols", default=None)
    child.add_argument("--all", dest="all_symbols", action="store_true")
    child.add_argument("--limit", type=int, default=0,
                       help="symbol cap for --all (0 = whole universe)")
    child.add_argument("--sleep", type=float, default=0.2)
    child.add_argument("--timeout", type=float, default=20.0,
                       help="per-symbol wall-clock timeout in seconds")
    child.add_argument("--chunk-size", dest="chunk_size", type=int, default=50)
    child.add_argument("--force", action="store_true",
                       help="re-fetch symbols already marked ok")
    child = sub.add_parser("import", help="load a manual CSV")
    child.add_argument("--file", required=True)
    child = sub.add_parser("list", help="print recorded actions")
    child.add_argument("--symbol", default=None)
    sub.add_parser("summary", help="counts by source/status/kind")
    child = sub.add_parser("explain", help="what happened to SYMBOL on DATE")
    child.add_argument("symbol")
    child.add_argument("date")
    child.add_argument("--window", type=int, default=10)
    args = parser.parse_args(argv)

    import db                                     # lazy: CLI-only dependency

    conn = db.get_conn()
    try:
        if args.cmd == "detect":
            symbols = _split_symbols(args.symbols) if args.symbols else None
            payload = detect_price_gaps(conn, symbols, args.min_gap, args.limit)
        elif args.cmd == "fetch":
            if not args.symbols and not args.all_symbols:
                parser.error("fetch needs --symbols A,B or --all")
            symbols = (_split_symbols(args.symbols) if args.symbols
                       else _scan_symbols(conn, None,
                                          args.limit if args.limit else None))
            if args.all_symbols:
                payload = fetch_all_resumable(
                    conn, symbols, sleep_seconds=args.sleep,
                    per_symbol_timeout=args.timeout,
                    chunk_size=args.chunk_size, force=args.force,
                    progress=True)
            else:
                actions = fetch_yfinance_actions(symbols, args.sleep)
                payload = {"symbols": len(symbols), "fetched": len(actions),
                           **merge_actions(conn, actions)}
        elif args.cmd == "import":
            payload = import_csv(conn, args.file)
        elif args.cmd == "list":
            sql, params = _SELECT, ()
            if args.symbol:
                sql += " WHERE symbol=?"
                params = (_clean_symbol(args.symbol)
                          or args.symbol.strip().upper(),)
            payload = [dict(zip(_FIELDS, row)) for row in
                       conn.execute(sql + " ORDER BY symbol, ex_date, kind",
                                    params)]
        elif args.cmd == "summary":
            payload = summary(conn)
        else:
            payload = explain(conn, args.symbol, args.date, args.window)
    finally:
        conn.close()
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
