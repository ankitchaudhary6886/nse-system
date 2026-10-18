"""Offline tests for the veto-only ScanX enrichment (Option B, 18 Oct 2026).

Everything here runs on ``sqlite3.connect(":memory:")`` built from
``db.SCHEMA`` + ``db._migrate`` (the migration is what adds ``field_sources``,
``field_updated_at`` and ``data_quality_flags``).  ``db.SCHEMA`` deliberately
does not create ``scanx_fundamentals_snapshots`` -- scanx_import.py owns that
DDL -- so the helper below adds the minimal snapshot table and nothing here
ever opens ``data/app.db``.
"""
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db
import fundamentals_enrich as fe

AS_OF = "2026-09-26"
OWNERSHIP = ("promoter_holding", "fii_holding", "pledge_pct")
SNAPSHOT_DDL = (
    "CREATE TABLE scanx_fundamentals_snapshots ("
    "as_of_date TEXT, symbol TEXT, promoter_holding REAL, "
    "fii_holding REAL, dii_holding REAL, data_quality_flags TEXT, "
    "isin TEXT, imported_at TEXT)")


def memory_db(snapshot=True):
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    db._migrate(conn)  # add provenance/quality columns the merge helper writes
    conn.execute("PRAGMA temp_store=MEMORY")
    if snapshot:
        conn.execute(SNAPSHOT_DDL)
    return conn


def seed_snapshot(conn, rows, as_of=AS_OF):
    """rows: (symbol, promoter_holding, fii_holding, isin)."""
    conn.executemany(
        "INSERT INTO scanx_fundamentals_snapshots (as_of_date, symbol, "
        "promoter_holding, fii_holding, dii_holding, data_quality_flags, isin) "
        "VALUES (?,?,?,?,?,'[\"unavailable_sentinel:payout_ratio\"]',?)",
        [(as_of, symbol, promoter, fii, None, isin)
         for symbol, promoter, fii, isin in rows])
    conn.commit()


def seed_fundamentals(conn, symbol, **fields):
    cols = ["symbol"] + list(fields)
    conn.execute(
        "INSERT OR REPLACE INTO fundamentals ({}) VALUES ({})".format(
            ",".join(cols), ",".join("?" for _ in cols)),
        [symbol] + [fields[k] for k in fields])
    conn.commit()


def read_ownership(conn, symbol):
    row = conn.execute(
        "SELECT {} FROM fundamentals WHERE symbol=?".format(",".join(OWNERSHIP)),
        (symbol,)).fetchone()
    return dict(zip(OWNERSHIP, row)) if row else None


def provenance(conn, symbol):
    row = conn.execute(
        "SELECT field_sources, data_quality_flags FROM fundamentals "
        "WHERE symbol=?", (symbol,)).fetchone()
    return json.loads(row[0] or "{}"), json.loads(row[1] or "{}").get("flags", [])


def fundamental_count(conn):
    return conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0]


class BaseCase(unittest.TestCase):
    def db(self, snapshot=True):
        conn = memory_db(snapshot)
        self.addCleanup(conn.close)
        return conn


