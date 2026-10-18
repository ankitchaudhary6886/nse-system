"""Offline tests for rebuild_raw_history.py.

No network, no ``data/app.db``: every test runs against ``sqlite3`` in-memory
built from ``db.SCHEMA`` and a fake client that answers the two GETs
``FyersClient`` would make (``/data/history`` and ``/profile``). The fake is
local on purpose — importing another test module would couple these tests to
that module's fixtures.

Run with:  & .\\env\\Scripts\\python.exe -m unittest test_rebuild_raw_history -v
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import db
import ingest_fyers
import rebuild_raw_history as R

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
HISTORY_URL = "https://api-t1.fyers.in/data/history"
PROFILE_URL = "https://api-t1.fyers.in/api/v3/profile"


def candle_epoch(date_str: str) -> int:
    """Epoch seconds for 00:00 IST on ``date_str`` — Fyers' daily-bar stamp."""
    day = dt.date.fromisoformat(date_str)
    return int(dt.datetime(day.year, day.month, day.day, tzinfo=IST).timestamp())


def day(offset: int) -> str:
    """ISO date ``offset`` days before today (always inside the 5y window)."""
    return (dt.date.today() - dt.timedelta(days=offset)).isoformat()


def bar(date_str: str, close: float = 100.0, volume: float = 10000.0) -> list:
    return [candle_epoch(date_str), close, round(close * 1.01, 2),
            round(close * 0.99, 2), close, volume]


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code}")


class FakeSession:
    """Serves the broker's history/profile endpoints from an in-memory table."""

    def __init__(self, bars_by_ticker: dict):
        self.bars_by_ticker = {str(k).upper(): dict(v)
                               for k, v in bars_by_ticker.items()}
        self.calls: list = []

    def get(self, url, params=None, headers=None, timeout=None, **kwargs):
        params = dict(params or {})
        self.calls.append((url, params))
        if url.endswith("/profile"):
            return FakeResponse({"s": "ok", "data": {"name": "fake"}})
        if url.endswith("/data/history"):
            ticker = str(params.get("symbol", "")).upper()
            start = str(params.get("range_from", ""))[:10]
            stop = str(params.get("range_to", ""))[:10]
            bars = self.bars_by_ticker.get(ticker, {})
            candles = [bars[d] for d in sorted(bars) if start <= d <= stop]
            return FakeResponse({"s": "ok", "candles": candles})
        return FakeResponse({"s": "error"}, status_code=404)


class FakeClient:
    """Minimal stand-in for FyersClient: same ``token`` + ``history_range``."""

    def __init__(self, bars_by_ticker: dict, token: str = "fake-access-token",
                 failing: tuple = ()):
        self.session = FakeSession(bars_by_ticker)
        self.token = token
        self.failing = {str(s).upper() for s in failing}

    def history_range(self, symbol, start, end=None, resolution="1D",
                      chunk_days=300):
        ticker = str(symbol).upper()
        if ticker in self.failing:
            raise RuntimeError(f"synthetic broker failure for {ticker}")
        end_date = dt.date.fromisoformat(str(end or dt.date.today())[:10])
        start_date = dt.date.fromisoformat(str(start)[:10])
        rows = []
        cursor = start_date
        while cursor <= end_date:
            stop = min(cursor + dt.timedelta(days=chunk_days - 1), end_date)
            payload = self.session.get(HISTORY_URL, params={
                "symbol": ticker, "resolution": resolution,
                "range_from": cursor.isoformat(), "range_to": stop.isoformat(),
                "date_format": "1", "cont_flag": "1"})
            rows.extend(payload.json().get("candles") or [])
            cursor = stop + dt.timedelta(days=1)
        return rows


