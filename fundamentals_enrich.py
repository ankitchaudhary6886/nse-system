"""Fill fund_veto's ownership inputs from the free ScanX snapshot table.

WHY: ``fund_veto`` vetoes on ``promoter_holding < 20``, but the ownership fields
in ``fundamentals`` are 0% populated here (partly on the VM), so the rule never
fires and the gate runs blind.  ``scanx_fundamentals_snapshots`` -- the free
export that ``scanx_import.py`` imports -- already carries promoter / FII / DII
holding for ~750 symbols.

PIT CONSTRAINT: it is a live snapshot with no populated
``financial_period_end``/``published_at`` and only host clock time in
``imported_at``, so a row cannot be placed in time.  Values from it are tagged
``undated_snapshot`` / ``live_veto_only`` / ``not_point_in_time``: usable ONLY
for today's live veto/screening, never for backtests, replay or as-of history.
``pledge_pct`` has no snapshot source and is never invented; a snapshot symbol
with no ``fundamentals`` row gets one created (symbol + ownership only) because
``fund_veto`` treats an absent row as "not vetoed" -- that sparse row is what
makes the promoter rule evaluable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sqlite3
from typing import Any, Dict, List, Optional, Sequence

import fundamentals_store

SNAPSHOT_TABLE = "scanx_fundamentals_snapshots"
SNAPSHOT_FLAGS = ("undated_snapshot", "live_veto_only", "not_point_in_time")
DESIRED_FIELDS = ("promoter_holding", "fii_holding", "pledge_pct", "dii_holding")
VETO_FIELDS = ("promoter_holding", "fii_holding", "pledge_pct")
BOUNDED_FIELDS = ("promoter_holding", "fii_holding", "dii_holding")
SOURCE_PREFIX, MAX_SAMPLE, MAX_INVALID_DETAIL = "scanx_snapshot", 5, 20
PIT_WARNING = (
    "scanx_fundamentals_snapshots is a live cross-sectional snapshot with no "
    "financial_period_end/published_at (imported_at is host time, not "
    "observation time). These values are NOT point-in-time: usable only for "
    "today's live veto/screening, never for backtests, replay or as-of history."
)


def _columns(conn: sqlite3.Connection, table: str) -> List[str]:
    try:
        return [row[1] for row in conn.execute("PRAGMA table_info({})".format(table))]
    except sqlite3.Error:
        return []


def _number(value: Any) -> Optional[float]:
    """Finite float, or None. Bools and unparsable text are rejected."""
    if value is None or isinstance(value, bool):
        return None
    text = value.strip().replace(",", "").rstrip("%") \
        if isinstance(value, str) else value
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _age_days(value: Any) -> Optional[int]:
    try:
        return (dt.date.today() - dt.date.fromisoformat(str(value)[:10])).days
    except ValueError:
        return None


def _coverage(conn: sqlite3.Connection, fields: Sequence[str]) -> Dict[str, int]:
    """Non-null count in ``fundamentals`` per field; absent columns are omitted."""
    present = set(_columns(conn, "fundamentals"))
    return {field: conn.execute(
        "SELECT COUNT({}) FROM fundamentals".format(field)).fetchone()[0]
        for field in fields if field in present}


def latest_snapshot(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Describe the newest snapshot. Read-only; tolerates an absent table."""
    out: Dict[str, Any] = {
        "available": False, "reason": None, "as_of_date": None, "date_column": None,
        "rows": 0, "symbols": [], "available_fields": [], "field_rows": {},
        "age_days": None, "pit_valid": False, "missing_fields": list(DESIRED_FIELDS),
        "warning": PIT_WARNING}
    cols = _columns(conn, SNAPSHOT_TABLE)
    if not cols or "symbol" not in cols:
        out["reason"] = "{} absent or unusable (ScanX export not imported)".format(
            SNAPSHOT_TABLE)
        return out
    if "as_of_date" not in cols and "imported_at" not in cols:
        out["reason"] = "{} has no as_of_date/imported_at".format(SNAPSHOT_TABLE)
        return out
    column = "as_of_date" if "as_of_date" in cols else "imported_at"
    as_of = conn.execute("SELECT MAX({}) FROM {} WHERE {} IS NOT NULL".format(
        column, SNAPSHOT_TABLE, column)).fetchone()[0]
    if _blank(as_of) and column == "as_of_date" and "imported_at" in cols:
        column = "imported_at"  # as_of_date was imported empty: fall back
        as_of = conn.execute(
            "SELECT MAX(imported_at) FROM {} WHERE imported_at IS NOT NULL".format(
                SNAPSHOT_TABLE)).fetchone()[0]
    out["date_column"] = column
    if _blank(as_of):
        out["reason"] = "{} holds no dated rows".format(SNAPSHOT_TABLE)
        return out
    out["symbols"] = sorted(str(row[0] or "").strip().upper() for row in conn.execute(
        "SELECT symbol FROM {} WHERE {}=?".format(SNAPSHOT_TABLE, column), (as_of,)))
    fields = [field for field in DESIRED_FIELDS if field in cols]
    counts = conn.execute("SELECT {} FROM {} WHERE {}=?".format(
        ",".join("COUNT({})".format(field) for field in fields), SNAPSHOT_TABLE,
        column), (as_of,)).fetchone()
    out.update(available=True, as_of_date=as_of, rows=len(out["symbols"]),
               available_fields=fields, field_rows=dict(zip(fields, counts)),
               missing_fields=[f for f in DESIRED_FIELDS if f not in cols],
               age_days=_age_days(as_of))
    return out


