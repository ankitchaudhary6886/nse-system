"""Offline tests for the veto-only ScanX enrichment (Option B, 18 Oct 2026)."""
import json
import sqlite3
import unittest

import db
import fundamentals_enrich as fe


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    db._migrate(conn)  # add provenance/quality columns the merge helper writes
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        "CREATE TABLE scanx_fundamentals_snapshots ("
        "as_of_date TEXT, symbol TEXT, promoter_holding REAL, "
        "fii_holding REAL, dii_holding REAL, data_quality_flags TEXT, "
        "isin TEXT)")
    return conn


def seed_snapshot(conn, rows, as_of="2026-09-26"):
    conn.executemany(
        "INSERT INTO scanx_fundamentals_snapshots VALUES (?,?,?,?,?,?,?)",
        [(as_of, s, p, f, None, '["unavailable_sentinel:payout_ratio"]', isin)
         for s, p, f, isin in rows])
    conn.commit()


def seed_fundamentals(conn, symbol, **fields):
    cols = ["symbol"] + list(fields)
    conn.execute(
        "INSERT OR REPLACE INTO fundamentals ({}) VALUES ({})".format(
            ",".join(cols), ",".join("?" for _ in cols)),
        [symbol] + [fields[k] for k in fields])
    conn.commit()


class EnrichTests(unittest.TestCase):
    def test_snapshot_description(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        snapshot = fe.latest_snapshot(conn)
        self.assertTrue(snapshot["available"])
        self.assertEqual(snapshot["as_of_date"], "2026-09-26")
        self.assertEqual(snapshot["rows"], 1)
        self.assertIn("promoter_holding", snapshot["available_fields"])
        self.assertIn("pledge_pct", snapshot["missing_fields"])

    def test_absent_snapshot_is_clean(self):
        conn = memory_db()
        conn.execute("DROP TABLE scanx_fundamentals_snapshots")
        result = fe.enrich(conn)
        self.assertFalse(result["available"])
        self.assertIn("absent", result["reason"])
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM fundamentals").fetchone()[0], 0)

    def test_dry_run_reports_but_writes_nothing(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        result = fe.enrich(conn, dry_run=True)
        self.assertTrue(result["available"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["rows_touched"], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM fundamentals").fetchone()[0], 0)

    def test_apply_fills_missing_only_by_default(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 60.0, 25.0, "INE1")])
        seed_fundamentals(conn, "AAA", promoter_holding=55.0)
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["rows_touched"], 1)
        self.assertEqual(result["fields_filled"].get("fii_holding"), 1)
        self.assertEqual(result["fields_filled"].get("promoter_holding", 0), 0)
        row = conn.execute(
            "SELECT promoter_holding, fii_holding FROM fundamentals "
            "WHERE symbol='AAA'").fetchone()
        self.assertEqual(row, (55.0, 25.0))

    def test_overwrite_replaces_existing(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 60.0, 25.0, "INE1")])
        seed_fundamentals(conn, "AAA", promoter_holding=55.0)
        fe.enrich(conn, dry_run=False, overwrite=True)
        row = conn.execute(
            "SELECT promoter_holding FROM fundamentals WHERE symbol='AAA'"
        ).fetchone()
        self.assertEqual(row[0], 60.0)

    def test_out_of_range_values_are_skipped(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 140.0, 25.0, "INE1")])
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["invalid_skipped"], 1)
        row = conn.execute(
            "SELECT promoter_holding, fii_holding FROM fundamentals "
            "WHERE symbol='AAA'").fetchone()
        self.assertEqual(row, (None, 25.0))

    def test_provenance_and_pit_flags_are_written(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        fe.enrich(conn, dry_run=False)
        row = conn.execute(
            "SELECT field_sources, data_quality_flags FROM fundamentals "
            "WHERE symbol='AAA'").fetchone()
        sources = json.loads(row[0])
        flags = json.loads(row[1])["flags"]
        self.assertTrue(sources["promoter_holding"].startswith(
            "scanx_snapshot:"))
        self.assertIn("not_point_in_time", flags)
        self.assertIn("live_veto_only", flags)

    def test_missing_fundamentals_row_is_created(self):
        conn = memory_db()
        seed_snapshot(conn, [("NEWCO", 51.0, 8.0, "INE9")])
        fe.enrich(conn, dry_run=False)
        row = conn.execute(
            "SELECT promoter_holding FROM fundamentals WHERE symbol='NEWCO'"
        ).fetchone()
        self.assertEqual(row[0], 51.0)

    def test_reapply_is_idempotent(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        fe.enrich(conn, dry_run=False)
        result = fe.enrich(conn, dry_run=False)
        self.assertEqual(result["rows_touched"], 0)
        self.assertEqual(result["fields_filled"], {"promoter_holding": 0,
                                                   "fii_holding": 0})

    def test_report_band_coverage(self):
        conn = memory_db()
        seed_snapshot(conn, [("AAA", 55.0, 12.0, "INE1")])
        seed_fundamentals(conn, "AAA", market_cap_cr=2000.0)
        conn.execute(
            "INSERT OR REPLACE INTO universe_broad "
            "(symbol,mcap_cr,updated_at) VALUES ('AAA',2000,'2026-10-18')")
        conn.commit()
        fe.enrich(conn, dry_run=False)
        result = fe.report(conn)
        self.assertFalse(result["pit_valid"])
        self.assertEqual(result["band_total"], 1)
        self.assertEqual(result["band_coverage"]["promoter_holding"]["covered"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
