"""Tests for the two data-job plumbing fixes and the scan heartbeat.

Run:  .\\env\\Scripts\\python.exe -m unittest test_job_health -v
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import unittest
from unittest import mock

import broad_scan
import scheduler_bg
import verify_deployment


class _Conn:
    """sqlite wrapper whose close() is a no-op so the test can read results."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, *args):
        return self._conn.execute(*args)

    def commit(self):
        self._conn.commit()

    def close(self):
        pass


class JobPlumbingTests(unittest.TestCase):
    def test_value_radar_job_recomputes_before_reporting(self):
        with mock.patch.object(scheduler_bg, "log"), \
             mock.patch("value_radar.compute") as compute, \
             mock.patch("value_radar.report") as report:
            scheduler_bg._value_radar_job()
        compute.assert_called_once()
        report.assert_called_once()

    def test_broad_scan_replaces_the_snapshot(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("""CREATE TABLE universe_broad(
            symbol TEXT PRIMARY KEY, name TEXT, mcap_cr REAL, close REAL,
            pe REAL, perf1m REAL, perf3m REAL, relvol REAL, updated_at TEXT)""")
        conn.execute(
            "INSERT INTO universe_broad(symbol, name) VALUES('OLD', 'Delisted')")
        conn.commit()
        wrapped = _Conn(conn)
        data = [{"s": "NSE:NEW", "d": ["New Co", 100.0, 5e11, 20.0,
                                        10.0, 12.0, 2.5, 1000.0, 500.0]}]
        with mock.patch.object(broad_scan, "fetch", return_value=data), \
             mock.patch.object(broad_scan.db, "get_conn", return_value=wrapped), \
             mock.patch("builtins.print"):
            broad_scan.run()
        rows = conn.execute(
            "SELECT symbol, name FROM universe_broad ORDER BY symbol").fetchall()
        self.assertEqual(rows, [("NEW", "New Co")])


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE freshness_gate_log(run_at TEXT, artifact TEXT)")

    def _insert(self, when):
        self.conn.execute(
            "INSERT INTO freshness_gate_log VALUES(?, 'swing_live')",
            (when,))
        self.conn.commit()

    def test_recent_scan_run_is_a_heartbeat(self):
        self._insert(dt.datetime.now().isoformat(timespec="seconds"))
        self.assertIsNotNone(verify_deployment._scan_heartbeat(self.conn))

    def test_old_scan_run_is_not_a_heartbeat(self):
        self._insert("2026-01-01T16:15:00")
        self.assertIsNone(verify_deployment._scan_heartbeat(self.conn))


if __name__ == "__main__":
    unittest.main(verbosity=2)
