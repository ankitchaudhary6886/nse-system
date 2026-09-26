"""Attest overlapping KITE and ScanX values, then refresh confirmed fields.

Only same-date, symbol-matched values that meet explicit cross-source
agreement rules are promoted. Unconfirmed metrics remain in their isolated
source snapshots and are recorded as withheld in the attestation ledger.
"""

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path

from config import DB_PATH


SNAPSHOT_DATE = "2026-09-26"
FIELD_RULES = {
    "current_price": ("last_price", "current_price", 0.0),
    "market_cap_cr": ("market_cap_cr", "market_cap_cr", 0.01),
    "pe": ("pe", "pe", 0.01),
    "debt_to_equity": ("debt_to_equity", "debt_to_equity", 0.01),
    "dividend_yield": ("dividend_yield", "dividend_yield", 0.01),
    "roe": ("roe", "roe", 0.01),
}
FUNDAMENTALS_COLUMNS = {
    "current_price", "market_cap_cr", "pe", "debt_to_equity",
    "dividend_yield", "roe",
}


def values_agree(left, right, relative_tolerance):
    if left is None or right is None:
        return False
    left, right = float(left), float(right)
    if relative_tolerance == 0:
        return left == right
    return abs(left - right) <= max(abs(left), abs(right), 1e-9) * \
        relative_tolerance


