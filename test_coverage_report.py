"""Tests for the price-coverage diagnosis (18 Oct 2026)."""
import sqlite3
import unittest

import coverage_report as cr
import db


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    db._migrate(conn)
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def seed(conn, symbol, mcap=2000.0, active=None, price_date=None):
    conn.execute(
        "INSERT OR REPLACE INTO universe_broad (symbol,mcap_cr,updated_at) "
        "VALUES (?,?,'2026-10-18')", (symbol, mcap))
    if active is not None:
        conn.execute(
            "INSERT OR REPLACE INTO stocks (symbol,active) VALUES (?,?)",
            (symbol, active))
    if price_date:
        conn.execute(
            "INSERT OR REPLACE INTO prices_daily VALUES (?,?,1,1,1,1,100)",
            (symbol, price_date))
    conn.commit()


def master(conn, symbol, ticker, isin=None):
    conn.execute(
        "INSERT OR REPLACE INTO fyers_symbol_master (symbol,ticker,isin) "
        "VALUES (?,?,?)", (symbol, ticker, isin or "INE000000000"))
    conn.commit()


class CoverageTests(unittest.TestCase):
    def test_classifies_ok_missing_and_non_tradable(self):
        conn = memory_db()
        seed(conn, "GOOD", active=1, price_date="2026-10-16")
        seed(conn, "NEWCO", active=1, price_date=None)
        seed(conn, "SMEINC", active=1, price_date="2026-08-27")
        master(conn, "GOOD", "NSE:GOOD-EQ")
        master(conn, "NEWCO", "NSE:NEWCO-EQ")
        master(conn, "SMEINC", "NSE:SMEINC-SM")
        report = cr.diagnose(conn)
        self.assertEqual(report["coverage"]["ok"], 1)
        self.assertEqual(report["coverage"]["no_price"], 1)
        self.assertEqual(report["by_instrument"].get("non_tradable"), 1)

    def test_band_only_symbol_is_detected(self):
        conn = memory_db()
        seed(conn, "BANDONLY", active=None, price_date=None)
        master(conn, "BANDONLY", "NSE:BANDONLY-EQ")
        report = cr.diagnose(conn)
        self.assertEqual(report["band_only"], 1)
        row = report["gap_rows"][0]
        self.assertEqual(row["source_table"], "band_only")
        self.assertEqual(row["instrument"], "tradable_eq")

    def test_alias_candidate_for_punctuated_symbol(self):
        conn = memory_db()
        seed(conn, "BOSCH_HCIL", active=1, price_date=None)
        master(conn, "BOSCH-HCIL", "NSE:BOSCH-HCIL-EQ")
        report = cr.diagnose(conn)
        # project symbol resolves via normalization; classify as alias
        kinds = {row["instrument"] for row in report["gap_rows"]}
        self.assertIn("alias_candidate", kinds)

    def test_unresolved_symbol(self):
        conn = memory_db()
        seed(conn, "GHOST", active=1, price_date=None)
        report = cr.diagnose(conn)
        self.assertIn("unresolved", report["by_instrument"])
        self.assertTrue(any("ISIN" in s for s in report["suggestions"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
