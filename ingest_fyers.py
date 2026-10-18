"""Ingest Fyers NSE market data into data/app.db.

WHAT THIS WRITES
----------------
* ``prices_daily`` / ``price_meta`` — daily OHLCV (append-only by default)
* ``fyers_symbol_master`` — official NSE cash-segment symbol master
* ``fyers_quotes`` — point-in-time quote snapshots (audit trail)
* ``fyers_sync_log`` — one row per operation (what ran, when, result)

WHAT THIS NEVER DOES
--------------------
* no order / position / fund endpoint is called (data-only integration)
* no existing price bar is rewritten unless ``--mode rebuild`` is explicit
* no bar is written when the store's adjusted history and the broker's raw
  history disagree at the seam — that is how you get fake gaps around
  splits/dividends. The mismatch is reported and the symbol is skipped.

WHY THE SEAM CHECK MATTERS
--------------------------
Existing history came from yfinance with ``auto_adjust=True`` (split- and
dividend-adjusted). Fyers equity history is raw/unadjusted. Appending raw
prices to adjusted history silently creates a jump proportional to the
cumulative adjustment factor. So every incremental sync fetches a 10-day
overlap, measures the ratio, and refuses to append when it is off.

USAGE (after ``python fyers_client.py exchange --code ...``)
------------------------------------------------------------
    python ingest_fyers.py status
    python ingest_fyers.py master
    python ingest_fyers.py history --days 30            # stale symbols only
    python ingest_fyers.py history --symbols SBIN,TCS --days 30
    python ingest_fyers.py history --all --limit 20     # pilot batch
    python ingest_fyers.py verify --days 10 --limit 20  # cross-source proof
    python ingest_fyers.py quotes --all
    python ingest_fyers.py sync                         # daily driver

``--dry-run`` prints what would be written and writes nothing.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import db
import universe_helper as U
from config import HISTORY_YEARS
from fyers_client import (FyersAuthError, FyersClient, FyersError, IST,
                          _fmt_candles, from_fyers_symbol, parse_symbol_master,
                          to_fyers_symbol)

ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / "data" / "backups"
MASTER_STALE_DAYS = 7
SEAM_TOLERANCE = 0.02  # 2% = any corporate action; ordinary noise is <0.5%
# A corporate action *after* the last stored bar is invisible to the overlap
# check (all overlap dates are pre-event). The only remaining signal is the gap
# between the last stored close and the first new broker bar: a split/bonus is
# >15%, an ordinary session in this universe is <15%. Block, don't guess.
FIRST_BAR_GAP_TOLERANCE = 0.15
# A rebuild may legitimately return fewer rows (holidays, suspension), but not
# less than this fraction of what is stored: a 40% shrink means the fetch was
# truncated and deleting the history would destroy data.
REBUILD_MIN_COVERAGE = 0.60
MIN_BAR_VALIDATION = {
    "max_daily_move": 0.60,   # >60% in one day is almost certainly bad data
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def today_ist() -> dt.date:
    return now_ist().date()


def market_closed_today() -> bool:
    """Allow today's bar only after the 15:30 IST close (buffer to 15:40)."""
    now = now_ist()
    return (now.hour, now.minute) >= (15, 40)


def _latest_price(conn, symbol: str) -> Optional[str]:
    row = conn.execute(
        "SELECT last_date FROM price_meta WHERE symbol=?", (symbol,)).fetchone()
    if row and row[0]:
        return str(row[0])[:10]
    row = conn.execute(
        "SELECT MAX(date) FROM prices_daily WHERE symbol=?", (symbol,)).fetchone()
    return str(row[0])[:10] if row and row[0] else None


def _bar_is_valid(row: dict, previous_close: Optional[float]) -> bool:
    o, h, l, c = row["open"], row["high"], row["low"], row["close"]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (o, h, l, c)):
        return False
    if min(o, h, l, c) <= 0 or h < l:
        return False
    if c > h * 1.02 or c < l * 0.98:
        return False
    if row["volume"] is None or row["volume"] < 0:
        return False
    if previous_close and previous_close > 0:
        move = abs(c / previous_close - 1.0)
        if move > MIN_BAR_VALIDATION["max_daily_move"]:
            return False
    return True


def _dedupe_sorted(rows: Iterable[dict]) -> List[dict]:
    by_date = {}
    for row in rows:
        by_date[row["date"]] = row
    return [by_date[d] for d in sorted(by_date)]