class BaseCase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(db.SCHEMA)
        self.conn.commit()
        # Never let a rebuild write a real CSV into data/backups/.
        self._backup_tmp = tempfile.TemporaryDirectory()
        self._orig_backup = ingest_fyers.BACKUP_DIR
        ingest_fyers.BACKUP_DIR = Path(self._backup_tmp.name)

    def tearDown(self):
        ingest_fyers.BACKUP_DIR = self._orig_backup
        self._backup_tmp.cleanup()
        self.conn.close()

    # -- seeding -----------------------------------------------------------
    def seed_stock(self, symbol: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO stocks (symbol,name,sector,active,updated_at)"
            " VALUES (?,?,?,1,?)", (symbol, symbol, "Test", day(0)))

    def seed_master(self, symbol: str, ticker: str = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO fyers_symbol_master "
            "(symbol,ticker,name,isin,exchange,segment) VALUES (?,?,?,?,?,?)",
            (symbol, ticker or f"NSE:{symbol}-EQ", symbol, None, "NSE", "CM"))

    def seed_prices(self, symbol: str, dates, close: float = 100.0,
                    basis=None) -> None:
        for d in dates:
            self.conn.execute(
                "INSERT OR REPLACE INTO prices_daily "
                "(symbol,date,open,high,low,close,volume) VALUES (?,?,?,?,?,?,?)",
                (symbol, d, close, close * 1.01, close * 0.99, close, 10000.0))
        self.conn.execute(
            "INSERT OR REPLACE INTO price_meta "
            "(symbol,last_date,rows,updated_at,basis) VALUES (?,?,?,?,?)",
            (symbol, max(dates), len(list(dates)), day(0), basis))
        self.conn.commit()

    def seed_one(self, symbol: str, basis=None, offsets=(3, 4, 5)) -> None:
        self.seed_stock(symbol)
        self.seed_master(symbol)
        self.seed_prices(symbol, [day(o) for o in offsets], basis=basis)

    def price_rows(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0]

    def basis_of(self, symbol: str):
        row = self.conn.execute(
            "SELECT basis FROM price_meta WHERE symbol=?", (symbol,)).fetchone()
        return row[0] if row else None


class PlanTests(BaseCase):
    def test_plan_counts_and_estimates(self):
        self.seed_one("AAA", basis=None)
        self.seed_one("BBB", basis="fyers_raw")
        self.seed_one("CCC", basis="mixed_adjusted_then_raw")
        out = R.plan(self.conn)
        self.assertTrue(out["read_only"])
        self.assertEqual(out["universe"], 3)
        self.assertEqual(out["resolved"], 3)
        self.assertEqual(out["unresolved_count"], 0)
        self.assertEqual(out["by_basis"]["legacy_adjusted"], 1)
        self.assertEqual(out["by_basis"]["fyers_raw"], 1)
        self.assertEqual(out["by_basis"]["mixed"], 1)
        self.assertEqual(out["to_rebuild"], 2)
        self.assertGreater(out["estimated_api_calls"], 0)
        self.assertEqual(out["estimated_api_calls"],
                         2 * out["calls_per_symbol"])
        self.assertEqual(out["symbols_sample"], ["AAA", "CCC"])

    def test_plan_respects_limit_and_symbols(self):
        self.seed_one("AAA", basis=None)
        self.seed_one("BBB", basis=None)
        out = R.plan(self.conn, symbols=["BBB"])
        self.assertEqual(out["universe"], 1)
        self.assertEqual(out["to_rebuild"], 1)
        out = R.plan(self.conn, limit=1)
        self.assertEqual(out["universe"], 1)

    def test_plan_counts_symbol_without_price_meta_as_legacy(self):
        # A resolvable symbol with no price_meta row is still on the legacy
        # basis: it must be counted and queued, not silently dropped.
        self.seed_stock("AAA")
        self.seed_master("AAA")
        out = R.plan(self.conn)
        self.assertEqual(out["by_basis"]["legacy_adjusted"], 1)
        self.assertEqual(out["to_rebuild"], 1)
        self.assertEqual(sum(out["by_basis"].values()), out["resolved"])

    def test_plan_flags_unresolved_symbols(self):
        self.seed_one("AAA", basis=None)
        self.seed_stock("ZZZ")  # no master row -> cannot be fetched
        out = R.plan(self.conn)
        self.assertEqual(out["resolved"], 1)
        self.assertEqual(out["unresolved"], ["ZZZ"])


