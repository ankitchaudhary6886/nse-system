"""Offline tests for the portal freshness guard and external stale reference."""
import datetime as dt
import sqlite3
import unittest
from unittest import mock

import data_freshness as df
import db
import ingest_prices


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    db._migrate(conn)
    return conn


def add_bar(conn, date, symbol="AAA", close=100):
    conn.execute(
        "INSERT OR REPLACE INTO prices_daily "
        "(symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
        (symbol, date, close, close, close, close, 1000))
    conn.commit()


class AssessTests(unittest.TestCase):
    def test_whole_market_is_measured_against_external_session(self):
        conn = memory_db()
        add_bar(conn, "2026-10-16")
        now = dt.datetime(2026, 10, 20, 10, 0, tzinfo=df.IST)
        result = df.assess(conn, now=now)
        self.assertFalse(result["fresh"])
        self.assertEqual(result["expected"], "2026-10-19")
        self.assertEqual(result["missing_sessions"], 1)
        self.assertEqual(result["status"], "stale")

    def test_awaiting_yahoo_after_official_close(self):
        conn = memory_db()
        add_bar(conn, "2026-10-19")
        now = dt.datetime(2026, 10, 20, 16, 0, tzinfo=df.IST)
        result = df.assess(conn, now=now)
        self.assertFalse(result["fresh"])
        self.assertFalse(result["needs_official"])
        self.assertTrue(result["needs_yahoo"])
        self.assertEqual(result["status"], "awaiting_yahoo")

    def test_fresh_through_expected_session(self):
        conn = memory_db()
        add_bar(conn, "2026-10-20")
        now = dt.datetime(2026, 10, 20, 20, 0, tzinfo=df.IST)
        result = df.assess(conn, now=now)
        self.assertTrue(result["fresh"])
        self.assertEqual(result["missing_sessions"], 0)


class EnsureTests(unittest.TestCase):
    def test_official_repair_is_synchronous_and_starts_downstream(self):
        conn = memory_db()
        add_bar(conn, "2026-10-16")
        now = dt.datetime(2026, 10, 20, 20, 0, tzinfo=df.IST)

        def fake_catch_up(conn, days_back=15, include_today=None, **kwargs):
            add_bar(conn, "2026-10-19")
            add_bar(conn, "2026-10-20")
            return {"attempted": 2, "ok": 2, "missing": [], "errors": []}

        with mock.patch.object(df.nse_eod_ingest, "catch_up",
                               side_effect=fake_catch_up), \
             mock.patch("refresh_pipeline.start_background",
                        return_value={"started": True, "run_id": "test"}):
            result = df.ensure_fresh(now=now, conn=conn)

        self.assertTrue(result["fresh"])
        self.assertTrue(result["repaired"])
        self.assertEqual(result["latest"], "2026-10-20")
        self.assertEqual(result["refresh"]["run_id"], "test")

    def test_stale_after_failed_repair_starts_full_refresh(self):
        conn = memory_db()
        add_bar(conn, "2026-10-16")
        now = dt.datetime(2026, 10, 20, 20, 0, tzinfo=df.IST)

        with mock.patch.object(
                df.nse_eod_ingest, "catch_up",
                return_value={"attempted": 2, "ok": 0,
                              "missing": ["2026-10-19", "2026-10-20"],
                              "errors": []}), \
             mock.patch("refresh_pipeline.start_background",
                        return_value={"started": True, "run_id": "fallback"}):
            result = df.ensure_fresh(now=now, conn=conn)

        self.assertFalse(result["fresh"])
        self.assertFalse(result["repaired"])
        self.assertEqual(result["status"], "stale")
        self.assertTrue(result["refresh"]["started"])

    def test_fresh_spine_does_not_fetch(self):
        conn = memory_db()
        add_bar(conn, "2026-10-20")
        now = dt.datetime(2026, 10, 20, 20, 0, tzinfo=df.IST)
        with mock.patch.object(df.nse_eod_ingest, "catch_up") as catch_up:
            result = df.ensure_fresh(now=now, conn=conn)
        self.assertTrue(result["fresh"])
        catch_up.assert_not_called()


class StaleSymbolTests(unittest.TestCase):
    def test_frozen_market_returns_full_universe_not_just_laggards(self):
        conn = memory_db()
        add_bar(conn, "2026-10-16", "AAA")
        add_bar(conn, "2026-10-16", "BBB")
        conn.execute("INSERT OR REPLACE INTO price_meta "
                     "(symbol,last_date,rows) VALUES ('AAA','2026-10-16',1)")
        conn.execute("INSERT OR REPLACE INTO price_meta "
                     "(symbol,last_date,rows) VALUES ('BBB','2026-10-16',1)")
        conn.commit()
        stale = ingest_prices._stale_symbols(
            conn, ["AAA", "BBB", "CCC"], expected="2026-10-23")
        self.assertEqual(sorted(stale), ["AAA", "BBB", "CCC"])

    def test_current_market_returns_only_laggards(self):
        conn = memory_db()
        add_bar(conn, "2026-10-23", "AAA")
        add_bar(conn, "2026-10-23", "BBB")
        add_bar(conn, "2026-10-16", "CCC")
        for symbol, last in (("AAA", "2026-10-23"), ("BBB", "2026-10-23"),
                             ("CCC", "2026-10-16")):
            conn.execute(
                "INSERT OR REPLACE INTO price_meta "
                "(symbol,last_date,rows) VALUES (?,?,1)", (symbol, last))
        conn.commit()
        stale = ingest_prices._stale_symbols(
            conn, ["AAA", "BBB", "CCC"], expected="2026-10-23")
        self.assertEqual(stale, ["CCC"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
