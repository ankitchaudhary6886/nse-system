"""Quarantine derived rows that are NEWER than the price data behind them.

WHY THIS EXISTS
---------------
The price store froze on 2026-08-27, but pattern/template/institutional writers
kept running (2026-09-09 and 2026-10-07) and wrote artifacts computed from stale
bars. Those rows look current to every UI and every backtest. Deleting them
silently would destroy evidence, so this script MOVES them to
`stale_artifact_quarantine` (artifact, run_at, payload, reason) first and only
then removes them from the live table.

RULE
----
A row is invalid when its own date is later than `MAX(prices_daily.date)` by
more than LAG_DAYS (default 5). The lag exists because many artifact date
columns are RUN dates, not data dates: a scan on Saturday legitimately writes
`date = Saturday` while the last bar is Friday. On the laptop copy the gap was
13-41 days (impossible); on a live system the gap is 0-2 days. Rows inside the
lag are left alone.

USAGE
-----
    python purge_stale_artifacts.py              # dry run, prints what would move
    python purge_stale_artifacts.py --apply      # move to quarantine, then delete
    python purge_stale_artifacts.py --apply --artifact pattern_tags

Exit code 0 in both modes; this is maintenance, not a gate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "app.db"
# Artifact date columns are often RUN dates, not data dates: a Saturday scan
# legitimately writes date=Saturday while the last bar is Friday. Only a gap
# larger than this many calendar days is impossible.
LAG_DAYS = 5

# (table, date column). Only tables whose rows are derived from price data.
ARTIFACTS = [
    ("pattern_tags", "date"),
    ("pattern_grades", "tag_date"),
    ("template_scores", "date"),
    ("institutional", "date"),
    ("scan_results", "scan_date"),
    ("scan_reasons", "scan_date"),
    ("ml_predictions", "prediction_date"),
    ("pwin_daily", "date"),
    ("top_picks", "date"),
    ("swing_signals", "signal_date"),
    ("technicals_daily", "date"),
    ("breadth_daily", "date"),
    ("delivery_daily", "date"),
    ("macro_flow", "date"),
    ("trend_candidates", "date"),
    ("value_radar", "date"),
    ("positional_picks", "date"),
    ("validation_log", "run_date"),
]


def _row_to_payload(columns, row) -> str:
    return json.dumps(dict(zip(columns, row)), default=str)


def plan(conn, artifacts=None, lag_days=LAG_DAYS):
    max_price = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
    if not max_price:
        return {"max_price_date": None, "cutoff": None, "artifacts": []}
    cutoff = (dt.date.fromisoformat(str(max_price)[:10])
              + dt.timedelta(days=int(lag_days))).isoformat()
    plan_rows = []
    for table, date_col in ARTIFACTS:
        if artifacts and table not in artifacts:
            continue
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            if not cols or date_col not in cols:
                continue
            count = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE "{date_col}" > ?',
                (cutoff,)).fetchone()[0]
            if not count:
                continue
            dates = [r[0] for r in conn.execute(
                f'SELECT DISTINCT "{date_col}" FROM "{table}" '
                f'WHERE "{date_col}" > ? ORDER BY "{date_col}"',
                (cutoff,))]
            plan_rows.append({"artifact": table, "date_column": date_col,
                              "rows": count, "dates": dates[:10],
                              "cutoff": cutoff})
        except sqlite3.Error as exc:
            plan_rows.append({"artifact": table, "error": str(exc)})
    return {"max_price_date": max_price, "lag_days": int(lag_days),
            "cutoff": cutoff, "artifacts": plan_rows}


def apply_plan(conn, report, reason_prefix="newer_than_price_data"):
    run_at = dt.datetime.now().isoformat(timespec="seconds")
    moved = {}
    for entry in report["artifacts"]:
        table = entry.get("artifact")
        if not table or entry.get("error") or not entry.get("rows"):
            continue
        date_col = entry["date_column"]
        try:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            rows = conn.execute(
                f'SELECT * FROM "{table}" WHERE "{date_col}" > ?',
                (entry["cutoff"],)).fetchall()
            for row in rows:
                conn.execute(
                    "INSERT INTO stale_artifact_quarantine "
                    "(artifact, run_at, payload, reason) VALUES (?,?,?,?)",
                    (table, run_at, _row_to_payload(cols, row),
                     f"{reason_prefix}:{date_col} > {entry['cutoff']} "
                     f"(price max {report['max_price_date']} + "
                     f"{report['lag_days']}d lag)"))
            conn.execute(
                f'DELETE FROM "{table}" WHERE "{date_col}" > ?',
                (entry["cutoff"],))
            moved[table] = len(rows)
        except sqlite3.Error as exc:
            moved[table] = f"error: {exc}"
    conn.commit()
    return {"run_at": run_at, "moved": moved}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--artifact", action="append", default=None,
                        help="limit to one artifact table (repeatable)")
    parser.add_argument("--apply", action="store_true",
                        help="move rows to quarantine and delete them")
    parser.add_argument("--lag-days", type=int, default=LAG_DAYS,
                        help="tolerated calendar gap between artifact date and "
                             "last price bar (default 5)")
    args = parser.parse_args(argv)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA temp_store=MEMORY")
    # Ensure the quarantine table exists even when this script is the first
    # thing to open the database (db.SCHEMA is idempotent CREATE IF NOT EXISTS).
    try:
        import db
        conn.executescript(db.SCHEMA)
    except Exception:
        pass
    try:
        report = plan(conn, artifacts=args.artifact,
                      lag_days=args.lag_days)
        print(json.dumps(report, indent=2, default=str))
        if args.apply:
            result = apply_plan(conn, report)
            print(json.dumps(result, indent=2, default=str))
        else:
            print("\nDRY RUN — nothing moved. Re-run with --apply.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