class EnrichTests(BaseCase):
    def test_snapshot_description(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        snapshot = fe.latest_snapshot(conn)
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["as_of_date"], AS_OF)
        self.assertEqual(snapshot["date_column"], "as_of_date")
        self.assertEqual(snapshot["rows"], 1)
        self.assertIn("promoter_holding", snapshot["available_fields"])
        self.assertIn("pledge_pct", snapshot["missing_fields"])
        self.assertFalse(snapshot["pit_valid"])
        self.assertIn("point-in-time", snapshot["warning"])

    def test_snapshot_uses_latest_date_and_classifies_fields(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1"),
                             ("BBB", 40.0, None, "INE2")])
        seed_snapshot(conn, [("OLD", 70.0, 2.0, "INE0")], as_of="2026-09-01")
        snapshot = fe.latest_snapshot(conn)
        self.assertEqual(snapshot["as_of_date"], AS_OF)
        self.assertEqual(snapshot["rows"], 2)
        self.assertEqual(snapshot["symbols"], ["AAA", "BBB"])
        self.assertEqual(snapshot["available_fields"],
                         ["promoter_holding", "fii_holding", "dii_holding"])
        self.assertEqual(snapshot["missing_fields"], ["pledge_pct"])
        self.assertEqual(snapshot["field_rows"],
                         {"promoter_holding": 2, "fii_holding": 1,
                          "dii_holding": 0})

    def test_empty_as_of_date_falls_back_to_imported_at(self):
        conn = self.db()
        conn.execute(
            "INSERT INTO scanx_fundamentals_snapshots (as_of_date, symbol, "
            "promoter_holding, fii_holding, imported_at) VALUES "
            "('', 'AAA', 55, 8, '2026-10-01T09:00:00')")
        conn.commit()
        snapshot = fe.latest_snapshot(conn)
        self.assertEqual(snapshot["date_column"], "imported_at")
        self.assertEqual(snapshot["as_of_date"], "2026-10-01T09:00:00")
        self.assertEqual(snapshot["symbols"], ["AAA"])

    def test_absent_snapshot_is_clean(self):
        conn = self.db()
        conn.execute("DROP TABLE scanx_fundamentals_snapshots")
        result = fe.enrich(conn, dry_run=False)  # even apply must not write
        self.assertFalse(result["available"])
        self.assertIn("absent", result["reason"])
        self.assertIn("point-in-time", result["warning"])
        self.assertEqual(result["rows_touched"], 0)
        self.assertEqual(result["fields_filled"], {})
        self.assertEqual(fundamental_count(conn), 0)

    def test_report_is_clean_without_snapshot_or_universe(self):
        conn = self.db()
        conn.execute("DROP TABLE scanx_fundamentals_snapshots")
        report = fe.report(conn)
        self.assertFalse(report["snapshot_available"])
        self.assertIn("absent", report["snapshot_reason"])
        self.assertEqual(report["band_total"], 0)
        self.assertEqual(report["fundamentals_rows"], 0)
        self.assertFalse(report["pit_valid"])
        self.assertIn("point-in-time", report["pit_warning"])

    def test_dry_run_reports_but_writes_nothing(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        result = fe.enrich(conn, dry_run=True)
        self.assertTrue(result["available"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["rows_touched"], 1)
        self.assertEqual(result["fields_filled"],
                         {"promoter_holding": 1, "fii_holding": 1})
        self.assertEqual(result["sample"], [{
            "symbol": "AAA", "kept": [],
            "written": {"promoter_holding": 55.0, "fii_holding": 12.0}}])
        self.assertEqual(result["coverage_after"],
                         {"promoter_holding": 0, "fii_holding": 0})
        self.assertEqual(result["snapshot_source"], "scanx_snapshot:" + AS_OF)
        self.assertEqual(fundamental_count(conn), 0)
        self.assertIsNone(read_ownership(conn, "AAA"))

    def test_apply_fills_missing_only_by_default(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 60.0, 25.0, "INE1")])
        seed_fundamentals(conn, "AAA", promoter_holding=55.0)
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["rows_touched"], 1)
        self.assertEqual(result["fields_filled"].get("fii_holding"), 1)
        self.assertEqual(result["fields_filled"].get("promoter_holding", 0), 0)
        self.assertEqual(result["fields_existing_kept"], 1)
        self.assertEqual(result["coverage_after"],
                         {"promoter_holding": 1, "fii_holding": 1})
        row = conn.execute(
            "SELECT promoter_holding, fii_holding FROM fundamentals "
            "WHERE symbol='AAA'").fetchone()
        self.assertEqual(row, (55.0, 25.0))

    def test_overwrite_replaces_existing(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 60.0, 25.0, "INE1")])
        seed_fundamentals(conn, "AAA", promoter_holding=55.0, fii_holding=1.0)
        fe.enrich(conn, dry_run=False, overwrite=True)
        row = conn.execute(
            "SELECT promoter_holding, fii_holding FROM fundamentals "
            "WHERE symbol='AAA'").fetchone()
        self.assertEqual(row, (60.0, 25.0))
        again = fe.enrich(conn, dry_run=False, overwrite=True)
        self.assertEqual(again["rows_touched"], 0)
        self.assertEqual(again["fields_unchanged"], 2)

    def test_out_of_range_values_are_skipped(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 140.0, 25.0, "INE1")])
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["invalid_skipped"], 1)
        self.assertEqual(result["invalid"][0]["reason"], "outside_0_100")
        row = conn.execute(
            "SELECT promoter_holding, fii_holding FROM fundamentals "
            "WHERE symbol='AAA'").fetchone()
        self.assertEqual(row, (None, 25.0))

    def test_negative_and_non_numeric_values_are_skipped(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", -5.0, 25.0, "INE1")])
        conn.execute(
            "UPDATE scanx_fundamentals_snapshots SET fii_holding='n/a' "
            "WHERE symbol='AAA'")
        conn.commit()
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["invalid_skipped"], 2)
        self.assertEqual({entry["reason"] for entry in result["invalid"]},
                         {"outside_0_100", "not_numeric"})
        self.assertIsNone(read_ownership(conn, "AAA"))  # nothing valid to write

    def test_provenance_and_pit_flags_are_written(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        seed_fundamentals(conn, "AAA", roe=14.0)  # prior, untouched provenance
        conn.execute(
            "UPDATE fundamentals SET field_sources='{\"roe\": \"tradingview:test\"}' "
            "WHERE symbol='AAA'")
        conn.commit()
        fe.enrich(conn, dry_run=False)
        sources, flags = provenance(conn, "AAA")
        self.assertTrue(sources["promoter_holding"].startswith(
            "scanx_snapshot:"))
        self.assertEqual(sources["roe"], "tradingview:test")
        self.assertIn("not_point_in_time", flags)
        self.assertIn("live_veto_only", flags)
        self.assertIn("undated_snapshot", flags)

    def test_unavailable_fields_are_never_invented(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["mapped_fields"],
                         ["promoter_holding", "fii_holding"])
        self.assertEqual(result["unavailable_fields"],
                         {"pledge_pct": "no snapshot column",
                          "dii_holding": "no fundamentals column"})
        sources, _ = provenance(conn, "AAA")
        self.assertNotIn("pledge_pct", sources)
        self.assertIsNone(read_ownership(conn, "AAA")["pledge_pct"])

    def test_missing_fundamentals_row_is_created(self):
        """Documented decision: sparse row so fund_veto can see promoter."""
        import fund_veto

        conn = self.db()
        seed_snapshot(conn, [("NEWCO", 51.0, 8.0, "INE9")])
        fe.enrich(conn, dry_run=False)
        row = conn.execute(
            "SELECT promoter_holding FROM fundamentals WHERE symbol='NEWCO'"
        ).fetchone()
        self.assertEqual(row[0], 51.0)

        seed_snapshot(conn, [("LOWPROM", 12.0, 4.0, "INE8")])
        self.assertEqual(fund_veto.vetoed("LOWPROM", conn=conn), (False, None))
        fe.enrich(conn, dry_run=False)  # NEWCO is unchanged, LOWPROM is new
        self.assertEqual(fund_veto.vetoed("LOWPROM", conn=conn),
                         (True, "promoter 12.0% < 20.0%"))

    def test_reapply_is_idempotent(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        fe.enrich(conn, dry_run=False)
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["rows_touched"], 0)
        self.assertEqual(result["fields_existing_kept"], 2)  # both kept, not new
        self.assertEqual(result["fields_filled"], {"promoter_holding": 0,
                                                   "fii_holding": 0})

    def test_symbols_and_limit_restrict_candidates(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1"),
                             ("BBB", 41.0, 5.0, "INE2")])
        only = fe.enrich(conn, symbols=["aaa"])
        self.assertEqual(only["candidates"], 1)
        self.assertEqual([item["symbol"] for item in only["sample"]], ["AAA"])
        capped = fe.enrich(conn, limit=1)
        self.assertEqual(capped["candidates"], 1)

    def test_report_band_coverage(self):
        conn = self.db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1"),
                             ("BBB", 12.0, 4.0, "INE2"),
                             ("NOFUND", 33.0, 6.0, "INE3")])
        seed_fundamentals(conn, "AAA", market_cap_cr=2000.0)
        seed_fundamentals(conn, "BBB", market_cap_cr=5000.0)
        for symbol, mcap in (("AAA", 2000.0), ("BBB", 5000.0),
                             ("BIG", 90000.0)):
            conn.execute(
                "INSERT OR REPLACE INTO universe_broad "
                "(symbol,mcap_cr,updated_at) VALUES (?,?,'2026-10-18')",
                (symbol, mcap))
        conn.commit()
        fe.enrich(conn, dry_run=False)
        result = fe.report(conn)
        self.assertFalse(result["pit_valid"])
        self.assertEqual(result["snapshot_as_of"], AS_OF)
        self.assertEqual(result["snapshot_rows"], 3)
        self.assertEqual(result["band_total"], 2)  # BIG is outside 1000-8000
        self.assertEqual(result["band_with_fundamentals"], 2)
        self.assertEqual(result["band_fillable_from_snapshot"], 2)
        self.assertEqual(result["band_coverage"]["promoter_holding"],
                         {"covered": 2, "pct": 100.0})
        self.assertEqual(result["band_coverage"]["pledge_pct"],
                         {"covered": 0, "pct": 0.0})
        # NOFUND was enriched from the snapshot too, so all 3 rows carry FII.
        self.assertEqual(result["coverage"]["fii_holding"]["non_null"], 3)
        self.assertEqual(result["coverage"]["promoter_holding"]["non_null"], 3)


class ModuleHygieneTests(BaseCase):
    def test_db_is_not_imported_at_module_level(self):
        self.assertFalse(hasattr(fe, "db"))

    def test_cli_snapshot_prints_json_from_a_temp_database(self):
        original = db.DB_PATH
        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            db.DB_PATH = Path(temp_dir) / "temp.db"
            try:
                conn = db.get_conn()
                try:
                    conn.execute(SNAPSHOT_DDL)  # not part of db.SCHEMA
                    seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
                finally:
                    conn.close()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(fe.main(["snapshot"]), 0)
            finally:
                db.DB_PATH = original
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["as_of_date"], AS_OF)
        self.assertEqual(payload["rows"], 1)
        self.assertFalse(payload["pit_valid"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