def _ensure_audit_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_attestations (
            as_of_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            field TEXT NOT NULL,
            kite_value REAL,
            scanx_value REAL,
            agreed INTEGER NOT NULL,
            acceptance_rule TEXT NOT NULL,
            live_before REAL,
            live_after REAL,
            universe_before REAL,
            universe_after REAL,
            action TEXT NOT NULL,
            attested_at TEXT NOT NULL,
            PRIMARY KEY (as_of_date, symbol, field)
        )
    """)


def reconcile(database, as_of=SNAPSHOT_DATE, apply=False,
              make_backup=True):
    """Compare both snapshots and optionally apply only attested values."""
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(f"Database does not exist: {database}")

    conn = sqlite3.connect(str(database), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        required = {
            "kite_market_snapshots", "scanx_fundamentals_snapshots",
            "fundamentals", "universe_broad",
        }
        missing = sorted(required - tables)
        if missing:
            raise RuntimeError(
                "Cannot reconcile; required tables are missing: "
                + ", ".join(missing))

        kite = {
            row["symbol"]: row for row in conn.execute(
                "SELECT * FROM kite_market_snapshots "
                "WHERE as_of_date=? AND symbol IS NOT NULL",
                (as_of,))
        }
        scanx = {
            row["symbol"]: row for row in conn.execute(
                "SELECT * FROM scanx_fundamentals_snapshots "
                "WHERE as_of_date=? AND symbol IS NOT NULL",
                (as_of,))
        }
        overlap = sorted(kite.keys() & scanx.keys())
        if not overlap:
            raise RuntimeError(
                f"No symbol-matched KITE/ScanX snapshots for {as_of}")

        live_rows = {
            row["symbol"]: row for row in conn.execute(
                "SELECT * FROM fundamentals")
        }
        broad_rows = {
            row["symbol"]: row for row in conn.execute(
                "SELECT * FROM universe_broad")
        }
        audit_rows = []
        updates = []
        counts = {field: {"compared": 0, "agreed": 0, "withheld": 0}
                  for field in FIELD_RULES}
        now = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        for symbol in overlap:
            for field, (kite_col, scanx_col, tolerance) in FIELD_RULES.items():
                left = kite[symbol][kite_col]
                right = scanx[symbol][scanx_col]
                if left is None or right is None:
                    continue
                accepted = values_agree(left, right, tolerance)
                counts[field]["compared"] += 1
                if accepted:
                    counts[field]["agreed"] += 1
                else:
                    counts[field]["withheld"] += 1

                existing = live_rows.get(symbol)
                before = existing[field] if existing else None
                action = "withheld_source_disagreement"
                after = before
                if accepted:
                    after = left
                    action = "attested_pending"
                    updates.append((symbol, field, left))
                broad = broad_rows.get(symbol)
                broad_field = {
                    "current_price": "close",
                    "market_cap_cr": "mcap_cr",
                }.get(field)
                broad_before = (broad[broad_field]
                                if broad and broad_field else None)
                broad_after = left if accepted and broad_field else broad_before
                audit_rows.append((
                    as_of, symbol, field, left, right, int(accepted),
                    ("exact" if tolerance == 0 else
                     f"relative_difference<={tolerance:.0%}"),
                    before, after, broad_before, broad_after, action, now,
                ))

        broad_update_counts = {"close": 0, "mcap_cr": 0}
        broad_updates = []
        for symbol in overlap:
            existing = broad_rows.get(symbol)
            if existing is None:
                continue
            k = kite[symbol]
            s = scanx[symbol]
            if values_agree(k["last_price"], s["current_price"], 0):
                broad_updates.append((
                    symbol, "close", k["last_price"], existing["close"]))
                broad_update_counts["close"] += 1
            if values_agree(k["market_cap_cr"], s["market_cap_cr"], 0.01):
                broad_updates.append((
                    symbol, "mcap_cr", k["market_cap_cr"],
                    existing["mcap_cr"]))
                broad_update_counts["mcap_cr"] += 1

        summary = {
            "as_of_date": as_of,
            "kite_symbols": len(kite),
            "scanx_symbols": len(scanx),
            "overlap_symbols": len(overlap),
            "fields": counts,
            "broad_universe_updates": broad_update_counts,
            "fundamentals_rows_before": len(live_rows),
            "fundamentals_symbols_to_refresh": len({
                symbol for symbol, _, _ in updates}),
            "applied": False,
            "backup": None,
        }
        if not apply:
            return summary

        backup_path = None
        if make_backup:
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = database.with_name(
                f"{database.name}.pre-kite-reconcile-{stamp}.bak")
            source_conn = sqlite3.connect(str(database))
            backup_conn = sqlite3.connect(str(backup_path))
            try:
                source_conn.backup(backup_conn)
            finally:
                backup_conn.close()
                source_conn.close()

        _ensure_audit_table(conn)
        conn.execute("BEGIN IMMEDIATE")
        for row in audit_rows:
            conn.execute(
                "INSERT INTO market_data_attestations "
                "(as_of_date,symbol,field,kite_value,scanx_value,agreed,"
                "acceptance_rule,live_before,live_after,universe_before,"
                "universe_after,action,attested_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(as_of_date,symbol,field) DO UPDATE SET "
                "kite_value=excluded.kite_value,"
                "scanx_value=excluded.scanx_value,agreed=excluded.agreed,"
                "acceptance_rule=excluded.acceptance_rule,"
                "live_before=excluded.live_before,"
                "live_after=excluded.live_after,"
                "universe_before=excluded.universe_before,"
                "universe_after=excluded.universe_after,"
                "action=excluded.action,"
                "attested_at=excluded.attested_at",
                row)

        by_symbol = {}
        for symbol, field, value in updates:
            by_symbol.setdefault(symbol, {})[field] = value

        source_time = conn.execute(
            "SELECT source_modified_at FROM kite_market_snapshots "
            "WHERE as_of_date=? ORDER BY source_modified_at DESC LIMIT 1",
            (as_of,)).fetchone()[0]
        uploaded_at = "csv:" + source_time
        for symbol, fields in by_symbol.items():
            current = live_rows.get(symbol)
            if current is None:
                snapshot = kite[symbol]
                values = {
                    "symbol": symbol,
                    "name": snapshot["company_name"],
                    "sector": snapshot["sector"],
                    "uploaded_at": uploaded_at,
                    "data_source": "kite_scanx_attested",
                    **fields,
                }
                columns = list(values)
                conn.execute(
                    "INSERT INTO fundamentals "
                    f"({','.join(columns)}) VALUES "
                    f"({','.join('?' for _ in columns)})",
                    [values[column] for column in columns])
            else:
                assignments = [f"{field}=?" for field in fields]
                values = list(fields.values())
                assignments.extend(
                    ["uploaded_at=?", "data_source=?"])
                values.extend([uploaded_at, "kite_scanx_attested", symbol])
                conn.execute(
                    "UPDATE fundamentals SET " + ",".join(assignments)
                    + " WHERE symbol=?", values)

        for symbol, field, value, _before in broad_updates:
            if field == "close":
                conn.execute(
                    "UPDATE universe_broad SET close=? WHERE symbol=?",
                    (value, symbol))
            else:
                conn.execute(
                    "UPDATE universe_broad SET mcap_cr=? WHERE symbol=?",
                    (value, symbol))

        actions = {}
        for row in audit_rows:
            symbol, field = row[1], row[2]
            broad_field = field in ("current_price", "market_cap_cr")
            actions[(symbol, field)] = (
                "updated_fundamentals_and_universe"
                if broad_field and symbol in broad_rows
                else "updated_fundamentals")
        for row in audit_rows:
            if row[5]:
                action = actions.get(
                    (row[1], row[2]), "attested_no_value_change")
                conn.execute(
                    "UPDATE market_data_attestations SET action=?,"
                    "live_after=?,universe_after=? "
                    "WHERE as_of_date=? AND symbol=? AND field=?",
                    (action, row[3], row[10], as_of, row[1], row[2]))

        conn.commit()
        summary["applied"] = True
        summary["backup"] = str(backup_path) if backup_path else None
        summary["fundamentals_rows_after"] = conn.execute(
            "SELECT COUNT(*) FROM fundamentals").fetchone()[0]
        summary["fundamentals_symbols_refreshed"] = len(by_symbol)
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--as-of", default=SNAPSHOT_DATE)
    parser.add_argument("--apply", action="store_true",
                        help="Back up and update confirmed fields")
    args = parser.parse_args(argv)
    summary = reconcile(args.db, args.as_of, args.apply)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
