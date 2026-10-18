"""Replace adjusted (yfinance) price history with raw Fyers exchange prices.

WHY: the store's history came from yfinance with ``auto_adjust=True`` (split-
and dividend-adjusted) while Fyers equity history is raw. Mixing the two bases
creates fake gaps around corporate actions, so the universe must move to ONE
basis, symbol by symbol, with a guard on every symbol.

SAFETY REQUIREMENTS (read before applying)
------------------------------------------
* Dry run by default. ``--apply`` is the only way this writes anything.
* One guarded writer: this module never touches ``prices_daily`` /
  ``price_meta`` itself. Every write goes through
  ``ingest_fyers.ingest_symbol_history(mode="rebuild")``, which validates OHLC,
  refuses a fetch smaller than 60% of the stored bars in the window
  (``rebuild_shrunk``), replaces only the fetched window, keeps older rows, and
  records the new ``price_meta.basis`` (``fyers_raw`` /
  ``mixed_adjusted_then_raw``).
* A rebuild changes the price BASIS of that symbol. Every downstream artifact —
  technicals, scans, patterns, Top Picks, backtests — was computed from the old
  adjusted basis and MUST be recomputed after an apply run. The CLI prints that
  warning on ``--apply``.
* Backups are written by ``ingest_fyers`` to ``data/backups/`` (gitignored)
  before any row of that symbol is deleted.
* ``plan`` and ``report`` are strictly read-only.

USAGE::

    python rebuild_raw_history.py plan
    python rebuild_raw_history.py run                     # dry run (default)
    python rebuild_raw_history.py run --apply --limit 20
    python rebuild_raw_history.py run --apply --symbols SBIN,TCS --force
    python rebuild_raw_history.py verify --limit 20
    python rebuild_raw_history.py report

Exit code 2 means "not ok" (missing token, per-symbol errors, nothing
written); 0 means the operation succeeded.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from typing import Dict, Iterable, List, Optional, Sequence

import db
import ingest_fyers
from config import HISTORY_YEARS
from fyers_client import FyersAuthError, FyersClient

# FyersClient.history_range() pages the broker in 300-day requests; the estimate
# below must use the same chunk size or the API-call forecast is fiction.
CHUNK_DAYS = 300
REQ_PER_MIN = 180
CALLS_PER_SYMBOL = math.ceil(HISTORY_YEARS * 365 / CHUNK_DAYS) + 1  # +1 profile
# Statuses meaning "the guard refused to write": the symbol keeps its old
# (adjusted) basis and needs a human, not a blind retry.
BLOCKED_STATUSES = ("seam_mismatch", "seam_gap_suspect", "no_overlap",
                    "rebuild_shrunk", "no_valid_bars")
BASIS_STATES = ("legacy_adjusted", "fyers_raw", "mixed", "other")
_TOKEN_ERROR = ("no Fyers access token: run 'python fyers_client.py login-url' "
                "then 'python fyers_client.py exchange --code <auth_code>'")


def _universe(conn, symbols: Optional[Iterable[str]] = None,
              limit: Optional[int] = None) -> List[str]:
    """Target symbols, deduped and alphabetical (call order must be stable).

    The universe is the project's combined universe unless the caller names
    symbols: a rebuild is normally a whole-store migration, and a hand-written
    list would silently leave symbols on the adjusted basis.
    """
    if symbols:
        items = symbols.split(",") if isinstance(symbols, str) else list(symbols)
        out = sorted({str(s).strip().upper() for s in items if str(s).strip()})
    else:
        import universe_helper  # local: keeps plan/report importable alone
        out = sorted({str(s).strip().upper()
                      for s in universe_helper.combined_universe(conn)
                      if str(s).strip()})
    return out[:int(limit)] if limit else out


def _normalise_basis(value: Optional[str]) -> str:
    """Collapse a raw basis string into one of ``BASIS_STATES``.

    Idempotent, so an already-normalised label (report's ``legacy_adjusted``
    bucket) can never fall through to ``other``.
    """
    text = str(value or "").strip()
    if not text or text == "legacy_adjusted":
        return "legacy_adjusted"
    if text == "fyers_raw":
        return "fyers_raw"
    return "mixed" if text.startswith("mixed") else "other"


def _basis_map(conn, symbols: Sequence[str]) -> Dict[str, Optional[str]]:
    """symbol -> basis (chunked: SQLite caps the number of bound parameters)."""
    out: Dict[str, Optional[str]] = {}
    symbols = [str(s) for s in symbols]
    for i in range(0, len(symbols), 500):
        chunk = symbols[i:i + 500]
        marks = ",".join("?" * len(chunk))
        for symbol, basis in conn.execute(
                f"SELECT symbol, basis FROM price_meta WHERE symbol IN ({marks})",
                chunk):
            out[str(symbol)] = str(basis) if basis else None
    return out


def _basis_counts(conn, symbols: Sequence[str]) -> Dict[str, int]:
    """Basis census over exactly ``symbols``; a missing meta row is legacy."""
    known = _basis_map(conn, symbols)
    counts = dict.fromkeys(BASIS_STATES, 0)
    for symbol in symbols:
        counts[_normalise_basis(known.get(str(symbol)))] += 1
    return counts


def plan(conn, symbols: Optional[Iterable[str]] = None,
         limit: Optional[int] = None) -> dict:
    """Forecast the rebuild: what is left, how many calls, how long.

    Read-only by construction. ``limit`` truncates the universe (alphabetical)
    so a pilot batch costs exactly the calls the plan predicts.
    """
    universe = _universe(conn, symbols, limit)
    resolution = ingest_fyers.resolve_symbols(conn, universe)
    tickers = resolution["resolved"]
    basis = _basis_map(conn, list(tickers))
    counts = _basis_counts(conn, list(tickers))
    # A 5-year rebuild keeps rows older than the fetch window, so such a symbol
    # ends up 'mixed_adjusted_then_raw' forever. Retrying it on every run would
    # never converge (and would burn API calls), so 'mixed' is reported as a
    # pending human decision instead of being queued blindly.
    to_rebuild = [s for s in sorted(tickers)
                  if _normalise_basis(basis.get(s))
                  in ("legacy_adjusted", "other")]
    mixed_pending = [s for s in sorted(tickers)
                     if _normalise_basis(basis.get(s)) == "mixed"]
    calls = len(to_rebuild) * CALLS_PER_SYMBOL
    return {
        "read_only": True,
        "universe": len(universe),
        "resolved": len(tickers),
        "unresolved": resolution["unresolved"][:20],
        "unresolved_count": len(resolution["unresolved"]),
        "by_method": resolution["by_method"],
        "by_basis": counts,
        "to_rebuild": len(to_rebuild),
        "mixed_pending": len(mixed_pending),
        "mixed_pending_sample": mixed_pending[:10],
        "calls_per_symbol": CALLS_PER_SYMBOL,
        "estimated_api_calls": calls,
        "estimated_minutes": round(calls / REQ_PER_MIN, 1),
        "symbols_sample": to_rebuild[:10],
    }


def run(conn, client, symbols: Optional[Iterable[str]] = None,
        limit: Optional[int] = None, force: bool = False, dry_run: bool = True,
        progress: bool = True) -> dict:
    """Rebuild the resolved universe alphabetically, one guarded symbol at a time.

    ``force`` is passed straight through to ``ingest_symbol_history`` and is the
    only way past the seam/coverage guards — meant for a human who has checked
    the corporate-action calendar. ``FyersAuthError`` aborts the batch (no later
    symbol can succeed); any other exception is recorded against that symbol and
    the batch continues, because one broken ticker must not strand a 5-year
    migration. This function performs no writes itself.
    """
    started = time.monotonic()
    universe = _universe(conn, symbols)
    resolution = ingest_fyers.resolve_symbols(conn, universe)
    tickers = resolution["resolved"]
    targets = sorted(tickers)[:int(limit)] if limit else sorted(tickers)

    if not client.token:
        payload = plan(conn, symbols=universe) if dry_run else {}
        payload.update({
            "ok": bool(dry_run),
            "status": "dry_run_no_token" if dry_run else "blocked_no_token",
            "dry_run": bool(dry_run), "attempted": 0, "written": 0,
            "by_status": {}, "blocked": [], "errors": [],
            "basis_after": _basis_counts(conn, targets),
            "elapsed_seconds": round(time.monotonic() - started, 2)})
        if dry_run:
            payload["note"] = "dry run without a token: nothing was fetched"
        else:
            payload["error"] = _TOKEN_ERROR
        return payload

    include_today = ingest_fyers.market_closed_today()  # decided once per batch
    results: List[dict] = []
    aborted: Optional[str] = None
    for i, symbol in enumerate(targets, 1):
        try:
            result = ingest_fyers.ingest_symbol_history(
                conn, client, symbol, mode="rebuild",
                ticker=tickers.get(symbol), include_today=include_today,
                dry_run=dry_run, force=force)
        except FyersAuthError as exc:
            aborted = f"FyersAuthError: {exc}"
            break
        except Exception as exc:  # one bad symbol must not kill the batch
            result = {"symbol": symbol, "status": "error", "written": 0,
                      "error": f"{type(exc).__name__}: {exc}"}
        results.append(result)
        if progress and (i % 25 == 0 or i == len(targets)):
            print(f"  [{i}/{len(targets)}] {symbol}: {result.get('status')} "
                  f"(+{result.get('written', 0)})")

    by_status: Dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "?")
        by_status[status] = by_status.get(status, 0) + 1
    written = sum(int(result.get("written") or 0) for result in results)
    errors = [r["symbol"] for r in results if r.get("status") == "error"]
    summary = {
        "ok": bool(written > 0 and not errors and not aborted),
        "status": ("aborted_auth" if aborted else
                   "ok" if (written > 0 and not errors) else "no_writes"),
        "dry_run": bool(dry_run),
        "attempted": len(results),
        "written": written,
        "by_status": by_status,
        "blocked": [r["symbol"] for r in results
                    if r.get("status") in BLOCKED_STATUSES],
        "errors": errors,
        "unresolved": resolution["unresolved"],
        "basis_after": _basis_counts(conn, [r["symbol"] for r in results]),
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    if aborted:
        summary["error"] = aborted
    return summary


def verify_after(conn, client, symbols: Sequence[str], limit: int = 20,
                 days: int = 10) -> dict:
    """Prove the rebuild: compare broker bars with stored bars on shared dates.

    Thin wrapper over ``ingest_fyers.verify`` so the Lead has one call site and
    ticker resolution stays here. An empty symbol list is a valid no-op — it
    must not raise on a fresh database.
    """
    universe = _universe(conn, list(symbols or []))
    if not universe:
        return {"checked": 0, "verdicts": {}, "details": [], "unresolved": []}
    resolution = ingest_fyers.resolve_symbols(conn, universe)
    out = ingest_fyers.verify(conn, client, sorted(resolution["resolved"]),
                              days=days, limit=limit,
                              tickers=resolution["resolved"])
    out["unresolved"] = resolution["unresolved"]
    return out


def report(conn) -> dict:
    """Read-only census of the price basis across ``price_meta``."""
    bases = {str(name): int(count) for name, count in conn.execute(
        "SELECT COALESCE(NULLIF(TRIM(basis), ''), 'legacy_adjusted') AS b, "
        "COUNT(*) FROM price_meta GROUP BY b")}
    by_basis = dict.fromkeys(BASIS_STATES, 0)
    for name, count in bases.items():
        by_basis[_normalise_basis(name)] += count
    mixed = [r[0] for r in conn.execute(
        "SELECT symbol FROM price_meta WHERE basis LIKE 'mixed%' "
        "ORDER BY symbol LIMIT 10")]
    nulls = [r[0] for r in conn.execute(
        "SELECT symbol FROM price_meta WHERE basis IS NULL OR TRIM(basis)='' "
        "ORDER BY symbol LIMIT 50")]
    return {
        "read_only": True,
        "price_meta_rows": sum(bases.values()),
        "bases": bases,
        "by_basis": by_basis,
        "mixed_count": by_basis["mixed"],
        "mixed_sample": mixed,
        "null_basis_count": by_basis["legacy_adjusted"],
        "null_basis_sample": nulls,
        "max_price_date": conn.execute(
            "SELECT MAX(date) FROM prices_daily").fetchone()[0],
        "max_last_date": conn.execute(
            "SELECT MAX(last_date) FROM price_meta").fetchone()[0],
    }


def _build_parser() -> argparse.ArgumentParser:
    """CLI. ``run`` is dry by default: writing requires the explicit --apply."""
    parser = argparse.ArgumentParser(
        description="Rebuild raw Fyers price history (dry run by default).")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan", help="forecast the rebuild (read-only)")
    p_plan.add_argument("--symbols", help="comma separated subset")
    p_plan.add_argument("--limit", type=int, help="first N symbols")
    p_run = sub.add_parser("run", help="rebuild (dry run unless --apply)")
    p_run.add_argument("--apply", action="store_true",
                       help="actually write; without it nothing changes")
    p_run.add_argument("--symbols", help="comma separated subset")
    p_run.add_argument("--limit", type=int, help="first N symbols")
    p_run.add_argument("--force", action="store_true",
                       help="bypass seam/coverage guards (human-checked only)")
    p_run.add_argument("--no-progress", action="store_true")
    p_verify = sub.add_parser("verify", help="cross-check broker vs stored bars")
    p_verify.add_argument("--symbols", help="comma separated subset")
    p_verify.add_argument("--limit", type=int, default=20)
    p_verify.add_argument("--days", type=int, default=10)
    sub.add_parser("report", help="basis census (read-only)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    conn = db.get_conn()  # CLI-only: the API functions accept a connection
    try:
        if args.cmd == "plan":
            print(json.dumps(plan(conn, symbols=args.symbols, limit=args.limit),
                             indent=2, default=str))
            return 0
        if args.cmd == "report":
            print(json.dumps(report(conn), indent=2, default=str))
            return 0
        client = FyersClient()
        if args.cmd == "verify":
            try:
                out = verify_after(conn, client, _universe(conn, args.symbols),
                                   limit=args.limit, days=args.days)
            except FyersAuthError as exc:  # no token -> clean exit 2, no trace
                print(json.dumps({"ok": False, "status": "blocked_no_token",
                                  "error": f"FyersAuthError: {exc}"}, indent=2))
                return 2
            print(json.dumps(out, indent=2, default=str))
            return 2 if {"error", "mismatch", "adjustment_mismatch"} & set(
                out.get("verdicts", {})) else 0
        if args.apply:
            print("WARNING: a rebuild changes the price BASIS of each written "
                  "symbol.\n         Recompute technicals, scans, patterns, Top "
                  "Picks and backtests\n         before trusting any downstream "
                  "number.\n         Pre-apply backups live in "
                  f"{ingest_fyers.BACKUP_DIR} (gitignored).", file=sys.stderr)
        out = run(conn, client, symbols=args.symbols, limit=args.limit,
                  force=args.force, dry_run=not args.apply,
                  progress=not args.no_progress)
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
