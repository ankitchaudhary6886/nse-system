"""Offline tests for the Fyers gap-filler (18 Oct 2026)."""
import datetime as dt
import sqlite3
import unittest

import backfill_gaps as bg
import db
import fyers_client as fc


def candle_epoch(date_str):
    moment = dt.datetime.fromisoformat(date_str).replace(tzinfo=fc.IST)
    return int(moment.timestamp())


def candle(date_str, close):
    return [candle_epoch(date_str), close, close + 1, close - 1, close, 1000]


class FakeClient:
    def __init__(self, candles_by_ticker, token="tok"):
        self.token = token
        self.candles = candles_by_ticker
        self.calls = []

    def history_range(self, ticker, start, end):
        self.calls.append((ticker, start, end))
        return self.candles.get(ticker, [])


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    db._migrate(conn)
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def seed_universe(conn, symbols=("SBIN",)):
    for symbol in symbols:
        conn.execute("INSERT OR REPLACE INTO universe_broad "
                     "(symbol,mcap_cr,updated_at) VALUES (?,2000,'2026-10-18')",
                     (symbol,))
    conn.commit()


def seed_day(conn, date):
    conn.execute("INSERT OR REPLACE INTO nse_eod_sync (date,status) "
                 "VALUES (?,'ok')", (date,))


class MissingReportTests(unittest.TestCase):
    def test_finds_holes(self):
        conn = memory_db()
        seed_universe(conn)
        seed_day(conn, "2026-10-15")
        seed_day(conn, "2026-10-16")
        conn.execute("INSERT INTO prices_daily VALUES "
                     "('SBIN','2026-10-15',1,1,1,100,10)")
        conn.commit()
        report = bg.missing_report(conn, days=5)
        self.assertEqual(report["symbols_missing"], 1)
        self.assertEqual(report["missing_sample"]["SBIN"], ["2026-10-16"])


class FillTests(unittest.TestCase):
    def test_fill_writes_only_missing_dates(self):
        conn = memory_db()
        seed_universe(conn)
        seed_day(conn, "2026-10-15")
        seed_day(conn, "2026-10-16")
        conn.execute("INSERT INTO prices_daily VALUES "
                     "('SBIN','2026-10-15',100,101,99,100,1000)")
        conn.execute("INSERT OR REPLACE INTO fyers_symbol_master "
                     "(symbol,ticker) VALUES ('SBIN','NSE:SBIN-EQ')")
        conn.commit()
        client = FakeClient({"NSE:SBIN-EQ": [
            candle("2026-10-15", 100.0), candle("2026-10-16", 105.0)]})
        result = bg.fill_with_fyers(conn, client=client, days=5)
        self.assertTrue(result["ok"])
        self.assertEqual(result["filled_rows"], 1)
        row = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol='SBIN' "
            "AND date='2026-10-16'").fetchone()
        self.assertEqual(row[0], 105.0)
        # existing official bar was not overwritten
        old = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol='SBIN' "
            "AND date='2026-10-15'").fetchone()
        self.assertEqual(old[0], 100.0)

    def test_fill_without_token_skips(self):
        conn = memory_db()
        client = FakeClient({}, token="")
        result = bg.fill_with_fyers(conn, client=client)
        self.assertFalse(result["ok"])
        self.assertIn("no fyers token", result["skipped"])

    def test_basis_becomes_mixed_raw_sources(self):
        conn = memory_db()
        seed_universe(conn)
        seed_day(conn, "2026-10-16")
        conn.execute("INSERT OR REPLACE INTO price_meta "
                     "(symbol,last_date,rows,updated_at,basis) "
                     "VALUES ('SBIN','2026-10-16',1,'', 'nse_bhavdata_raw')")
        conn.execute("INSERT OR REPLACE INTO fyers_symbol_master "
                     "(symbol,ticker) VALUES ('SBIN','NSE:SBIN-EQ')")
        conn.commit()
        client = FakeClient({"NSE:SBIN-EQ": [candle("2026-10-16", 105.0)]})
        bg.fill_with_fyers(conn, client=client, days=5)
        basis = conn.execute(
            "SELECT basis FROM price_meta WHERE symbol='SBIN'").fetchone()[0]
        self.assertEqual(basis, "mixed_raw_sources")
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM fyers_sync_log WHERE kind='gap_fill'"
        ).fetchone()[0], 1)

    def test_dry_run_writes_nothing(self):
        conn = memory_db()
        seed_universe(conn)
        seed_day(conn, "2026-10-16")
        conn.execute("INSERT OR REPLACE INTO fyers_symbol_master "
                     "(symbol,ticker) VALUES ('SBIN','NSE:SBIN-EQ')")
        conn.commit()
        client = FakeClient({"NSE:SBIN-EQ": [candle("2026-10-16", 105.0)]})
        result = bg.fill_with_fyers(conn, client=client, days=5, dry_run=True)
        self.assertEqual(result["filled_rows"], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0], 0)


class HistoricalFillTests(unittest.TestCase):
    def test_history_fills_only_missing(self):
        conn = memory_db()
        seed_universe(conn)
        conn.execute("INSERT INTO prices_daily VALUES "
                     "('SBIN','2026-01-02',50,51,49,50,10)")
        conn.execute("INSERT OR REPLACE INTO fyers_symbol_master "
                     "(symbol,ticker) VALUES ('SBIN','NSE:SBIN-EQ')")
        conn.commit()
        client = FakeClient({"NSE:SBIN-EQ": [
            candle("2026-01-02", 50.0), candle("2026-01-05", 55.0)]})
        result = bg.historical_fill(conn, client=client, start="2026-01-01",
                                    end="2026-01-06")
        self.assertEqual(result["filled_rows"], 1)
        row = conn.execute(
            "SELECT close FROM prices_daily WHERE date='2026-01-05'").fetchone()
        self.assertEqual(row[0], 55.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
