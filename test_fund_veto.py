"""Tests for the expanded fundamental veto gate (Option B, 2026-10-18)."""
import sqlite3
import unittest

import db
import fund_veto


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def seed(conn, symbol, **fields):
    cols = ["symbol"] + list(fields)
    conn.execute(
        "INSERT OR REPLACE INTO fundamentals ({}) VALUES ({})".format(
            ",".join(cols), ",".join("?" for _ in cols)),
        [symbol] + [fields[k] for k in fields])
    conn.commit()


class VetoTests(unittest.TestCase):
    def test_debt_veto(self):
        conn = memory_db()
        seed(conn, "AAA", debt_to_equity=4.0)
        self.assertTrue(fund_veto.vetoed("AAA", conn=conn)[0])

    def test_pledge_veto_is_new(self):
        conn = memory_db()
        seed(conn, "AAA", pledge_pct=40.0)
        vetoed, why = fund_veto.vetoed("AAA", conn=conn)
        self.assertTrue(vetoed)
        self.assertIn("pledge", why)

    def test_interest_coverage_veto_is_new(self):
        conn = memory_db()
        seed(conn, "AAA", interest_coverage=0.8)
        vetoed, why = fund_veto.vetoed("AAA", conn=conn)
        self.assertTrue(vetoed)
        self.assertIn("interest", why)

    def test_roce_and_promoter_veto_still_work(self):
        conn = memory_db()
        seed(conn, "AAA", roce=5.0)
        seed(conn, "BBB", promoter_holding=12.0)
        self.assertTrue(fund_veto.vetoed("AAA", conn=conn)[0])
        self.assertTrue(fund_veto.vetoed("BBB", conn=conn)[0])

    def test_healthy_and_missing_rows_pass(self):
        conn = memory_db()
        seed(conn, "AAA", debt_to_equity=0.5, roce=22.0,
             promoter_holding=55.0, pledge_pct=0.0,
             interest_coverage=8.0)
        self.assertFalse(fund_veto.vetoed("AAA", conn=conn)[0])
        # absence of data must never veto (current documented behaviour)
        self.assertFalse(fund_veto.vetoed("MISSING", conn=conn)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