# ---------------------------------------------------------------------------
# symbol master
# ---------------------------------------------------------------------------
def refresh_symbol_master(conn, client: FyersClient, dry_run: bool = False,
                          url: Optional[str] = None) -> dict:
    text = client.symbol_master_text(url) if url else client.symbol_master_text()
    rows = parse_symbol_master(text)
    if not rows:
        raise FyersError("symbol master parsed to zero rows — format changed")
    imported_at = now_ist().isoformat(timespec="seconds")
    latest_source = max((r["source_updated"] or "") for r in rows)
    stats = {"parsed": len(rows), "new": 0, "updated": 0,
             "source_updated": latest_source or None}
    existing = {r[0] for r in conn.execute(
        "SELECT symbol FROM fyers_symbol_master")}
    if not dry_run:
        for row in rows:
            conn.execute(
                "INSERT OR REPLACE INTO fyers_symbol_master VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["symbol"], row["ticker"], row["name"], row["isin"],
                 row["fy_token"], row["lot_size"], row["tick_size"],
                 row["exchange"], row["segment"], row["source_updated"],
                 imported_at, row["raw"]))
        conn.commit()
        stats["new"] = len(set(r["symbol"] for r in rows) - existing)
        stats["updated"] = len(rows) - stats["new"]
    record_sync(conn, "symbol_master", "ok", len(rows), len(rows),
                detail=json.dumps(stats), dry_run=dry_run)
    return stats

def master_symbols(conn) -> Dict[str, dict]:
    return {row[0]: {"ticker": row[1], "isin": row[2], "source_updated": row[3]}
            for row in conn.execute(
                "SELECT symbol, ticker, isin, source_updated "
                "FROM fyers_symbol_master")}


# Series suffixes Fyers uses for non-EQ NSE instruments: SME (-SM),
# trade-to-trade (-BE/-BZ), REIT (-RR), InvIT (-IV), mutual funds (-MF).
SERIES_SUFFIXES = ("-SM", "-BE", "-BZ", "-ST", "-RR", "-IV", "-MF", "-N1")


def _symbol_candidates(symbol: str) -> List[str]:
    text = str(symbol or "").strip().upper()
    out = [text]
    if "_" in text:
        out.append(text.replace("_", "-"))
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        out.append(f"{base}-{suffix}")
        out.append(base)
    for suffix in SERIES_SUFFIXES:
        out.append(text + suffix)
    seen = set()
    return [x for x in out if x and not (x in seen or seen.add(x))]


def resolve_symbols(conn, symbols: Sequence[str]) -> dict:
    """Map project symbols to Fyers NSE tickers, with evidence of how.

    Order of evidence:
      1. exact symbol match in the broker master
      2. punctuation normalization (``BAJAJ_AUTO`` -> ``BAJAJ-AUTO``)
      3. known series suffix (``BAGMANE.RR`` -> ``BAGMANE-RR``, SME ``-SM``)
      4. ISIN join via the ScanX snapshot (official identifier, best proof)

    Unresolved symbols are returned, never silently dropped: they are usually
    renamed/delisted tickers and must not be fetched under a guessed ticker.
    """
    master = master_symbols(conn)
    isin_to_ticker = {row["isin"]: row["ticker"] for row in master.values()
                      if row.get("isin")}
    scanx_isin = {}
    try:
        for symbol, isin in conn.execute(
                "SELECT symbol, isin FROM scanx_fundamentals_snapshots "
                "WHERE isin IS NOT NULL AND isin != ''"):
            scanx_isin[str(symbol).upper()] = isin
    except Exception:
        scanx_isin = {}
    resolved, unresolved, methods = {}, [], {}
    for raw in symbols:
        symbol = str(raw or "").strip().upper()
        if not symbol:
            continue
        for candidate in _symbol_candidates(symbol):
            if candidate in master:
                resolved[symbol] = master[candidate]["ticker"]
                methods[symbol] = "exact" if candidate == symbol else "normalized"
                break
        else:
            isin = scanx_isin.get(symbol)
            if isin and isin in isin_to_ticker:
                resolved[symbol] = isin_to_ticker[isin]
                methods[symbol] = "isin"
                continue
            unresolved.append(symbol)
    by_method = {}
    for method in methods.values():
        by_method[method] = by_method.get(method, 0) + 1
    return {"resolved": resolved, "tickers": methods,
            "unresolved": unresolved, "by_method": by_method}


