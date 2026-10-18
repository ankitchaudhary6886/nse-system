"""Data inventory + usefulness + freshness audit for data/app.db.

Why this exists
---------------
data_quality.py answers "is today's pipeline healthy?" (6 checks, alerting).
It does NOT answer the questions that decide what to build next:

  * which tables are actually populated, which are empty shells?
  * how much of the stored data is usable (enough history to compute 200-DMA)?
  * which columns are dead weight (100% null)?
  * how stale is each dataset relative to the last trading day?
  * how many code modules actually read each table (= usefulness proxy)?
  * what can be derived algebraically from what we already own?

This script is read-only. It prints a report and can dump machine-readable
JSON so docs can cite exact numbers instead of impressions.

Usage
-----
    python data_audit.py
    python data_audit.py --json docs/data_audit.json
    python data_audit.py --db data/app.db --quiet

Exit code is 0 even when problems are found: this is a report, not a gate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "app.db"

# Freshness column + allowed age in calendar days before a table is called
# STALE. Tables without a date column get no staleness verdict.
FRESHNESS = {
    "prices_daily": ("date", 5),
    "price_meta": ("last_date", 5),
    "technicals_daily": ("date", 5),
    "fundamentals": ("uploaded_at", 90),
    "universe_broad": ("updated_at", 5),
    "scan_results": ("scan_date", 5),
    "scan_reasons": ("scan_date", 5),
    "ml_predictions": ("prediction_date", 5),
    "pattern_tags": ("date", 5),
    "template_scores": ("date", 5),
    "institutional": ("date", 5),
    "delivery_daily": ("date", 5),
    "breadth_daily": ("date", 5),
    "macro_flow": ("date", 5),
    "sentiment_results": ("created_at", 5),
    "scanx_fundamentals_snapshots": ("imported_at", 120),
    "swing_signals": ("signal_date", 5),
    "top_picks": ("date", 5),
    "events": ("date", 5),
    "fyers_symbol_master": ("imported_at", 30),
    "fyers_quotes": ("ts", 3),
}

# Only these are judged as "core" for the trading pipeline.
CORE = {"prices_daily", "price_meta", "fundamentals", "universe_broad",
        "stocks", "technicals_daily", "scan_results"}

# History needed before a row is useful for the 200-DMA / 52-week logic.
MIN_HISTORY = 210

_PY_SKIP = {".git", "env", "node_modules", "__pycache__", "trading-agents-swarm",
            "_fyers_sdk", ".codegraph", ".aicache", ".graphflow-cache"}


def _iso(value):
    if value is None:
        return None
    text = str(value)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    return m.group(1) if m else None


def _table_refs():
    """How many project modules read each table (grep, no SQL parsing)."""
    counts = {}
    pattern = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                         re.IGNORECASE)
    for path in ROOT.rglob("*.py"):
        if any(part in _PY_SKIP for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in pattern.findall(text):
            name = match.lower()
            counts.setdefault(name, set()).add(path.name)
    return {name: len(files) for name, files in counts.items()}


def inventory(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    refs = _table_refs()
    out = []
    for name in tables:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')]
        rows = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        fresh_col, max_age = FRESHNESS.get(name, (None, None))
        latest = None
        if fresh_col and fresh_col in cols:
            latest = _iso(conn.execute(
                f'SELECT MAX("{fresh_col}") FROM "{name}"').fetchone()[0])
        age = None
        if latest:
            age = (dt.date.today() - dt.date.fromisoformat(latest)).days
        if rows == 0:
            status = "EMPTY"
        elif age is not None and max_age is not None and age > max_age:
            status = "STALE"
        elif rows < 100:
            status = "THIN"
        else:
            status = "ACTIVE"
        out.append({
            "table": name, "rows": rows, "cols": len(cols),
            "status": status, "latest": latest, "age_days": age,
            "modules_using": refs.get(name, 0),
            "core": name in CORE,
        })
    return out


def _trading_days(conn, limit=70):
    # A date is a trading day if at least half the active symbols printed a bar.
    rows = conn.execute(
        "SELECT date, COUNT(*) n FROM prices_daily GROUP BY date "
        "HAVING n > 200 ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    return [r[0] for r in rows]


def price_audit(conn):
    rows = conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
    symbols = conn.execute("SELECT COUNT(DISTINCT symbol) FROM prices_daily").fetchone()[0]
    min_d, max_d = conn.execute(
        "SELECT MIN(date), MAX(date) FROM prices_daily").fetchone()
    stale_days = (dt.date.today() - dt.date.fromisoformat(max_d)).days
    buckets = {"<60": 0, "60-209": 0, "210-499": 0, ">=500": 0}
    for (n,) in conn.execute("SELECT rows FROM price_meta"):
        n = n or 0
        if n < 60:
            buckets["<60"] += 1
        elif n < MIN_HISTORY:
            buckets["60-209"] += 1
        elif n < 500:
            buckets["210-499"] += 1
        else:
            buckets[">=500"] += 1
    days = _trading_days(conn)
    coverage = None
    if days:
        cutoff = days[min(59, len(days) - 1)]
        total = conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE date>=?", (cutoff,)).fetchone()[0]
        expected = len(days[:60]) * 1086
        coverage = round(100.0 * total / expected, 1) if expected else None
    zero_vol = conn.execute(
        "SELECT COUNT(*) FROM prices_daily WHERE volume IS NULL OR volume<=0").fetchone()[0]
    bad_ohlc = conn.execute("""
        SELECT COUNT(*) FROM prices_daily
        WHERE open<=0 OR high<=0 OR low<=0 OR close<=0 OR high<low
           OR close>high*1.02 OR close<low*0.98""").fetchone()[0]
    latest_n = conn.execute(
        "SELECT COUNT(*) FROM prices_daily WHERE date=?", (max_d,)).fetchone()[0]
    return {
        "rows": rows, "symbols": symbols, "min_date": min_d, "max_date": max_d,
        "stale_days": stale_days, "history_buckets": buckets,
        "last_60d_bar_coverage_pct": coverage,
        "zero_volume_rows": zero_vol,
        "zero_volume_pct": round(100.0 * zero_vol / rows, 2) if rows else None,
        "invalid_ohlc_rows": bad_ohlc,
        "symbols_on_latest_date": latest_n,
    }


def fundamentals_audit(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(fundamentals)")]
    total = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0]
    fields = {}
    for col in cols:
        if col == "symbol":
            continue
        if col in ("name", "sector"):
            fields[col] = total - conn.execute(
                "SELECT COUNT(*) FROM fundamentals WHERE {0} IS NULL "
                "OR {0}=''".format(col)).fetchone()[0]
            continue
        n = conn.execute(
            f"SELECT COUNT(*) FROM fundamentals WHERE {col} IS NOT NULL").fetchone()[0]
        fields[col] = n
    dead = [c for c, n in fields.items() if n == 0]
    usable = [c for c, n in fields.items() if n and n >= total * 0.8]
    anomalies = {
        "pe_negative": conn.execute("SELECT COUNT(*) FROM fundamentals WHERE pe<0").fetchone()[0],
        "pe_over_200": conn.execute("SELECT COUNT(*) FROM fundamentals WHERE pe>200").fetchone()[0],
        "pb_negative": conn.execute("SELECT COUNT(*) FROM fundamentals WHERE pb<0").fetchone()[0],
        "debt_equity_over_10": conn.execute(
            "SELECT COUNT(*) FROM fundamentals WHERE debt_to_equity>10").fetchone()[0],
        "price_zero_or_null": conn.execute(
            "SELECT COUNT(*) FROM fundamentals WHERE current_price IS NULL OR current_price<=0").fetchone()[0],
    }
    derivable = {
        "eps_from_price_over_pe": conn.execute(
            "SELECT COUNT(*) FROM fundamentals WHERE current_price>0 AND pe>0").fetchone()[0],
        "book_value_from_price_over_pb": conn.execute(
            "SELECT COUNT(*) FROM fundamentals WHERE current_price>0 AND pb>0").fetchone()[0],
        "shares_outstanding_from_mcap_over_price": conn.execute(
            "SELECT COUNT(*) FROM fundamentals WHERE current_price>0 AND market_cap_cr>0").fetchone()[0],
    }
    return {"rows": total, "columns": len(cols), "field_filled": fields,
            "dead_columns": dead, "usable_columns_80pct": usable,
            "anomalies": anomalies, "derivable_rows": derivable}


def universe_audit(conn):
    rows = conn.execute("SELECT COUNT(*) FROM universe_broad").fetchone()[0]
    with_price = conn.execute(
        "SELECT COUNT(*) FROM universe_broad u WHERE EXISTS "
        "(SELECT 1 FROM prices_daily p WHERE p.symbol=u.symbol)").fetchone()[0]
    relvol = conn.execute(
        "SELECT COUNT(*) FROM universe_broad WHERE relvol IS NOT NULL").fetchone()[0]
    pe = conn.execute(
        "SELECT COUNT(*) FROM universe_broad WHERE pe IS NOT NULL").fetchone()[0]
    mcap = conn.execute(
        "SELECT COUNT(*) FROM universe_broad WHERE mcap_cr IS NOT NULL").fetchone()[0]
    stale = conn.execute(
        "SELECT COUNT(*) FROM universe_broad WHERE updated_at < ?",
        ((dt.date.today() - dt.timedelta(days=5)).isoformat(),)).fetchone()[0]
    band = conn.execute(
        "SELECT COUNT(*) FROM universe_broad WHERE mcap_cr BETWEEN 1000 AND 8000"
    ).fetchone()[0]
    return {"rows": rows, "with_price_history": with_price,
            "with_mcap": mcap, "with_pe": pe, "with_relvol": relvol,
            "rows_older_than_5d": stale, "band_1000_8000cr": band}


def snapshot_audit(conn):
    out = {}
    for name in ("scanx_fundamentals_snapshots", "kite_market_snapshots"):
        try:
            out[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        except sqlite3.Error:
            out[name] = "table absent"
    return out


def run(db_path):
    conn = sqlite3.connect(str(db_path))
    # GROUP BY over 1.1M price rows spills to SQLite's temp file. On machines
    # where the temp directory is not writable by the process (observed on the
    # sandboxed laptop), that surfaces as "unable to open database file".
    # Keeping temp tables in memory makes the audit independent of that.
    conn.execute("PRAGMA temp_store=MEMORY")
    try:
        report = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "db": str(db_path),
            "db_mb": round(Path(db_path).stat().st_size / 1e6, 1),
            "inventory": inventory(conn),
            "prices": price_audit(conn),
            "fundamentals": fundamentals_audit(conn),
            "universe": universe_audit(conn),
            "snapshots": snapshot_audit(conn),
        }
    finally:
        conn.close()
    counts = {}
    for row in report["inventory"]:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report["summary"] = {
        "tables": len(report["inventory"]),
        "by_status": counts,
        "empty_tables": [r["table"] for r in report["inventory"]
                         if r["status"] == "EMPTY"],
        "stale_tables": [r["table"] for r in report["inventory"]
                         if r["status"] == "STALE"],
        "dead_fundamental_columns": report["fundamentals"]["dead_columns"],
    }
    return report


def print_report(report):
    p, f, u = report["prices"], report["fundamentals"], report["universe"]
    print("=" * 78)
    print(f"DATA AUDIT  {report['generated_at']}  db={report['db_mb']} MB")
    print("=" * 78)

    print("\n[1] TABLES")
    print(f"{'table':32s} {'rows':>10s} {'cols':>5s} {'status':8s} "
          f"{'latest':10s} {'age':>4s} {'mods':>4s}")
    for r in report["inventory"]:
        print(f"{r['table']:32s} {r['rows']:>10d} {r['cols']:>5d} "
              f"{r['status']:8s} {str(r['latest'] or '-'):10s} "
              f"{str(r['age_days'] if r['age_days'] is not None else '-'):>4s} "
              f"{r['modules_using']:>4d}")
    s = report["summary"]
    print(f"\n  status counts: {s['by_status']}")
    print(f"  empty tables ({len(s['empty_tables'])}): {', '.join(s['empty_tables'])}")

    print("\n[2] PRICES")
    print(f"  rows={p['rows']:,}  symbols={p['symbols']}  "
          f"range={p['min_date']}..{p['max_date']}  STALE={p['stale_days']}d")
    print(f"  history length buckets: {p['history_buckets']}")
    print(f"  last-60-session bar coverage: {p['last_60d_bar_coverage_pct']}%  "
          f"(symbols on latest date: {p['symbols_on_latest_date']})")
    print(f"  zero-volume rows: {p['zero_volume_pct']}%   "
          f"invalid OHLC rows: {p['invalid_ohlc_rows']}")

    print("\n[3] FUNDAMENTALS")
    print(f"  rows={f['rows']}  columns={f['columns']}  "
          f"dead columns={len(f['dead_columns'])}: {', '.join(f['dead_columns'])}")
    filled = sorted(((c, n) for c, n in f["field_filled"].items() if n),
                    key=lambda kv: -kv[1])
    print("  filled: " + ", ".join(f"{c}={n}" for c, n in filled[:8]) + " ...")
    print(f"  anomalies: {f['anomalies']}")
    print(f"  derivable now: {f['derivable_rows']}")

    print("\n[4] UNIVERSE")
    print(f"  {u}")
    print("\n[5] SNAPSHOTS")
    print(f"  {report['snapshots']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--json", dest="json_path", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    report = run(args.db)
    if not args.quiet:
        print_report(report)
    if args.json_path:
        Path(args.json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_path).write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nJSON written: {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
