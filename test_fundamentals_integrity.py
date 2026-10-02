import sqlite3
import unittest

import db
from fundamentals_store import integrity_report, merge


class FundamentalsIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(db.SCHEMA)
        db._migrate(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_null_import_does_not_erase_existing_field(self):
        merge(self.conn, {"symbol": "ABC", "roe": 18.0},
              source="official", observed_at="2026-09-01")
        merge(self.conn, {"symbol": "ABC", "pe": 12.0, "roe": None},
              source="screener", observed_at="2026-09-02")
        row = self.conn.execute(
            "SELECT roe, pe, field_sources, field_updated_at "
            "FROM fundamentals WHERE symbol='ABC'").fetchone()
        self.assertEqual(row[0:2], (18.0, 12.0))
        self.assertIn('"roe": "official"', row[2])
        self.assertIn('"pe": "screener"', row[2])
        self.assertIn('"roe": "2026-09-01"', row[3])

    def test_roic_is_stored_separately_and_legacy_rows_are_reported(self):
        merge(self.conn, {"symbol": "TV", "roic": 14.0,
                          "fcf_fy": 100.0,
                          "data_quality_flags": ["cfo_unverified"]},
              source="tradingview", observed_at="2026-09-01")
        row = self.conn.execute(
            "SELECT roe, roce, roic, cfo_positive, fcf_fy "
            "FROM fundamentals WHERE symbol='TV'").fetchone()
        self.assertEqual(row, (None, None, 14.0, None, 100.0))
        report = integrity_report(self.conn)
        self.assertFalse(report["remediation_needed"])

        self.conn.execute(
            "INSERT INTO fundamentals(symbol, cfo_positive, fcf_fy) "
            "VALUES ('OLD', 1, 20.0)")
        report = integrity_report(self.conn)
        old = {r["symbol"]: r["reasons"] for r in report["rows"]}
        self.assertIn("OLD", old)
        self.assertIn("legacy row has no field provenance", old["OLD"])


if __name__ == "__main__":
    unittest.main()
