"""F-28 - a replay that dies before doing work must not delete anything.

2026-10-23: replay(fresh=True) deleted every stored signal and every
league_progress row BEFORE build_context() ran, and build_context then raised
NameError (F-27). The books were emptied, and because status() derives
``code_changed`` from league_progress.code_hash, the emptied books also became
invisible to ``replay --changed`` - the command meant to repair them.

Test 1 fails if the destructive step ever moves back in front of
build_context(). Test 2 pins the other half: once the context is up, a fresh
replay must still clear the old rows.
"""
import sqlite3
import unittest
from unittest import mock

import trader_league


class _KeepOpen:
    """Connection proxy whose close() is a no-op.

    replay() closes its own connection before returning; the tests need to
    read the row counts afterwards.
    """

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


class ReplayFreshSafetyTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(trader_league.TABLES)
        self.conn.execute(
            "INSERT INTO league_signals (source, player, date, symbol, "
            "method, kind) VALUES "
            "('replay','home','2026-01-01','AAA','m','ENTRY')")
        self.conn.execute(
            "INSERT INTO league_progress VALUES "
            "('home','AAA','2024-01-01','2026-01-01',10,'deadbeef','2026-01-01')")
        self.conn.commit()
        self.cfg = {"REPLAY_YEARS": 3, "REPLAY_SYMBOLS": 2,
                    "HOME_BAND_LIMIT": 2}

    def tearDown(self):
        self.conn.close()

    def _patches(self, context, syms=("AAA", "BBB")):
        return (
            mock.patch.object(trader_league, "_conn",
                              return_value=_KeepOpen(self.conn)),
            mock.patch.object(trader_league, "config", return_value=self.cfg),
            mock.patch.object(trader_league, "_last_price_date",
                              return_value="2026-10-16"),
            mock.patch("universe_helper.band_universe",
                       return_value=list(syms)),
            mock.patch("universe_helper.combined_universe",
                       return_value=list(syms)),
            mock.patch.object(trader_league, "build_context",
                              **context),
            mock.patch.object(trader_league, "_worker_init"),
        )

    def _run(self, patches, **kwargs):
        for p in patches:
            p.start()
        try:
            return trader_league.replay(quiet=True, simulate_after=False,
                                        **kwargs)
        finally:
            for p in reversed(patches):
                p.stop()

    def test_crash_before_context_keeps_stored_data(self):
        patches = self._patches({"side_effect": RuntimeError("context boom")})
        with self.assertRaises(RuntimeError):
            self._run(patches, years=1, n_symbols=2, slugs=["home"],
                      workers=1, fresh=True)

        signals = self.conn.execute(
            "SELECT COUNT(*) FROM league_signals").fetchone()[0]
        progress = self.conn.execute(
            "SELECT COUNT(*) FROM league_progress").fetchone()[0]
        self.assertEqual(
            signals, 1,
            "replay(fresh=True) deleted stored signals before build_context()")
        self.assertEqual(
            progress, 1,
            "replay(fresh=True) deleted league_progress before build_context()")

    def test_successful_fresh_replay_still_clears_old_rows(self):
        patches = self._patches({"return_value": {"bench_label": "TEST"}},
                                syms=("AAA",))
        task = {"symbol": "AAA", "rows": [], "done": [],
                "errors": 0, "calls": 0}
        with mock.patch.object(trader_league, "_worker_task",
                               return_value=task):
            out = self._run(patches, years=1, n_symbols=1, slugs=["home"],
                            workers=1, fresh=True)

        self.assertEqual(out["stocks"], 1)
        signals = self.conn.execute(
            "SELECT COUNT(*) FROM league_signals").fetchone()[0]
        progress = self.conn.execute(
            "SELECT COUNT(*) FROM league_progress").fetchone()[0]
        self.assertEqual(
            signals, 0,
            "a successful fresh replay must clear the previous signals")
        self.assertEqual(
            progress, 0,
            "a successful fresh replay must clear the previous progress rows")


if __name__ == "__main__":
    unittest.main()