def master_status(conn) -> dict:
    row = conn.execute(
        "SELECT COUNT(*), MIN(imported_at), MAX(imported_at), MAX(source_updated) "
        "FROM fyers_symbol_master").fetchone()
    count, imported_from, imported_to, source_updated = row
    age = None
    if imported_to:
        try:
            age = (now_ist().date()
                   - dt.date.fromisoformat(str(imported_to)[:10])).days
        except ValueError:
            age = None
    return {"rows": count, "imported_from": imported_from,
            "imported_to": imported_to, "source_updated": source_updated,
            "age_days": age}


# ---------------------------------------------------------------------------
# price history
# ---------------------------------------------------------------------------
def _overlap_factor(conn, symbol: str, rows: List[dict]) -> dict:
    """Compare freshly fetched bars with stored bars on shared dates."""
    stored = dict(conn.execute(
        "SELECT date, close FROM prices_daily WHERE symbol=? ORDER BY date DESC "
        "LIMIT 30", (symbol,)).fetchall())
    both = [(r["date"], stored[r["date"]], r["close"]) for r in rows
            if r["date"] in stored and stored[r["date"]]]
    if not both:
        return {"overlap_days": 0, "factor": None, "mismatches": []}
    ratios = [float(f) / float(s) for _, s, f in both if s and s > 0]
    ratios.sort()
    factor = ratios[len(ratios) // 2] if ratios else None
    mismatches = [{"date": d, "stored": s, "fyers": f,
                   "ratio": round(float(f) / float(s), 6)}
                  for d, s, f in both
                  if s and s > 0 and abs(float(f) / float(s) - 1.0) > 0.005]
    return {"overlap_days": len(both), "factor": factor,
            "mismatches": mismatches}


def _attach_corporate_action(conn, symbol: str, date: str,
                             result: dict) -> None:
    """Best-effort: attach the recorded corporate action behind a seam block.

    Turns "refusing to append" into "probable 1:10 split on 2026-10-09" when the
    corporate-action book (corporate_actions.py) knows the event. Never raises;
    a lookup failure must not change the guard decision.
    """
    try:
        import corporate_actions
        explanation = corporate_actions.explain(conn, symbol, date)
    except Exception:
        return
    action = explanation.get("action") if isinstance(explanation, dict) else None
    if action:
        result["corporate_action"] = action
        result["note"] = (
            f"{result.get('note', '')} (probable {action.get('kind')} on "
            f"{action.get('ex_date')} from {action.get('source')}; "
            f"status={action.get('status')})").strip()


def _stored_basis(conn, symbol: str) -> Optional[str]:
    try:
        row = conn.execute(
            "SELECT basis FROM price_meta WHERE symbol=?", (symbol,)).fetchone()
    except Exception:  # pre-migration database
        return None
    return (row[0] if row and row[0] else None)


def _last_stored_close(conn, symbol: str) -> Optional[float]:
    row = conn.execute(
        "SELECT close FROM prices_daily WHERE symbol=? ORDER BY date DESC "
        "LIMIT 1", (symbol,)).fetchone()
    try:
        return float(row[0]) if row and row[0] is not None else None
    except (TypeError, ValueError):
        return None


def ingest_symbol_history(conn, client: FyersClient, symbol: str,
                          start: Optional[str] = None, end: Optional[str] = None,
                          mode: str = "append", force: bool = False,
                          dry_run: bool = False,
                          include_today: Optional[bool] = None,
                          ticker: Optional[str] = None) -> dict:
    """Fetch and store one symbol's daily bars. Returns a result dict.

    The function is deliberately paranoid. It refuses to write when it cannot
    prove the broker bars are on the same price basis as the stored series
    (no overlap, seam ratio off, or a >15% jump between the last stored close
    and the first new bar). ``force=True`` is the only way past these guards and
    is meant for a human who has checked the corporate-action calendar.
    """
    symbol = symbol.strip().upper()
    fetch_symbol = (ticker or to_fyers_symbol(symbol))
    end_date = end or today_ist().isoformat()
    include_today = market_closed_today() if include_today is None else include_today
    last_existing = _latest_price(conn, symbol)
    last_close = _last_stored_close(conn, symbol) if last_existing else None

    if mode == "rebuild":
        fetch_start = start or (today_ist()
                                - dt.timedelta(days=365 * HISTORY_YEARS)).isoformat()
    else:
        fetch_start = start or (last_existing
                                or (today_ist() - dt.timedelta(days=365)).isoformat())
        # overlap window lets us measure the adjustment factor at the seam
        fetch_start = (dt.date.fromisoformat(str(fetch_start)[:10])
                       - dt.timedelta(days=15)).isoformat()

    candles = client.history_range(fetch_symbol, fetch_start, end_date)
    rows = _dedupe_sorted(_fmt_candles(candles))
    if not include_today:
        rows = [r for r in rows if r["date"] < today_ist().isoformat()]
    if not rows:
        return {"symbol": symbol, "ticker": fetch_symbol, "status": "no_data",
                "written": 0, "fetched": 0, "last_existing": last_existing,
                "basis": _stored_basis(conn, symbol)}

    result = {"symbol": symbol, "ticker": fetch_symbol, "fetched": len(rows),
              "written": 0, "last_existing": last_existing, "status": "ok",
              "seam_factor": None, "first_new_gap_pct": None,
              "skipped_invalid": 0, "basis": _stored_basis(conn, symbol)}

    overlap = _overlap_factor(conn, symbol, rows)
    result["seam_factor"] = (round(overlap["factor"], 6)
                             if overlap["factor"] is not None else None)
    result["overlap_days"] = overlap["overlap_days"]

    if mode == "append" and last_existing:
        factor = overlap["factor"]
        if overlap["overlap_days"] == 0 or factor is None:
            # No shared dates (or unreadable stored closes) means the two series
            # cannot be proven to share a price basis. Writing anyway is how a
            # 45% fake gap gets created the day after a split.
            result["status"] = "no_overlap"
            result["note"] = ("no provable overlap with stored history; "
                              "refusing to append (use --mode rebuild, or "
                              "--force only after checking corporate actions)")
            record_sync(conn, "history", "no_overlap", 1, 0,
                        error=json.dumps(result), dry_run=dry_run)
            return result
        if abs(factor - 1.0) > SEAM_TOLERANCE and not force:
            result["status"] = "seam_mismatch"
            result["seam_mismatches"] = overlap["mismatches"][:5]
            result["note"] = ("store history looks split/dividend-adjusted and "
                              "broker history is raw; rebuild the symbol "
                              "(--mode rebuild) instead of appending")
            _attach_corporate_action(conn, symbol, rows[0]["date"], result)
            record_sync(conn, "history", "seam_mismatch", 1, 0,
                        error=json.dumps(result), dry_run=dry_run)
            return result
        rows = [r for r in rows if r["date"] > last_existing]
        if not rows:
            result["status"] = "up_to_date"
            return result
        # Corporate action after the last stored bar: invisible to the overlap
        # check, visible as a jump between the last stored close and the first
        # new broker close.
        if last_close and last_close > 0:
            gap = rows[0]["close"] / last_close - 1.0
            result["first_new_gap_pct"] = round(gap * 100, 2)
            if abs(gap) > FIRST_BAR_GAP_TOLERANCE and not force:
                result["status"] = "seam_gap_suspect"
                result["note"] = ("first new bar jumps more than "
                                  f"{FIRST_BAR_GAP_TOLERANCE:.0%} from the last "
                                  "stored close — probable split/bonus/dividend "
                                  "after the last stored bar; rebuild instead of "
                                  "appending")
                _attach_corporate_action(conn, symbol, rows[0]["date"], result)
                record_sync(conn, "history", "seam_gap_suspect", 1, 0,
                            error=json.dumps(result), dry_run=dry_run)
                return result

    # Validate bars in sequence. For a rebuild the fetched series is raw
    # exchange data, which legitimately contains split/bonus jumps, so only the
    # structural checks apply there. For an append the chain is seeded with the
    # last stored close so even the first new bar is checked against a real
    # price (an unseeded chain validates the first bar against nothing).
    previous_close = last_close if mode == "append" else None
    valid: List[dict] = []
    for row in rows:
        if _bar_is_valid(row, previous_close):
            valid.append(row)
            previous_close = row["close"]
        else:
            result["skipped_invalid"] += 1
    if not valid:
        result["status"] = "no_valid_bars"
        return result

    if dry_run:
        result["status"] = "dry_run"
        result["written"] = len(valid)
        result["sample"] = valid[:3]
        return result

    if mode == "rebuild":
        # Coverage guard: compare against what the store holds *inside the
        # fetched window* (not the whole history, which may legitimately start
        # earlier than the requested range).
        existing_in_window = conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE symbol=? AND date>=?",
            (symbol, fetch_start)).fetchone()[0]
        if (existing_in_window
                and len(valid) < existing_in_window * REBUILD_MIN_COVERAGE
                and not force):
            result["status"] = "rebuild_shrunk"
            result["note"] = (f"broker returned {len(valid)} bars for "
                              f"{existing_in_window} stored in the requested "
                              "window; refusing to delete history on a "
                              "truncated fetch (use --force)")
            record_sync(conn, "history", "rebuild_shrunk", 1, 0,
                        error=json.dumps(result), dry_run=dry_run)
            return result
        # Keep rows older than the fetched window: a 5-year rebuild must not
        # silently amputate history the store already had.
        keep_before = valid[0]["date"]
        backup = _backup_symbol(conn, symbol)
        result["backup"] = str(backup) if backup else None
        conn.execute("DELETE FROM prices_daily WHERE symbol=? AND date>=?",
                     (symbol, keep_before))
        kept_older = conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE symbol=? AND date<?",
            (symbol, keep_before)).fetchone()[0]
        basis = "mixed_adjusted_then_raw" if kept_older else "fyers_raw"
    else:
        prior = _stored_basis(conn, symbol)
        if prior == "fyers_raw":
            basis = "fyers_raw"
        elif prior and prior.startswith("mixed"):
            basis = prior
        elif last_existing:
            basis = "mixed_adjusted_then_raw"
        else:
            basis = "fyers_raw"

    conn.executemany(
        "INSERT OR REPLACE INTO prices_daily "
        "(symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
        [(symbol, r["date"], r["open"], r["high"], r["low"], r["close"],
          r["volume"]) for r in valid])
    agg = conn.execute(
        "SELECT MAX(date), COUNT(*) FROM prices_daily WHERE symbol=?",
        (symbol,)).fetchone()
    conn.execute(
        "INSERT OR REPLACE INTO price_meta "
        "(symbol,last_date,rows,updated_at,basis) VALUES (?,?,?,?,?)",
        (symbol, agg[0], agg[1], now_ist().isoformat(timespec="seconds"),
         basis))
    conn.commit()
    result["written"] = len(valid)
    result["last_date"] = agg[0]
    result["basis"] = basis
    return result