def enrich(conn: sqlite3.Connection, dry_run: bool = True, overwrite: bool = False,
           symbols: Optional[Sequence[str]] = None,
           limit: Optional[int] = None) -> Dict[str, Any]:
    """Copy snapshot ownership fields into ``fundamentals`` (never PIT-safe)."""
    result: Dict[str, Any] = dict(
        available=False, reason=None, snapshot_as_of=None, snapshot_source=None,
        candidates=0, rows_touched=0, fields_filled={}, fields_existing_kept=0,
        fields_unchanged=0, invalid_skipped=0, invalid=[], mapped_fields=[],
        unavailable_fields={}, dry_run=dry_run, coverage_after={}, sample=[],
        pit_valid=False, warning=PIT_WARNING)
    snapshot = latest_snapshot(conn)
    if not snapshot["available"]:
        result["reason"] = snapshot["reason"]
        return result
    as_of, column = snapshot["as_of_date"], snapshot["date_column"]
    fund = set(_columns(conn, "fundamentals"))
    snap = set(snapshot["available_fields"])
    mapped = [field for field in DESIRED_FIELDS if field in snap and field in fund]
    result.update(
        mapped_fields=mapped, snapshot_as_of=as_of,
        snapshot_source="{}:{}".format(SOURCE_PREFIX, as_of),
        unavailable_fields={field: ("no snapshot column" if field not in snap
                                    else "no fundamentals column")
                            for field in DESIRED_FIELDS if field not in mapped},
        fields_filled={field: 0 for field in mapped})
    if not fund or not mapped:
        result["reason"] = ("fundamentals table is absent" if not fund
                            else "no ownership field exists in both tables")
        result["coverage_after"] = _coverage(conn, DESIRED_FIELDS)
        return result

    wanted = {str(s or "").strip().upper() for s in (symbols or [])} - {""}
    rows = conn.execute(
        "SELECT {} FROM {} WHERE {}=? ORDER BY symbol".format(
            ",".join(["symbol"] + mapped), SNAPSHOT_TABLE, column),
        (as_of,)).fetchall()
    candidates = touched = 0
    for raw in rows:
        symbol = str(raw[0] or "").strip().upper()
        if not symbol or (wanted and symbol not in wanted):
            continue
        if limit is not None and candidates >= int(limit):
            break
        candidates += 1
        held = dict(zip(mapped, conn.execute(
            "SELECT {} FROM fundamentals WHERE symbol=?".format(",".join(mapped)),
            (symbol,)).fetchone() or (None,) * len(mapped)))
        values: Dict[str, Any] = {"symbol": symbol}
        written: Dict[str, float] = {}
        kept: List[str] = []
        invalid: List[Dict[str, Any]] = []
        for field, value in zip(mapped, raw[1:]):
            number = _number(value)
            if number is None:
                if not _blank(value):
                    invalid.append({"symbol": symbol, "field": field,
                                    "value": str(value), "reason": "not_numeric"})
                continue
            if field in BOUNDED_FIELDS and not 0.0 <= number <= 100.0:
                invalid.append({"symbol": symbol, "field": field,
                                "value": str(value), "reason": "outside_0_100"})
                continue
            if not overwrite and not _blank(held[field]):
                kept.append(field)  # overwrite=False never clobbers a value
            elif _number(held[field]) is not None \
                    and abs(_number(held[field]) - number) < 1e-9:
                result["fields_unchanged"] += 1  # idempotent re-apply
            else:
                values[field] = written[field] = number
        result["invalid_skipped"] += len(invalid)
        result["fields_existing_kept"] += len(kept)
        result["invalid"] += invalid[:max(0, MAX_INVALID_DETAIL - len(result["invalid"]))]
        if not written:
            continue
        touched += 1
        for field in written:
            result["fields_filled"][field] += 1
        if len(result["sample"]) < MAX_SAMPLE:
            result["sample"].append(
                {"symbol": symbol, "written": written, "kept": kept})
        if not dry_run:
            fundamentals_store.merge(
                conn, dict(values, data_quality_flags=list(SNAPSHOT_FLAGS)),
                source=result["snapshot_source"])
    if not dry_run:
        conn.commit()
    result.update(available=True, candidates=candidates, rows_touched=touched,
                  coverage_after=_coverage(conn, mapped))
    return result


