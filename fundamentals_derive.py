"""Derive fundamentals that are algebraically implied by data we already own.

WHAT THIS ADDS (and why these three, not more)
----------------------------------------------
With ``current_price``, ``pe``, ``pb`` and ``market_cap_cr`` already in the
``fundamentals`` table, three reported figures are exactly recoverable:

    eps_ttm            = current_price / pe          (trailing P/E definition)
    book_value         = current_price / pb          (P/B definition)
    shares_outstanding = market_cap_cr * 1e7 / price (crore -> rupee)

Nothing is guessed. Each value is written with per-field provenance via
fundamentals_store.merge (``field_sources``) and a data-quality flag, so a
derived number can never masquerade as a reported one. ``eps_fy`` (the
reported fiscal-year column) is deliberately left untouched.

WHAT CANNOT BE DERIVED WITHOUT NEW SOURCE DATA
----------------------------------------------
sales/EBITDA/cash/debt levels (so no P/S, EV/EBITDA, ROIC beyond a guess),
promoter/pledge/FII holdings, dividend history, filing dates. Those require
the owner's DR-01/DR-16 data (see DATA_REQUESTS.md). The ScanX snapshot holds
many of them but has no financial period-end or publication date, so it stays
research-only and is not promoted here.

USAGE
-----
    python fundamentals_derive.py             # dry run (default): print only
    python fundamentals_derive.py --apply     # write derived fields
    python fundamentals_derive.py --symbol SBIN --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Optional

import db
from fundamentals_store import merge

SOURCE = "derived:price_pe_pb"
FLAGS = ["derived_not_reported",
         "derived_from_valuation_snapshot_without_filing_date"]


def _num(value) -> Optional[float]:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def derive_row(row: dict) -> Dict[str, float]:
    """Return only the values that pass sanity checks for one fundamentals row."""
    price = _num(row.get("current_price"))
    if not price or price <= 0:
        return {}
    out: Dict[str, float] = {}
    pe = _num(row.get("pe"))
    if pe and pe > 0:
        out["eps_ttm"] = round(price / pe, 4)
    pb = _num(row.get("pb"))
    if pb and pb > 0:
        out["book_value"] = round(price / pb, 4)
    mcap_cr = _num(row.get("market_cap_cr"))
    if mcap_cr and mcap_cr > 0:
        out["shares_outstanding"] = round(mcap_cr * 1e7 / price, 0)
    return out


def _sane(derived: Dict[str, float]) -> bool:
    eps = derived.get("eps_ttm")
    if eps is not None and abs(eps) > 100000:  # P/E of 0.001 is bad data
        return False
    shares = derived.get("shares_outstanding")
    if shares is not None and not (1e4 <= shares <= 1e13):
        return False
    book = derived.get("book_value")
    if book is not None and not (0 < book <= 1e7):
        return False
    return True


def run(apply: bool = False, symbol: Optional[str] = None,
        limit: Optional[int] = None) -> dict:
    conn = db.get_conn()
    sql = "SELECT * FROM fundamentals"
    params = []
    if symbol:
        sql += " WHERE symbol=?"
        params.append(symbol.strip().upper())
    sql += " ORDER BY symbol"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    cursor = conn.execute(sql, params)
    names = [d[0] for d in cursor.description]
    rows = [dict(zip(names, values)) for values in cursor]

    stats = {"rows": len(rows), "with_derivable": 0, "applied": 0,
             "skipped_implausible": 0, "fields": {}, "samples": [],
             "before": {}, "after": {}}
    for field in ("eps_ttm", "book_value", "shares_outstanding"):
        stats["before"][field] = conn.execute(
            f"SELECT COUNT(*) FROM fundamentals WHERE {field} IS NOT NULL"
        ).fetchone()[0]

    for row in rows:
        derived = derive_row(row)
        if not derived:
            continue
        if not _sane(derived):
            stats["skipped_implausible"] += 1
            continue
        stats["with_derivable"] += 1
        for field in derived:
            stats["fields"][field] = stats["fields"].get(field, 0) + 1
        if len(stats["samples"]) < 5:
            stats["samples"].append({"symbol": row["symbol"], **derived})
        if apply:
            values = {"symbol": row["symbol"], **derived,
                      "data_quality_flags": FLAGS}
            changed = merge(conn, values, source=SOURCE)
            if changed:
                stats["applied"] += 1
    if apply:
        conn.commit()
        for field in ("eps_ttm", "book_value", "shares_outstanding"):
            stats["after"][field] = conn.execute(
                f"SELECT COUNT(*) FROM fundamentals WHERE {field} IS NOT NULL"
            ).fetchone()[0]
    conn.close()
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write derived fields (default: dry run)")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    stats = run(apply=args.apply, symbol=args.symbol, limit=args.limit)
    print(json.dumps(stats, indent=2))
    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to store.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