def _backup_symbol(conn, symbol: str) -> Optional[Path]:
    rows = conn.execute(
        "SELECT date,open,high,low,close,volume FROM prices_daily "
        "WHERE symbol=? ORDER BY date", (symbol,)).fetchall()
    if not rows:
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_ist().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", symbol) or "UNKNOWN"
    path = BACKUP_DIR / f"fyers_rebuild_{safe}_{stamp}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        writer.writerows(rows)
    return path


def stale_symbols(conn, symbols: Sequence[str]) -> List[str]:
    """Symbols whose last bar is behind the market's most recent close."""
    market_last = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
    if not market_last:
        return list(symbols)
    out = []
    for symbol in symbols:
        last = _latest_price(conn, symbol)
        if last is None or last < str(market_last)[:10]:
            out.append(symbol)
    return out


def sync_history(conn, client: FyersClient, symbols: Sequence[str],
                 days: Optional[int] = None, mode: str = "append",
                 dry_run: bool = False, limit: Optional[int] = None,
                 force: bool = False, progress: bool = True,
                 tickers: Optional[Dict[str, str]] = None) -> dict:
    symbols = [s.upper() for s in symbols if s]
    if mode != "rebuild" and days:
        cutoff = (today_ist() - dt.timedelta(days=int(days))).isoformat()
        market_last = conn.execute(
            "SELECT MAX(date) FROM prices_daily").fetchone()[0]
        if market_last and str(market_last)[:10] >= cutoff:
            symbols = stale_symbols(conn, symbols)
    if limit:
        symbols = symbols[:int(limit)]
    results = []
    tickers = tickers or {}
    # Decide once whether today's (possibly half-formed) bar is allowed, so a
    # run that crosses 15:40 IST cannot treat earlier and later symbols
    # differently.
    include_today = market_closed_today()
    for i, symbol in enumerate(symbols, 1):
        try:
            result = ingest_symbol_history(conn, client, symbol, mode=mode,
                                           dry_run=dry_run, force=force,
                                           ticker=tickers.get(symbol),
                                           include_today=include_today)
        except FyersAuthError:
            raise
        except Exception as exc:  # one bad symbol must not kill the batch
            result = {"symbol": symbol, "status": "error",
                      "error": f"{type(exc).__name__}: {exc}", "written": 0}
            record_sync(conn, "history", "error", 1, 0,
                        error=f"{symbol}: {exc}", dry_run=dry_run)
        results.append(result)
        if progress and (i % 25 == 0 or i == len(symbols)):
            print(f"  [{i}/{len(symbols)}] {symbol}: "
                  f"{result.get('status')} (+{result.get('written', 0)})")
    summary = {
        "symbols": len(results),
        "written": sum(r.get("written", 0) for r in results),
        "ok": sum(1 for r in results if r.get("status") == "ok"),
        "dry_run": dry_run,
        "by_status": {},
    }
    for r in results:
        status = r.get("status", "?")
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
    summary["seam_mismatches"] = [r["symbol"] for r in results
                                  if r.get("status") == "seam_mismatch"]
    summary["seam_gap_suspects"] = [r["symbol"] for r in results
                                    if r.get("status") == "seam_gap_suspect"]
    blocked_states = {"seam_mismatch", "seam_gap_suspect", "no_overlap",
                      "rebuild_shrunk", "no_valid_bars"}
    summary["blocked"] = [r["symbol"] for r in results
                          if r.get("status") in blocked_states]
    summary["errors"] = [r["symbol"] for r in results
                         if r.get("status") == "error"]
    # One log row per batch (anomalies are logged per symbol). A per-symbol row
    # would add ~1,347 rows every trading day for no audit value.
    record_sync(conn, "history", "batch", len(results), summary["written"],
                detail=json.dumps(summary, default=str), dry_run=dry_run)
    return summary


