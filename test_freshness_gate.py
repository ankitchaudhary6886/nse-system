"""Offline tests for freshness_gate: in-memory schema, fixed IST clocks."""

import contextlib
import datetime as dt
import io
import json
import os
import sqlite3
import unittest
from unittest.mock import patch

import db
import freshness_gate as fg


def ist(year: int, month: int, day: int, hour: int = 16,
        minute: int = 0) -> dt.datetime:
    """Fixed IST wall clock, e.g. ist(2026, 10, 8, 16, 0) = Thu 4pm IST."""
    return dt.datetime(year, month, day, hour, minute, tzinfo=fg.IST)


class FreshnessGateTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(db.SCHEMA)
        self._clear_env()

    def tearDown(self):
        self._clear_env()
        try:
            self.conn.close()
        except Exception:
            pass

    def _clear_env(self):
        for key in (fg.ENV_BLOCK_SESSIONS, fg.ENV_MAX_STALE_DAYS):
            os.environ.pop(key, None)

    def seed(self, date_str: str, symbol: str = "AAA") -> None:
        self.conn.execute(
            "INSERT INTO prices_daily (symbol, date, open, high, low, close, "
            "volume) VALUES (?,?,?,?,?,?,?)",
            (symbol, date_str, 100.0, 101.0, 99.0, 100.5, 1000.0))
        self.conn.commit()

    def gate_rows(self):
        return self.conn.execute(
            "SELECT run_at, artifact, status, max_price_date, expected_date, "
            "stale_sessions, action, detail FROM freshness_gate_log "
            "ORDER BY rowid").fetchall()

    # ------------------------------------------------------------------
    # assess()
    # ------------------------------------------------------------------
    def test_fresh_data_after_close_is_not_blocked(self):
        self.seed("2026-10-08")
        res = fg.assess(self.conn, now=ist(2026, 10, 8, 16, 0))
        self.assertEqual(res["max_price_date"], "2026-10-08")
        self.assertEqual(res["expected_session"], "2026-10-08")
        self.assertEqual(res["missing_sessions"], 0)
        self.assertEqual(res["calendar_days_stale"], 0)
        self.assertTrue(res["market_closed"])
        self.assertFalse(res["blocked"])
        self.assertEqual(res["threshold_sessions"], 2)
        self.assertEqual(res["threshold_calendar_days"], 7)
        self.assertIn("OK", res["reason"])

    def test_weekend_expects_friday(self):
        self.seed("2026-10-09")
        res = fg.assess(self.conn, now=ist(2026, 10, 10, 11, 0))
        self.assertEqual(fg.expected_session(ist(2026, 10, 10, 11, 0)),
                         dt.date(2026, 10, 9))
        self.assertEqual(res["expected_session"], "2026-10-09")
        self.assertEqual(res["missing_sessions"], 0)
        self.assertFalse(res["market_closed"])
        self.assertFalse(res["blocked"])

    def test_pre_close_weekday_expects_previous_weekday(self):
        self.seed("2026-10-09")
        res = fg.assess(self.conn, now=ist(2026, 10, 12, 9, 30))
        self.assertEqual(res["expected_session"], "2026-10-09")
        self.assertEqual(res["missing_sessions"], 0)
        self.assertFalse(res["market_closed"])
        self.assertFalse(res["blocked"])

    def test_single_missing_weekday_is_tolerated(self):
        self.seed("2026-10-09")
        res = fg.assess(self.conn, now=ist(2026, 10, 12, 16, 30))
        self.assertEqual(res["expected_session"], "2026-10-12")
        self.assertEqual(res["missing_sessions"], 1)
        self.assertEqual(res["calendar_days_stale"], 3)
        self.assertFalse(res["blocked"])
        self.assertIn("tolerated", res["reason"].lower())

    def test_two_missing_weekdays_block(self):
        self.seed("2026-10-09")
        res = fg.assess(self.conn, now=ist(2026, 10, 13, 16, 30))
        self.assertEqual(res["missing_sessions"], 2)
        self.assertTrue(res["blocked"])
        self.assertTrue(res["reason"].startswith("BLOCKED"))
        self.assertIn("weekday session", res["reason"])

    def test_calendar_staleness_blocks_even_when_sessions_under_threshold(self):
        self.seed("2026-10-09")
        with patch.dict(os.environ, {fg.ENV_BLOCK_SESSIONS: "99"}):
            res = fg.assess(self.conn, now=ist(2026, 10, 21, 16, 30))
        self.assertEqual(res["threshold_sessions"], 99)
        self.assertEqual(res["missing_sessions"], 8)
        self.assertLess(res["missing_sessions"], res["threshold_sessions"])
        self.assertEqual(res["calendar_days_stale"], 12)
        self.assertTrue(res["blocked"])
        self.assertIn("calendar days stale", res["reason"])

    def test_empty_price_table_blocks_without_exception(self):
        res = fg.assess(self.conn, now=ist(2026, 10, 8, 16, 0))
        self.assertIsNone(res["max_price_date"])
        self.assertTrue(res["blocked"])
        self.assertIn("prices_daily", res["reason"])
        self.assertNotIn("cannot determine", res["reason"])

    # ------------------------------------------------------------------
    # require_fresh()
    # ------------------------------------------------------------------
    def test_require_fresh_writes_exactly_one_row_per_call(self):
        self.seed("2026-10-08")
        out = fg.require_fresh(self.conn, "pattern_tags",
                               now=ist(2026, 10, 8, 16, 0))
        self.assertEqual(out["artifact"], "pattern_tags")
        self.assertEqual(out["status"], "OK")
        self.assertEqual(out["action"], "proceed")
        self.assertFalse(out["blocked"])
        fg.require_fresh(self.conn, "template_scores",
                         now=ist(2026, 10, 8, 16, 0))
        rows = self.gate_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][1], "pattern_tags")
        self.assertEqual(rows[1][1], "template_scores")
        self.assertEqual(rows[0][2], "OK")
        self.assertEqual(rows[0][6], "proceed")
        self.assertEqual(rows[0][3], "2026-10-08")
        self.assertEqual(rows[0][4], "2026-10-08")
        self.assertEqual(rows[0][5], 0)

    def test_require_fresh_records_refusal_when_blocked(self):
        self.seed("2026-10-09")
        out = fg.require_fresh(self.conn, "institutional",
                               now=ist(2026, 10, 13, 16, 30))
        self.assertTrue(out["blocked"])
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["action"], "refuse")
        rows = self.gate_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "institutional")
        self.assertEqual(rows[0][2], "BLOCKED")
        self.assertEqual(rows[0][6], "refuse")
        self.assertEqual(rows[0][5], 2)
        self.assertIn("BLOCKED", rows[0][7])

    def test_require_fresh_fails_safe_when_audit_table_is_missing(self):
        self.seed("2026-10-08")
        self.conn.execute("DROP TABLE freshness_gate_log")
        self.conn.commit()
        out = fg.require_fresh(self.conn, "pattern_tags",
                               now=ist(2026, 10, 8, 16, 0))
        self.assertTrue(out["blocked"])
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["action"], "refuse")
        self.assertEqual(out["reason"], fg.FAILSAFE_REASON)
        self.assertEqual(out["artifact"], "pattern_tags")

    def test_require_fresh_fails_safe_on_broken_connection(self):
        broken = sqlite3.connect(":memory:")
        broken.close()
        out = fg.require_fresh(broken, "pattern_tags",
                               now=ist(2026, 10, 8, 16, 0))
        self.assertTrue(out["blocked"])
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["reason"], fg.FAILSAFE_REASON)
        self.assertIn("error", out)

    def test_env_override_blocks_a_single_missing_session(self):
        self.seed("2026-10-09")
        with patch.dict(os.environ, {fg.ENV_BLOCK_SESSIONS: "1"}):
            res = fg.assess(self.conn, now=ist(2026, 10, 12, 16, 30))
        self.assertEqual(res["threshold_sessions"], 1)
        self.assertEqual(res["missing_sessions"], 1)
        self.assertTrue(res["blocked"])

    def test_invalid_env_values_fall_back_to_defaults(self):
        self.seed("2026-10-08")
        with patch.dict(os.environ, {fg.ENV_BLOCK_SESSIONS: "zero",
                                     fg.ENV_MAX_STALE_DAYS: "0"}):
            res = fg.assess(self.conn, now=ist(2026, 10, 8, 16, 0))
        self.assertEqual(res["threshold_sessions"], fg.DEFAULT_BLOCK_SESSIONS)
        self.assertEqual(res["threshold_calendar_days"],
                         fg.DEFAULT_MAX_STALE_DAYS)

    # ------------------------------------------------------------------
    # status() + CLI
    # ------------------------------------------------------------------
    def test_status_returns_assessment_and_last_ten_rows(self):
        self.seed("2026-10-08")
        for i in range(12):
            fg.require_fresh(self.conn, f"artifact_{i}",
                             now=ist(2026, 10, 8, 16, 0))
        out = fg.status(self.conn, now=ist(2026, 10, 8, 16, 0))
        self.assertFalse(out["blocked"])
        self.assertEqual(out["max_price_date"], "2026-10-08")
        self.assertEqual(len(out["recent_log"]), 10)
        self.assertEqual(out["recent_log"][0]["artifact"], "artifact_11")

    def _cli(self, argv, conn):
        buffer = io.StringIO()
        with patch.object(db, "get_conn", return_value=conn), \
                contextlib.redirect_stdout(buffer):
            code = fg.main(argv)
        return code, json.loads(buffer.getvalue())

    def test_cli_check_exits_zero_when_fresh(self):
        # The CLI has no clock argument, so seed the session it should expect.
        expected = fg.expected_session().isoformat()
        self.seed(expected)
        code, payload = self._cli(["check"], self.conn)
        self.assertEqual(code, 0)
        self.assertFalse(payload["blocked"])
        self.assertEqual(payload["max_price_date"], expected)

    def test_cli_check_exits_two_when_blocked(self):
        stale = (fg.now_ist().date() - dt.timedelta(days=30)).isoformat()
        self.seed(stale)
        code, payload = self._cli(["check"], self.conn)
        self.assertEqual(code, 2)
        self.assertTrue(payload["blocked"])

    def test_cli_status_prints_json_and_exits_zero(self):
        self.seed(fg.expected_session().isoformat())
        code, payload = self._cli(["status"], self.conn)
        self.assertEqual(code, 0)
        self.assertIn("recent_log", payload)
        self.assertFalse(payload["blocked"])

    def test_cli_rejects_unknown_command(self):
        code, payload = self._cli(["nope"], self.conn)
        self.assertEqual(code, 1)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
