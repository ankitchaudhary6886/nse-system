"""FREE official NSE end-of-day ingestion — no Fyers, no login, no API key.

WHY THIS EXISTS
---------------
The owner wants daily data updates that are free and require no intervention.
NSE publishes the whole cash market as public archive files, and (verified
2026-10-18 from the live VM, which is a cloud IP that the interactive NSE site
blocks) these archives ARE reachable with a plain browser User-Agent:

  * equity OHLCV + delivery:
    https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv
  * every official index close:
    https://nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv
  * official security master (symbol/ISIN/series):
    https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv
  * historical daily bhavcopy (raw, for rebuilding old history):
    https://nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MMM/cmDDMMMYYYYbhav.csv.zip

That stack covers prices, volume, delivery %, and index series (NIFTY50/500,
sectors) — everything the daily-bar swing system needs — with zero credential
churn. Fyers remains an optional upgrade, not a dependency.

HYGIENE
- One file per trading day, so a missing file is simply a holiday: recorded as
  status 'holiday', never treated as stale data.
- Only symbols in our own universe are written; foreign rows are counted and
  dropped, so the price store cannot silently grow a second universe.
- Official prices are RAW (unadjusted). Each adopted symbol gets
  price_meta.basis='nse_bhavdata_raw'; a symbol that already had adjusted
  history becomes 'mixed_adjusted_then_raw'. `history --apply` rebuilds a date
  range from the official archives (with a one-time backup table) when the owner
  wants a pure raw history.
- Every date is recorded in nse_eod_sync (status/rows/delivery/source/error), so
  catch-up is idempotent and auditable.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "app.db"
ARCHIVE = "https://nsearchives.nseindia.com"
SEC_BHAV = ARCHIVE + "/products/content/sec_bhavdata_full_%s.csv"
INDEX_CLOSE = ARCHIVE + "/content/indices/ind_close_all_%s.csv"
EQUITY_MASTER = ARCHIVE + "/content/equities/EQUITY_L.csv"
LEGACY_BHAV = (ARCHIVE + "/content/historical/EQUITIES/%Y/%b/"
               "cm%d%b%Ybhav.csv.zip")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "text/csv,application/zip,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
EQ_SERIES = {"EQ", "BE", "BZ", "ST"}
INDEX_NAME_MAP = {
    "NIFTY 50": "NIFTY50",
    "NIFTY 500": "NIFTY500",
    "NIFTY BANK": "NIFTYBANK",
    "NIFTY MIDCAP 100": "NIFTYMIDCAP100",
    "NIFTY SMALLCAP 100": "NIFTYSMALLCAP100",
    "NIFTY NEXT 50": "NIFTYNEXT50",
}
WEEKDAYS = (0, 1, 2, 3, 4)


class OfficialDataError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _get(session: requests.Session, url: str, timeout: int = 30) -> bytes:
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        raise FileNotFoundError(url)
    response.raise_for_status()
    return response.content


def _text(session: requests.Session, url: str) -> str:
    data = _get(session, url)
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# symbol & date helpers
# ---------------------------------------------------------------------------
def _norm_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    for char in ("_", "."):
        text = text.replace(char, "-")
    return text


def universe_map(conn: sqlite3.Connection) -> Dict[str, str]:
    """normalized exchange symbol -> project symbol (universe + stocks rows)."""
    import universe_helper as U
    project = set(U.combined_universe(conn))
    try:
        project |= {row[0] for row in conn.execute(
            "SELECT symbol FROM stocks")}
    except Exception:
        pass
    mapping: Dict[str, str] = {}
    for symbol in project:
        mapping.setdefault(_norm_symbol(symbol), symbol)
        mapping.setdefault(str(symbol).strip().upper(), symbol)
    return mapping


def _parse_date(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y",
                "%d-%b-%y"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _float(value: Any) -> Optional[float]:
    text = str(value or "").strip().replace(",", "")
    if not text or text in ("-", "NA", "N.A.", "NULL"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def legacy_bhav_url(day: dt.date) -> str:
    """NSE legacy bhavcopy URL. Month/day are UPPERCASE in the real archive
    (cm17AUG2021bhav.csv.zip); %b locale output is 'Aug', so build it manually."""
    stamp = day.strftime("%d%b%Y").upper()
    month = day.strftime("%b").upper()
    return (f"{ARCHIVE}/content/historical/EQUITIES/{day.year}/{month}/"
            f"cm{stamp}bhav.csv.zip")


def trading_days(start: dt.date, end: dt.date) -> List[str]:
    out = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() in WEEKDAYS:
            out.append(cursor.isoformat())
        cursor += dt.timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# parsers
# ---------------------------------------------------------------------------
def parse_sec_bhav(text: str) -> List[dict]:
    """Parse sec_bhavdata_full_*.csv into raw price/delivery rows."""
    reader = csv.DictReader(io.StringIO(text))
    rows: List[dict] = []
    for raw in reader:
        row = {str(k).strip().upper(): (v.strip() if isinstance(v, str) else v)
               for k, v in raw.items() if k}
        symbol = row.get("SYMBOL")
        series = str(row.get("SERIES") or "").strip().upper()
        date = _parse_date(row.get("DATE1"))
        close = _float(row.get("CLOSE_PRICE"))
        if not symbol or series not in EQ_SERIES or not date or close is None:
            continue
        rows.append({
            "symbol": symbol, "series": series, "date": date,
            "prev_close": _float(row.get("PREV_CLOSE")),
            "open": _float(row.get("OPEN_PRICE")),
            "high": _float(row.get("HIGH_PRICE")),
            "low": _float(row.get("LOW_PRICE")),
            "close": close,
            "volume": _float(row.get("TTL_TRD_QNTY")),
            "value": _float(row.get("TURNOVER_LACS")),
            "trades": _float(row.get("NO_OF_TRADES")),
            "delivery_qty": _float(row.get("DELIV_QTY")),
            "delivery_pct": _float(row.get("DELIV_PER")),
        })
    return rows


def parse_index_close(text: str) -> List[dict]:
    reader = csv.DictReader(io.StringIO(text))
    rows: List[dict] = []
    for raw in reader:
        row = {str(k).strip(): (v.strip() if isinstance(v, str) else v)
               for k, v in raw.items() if k}
        name = row.get("Index Name") or row.get("INDEX NAME") or ""
        date = _parse_date(row.get("Index Date") or row.get("INDEX DATE"))
        close = _float(row.get("Closing Index Value")
                       or row.get("CLOSING INDEX VALUE"))
        if not name or not date or close is None:
            continue
        symbol = INDEX_NAME_MAP.get(name.upper(),
                                    _norm_symbol(name))
        rows.append({
            "symbol": symbol, "name": name, "date": date,
            "open": _float(row.get("Open Index Value")),
            "high": _float(row.get("High Index Value")),
            "low": _float(row.get("Low Index Value")),
            "close": close,
            "prev_close": None,
            "change_pct": _float(row.get("Change(%)")),
            "volume": _float(row.get("Volume")),
        })
    return rows


def parse_equity_master(text: str) -> List[dict]:
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for raw in reader:
        row = {str(k).strip().upper(): (v.strip() if isinstance(v, str) else v)
               for k, v in raw.items() if k}
        symbol = row.get("SYMBOL")
        if not symbol:
            continue
        rows.append({
            "symbol": str(symbol).strip().upper(),
            "name": row.get("NAME OF COMPANY"),
            "series": row.get("SERIES"),
            "listing_date": _parse_date(row.get("DATE OF LISTING")),
            "isin": row.get("ISIN NUMBER"),
            "market_lot": _float(row.get("MARKET LOT")),
            "face_value": _float(row.get("FACE VALUE")),
        })
    return rows


def parse_legacy_bhav(text: str) -> List[dict]:
    """Old daily bhavcopy format (SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,...)."""
    reader = csv.DictReader(io.StringIO(text))
    rows: List[dict] = []
    for raw in reader:
        row = {str(k).strip().upper(): (v.strip() if isinstance(v, str) else v)
               for k, v in raw.items() if k}
        symbol = row.get("SYMBOL")
        series = str(row.get("SERIES") or "").strip().upper()
        close = _float(row.get("CLOSE"))
        if not symbol or series not in EQ_SERIES or close is None:
            continue
        rows.append({
            "symbol": str(symbol).strip().upper(), "series": series,
            "open": _float(row.get("OPEN")), "high": _float(row.get("HIGH")),
            "low": _float(row.get("LOW")), "close": close,
            "prev_close": _float(row.get("PREVCLOSE")),
            "volume": _float(row.get("TOTTRDQTY")),
            "delivery_pct": None, "delivery_qty": None,
        })
    return rows


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------
def _sync(conn, date: str, status: str, rows: int = 0, delivery: int = 0,
          source: str = "nse_archive", error: Optional[str] = None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO nse_eod_sync "
        "(date,status,rows,delivery_rows,source,fetched_at,error) "
        "VALUES (?,?,?,?,?,?,?)",
        (date, status, rows, delivery, source,
         dt.datetime.now().isoformat(timespec="seconds"), error))
    conn.commit()


def ingest_prices(conn, rows: List[dict], replace: bool = False) -> dict:
    mapping = universe_map(conn)
    adopted = []
    skipped = 0
    for row in rows:
        project = mapping.get(_norm_symbol(row["symbol"]))
        if not project:
            skipped += 1
            continue
        adopted.append((project, row))
    if not adopted:
        return {"rows": 0, "skipped": skipped, "symbols": 0}
    dates = sorted({row["date"] for _, row in adopted})
    for date in dates:
        conn.executemany(
            "INSERT OR REPLACE INTO prices_daily "
            "(symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
            [(project, row["date"], row["open"], row["high"], row["low"],
              row["close"], row["volume"]) for project, row in adopted
             if row["date"] == date])
    # provenance: raw official basis (mixed if the symbol already had a basis)
    symbols = {project for project, _ in adopted}
    for project in symbols:
        existing = conn.execute(
            "SELECT basis FROM price_meta WHERE symbol=?", (project,)).fetchone()
        prior = existing[0] if existing else None
        basis = ("nse_bhavdata_raw"
                 if prior in (None, "", "nse_bhavdata_raw")
                 else (prior if str(prior).startswith("mixed")
                       else "mixed_adjusted_then_raw"))
        agg = conn.execute(
            "SELECT MAX(date), COUNT(*) FROM prices_daily WHERE symbol=?",
            (project,)).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO price_meta "
            "(symbol,last_date,rows,updated_at,basis) VALUES (?,?,?,?,?)",
            (project, agg[0], agg[1],
             dt.datetime.now().isoformat(timespec="seconds"), basis))
    delivery_rows = 0
    for date in dates:
        for project, row in adopted:
            if row["date"] != date or row.get("delivery_pct") is None:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO delivery_daily "
                "(date,symbol,traded_qty,deliverable_qty,delivery_pct,close,"
                "created_at) VALUES (?,?,?,?,?,?,?)",
                (date, project, row.get("volume"), row.get("delivery_qty"),
                 row.get("delivery_pct"), row.get("close"),
                 dt.datetime.now().isoformat(timespec="seconds")))
            delivery_rows += 1
    conn.commit()
    return {"rows": len(adopted), "skipped": skipped,
            "symbols": len(symbols), "dates": dates,
            "delivery_rows": delivery_rows}


def ingest_indices(conn, rows: List[dict]) -> dict:
    if not rows:
        return {"rows": 0}
    conn.executemany(
        "INSERT OR REPLACE INTO index_daily "
        "(symbol,date,name,open,high,low,close,prev_close,change_pct,volume,"
        "source) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(row["symbol"], row["date"], row["name"], row["open"], row["high"],
          row["low"], row["close"], row["prev_close"], row["change_pct"],
          row["volume"], "nse_archive") for row in rows])
    conn.commit()
    return {"rows": len(rows), "symbols": len({r["symbol"] for r in rows})}


def ingest_master(conn, rows: List[dict]) -> dict:
    if not rows:
        return {"rows": 0}
    now = dt.datetime.now().isoformat(timespec="seconds")
    conn.executemany(
        "INSERT OR REPLACE INTO nse_security_master "
        "(symbol,name,series,listing_date,isin,market_lot,face_value,"
        "updated_at,source) VALUES (?,?,?,?,?,?,?,?,?)",
        [(r["symbol"], r["name"], r["series"], r["listing_date"], r["isin"],
          r["market_lot"], r["face_value"], now, "nse_equity_l")
         for r in rows])
    conn.commit()
    return {"rows": len(rows)}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def ingest_date(conn, date: str, session: Optional[requests.Session] = None,
                include_indices: bool = True) -> dict:
    day = dt.date.fromisoformat(date)
    stamp = day.strftime("%d%m%Y")
    session = session or _session()
    result: Dict[str, Any] = {"date": date}
    try:
        text = _text(session, SEC_BHAV % stamp)
    except FileNotFoundError:
        result.update({"status": "holiday", "reason": "no bhavcopy file"})
        _sync(conn, date, "holiday")
        return result
    except Exception as exc:
        result.update({"status": "error", "error": f"bhavcopy: {exc}"})
        _sync(conn, date, "error", error=str(exc))
        return result
    prices = parse_sec_bhav(text)
    written = ingest_prices(conn, prices)
    result.update({"status": "ok", "prices": written})
    if include_indices:
        try:
            index_rows = parse_index_close(_text(session, INDEX_CLOSE % stamp))
            result["indices"] = ingest_indices(conn, index_rows)
        except Exception as exc:
            result["indices"] = {"error": str(exc)}
    _sync(conn, date, "ok", rows=written.get("rows", 0),
          delivery=written.get("delivery_rows", 0), error=None)
    return result


def catch_up(conn, days_back: int = 15, sleep: float = 0.25,
             session: Optional[requests.Session] = None) -> dict:
    """Ingest every weekday in the window that is not already recorded ok."""
    today = dt.date.today()
    start = today - dt.timedelta(days=max(1, int(days_back)))
    done = {row[0] for row in conn.execute(
        "SELECT date FROM nse_eod_sync WHERE status IN ('ok','holiday')")}
    pending = [d for d in trading_days(start, today) if d not in done]
    session = session or _session()
    results = []
    for date in pending:
        result = ingest_date(conn, date, session=session)
        results.append(result)
        if sleep:
            time.sleep(float(sleep))
    return {"attempted": len(pending),
            "ok": sum(1 for r in results if r.get("status") == "ok"),
            "holidays": [r["date"] for r in results
                         if r.get("status") == "holiday"],
            "errors": [r["date"] for r in results
                       if r.get("status") == "error"],
            "details": results}


def fetch_history(conn, start: str, end: str, apply: bool = False,
                  sleep: float = 0.15, session: Optional[requests.Session] = None,
                  progress: bool = True) -> dict:
    """Rebuild a date range from the RAW legacy bhavcopy archives.

    With apply=False it only probes/reports; with apply=True it writes the raw
    official bars (backing up the current prices table once per run).
    """
    session = session or _session()
    start_day = dt.date.fromisoformat(start)
    end_day = dt.date.fromisoformat(end)
    days = trading_days(start_day, end_day)
    mapping = universe_map(conn)
    backup = None
    if apply:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = f"prices_daily_adj_backup_{stamp}"
        conn.execute(f"CREATE TABLE IF NOT EXISTS {backup} AS "
                     "SELECT * FROM prices_daily WHERE 0")
        conn.execute(f"INSERT INTO {backup} SELECT * FROM prices_daily")
        conn.commit()
    result = {"dates": len(days), "ok": 0, "holidays": [], "errors": [],
              "rows": 0, "skipped": 0, "backup_table": backup}
    for index, date in enumerate(days, 1):
        day = dt.date.fromisoformat(date)
        url = legacy_bhav_url(day)
        try:
            blob = _get(session, url)
        except FileNotFoundError:
            result["holidays"].append(date)
            continue
        except Exception as exc:
            result["errors"].append({"date": date, "error": str(exc)})
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                name = archive.namelist()[0]
                text = archive.read(name).decode("utf-8", "replace")
        except Exception as exc:
            result["errors"].append({"date": date, "error": f"zip: {exc}"})
            continue
        rows = []
        for row in parse_legacy_bhav(text):
            project = mapping.get(_norm_symbol(row["symbol"]))
            if not project:
                result["skipped"] += 1
                continue
            rows.append((project, date, row["open"], row["high"],
                         row["low"], row["close"], row["volume"]))
        if apply and rows:
            conn.executemany(
                "INSERT OR REPLACE INTO prices_daily "
                "(symbol,date,open,high,low,close,volume) "
                "VALUES (?,?,?,?,?,?,?)", rows)
            conn.commit()
        result["rows"] += len(rows)
        result["ok"] += 1
        if progress and (index % 50 == 0 or index == len(days)):
            print(f"  history {index}/{len(days)} {date}: "
                  f"{len(rows)} rows, errors={len(result['errors'])}",
                  flush=True)
        if sleep:
            time.sleep(float(sleep))
    if apply:
        for (project,) in conn.execute(
                "SELECT DISTINCT symbol FROM prices_daily"):
            agg = conn.execute(
                "SELECT MAX(date), COUNT(*) FROM prices_daily WHERE symbol=?",
                (project,)).fetchone()
            conn.execute(
                "INSERT OR REPLACE INTO price_meta "
                "(symbol,last_date,rows,updated_at,basis) VALUES (?,?,?,?,?)",
                (project, agg[0], agg[1],
                 dt.datetime.now().isoformat(timespec="seconds"),
                 "nse_bhavdata_raw"))
        conn.commit()
    return result


def report(conn) -> dict:
    sync = [dict(zip(("date", "status", "rows", "delivery_rows", "source",
                      "fetched_at", "error"), row))
            for row in conn.execute(
                "SELECT date,status,rows,delivery_rows,source,fetched_at,error "
                "FROM nse_eod_sync ORDER BY date DESC LIMIT 20")]
    official = conn.execute(
        "SELECT COUNT(*) FROM price_meta WHERE basis='nse_bhavdata_raw'"
    ).fetchone()[0]
    mixed = conn.execute(
        "SELECT COUNT(*) FROM price_meta WHERE basis LIKE 'mixed%'").fetchone()[0]
    delivery = conn.execute("SELECT COUNT(*) FROM delivery_daily").fetchone()[0]
    indices = conn.execute(
        "SELECT COUNT(DISTINCT symbol), MAX(date) FROM index_daily").fetchone()
    return {"recent_sync": sync, "official_basis_symbols": official,
            "mixed_basis_symbols": mixed, "delivery_rows": delivery,
            "index_symbols": indices[0], "index_latest": indices[1],
            "master_rows": conn.execute(
                "SELECT COUNT(*) FROM nse_security_master").fetchone()[0]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe")
    sub.add_parser("master")
    child = sub.add_parser("ingest")
    child.add_argument("--date", required=True)
    child = sub.add_parser("catchup")
    child.add_argument("--days", type=int, default=15)
    child.add_argument("--sleep", type=float, default=0.25)
    child = sub.add_parser("history")
    child.add_argument("--from", dest="start", required=True)
    child.add_argument("--to", dest="end", required=True)
    child.add_argument("--apply", action="store_true")
    child.add_argument("--sleep", type=float, default=0.15)
    sub.add_parser("report")
    args = parser.parse_args(argv)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA temp_store=MEMORY")
    try:
        import db as central
        conn.executescript(central.SCHEMA)
        if args.cmd == "probe":
            session = _session()
            for url in (SEC_BHAV % dt.date.today().strftime("%d%m%Y"),
                        INDEX_CLOSE % dt.date.today().strftime("%d%m%Y")):
                try:
                    response = session.get(url, timeout=20)
                    print(response.status_code, len(response.content), url)
                except Exception as exc:
                    print("ERR", type(exc).__name__, exc, url)
            return 0
        if args.cmd == "master":
            rows = parse_equity_master(_text(_session(), EQUITY_MASTER))
            print(json.dumps(ingest_master(conn, rows), default=str))
            return 0
        if args.cmd == "ingest":
            print(json.dumps(ingest_date(conn, args.date), indent=2,
                             default=str))
            return 0
        if args.cmd == "catchup":
            print(json.dumps(catch_up(conn, args.days, args.sleep),
                             indent=2, default=str))
            return 0
        if args.cmd == "history":
            print(json.dumps(fetch_history(conn, args.start, args.end,
                                           apply=args.apply,
                                           sleep=args.sleep),
                             indent=2, default=str))
            return 0
        print(json.dumps(report(conn), indent=2, default=str))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