# ---------------------------------------------------------------------------
# quotes snapshot
# ---------------------------------------------------------------------------
def snapshot_quotes(conn, client: FyersClient, symbols: Sequence[str],
                    dry_run: bool = False) -> dict:
    tickers = [s for s in symbols if s]
    quotes = client.quotes(tickers)
    # Seconds, not minutes: two snapshots inside one minute must not collide on
    # the (symbol, ts) primary key.
    ts = now_ist().isoformat(timespec="seconds")
    source = "fyers_eod" if market_closed_today() else "fyers_live"
    written = 0
    if not dry_run:
        for symbol, quote in quotes.items():
            conn.execute(
                "INSERT OR REPLACE INTO fyers_quotes VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (symbol, ts, quote.get("ltp"), quote.get("prev_close"),
                 quote.get("open"), quote.get("high"), quote.get("low"),
                 quote.get("close"), quote.get("volume"), quote.get("change"),
                 quote.get("change_pct"), quote.get("bid"), quote.get("ask"),
                 quote.get("spread"), source,
                 json.dumps(quote.get("raw"), default=str)))
            written += 1
        conn.commit()
    record_sync(conn, "quotes", "ok" if quotes else "empty", len(tickers),
                written, dry_run=dry_run)
    return {"requested": len(tickers), "returned": len(quotes),
            "written": written, "ts": ts}


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------
def verify_symbol(conn, client: FyersClient, symbol: str,
                  days: int = 10, tolerance: float = 0.01,
                  ticker: Optional[str] = None) -> dict:
    """Cross-check broker bars against stored bars on overlapping dates."""
    end = today_ist().isoformat()
    start = (today_ist() - dt.timedelta(days=days + 5)).isoformat()
    candles = client.history_range(ticker or to_fyers_symbol(symbol), start, end)
    rows = _dedupe_sorted(_fmt_candles(candles))
    overlap = _overlap_factor(conn, symbol, rows)
    stored = {d: c for d, c in conn.execute(
        "SELECT date, close FROM prices_daily WHERE symbol=? AND date>=?",
        (symbol, start)).fetchall()}
    compared = []
    for row in rows:
        if row["date"] in stored and stored[row["date"]]:
            diff = abs(row["close"] / stored[row["date"]] - 1.0) \
                if stored[row["date"]] else None
            compared.append({"date": row["date"], "stored": stored[row["date"]],
                             "fyers": row["close"],
                             "diff_pct": round(diff * 100, 3) if diff is not None else None})
    matched = [c for c in compared if c["diff_pct"] is not None
               and c["diff_pct"] <= tolerance * 100]
    fresh_dates = [r["date"] for r in rows if r["date"] not in stored]
    return {
        "symbol": symbol,
        "broker_rows": len(rows),
        "overlap_rows": len(compared),
        "matched": len(matched),
        "factor": (round(overlap["factor"], 6)
                   if overlap["factor"] is not None else None),
        "new_dates": len(fresh_dates),
        "max_diff_pct": (max(abs(c["diff_pct"]) for c in compared
                             if c["diff_pct"] is not None)
                         if compared else None),
        "verdict": _verify_verdict(overlap["factor"], len(compared), len(matched)),
    }


