"""Read-only coverage and data-quality report for imported ScanX snapshots."""
import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

import db


GROUPS = {
    "Long-term quality": (
        "roe_avg_3y", "roe_avg_10y", "roa_avg_3y", "roa_avg_5y",
        "opm_avg_5y", "opm_avg_10y", "roce_growth_5y", "roe_growth_5y",
    ),
    "Earnings growth": (
        "quarter_sales_yoy_growth", "quarter_profit_yoy_growth",
        "annual_revenue_growth", "sales_growth_qoq", "profit_growth_qoq",
    ),
    "Cash flow and balance sheet": (
        "free_cash_flow", "profit_after_tax", "net_change_in_cash",
        "change_in_working_capital", "current_assets", "current_liabilities",
        "total_assets", "total_liabilities", "total_equity", "inventory",
        "capex_growth",
    ),
    "Valuation and peers": (
        "ev_ebitda", "pe_sector_ratio", "market_cap_sales", "industry_pe",
        "industry_pb", "industry_dividend_yield",
    ),
    "Ownership": (
        "dii_holding_change", "fii_holding_change", "public_holding",
        "promoter_holding_change",
    ),
}


def report(database, as_of=None):
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "scanx_fundamentals_snapshots" not in tables:
            raise RuntimeError("No ScanX snapshot table exists in this database")
        dates = [row[0] for row in conn.execute(
            "SELECT DISTINCT as_of_date FROM scanx_fundamentals_snapshots "
            "ORDER BY as_of_date")]
        if not dates:
            raise RuntimeError("The ScanX snapshot table is empty")
        selected_date = as_of or dates[-1]
        if selected_date not in dates:
            raise ValueError(
                f"No ScanX snapshot found for {selected_date}; "
                f"available dates: {', '.join(dates)}")
        row_count = conn.execute(
            "SELECT count(*) FROM scanx_fundamentals_snapshots "
            "WHERE as_of_date=?", (selected_date,)).fetchone()[0]
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(scanx_fundamentals_snapshots)")}
        print(f"ScanX export snapshot: {selected_date} ({row_count} rows)")
        print("Underlying financial-period end / publication date: not supplied")
        for group, fields in GROUPS.items():
            present = [field for field in fields if field in cols]
            if not present:
                continue
            select = ",".join(
                f"count({field})" for field in present)
            counts = conn.execute(
                f"SELECT {select} FROM scanx_fundamentals_snapshots "
                "WHERE as_of_date=?", (selected_date,)).fetchone()
            print(f"\n{group}")
            for field, count in zip(present, counts):
                print(f"  {field}: {count}/{row_count}")

        flags = Counter()
        for (payload,) in conn.execute(
                "SELECT data_quality_flags FROM scanx_fundamentals_snapshots "
                "WHERE as_of_date=?", (selected_date,)):
            try:
                flags.update(json.loads(payload or "[]"))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Malformed data_quality_flags JSON in snapshot") from exc
        print("\nQuality flags (row counts)")
        if flags:
            for flag, count in sorted(flags.items()):
                print(f"  {flag}: {count}")
        else:
            print("  none")
        print("\nRaw source rows remain preserved. Snapshot values are "
              "research-only unless a separate, explicit cross-source "
              "attestation promotes an individual field.")
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(db.DB_PATH),
                        help="SQLite database (opened read-only)")
    parser.add_argument("--as-of", help="Export snapshot date YYYY-MM-DD")
    args = parser.parse_args(argv)
    report(args.db, args.as_of)


if __name__ == "__main__":
    main()
