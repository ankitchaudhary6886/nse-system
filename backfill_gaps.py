"""Fyers gap-filler: historicals and holes the free official files cannot cover.

ROLE (owner decision, 18 Oct 2026):
- NSE official archives are the DAILY OHLCV source (free, no login).
- Fyers is used ONLY to fill what those archives miss: a symbol absent from a
  day's bhavcopy, a day whose archive file is unavailable, symbols the archives
  do not map (odd series/SME/renamed), and historical stretches the owner wants
  from the broker feed.

RULES
- Never overwrites an existing bar: only dates missing for that symbol are
  written. Existing official raw rows are authoritative.
- Requires a valid Fyers token (browser login once, then the pin-based refresh
  keeps it alive). Without a token every function returns a clean "skipped",
  never an exception, so the daily chain continues.
- Provenance: a symbol that receives broker bars on top of official bars becomes
  `mixed_raw_sources`; basis is never silently relabelled.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any, Dict, List, Optional, Sequence

import db


def _client():
    from fyers_client import FyersClient
    return FyersClient()


def _calendar(conn, days: int) -> List[str]:
    """Trading dates from the official sync log (fallback: price dates)."""
    rows = [r[0] for r in conn.execute(
        "SELECT date FROM nse_eod_sync WHERE status='ok' "
        "ORDER BY date DESC LIMIT ?", (max(1, int(days)),))]
    if rows:
        return sorted(rows)
    rows = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM prices_daily ORDER BY date DESC LIMIT ?",
        (max(1, int(days)),))]
    return sorted(rows)


def missing_report(conn, days: int = 30, limit: int = 200) -> dict:
    """Which universe symbols are missing which recent official sessions."""
    import universe_helper as U
    dates = _calendar(conn, days)
    if not dates:
        return {"dates": 0, "symbols_scanned": 0, "missing": {},
                "symbols_missing": 0}
    start = dates[0]
    symbols = U.combined_universe(conn)
    missing: Dict[str, List[str]] = {}
    for symbol in symbols:
        have = {row[0] for row in conn.execute(
            "SELECT date FROM prices_daily WHERE symbol=? AND date>=?",
            (symbol, start))}
        holes = [d for d in dates if d not in have]
        if holes:
            missing[symbol] = holes
    return {"dates": len(dates), "window": [dates[0], dates[-1]],
            "symbols_scanned": len(symbols), "symbols_missing": len(missing),
            "missing_sample": dict(list(missing.items())[:limit]),
            "holes_total": sum(len(v) for v in missing.values())}


def _write_rows(conn, symbol: str, rows: List[dict]) -> int:
    if not rows:
        return 0
    conn.executemany(
        "INSERT OR REPLACE INTO prices_daily "
        "(symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
        [(symbol, r["date"], r["open"], r["high"], r["low"], r["close"],
          r["volume"]) for r in rows])
    agg = conn.execute(
        "SELECT MAX(date), COUNT(*) FROM prices_daily WHERE symbol=?",
        (symbol,)).fetchone()
    prior = conn.execute(
        "SELECT basis FROM price_meta WHERE symbol=?", (symbol,)).fetchone()
    basis = (prior[0] if prior and prior[0] else "fyers_raw")
    if basis != "fyers_raw":
        basis = "mixed_raw_sources"
    conn.execute(
        "INSERT OR REPLACE INTO price_meta "
        "(symbol,last_date,rows,updated_at,basis) VALUES (?,?,?,?,?)",
        (symbol, agg[0], agg[1],
         dt.datetime.now().isoformat(timespec="seconds"), basis))
    conn.execute(
        "INSERT INTO fyers_sync_log "
        "(run_at,kind,status,symbols,rows,error,detail) VALUES (?,?,?,?,?,?,?)",
        (dt.datetime.now().isoformat(timespec="seconds"), "gap_fill", "ok",
         1, len(rows), None, json.dumps({"symbol": symbol})))
    conn.commit()
    return len(rows)


def fill_with_fyers(conn, client=None, days: int = 30,
                    symbols: Optional[Sequence[str]] = None,
                    limit: Optional[int] = None, dry_run: bool = False,
                    progress: bool = True) -> dict:
    """Fill recent holes from Fyers. Never overwrites existing bars."""
    try:
        client = client or _client()
        if not getattr(client, "token", ""):
            return {"ok": False, "skipped": "no fyers token",
                    "message": "Fyers is optional; official daily data is unaffected"}
    except Exception as exc:
        return {"ok": False, "skipped": f"fyers unavailable: {exc}"}
    report = missing_report(conn, days=days, limit=limit or 200)
    if not report["symbols_missing"]:
        return {"ok": True, "filled": 0, "message": "no holes in the window"}
    import ingest_fyers
    mapping = ingest_fyers.resolve_symbols(conn, list(report["missing_sample"]))
    resolved = mapping["resolved"]
    targets = list(resolved)[:limit] if limit else list(resolved)
    filled_symbols = 0
    filled_rows = 0
    errors = []
    for index, symbol in enumerate(targets, 1):
        holes = report["missing_sample"].get(symbol) or []
        if not holes:
            continue
        start = (dt.date.fromisoformat(min(holes))
                 - dt.timedelta(days=5)).isoformat()
        end = max(holes)
        try:
            candles = client.history_range(resolved[symbol], start, end)
            rows = ingest_fyers._fmt_candles(candles)
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
            continue
        wanted = set(holes)
        rows = [r for r in rows if r["date"] in wanted
                and r["close"] and r["close"] > 0 and r["high"] >= r["low"]]
        if not rows:
            continue
        if dry_run:
            filled_rows += len(rows)
            filled_symbols += 1
        else:
            filled_rows += _write_rows(conn, symbol, rows)
            filled_symbols += 1
        if progress and (index % 25 == 0 or index == len(targets)):
            print(f"  gap-fill {index}/{len(targets)} {symbol}: "
                  f"{len(rows)} rows", flush=True)
    return {"ok": True, "candidates": report["symbols_missing"],
            "resolved": len(resolved), "filled_symbols": filled_symbols,
            "filled_rows": filled_rows, "errors": errors,
            "dry_run": dry_run}


def historical_fill(conn, client=None, symbols: Optional[Sequence[str]] = None,
                    start: str = "", end: str = "", limit: Optional[int] = None,
                    dry_run: bool = False) -> dict:
    """Fill a historical range from Fyers for symbols/dates the archives lack."""
    if not start or not end:
        raise ValueError("historical_fill needs start and end (YYYY-MM-DD)")
    try:
        client = client or _client()
        if not getattr(client, "token", ""):
            return {"ok": False, "skipped": "no fyers token"}
    except Exception as exc:
        return {"ok": False, "skipped": f"fyers unavailable: {exc}"}
    import universe_helper as U
    import ingest_fyers
    if not symbols:
        symbols = U.combined_universe(conn)
    mapping = ingest_fyers.resolve_symbols(conn, list(symbols))
    resolved = mapping["resolved"]
    targets = list(resolved)[:limit] if limit else list(resolved)
    result = {"ok": True, "symbols": len(targets), "filled_rows": 0,
              "symbols_filled": 0, "errors": []}
    for symbol in targets:
        have = {row[0] for row in conn.execute(
            "SELECT date FROM prices_daily WHERE symbol=? AND date BETWEEN ? "
            "AND ?", (symbol, start, end))}
        try:
            rows = ingest_fyers._fmt_candles(
                client.history_range(resolved[symbol],
                                     (dt.date.fromisoformat(start)
                                      - dt.timedelta(days=5)).isoformat(),
                                     end))
        except Exception as exc:
            result["errors"].append({"symbol": symbol, "error": str(exc)})
            continue
        rows = [r for r in rows if start <= r["date"] <= end
                and r["date"] not in have and r["close"] and r["close"] > 0]
        if not rows:
            continue
        if not dry_run:
            result["filled_rows"] += _write_rows(conn, symbol, rows)
        else:
            result["filled_rows"] += len(rows)
        result["symbols_filled"] += 1
    result["dry_run"] = dry_run
    return result


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    child = sub.add_parser("report")
    child.add_argument("--days", type=int, default=30)
    child = sub.add_parser("fill")
    child.add_argument("--days", type=int, default=30)
    child.add_argument("--limit", type=int, default=None)
    child.add_argument("--apply", action="store_true")
    child = sub.add_parser("history")
    child.add_argument("--from", dest="start", required=True)
    child.add_argument("--to", dest="end", required=True)
    child.add_argument("--symbols", default="")
    child.add_argument("--limit", type=int, default=None)
    child.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    conn = db.get_conn()
    try:
        if args.cmd == "report":
            out = missing_report(conn, days=args.days)
        elif args.cmd == "fill":
            out = fill_with_fyers(conn, days=args.days, limit=args.limit,
                                  dry_run=not args.apply)
        else:
            symbols = [s.strip().upper() for s in args.symbols.split(",")
                       if s.strip()] or None
            out = historical_fill(conn, symbols=symbols, start=args.start,
                                  end=args.end, limit=args.limit,
                                  dry_run=not args.apply)
        print(json.dumps(out, indent=2, default=str))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