def _verify_verdict(factor, compared: int, matched: int) -> str:
    if compared == 0:
        return "no_overlap"
    if factor is not None and abs(factor - 1.0) > SEAM_TOLERANCE:
        return "adjustment_mismatch"
    if matched == compared:
        return "match"
    if matched / compared >= 0.8:
        return "mostly_match"
    return "mismatch"


def verify(conn, client: FyersClient, symbols: Sequence[str], days: int = 10,
           limit: Optional[int] = None,
           tickers: Optional[Dict[str, str]] = None) -> dict:
    symbols = list(symbols)
    if limit:
        symbols = symbols[:int(limit)]
    tickers = tickers or {}
    out = []
    for i, symbol in enumerate(symbols, 1):
        try:
            out.append(verify_symbol(conn, client, symbol, days=days,
                                     ticker=tickers.get(symbol)))
        except FyersAuthError:
            raise
        except Exception as exc:
            out.append({"symbol": symbol, "verdict": "error",
                        "error": f"{type(exc).__name__}: {exc}"})
        if i % 25 == 0 or i == len(symbols):
            print(f"  verified {i}/{len(symbols)}")
    verdicts: Dict[str, int] = {}
    for row in out:
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    return {"checked": len(out), "verdicts": verdicts, "details": out}


# ---------------------------------------------------------------------------
# sync log + status
# ---------------------------------------------------------------------------
def record_sync(conn, kind: str, status: str, symbols: int, rows: int,
                error: Optional[str] = None, detail: Optional[str] = None,
                dry_run: bool = False) -> None:
    if dry_run:
        return
    conn.execute(
        "INSERT INTO fyers_sync_log "
        "(run_at, kind, status, symbols, rows, error, detail) "
        "VALUES (?,?,?,?,?,?,?)",
        (now_ist().isoformat(timespec="seconds"), kind, status, symbols, rows,
         error, detail))
    conn.commit()


