"""Tests for the hard freshness gate wiring (signal_guard.py).

These lock the owner-approved behaviour: when the price spine is stale, every
signal writer refuses to write. The gate module itself is tested separately in
test_freshness_gate.py; here we test the adapter contract and failure modes.
"""
import datetime as dt
import sqlite3
import unittest
from unittest import mock

import db
import signal_guard


def memory_db(max_date="2026-10-16"):
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute(
        "INSERT INTO prices_daily VALUES ('SBIN',?,100,101,99,100,1000)",
        (max_date,))
    conn.commit()
    return conn


class SignalGuardTests(unittest.TestCase):
    def test_stale_data_blocks(self):
        conn = memory_db("2026-08-27")
        # today is fixed well past the stored date -> many missing sessions
        self.assertTrue(signal_guard.check(conn, "patterns"))
        logged = conn.execute(
            "SELECT artifact, status, action FROM freshness_gate_log "
            "ORDER BY rowid DESC LIMIT 1").fetchone()
        self.assertEqual(logged, ("patterns", "BLOCKED", "refuse"))

    def test_fresh_data_allows(self):
        now = dt.datetime(2026, 10, 18, 21, 0)  # Sunday after a Friday close
        conn = memory_db("2026-10-16")
        with mock.patch("freshness_gate.now_ist", return_value=now.replace(
                tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))):
            self.assertFalse(signal_guard.check(conn, "patterns"))
        logged = conn.execute(
            "SELECT status FROM freshness_gate_log ORDER BY rowid DESC "
            "LIMIT 1").fetchone()
        self.assertEqual(logged[0], "OK")

    def test_gate_error_blocks_fail_safe(self):
        conn = memory_db("2026-10-16")
        with mock.patch("freshness_gate.require_fresh",
                        side_effect=RuntimeError("boom")):
            self.assertTrue(signal_guard.check(conn, "scan"))

    def test_missing_gate_module_does_not_break_pipeline(self):
        conn = memory_db("2026-08-27")
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "freshness_gate":
                raise ImportError("not deployed")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            self.assertFalse(signal_guard.check(conn, "patterns"))

    def test_never_writes_signal_rows(self):
        conn = memory_db("2026-08-27")
        before = conn.execute("SELECT COUNT(*) FROM pattern_tags").fetchone()[0]
        signal_guard.check(conn, "patterns")
        after = conn.execute("SELECT COUNT(*) FROM pattern_tags").fetchone()[0]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
