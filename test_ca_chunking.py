"""Tests for the chunked/resumable corporate-action harvest (18 Oct 2026).

The full-universe harvest hung on one symbol inside yfinance (no timeout of its
own). These tests lock the fix: per-symbol timeout, resumable state, and chunk
merging that persists progress.
"""
import sqlite3
import unittest
from unittest import mock

import db
import corporate_actions as ca


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    conn.execute("PRAGMA temp_store=MEMORY")
    ca.ensure_fetch_state(conn)
    return conn


def action(symbol):
    return {"symbol": symbol, "ex_date": "2026-01-02", "kind": "dividend",
            "ratio": None, "amount": 2.0, "source": "yfinance",
            "status": "unconfirmed", "raw": "{}"}


class ChunkedHarvestTests(unittest.TestCase):
    def test_timeout_is_recorded_and_batch_continues(self):
        def fake(symbol, timeout):
            if symbol == "BAD":
                return [], "timeout"
            return [action(symbol)], None

        conn = memory_db()
        with mock.patch.object(ca, "_fetch_one_with_timeout", side_effect=fake):
            result = ca.fetch_all_resumable(
                conn, ["AAA", "BAD", "BBB"], sleep_seconds=0,
                per_symbol_timeout=1, chunk_size=2, progress=False)
        self.assertEqual(result["fetched_symbols"], 2)
        self.assertEqual(result["timeouts"], ["BAD"])
        state = dict(conn.execute(
            "SELECT symbol, status FROM corporate_actions_fetch_state"))
        self.assertEqual(state["BAD"], "error")
        self.assertEqual(state["AAA"], "ok")

    def test_resume_skips_completed_symbols(self):
        conn = memory_db()
        calls = []

        def fake(symbol, timeout):
            calls.append(symbol)
            return [action(symbol)], None

        with mock.patch.object(ca, "_fetch_one_with_timeout", side_effect=fake):
            ca.fetch_all_resumable(conn, ["AAA"], sleep_seconds=0,
                                   per_symbol_timeout=1, progress=False)
            second = ca.fetch_all_resumable(
                conn, ["AAA", "BBB"], sleep_seconds=0,
                per_symbol_timeout=1, progress=False)
        self.assertEqual(calls, ["AAA", "BBB"])
        self.assertEqual(second["already_done"], 1)

    def test_actions_are_merged_per_symbol(self):
        conn = memory_db()
        with mock.patch.object(ca, "_fetch_one_with_timeout",
                               return_value=([action("AAA")], None)):
            result = ca.fetch_all_resumable(
                conn, ["AAA"], sleep_seconds=0, per_symbol_timeout=1,
                progress=False)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM corporate_actions").fetchone()[0], 1)

    def test_force_refetches_completed(self):
        conn = memory_db()
        calls = []

        def fake(symbol, timeout):
            calls.append(symbol)
            return [], None

        with mock.patch.object(ca, "_fetch_one_with_timeout", side_effect=fake):
            ca.fetch_all_resumable(conn, ["AAA"], sleep_seconds=0,
                                   per_symbol_timeout=1, progress=False)
            ca.fetch_all_resumable(conn, ["AAA"], sleep_seconds=0,
                                   per_symbol_timeout=1, force=True,
                                   progress=False)
        self.assertEqual(calls, ["AAA", "AAA"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