def report(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Read-only: snapshot freshness plus the coverage the veto gate really has."""
    snapshot = latest_snapshot(conn)
    fields = set(_columns(conn, "fundamentals"))
    total = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0] \
        if fields else 0
    try:
        import universe_helper
        band = set(universe_helper.band_universe(conn, None))
    except Exception:  # band needs universe_broad; a thin DB must not fatal here
        band = set()
    with_row = {str(row[0] or "").strip().upper() for row in conn.execute(
        "SELECT symbol FROM fundamentals")} if fields else set()
    coverage, band_coverage = {}, {}
    for field in VETO_FIELDS:
        if field not in fields:
            coverage[field] = {"available": False, "non_null": 0, "pct": 0.0}
            band_coverage[field] = {"covered": 0, "pct": 0.0}
            continue
        non_null = conn.execute(
            "SELECT COUNT({}) FROM fundamentals".format(field)).fetchone()[0]
        coverage[field] = {"available": True, "non_null": non_null, "pct":
                           round(100.0 * non_null / total, 1) if total else 0.0}
        covered = len(band & {str(row[0] or "").strip().upper() for row in conn.execute(
            "SELECT symbol FROM fundamentals WHERE {} IS NOT NULL".format(field))})
        band_coverage[field] = {"covered": covered, "pct":
                                round(100.0 * covered / len(band), 1) if band else 0.0}
    return {
        "snapshot_available": snapshot["available"],
        "snapshot_reason": snapshot["reason"],
        "snapshot_as_of": snapshot["as_of_date"],
        "snapshot_date_column": snapshot["date_column"],
        "snapshot_rows": snapshot["rows"], "snapshot_age_days": snapshot["age_days"],
        "snapshot_field_rows": snapshot["field_rows"],
        "snapshot_missing_fields": snapshot["missing_fields"],
        "fundamentals_rows": total, "coverage": coverage,
        "band_total": len(band), "band_with_fundamentals": len(band & with_row),
        "band_coverage": band_coverage,
        "band_fillable_from_snapshot": len(band & set(snapshot.get("symbols") or [])),
        "pit_valid": False, "pit_warning": PIT_WARNING,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("snapshot", help="describe the newest snapshot")
    commands.add_parser("report", help="read-only snapshot + coverage report")
    write = commands.add_parser("enrich", help="copy ownership fields (dry run)")
    write.add_argument("--apply", action="store_true", help="actually write")
    write.add_argument("--overwrite", action="store_true",
                       help="replace existing non-null values")
    write.add_argument("--limit", type=int, help="max snapshot rows processed")
    args = parser.parse_args(argv)
    import db  # lazy: the CLI is the only place a real database is opened
    conn = db.get_conn()
    try:
        if args.command == "snapshot":
            output: Any = latest_snapshot(conn)
        elif args.command == "report":
            output = report(conn)
        else:
            output = enrich(conn, dry_run=not args.apply,
                            overwrite=args.overwrite, limit=args.limit)
    finally:
        conn.close()
    print(json.dumps(output, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