def status(conn, client: Optional[FyersClient] = None) -> dict:
    client = client or FyersClient()
    price_last = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
    quotes = conn.execute("SELECT COUNT(*), MAX(ts) FROM fyers_quotes").fetchone()
    sync = conn.execute(
        "SELECT run_at, kind, status, symbols, rows FROM fyers_sync_log "
        "ORDER BY run_at DESC LIMIT 5").fetchall()
    out = {
        "credentials": {
            "app_id": client.app_id or None,
            "token": client.token_store.status(),
        },
        "prices_latest_date": price_last,
        "prices_stale_days": ((today_ist()
                               - dt.date.fromisoformat(str(price_last)[:10])).days
                              if price_last else None),
        "symbol_master": master_status(conn),
        "quotes": {"rows": quotes[0], "latest_ts": quotes[1]},
        "last_sync_log": [{"run_at": r[0], "kind": r[1], "status": r[2],
                           "symbols": r[3], "rows": r[4]} for r in sync],
    }
    if client.token:
        try:
            out["token_valid"] = client.is_token_valid()
        except FyersError as exc:
            out["token_valid"] = False
            out["token_error"] = str(exc)
    else:
        out["token_valid"] = False
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _resolve_symbols(conn, args) -> List[str]:
    if args.symbols:
        return [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if args.all:
        return U.combined_universe(conn)
    return stale_symbols(conn, U.combined_universe(conn))


def _cmd_history(conn, client, args) -> int:
    symbols = _resolve_symbols(conn, args)
    if not symbols:
        print("no symbols selected")
        return 0
    resolution = resolve_symbols(conn, symbols)
    if resolution["unresolved"]:
        print("unresolved (not in broker master): "
              + ", ".join(resolution["unresolved"][:20]))
    symbols = list(resolution["resolved"])
    summary = sync_history(conn, client, symbols, days=args.days,
                           mode=args.mode, dry_run=args.dry_run,
                           limit=args.limit, force=args.force,
                           tickers=resolution["resolved"])
    print(json.dumps(summary, indent=2))
    if summary["seam_mismatches"] or summary.get("seam_gap_suspects"):
        print("\nSEAM PROBLEM (not appended — adjusted-vs-raw history):")
        print("  mismatch: " + ", ".join(summary["seam_mismatches"][:30]))
        print("  suspect : " + ", ".join(summary.get("seam_gap_suspects", [])[:30]))
        print("  Fix: python ingest_fyers.py history --mode rebuild "
              "--symbols <symbols>")
    return 1 if summary["errors"] else 0


def _cmd_verify(conn, client, args) -> int:
    symbols = _resolve_symbols(conn, args)
    resolution = resolve_symbols(conn, symbols)
    report = verify(conn, client, list(resolution["resolved"]), days=args.days,
                    limit=args.limit or 20, tickers=resolution["resolved"])
    print(json.dumps({k: report[k] for k in ("checked", "verdicts")}, indent=2))
    for row in report["details"]:
        if row["verdict"] not in ("match",):
            print("  ", json.dumps(row))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="status",
                        choices=["status", "master", "history", "quotes",
                                 "verify", "sync"])
    parser.add_argument("--symbols", default="")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mode", default="append", choices=["append", "rebuild"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.get_conn()
    client = FyersClient()
    try:
        if args.command == "status":
            print(json.dumps(status(conn, client), indent=2))
            return 0
        if args.command == "master":
            stats = refresh_symbol_master(conn, client, dry_run=args.dry_run)
            print(json.dumps(stats, indent=2))
            return 0
        if not client.token:
            print("No Fyers token. Run: python fyers_client.py login-url",
                  file=sys.stderr)
            return 1
        if args.command == "history":
            return _cmd_history(conn, client, args)
        if args.command == "quotes":
            symbols = _resolve_symbols(conn, args)
            print(json.dumps(snapshot_quotes(conn, client, symbols,
                                             dry_run=args.dry_run), indent=2))
            return 0
        if args.command == "verify":
            return _cmd_verify(conn, client, args)
        if args.command == "sync":
            return _cmd_sync(conn, client, args)
        return 0
    except FyersAuthError as exc:
        print(f"AUTH FAILED: {exc}", file=sys.stderr)
        return 2
    except FyersError as exc:
        print(f"FYERS ERROR: {exc} (code={exc.code})", file=sys.stderr)
        return 2
    finally:
        conn.close()