class RunTests(BaseCase):
    def test_dry_run_writes_nothing(self):
        self.seed_one("AAA", basis=None)
        before_rows = self.price_rows()
        client = FakeClient({"NSE:AAA-EQ": {day(3): bar(day(3)),
                                          day(4): bar(day(4)),
                                          day(6): bar(day(6))}})
        out = R.run(self.conn, client, symbols=["AAA"], dry_run=True,
                    progress=False)
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["attempted"], 1)
        self.assertEqual(out["by_status"], {"dry_run": 1})
        self.assertEqual(out["errors"], [])
        self.assertEqual(self.price_rows(), before_rows)
        self.assertIsNone(self.basis_of("AAA"))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM fyers_sync_log").fetchone()[0], 0)

    def test_apply_rebuild_writes_bars_and_raw_basis(self):
        self.seed_stock("AAA")
        self.seed_master("AAA")
        client = FakeClient({"NSE:AAA-EQ": {day(40): bar(day(40), 90.0),
                                          day(41): bar(day(41), 91.0),
                                          day(42): bar(day(42), 92.0)}})
        out = R.run(self.conn, client, symbols=["AAA"], dry_run=False,
                    progress=False)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["written"], 3)
        self.assertEqual(self.price_rows(), 3)
        self.assertEqual(self.basis_of("AAA"), "fyers_raw")
        self.assertEqual(out["basis_after"]["fyers_raw"], 1)
        self.assertEqual(out["elapsed_seconds"] >= 0, True)
        # Second pass over the same symbol must still report, not crash.
        again = R.run(self.conn, client, symbols=["AAA"], dry_run=False,
                      progress=False)
        self.assertIn("ok", again["by_status"])
        self.assertEqual(self.price_rows(), 3)

    def test_apply_keeps_bars_older_than_the_fetched_window(self):
        # A bar older than HISTORY_YEARS survives; the series becomes 'mixed'.
        old = day(365 * 6)
        self.seed_stock("AAA")
        self.seed_master("AAA")
        self.seed_prices("AAA", [old])
        client = FakeClient({"NSE:AAA-EQ": {day(40): bar(day(40)),
                                          day(41): bar(day(41))}})
        out = R.run(self.conn, client, symbols=["AAA"], dry_run=False,
                    progress=False)
        self.assertTrue(out["ok"], out)
        self.assertEqual(self.basis_of("AAA"), "mixed_adjusted_then_raw")
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE symbol='AAA' AND date<?",
            (day(365 * 5),)).fetchone()[0], 1)

    def test_run_refuses_without_token_when_applying(self):
        self.seed_one("AAA", basis=None)
        client = FakeClient({}, token="")
        out = R.run(self.conn, client, symbols=["AAA"], dry_run=False,
                    progress=False)
        self.assertFalse(out["ok"])
        self.assertEqual(out["status"], "blocked_no_token")
        self.assertIn("token", out["error"].lower())
        self.assertEqual(self.price_rows(), 3)

    def test_dry_run_without_token_returns_plan_shape(self):
        self.seed_one("AAA", basis=None)
        out = R.run(self.conn, FakeClient({}, token=""), symbols=["AAA"],
                    dry_run=True, progress=False)
        self.assertEqual(out["status"], "dry_run_no_token")
        self.assertEqual(out["attempted"], 0)
        self.assertIn("to_rebuild", out)
        self.assertEqual(self.price_rows(), 3)

    def test_one_failing_symbol_does_not_abort_the_batch(self):
        self.seed_stock("AAA")
        self.seed_master("AAA")
        self.seed_stock("BBB")
        self.seed_master("BBB")
        client = FakeClient({"NSE:AAA-EQ": {day(3): bar(day(3))}},
                            failing=("NSE:BBB-EQ",))
        out = R.run(self.conn, client, symbols=["AAA", "BBB"], dry_run=False,
                    progress=False)
        self.assertEqual(out["attempted"], 2)
        self.assertEqual(out["by_status"].get("ok"), 1)
        self.assertEqual(out["by_status"].get("error"), 1)
        self.assertEqual(out["errors"], ["BBB"])
        self.assertFalse(out["ok"])

    def test_run_skips_unresolved_symbols(self):
        self.seed_stock("ZZZ")
        out = R.run(self.conn, FakeClient({}), dry_run=False, progress=False)
        self.assertEqual(out["attempted"], 0)
        self.assertEqual(out["unresolved"], ["ZZZ"])
        self.assertFalse(out["ok"])


class ReportTests(BaseCase):
    def test_report_basis_counts(self):
        self.seed_one("AAA", basis=None)
        self.seed_one("BBB", basis="fyers_raw")
        self.seed_one("CCC", basis="mixed_adjusted_then_raw")
        out = R.report(self.conn)
        self.assertTrue(out["read_only"])
        self.assertEqual(out["price_meta_rows"], 3)
        self.assertEqual(out["bases"]["legacy_adjusted"], 1)
        self.assertEqual(out["bases"]["fyers_raw"], 1)
        self.assertEqual(out["bases"]["mixed_adjusted_then_raw"], 1)
        self.assertEqual(out["by_basis"]["mixed"], 1)
        self.assertEqual(out["mixed_sample"], ["CCC"])
        self.assertEqual(out["null_basis_sample"], ["AAA"])
        self.assertEqual(out["max_price_date"], day(3))

    def test_verify_after_handles_empty_list(self):
        out = R.verify_after(self.conn, FakeClient({}), [])
        self.assertEqual(out["checked"], 0)
        self.assertEqual(out["verdicts"], {})
        self.assertEqual(out["details"], [])

    def test_verify_after_matches_stored_bars(self):
        self.seed_one("AAA", basis="fyers_raw", offsets=(3, 4, 5))
        bars = {day(o): bar(day(o)) for o in (3, 4, 5, 6)}
        out = R.verify_after(self.conn, FakeClient({"NSE:AAA-EQ": bars}),
                             ["AAA"], limit=5, days=10)
        self.assertEqual(out["checked"], 1)
        self.assertEqual(out["verdicts"], {"match": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
