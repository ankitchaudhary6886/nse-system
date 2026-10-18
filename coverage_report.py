"""Price-coverage diagnosis for the tradable universe (18 Oct 2026).

WHY THIS EXISTS
---------------
The live VM's last-60-session bar coverage was 75.2% while the freshness gate
was green. A fresh max date says nothing about *how many symbols* have bars:
40 universe symbols had no recent history at all. This module classifies every
gap so it can be fixed deliberately instead of being hidden inside an average:

  ok               latest bar == market max
  behind_max       has bars but older than the market max
  no_price         no bars at all
  ingest_gap       cash-equity symbol that SHOULD have been fetched (the old
                   price ingest only walked stocks.active, skipping band names)
  alias_candidate  project symbol differs from the exchange ticker (BOSCH_HCIL
                   vs BOSCH-HCIL); ingestion needs a punctation fallback
  non_tradable     SME / InvIT / REIT series that the swing universe should not
                   trade at all
  unresolved       no mapping in the Fyers cash-segment master

Read-only: it never writes prices, universe rows or settings. CLI prints JSON;
run `python coverage_report.py` for the diagnosis.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "app.db"
RECENT_DAYS = 10

# Exchange series suffixes that should not be in a daily-bar swing universe.
NON_TRADABLE_SUFFIXES = ("-SM", "-IV", "-RR", "-MF")


def _series_of(ticker: str) -> str:
    """'NSE:FOO-SM' -> 'SM'; 'NSE:FOO-EQ' / bare -> 'EQ'."""
    text = ticker.split(":")[-1]
    if "-" not in text:
        return "EQ"
    return text.rsplit("-", 1)[-1].upper()


def _classify_ticker(project_symbol: str, ticker: Optional[str]) -> str:
    if not ticker:
        return "unresolved"
    series = _series_of(ticker)
    if series in [s.lstrip("-") for s in NON_TRADABLE_SUFFIXES]:
        return "non_tradable"
    if series != "EQ":
        return "other_series"
    # A project symbol that needs punctuation normalization (BOSCH_HCIL,
    # BAGMANE.RR) is an alias candidate: the free price feeds expect the
    # exchange spelling and the old ingest did not retry it.
    if "_" in project_symbol or "." in project_symbol:
        return "alias_candidate"
    return "tradable_eq"


def diagnose(conn: sqlite3.Connection) -> Dict:
    """Classify every universe symbol's price coverage. READ-ONLY."""
    import universe_helper as U

    max_date = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
    universe = U.combined_universe(conn)
    last_seen = {row[0]: row[1] for row in conn.execute(
        "SELECT symbol, MAX(date) FROM prices_daily GROUP BY symbol")}
    in_stocks = {row[0] for row in conn.execute(
        "SELECT symbol FROM stocks WHERE active=1")}

    try:
        import ingest_fyers
        resolution = ingest_fyers.resolve_symbols(conn, universe)
        resolved: Dict[str, str] = resolution["resolved"]
        methods = resolution.get("tickers", {})
    except Exception:
        resolved, methods = {}, {}

    entries: List[Dict] = []
    for symbol in universe:
        last = last_seen.get(symbol)
        ticker = resolved.get(symbol)
        kind = _classify_ticker(symbol, ticker)
        if last and max_date and last >= max_date:
            status = "ok"
        elif last:
            status = "behind_max"
        else:
            status = "no_price"
        entries.append({
            "symbol": symbol,
            "status": status,
            "last_date": last,
            "ticker": ticker,
            "resolution": methods.get(symbol),
            "instrument": kind,
            "source_table": "stocks" if symbol in in_stocks else "band_only",
        })

    def bucket(predicate):
        return [e for e in entries if predicate(e)]

    no_price = bucket(lambda e: e["status"] == "no_price")
    behind = bucket(lambda e: e["status"] == "behind_max")
    gaps = bucket(lambda e: e["status"] != "ok")

    def count(values):
        out: Dict[str, int] = {}
        for value in values:
            out[value] = out.get(value, 0) + 1
        return out

    suggestions = []
    if bucket(lambda e: e["instrument"] == "tradable_eq"
              and e["status"] == "no_price"):
        suggestions.append(
            "price ingest should walk universe_helper.combined_universe (band + "
            "core), not only stocks.active, then retry punctuation-normalized "
            "tickers for alias_candidate symbols")
    if bucket(lambda e: e["instrument"] == "non_tradable"):
        suggestions.append("exclude SME/InvIT/REIT series from the swing "
                           "universe (they are not daily-swing instruments)")
    if bucket(lambda e: e["instrument"] == "unresolved"):
        suggestions.append("resolve remaining symbols via ISIN or mark them "
                           "inactive in the universe")
    if bucket(lambda e: e["status"] == "behind_max"):
        suggestions.append("symbols behind the market max may be suspended or "
                           "renamed; check the symbol master before re-fetching")

    return {
        "read_only": True,
        "max_price_date": max_date,
        "universe": len(universe),
        "in_stocks": len(in_stocks),
        "band_only": len([e for e in entries
                          if e["source_table"] == "band_only"]),
        "coverage": {
            "ok": len(entries) - len(gaps),
            "ok_pct": round(100.0 * (len(entries) - len(gaps))
                            / max(1, len(entries)), 1),
            "no_price": len(no_price),
            "behind_max": len(behind),
        },
        "by_instrument": count(e["instrument"] for e in gaps),
        "gap_rows": gaps,
        "suggestions": suggestions,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--sample", type=int, default=25,
                        help="gap rows to print in the text summary")
    args = parser.parse_args(argv)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA temp_store=MEMORY")
    try:
        report = diagnose(conn)
    finally:
        conn.close()
    print(json.dumps(report, indent=2, default=str)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