def _cmd_sync(conn, client, args) -> int:
    """Daily driver: refresh master when old, then append stale price history."""
    out = {}
    master = master_status(conn)
    if master["rows"] == 0 or (master["age_days"] is not None
                               and master["age_days"] > MASTER_STALE_DAYS):
        out["master"] = refresh_symbol_master(conn, client, dry_run=args.dry_run)
    universe = U.combined_universe(conn)
    resolution = resolve_symbols(conn, universe)
    out["universe"] = {
        "total": len(universe),
        "resolved": len(resolution["resolved"]),
        "unresolved": len(resolution["unresolved"]),
        "by_method": resolution["by_method"],
        "unresolved_sample": resolution["unresolved"][:15],
    }
    out["history"] = sync_history(
        conn, client, list(resolution["resolved"]), days=args.days or 15,
        dry_run=args.dry_run, limit=args.limit, tickers=resolution["resolved"])
    print(json.dumps(out, indent=2))
    if not out["universe"]["resolved"]:
        print("Nothing resolved to broker tickers — check fyers_symbol_master.",
              file=sys.stderr)
        return 1
    return 1 if out["history"]["errors"] else 0


def sync_recent(days: int = 15, dry_run: bool = False,
                conn=None, client=None) -> dict:
    """Entry point used by daily_update.py; never raises.

    ``ok`` means *something moved forward*: at least one resolved symbol either
    received new bars or was already up to date. A run that resolved nothing or
    wrote nothing reports ``ok: False`` so the daily log cannot say "FYERS OK"
    after a total no-op.
    """
    own_conn = conn is None
    conn = conn
    try:
        if conn is None:
            try:
                conn = db.get_conn()
            except Exception as exc:
                return {"ok": False, "error": f"db: {exc}"}
        client = client or FyersClient()
        if not client.token:
            return {"ok": False, "skipped": "no fyers token"}
        master = master_status(conn)
        refreshed = None
        if master["rows"] == 0 or (master["age_days"] is not None
                                   and master["age_days"] > MASTER_STALE_DAYS):
            refreshed = refresh_symbol_master(conn, client, dry_run=dry_run)
        resolution = resolve_symbols(conn, U.combined_universe(conn))
        resolved = len(resolution["resolved"])
        if not resolved:
            return {"ok": False, "resolved": 0,
                    "unresolved": len(resolution["unresolved"]),
                    "error": "no universe symbol resolved to a broker ticker"}
        result = sync_history(conn, client, list(resolution["resolved"]),
                              days=days, dry_run=dry_run, progress=False,
                              tickers=resolution["resolved"])
        up_to_date = result["by_status"].get("up_to_date", 0)
        ok = bool(result["written"] > 0 or up_to_date == resolved)
        return {"ok": ok, "master_refreshed": refreshed is not None,
                "resolved": resolved,
                "unresolved": len(resolution["unresolved"]), **result}
    except FyersAuthError as exc:
        return {"ok": False, "auth_error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if own_conn and conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
