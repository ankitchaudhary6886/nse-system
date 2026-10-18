"""Offline tests for the one-click refresh orchestrator (18 Oct 2026)."""
import sqlite3
import unittest
from unittest import mock

import db
import refresh_pipeline as rp


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


class RunTests(unittest.TestCase):
    def test_successful_chain_records_ok(self):
        conn = memory_db()
        steps = [("a", lambda: {"n": 1}), ("b", lambda: {"n": 2})]
        result = rp.run(trigger="test", steps=steps, conn=conn)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ok")
        row = conn.execute(
            "SELECT status, trigger FROM refresh_runs WHERE run_id=?",
            (result["run_id"],)).fetchone()
        self.assertEqual(row, ("ok", "test"))

    def test_one_failure_makes_partial_and_continues(self):
        conn = memory_db()
        calls = []

        def boom():
            raise RuntimeError("nope")

        def later():
            calls.append(1)
            return {"ok": True}

        result = rp.run(trigger="test", steps=[("a", boom), ("b", later)],
                        conn=conn)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(calls, [1])
        row = conn.execute(
            "SELECT status FROM refresh_runs WHERE run_id=?",
            (result["run_id"],)).fetchone()
        self.assertEqual(row[0], "partial")

    def test_second_run_while_locked_is_rejected(self):
        conn = memory_db()
        inner = {}

        def reentrant():
            inner["result"] = rp.run(trigger="test2", steps=[], conn=conn)
            return {"ok": True}

        outer = rp.run(trigger="test1", steps=[("x", reentrant)], conn=conn)
        self.assertTrue(outer["ok"])
        self.assertTrue(inner["result"]["already_running"])

    def test_status_reports_latest_run(self):
        conn = memory_db()
        result = rp.run(trigger="test", steps=[("a", lambda: {"ok": True})],
                        conn=conn)
        state = rp.status(conn)
        self.assertEqual(state["latest_run"]["run_id"], result["run_id"])
        self.assertFalse(state["running"])

    def test_skipped_step_still_counts_as_ok(self):
        conn = memory_db()
        result = rp.run(trigger="test",
                        steps=[("fyers", lambda: {"skipped": "no token"})],
                        conn=conn)
        self.assertTrue(result["ok"])
        self.assertEqual(result["skipped"], ["fyers"])


class HealthTests(unittest.TestCase):
    def test_health_reports_prices_and_gate(self):
        conn = memory_db()
        conn.execute(
            "INSERT INTO prices_daily VALUES ('AAA','2026-10-16',1,1,1,1,10)")
        conn.commit()
        health = rp.health(conn)
        self.assertEqual(health["prices_rows"], 1)
        self.assertEqual(health["max_price_date"], "2026-10-16")
        self.assertIn("freshness", health)
        self.assertIn("artifacts_today", health)

    def test_health_on_empty_db_is_not_ok(self):
        conn = memory_db()
        health = rp.health(conn)
        self.assertFalse(health["ok"])
        self.assertIsNone(health["max_price_date"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
