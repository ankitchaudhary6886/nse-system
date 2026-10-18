"""Offline tests for the Fyers data integration.

Everything here runs without network access or a broker token: HTTP is faked
at the session boundary, and the database is an in-memory copy of the real
schema. Run with:

    python -m unittest test_fyers_integration -v
"""
import datetime as dt
import json
import os
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

import db
import fyers_client as fc
import ingest_fyers as ing


class FakeResponse:
    def __init__(self, payload=None, status_code=200, text=None):
        self.payload = payload if payload is not None else {}
        self.status_code = status_code
        self.text = text if text is not None else json.dumps(self.payload)

    def json(self):
        if isinstance(self.payload, str):
            raise ValueError("not json")
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Routes requests to a handler; records every call for assertions."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    @staticmethod
    def _wrap(value):
        return value if isinstance(value, FakeResponse) else FakeResponse(value)

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(("GET", url, params, headers))
        return self._wrap(self.handler("GET", url, params))

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", url, json, headers))
        return self._wrap(self.handler("POST", url, json))


def make_client(handler, token="test-token", **kwargs):
    return fc.FyersClient(app_id="APP-100", access_token=token,
                          session=FakeSession(handler), **kwargs)


def candle_epoch(date_str):
    """Epoch for 00:00 IST on a date (what Fyers sends for a daily bar)."""
    moment = dt.datetime.fromisoformat(date_str).replace(tzinfo=fc.IST)
    return int(moment.timestamp())


def sm(items):
    return {"s": "ok", "code": 200, "items": items}


class AuthTests(unittest.TestCase):
    def test_app_id_hash_is_sha256_of_app_and_secret(self):
        digest = fc.app_id_hash("ABC-100", "secret")
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, fc.app_id_hash("ABC-100", "secret"))
        self.assertNotEqual(digest, fc.app_id_hash("ABC-100", "secret2"))

    def test_auth_url_contains_required_oauth_params(self):
        url = fc.build_auth_url(app_id="APP-100",
                                redirect_uri="https://example.test/cb",
                                state="s1")
        self.assertIn("/generate-authcode?", url)
        self.assertIn("client_id=APP-100", url)
        self.assertIn("response_type=code", url)
        self.assertIn("state=s1", url)
        self.assertIn("redirect_uri=https%3A%2F%2Fexample.test%2Fcb", url)

    def test_extract_auth_code_from_url_or_bare_value(self):
        url = "https://fyers.in/?auth_code=abc123&state=s1"
        self.assertEqual(fc.extract_auth_code(url), "abc123")
        self.assertEqual(fc.extract_auth_code("abc123"), "abc123")
        with self.assertRaises(fc.FyersAuthError):
            fc.extract_auth_code("")

    def test_token_store_roundtrip_and_expiry(self):
        path = Path("data") / f"test_token_{self._testMethodName}.json"
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        store = fc.TokenStore(path)
        self.assertIsNone(store.access_token())
        store.save("tok-1", "refresh-1")
        self.assertEqual(store.access_token(), "tok-1")
        data = store.load()
        expiry = dt.datetime.fromisoformat(data["expires_at"])
        self.assertEqual(expiry.tzinfo, fc.IST)
        self.assertEqual((expiry.hour, expiry.minute), (5, 55))
        self.assertFalse(store.expired())
        # force an expiry in the past
        data["expires_at"] = (dt.datetime.now(fc.IST)
                              - dt.timedelta(minutes=1)).isoformat()
        store.path.write_text(json.dumps(data))
        self.assertTrue(store.expired())
        store.clear()
        self.assertIsNone(store.access_token())

    def test_expiry_is_next_0555_ist(self):
        now = dt.datetime(2026, 10, 18, 20, 0, tzinfo=fc.IST)
        self.assertEqual(fc.next_token_expiry(now),
                         dt.datetime(2026, 10, 19, 5, 55, tzinfo=fc.IST))
        early = dt.datetime(2026, 10, 18, 3, 0, tzinfo=fc.IST)
        self.assertEqual(fc.next_token_expiry(early),
                         dt.datetime(2026, 10, 18, 5, 55, tzinfo=fc.IST))


class SymbolTests(unittest.TestCase):
    def test_to_fyers_symbol(self):
        self.assertEqual(fc.to_fyers_symbol("sbin"), "NSE:SBIN-EQ")
        self.assertEqual(fc.to_fyers_symbol("NSE:SBIN-EQ"), "NSE:SBIN-EQ")
        self.assertEqual(fc.to_fyers_symbol("NIFTY50"), "NSE:NIFTY50-INDEX")
        self.assertEqual(fc.to_fyers_symbol("BAJAJ-AUTO"), "NSE:BAJAJ-AUTO-EQ")

    def test_from_fyers_symbol(self):
        self.assertEqual(fc.from_fyers_symbol("NSE:SBIN-EQ"), "SBIN")
        self.assertEqual(fc.from_fyers_symbol("NSE:NIFTY50-INDEX"),
                         "NIFTY50-INDEX")

    def test_parse_symbol_master_detects_columns_by_content(self):
        line = ("101000000016921,20 MICRONS LTD,0,1,0.01,INE144J01027,"
                "0915-1530|1815-1915:,2026-10-16,,NSE:20MICRONS-EQ,10,10,"
                "16921,20MICRONS,16921,-1.0,XX,101000000016921,None,1,2.0")
        rows = fc.parse_symbol_master(line)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["symbol"], "20MICRONS")
        self.assertEqual(row["ticker"], "NSE:20MICRONS-EQ")
        self.assertEqual(row["isin"], "INE144J01027")
        self.assertEqual(row["source_updated"], "2026-10-16")
        self.assertEqual(row["fy_token"], 101000000016921)

    def test_parse_symbol_master_skips_non_equity_rows(self):
        self.assertEqual(fc.parse_symbol_master("garbage,line,without,ticker"), [])


class HistoryTests(unittest.TestCase):
    def test_history_normalizes_candles_to_project_dates(self):
        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-15"), 100, 105, 99, 104, 10000],
                [candle_epoch("2026-10-16"), 104, 108, 103, 107, 12000],
            ]}

        client = make_client(handler)
        rows = fc._fmt_candles(client.history_candles("SBIN"))
        self.assertEqual([r["date"] for r in rows],
                         ["2026-10-15", "2026-10-16"])
        self.assertEqual(rows[0]["close"], 104.0)
        self.assertEqual(rows[1]["volume"], 12000.0)

    def test_history_request_uses_expected_params(self):
        seen = {}

        def handler(method, url, params):
            seen.update(params or {})
            return {"s": "ok", "candles": []}

        client = make_client(handler)
        client.history_candles("SBIN", range_from="2026-10-01",
                               range_to="2026-10-16")
        self.assertEqual(seen["symbol"], "NSE:SBIN-EQ")
        self.assertEqual(seen["resolution"], "1D")
        self.assertEqual(seen["date_format"], "1")
        self.assertEqual(seen["cont_flag"], "1")

    def test_history_range_chunks_long_ranges(self):
        calls = []

        def handler(method, url, params):
            calls.append(params["range_from"])
            return {"s": "ok", "candles": []}

        client = make_client(handler)
        client.history_range("SBIN", "2026-08-01", "2026-10-16", chunk_days=30)
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(calls[0], "2026-08-01")

    def test_bad_candles_are_dropped_not_raised(self):
        def handler(method, url, params):
            return {"s": "ok", "candles": [
                ["not-an-epoch", 1, 2, 1, 2, 10],
                [candle_epoch("2026-10-15")],  # too short
                [99999999999999, 1, 2, 1, 2, 10],  # out-of-range epoch
            ]}

        client = make_client(handler)
        self.assertEqual(fc._fmt_candles(client.history_candles("SBIN")), [])


class ErrorTests(unittest.TestCase):
    def test_invalid_token_raises_auth_error(self):
        def handler(method, url, params):
            return FakeResponse({"s": "error", "code": -16,
                                 "message": "Token is Invalid or Expired"},
                                status_code=401)

        client = make_client(handler)
        with self.assertRaises(fc.FyersAuthError) as ctx:
            client.quotes(["SBIN"])
        self.assertEqual(ctx.exception.code, -16)
        self.assertIn("login", str(ctx.exception).lower())

    def test_broker_error_envelope_raises_fyers_error(self):
        def handler(method, url, params):
            return FakeResponse({"s": "error", "code": -437,
                                 "message": "invalid auth code"},
                                status_code=400)

        client = make_client(handler)
        with self.assertRaises(fc.FyersError) as ctx:
            client.history_candles("SBIN")
        self.assertEqual(ctx.exception.code, -437)

    def test_missing_token_fails_before_network(self):
        def handler(method, url, params):  # pragma: no cover - must not run
            raise AssertionError("network call without a token")

        absent = Path("data") / "test_token_absent.json"
        with mock.patch.dict(os.environ, {"FYERS_ACCESS_TOKEN": ""}):
            client = fc.FyersClient(
                app_id="APP-100", access_token="",
                token_store=fc.TokenStore(absent),
                session=FakeSession(handler))
            with self.assertRaises(fc.FyersAuthError):
                client.history_candles("SBIN")


class QuoteTests(unittest.TestCase):
    def test_quotes_normalized_and_raw_preserved(self):
        def handler(method, url, params):
            return {"s": "ok", "d": [{
                "n": "NSE:SBIN-EQ", "s": "ok",
                "v": {"lp": 512.5, "prev_close_price": 510.0, "ch": 2.5,
                      "chp": 0.49, "bid": 512.4, "ask": 512.6,
                      "vol": 123456, "o": 511.0, "h": 514.0, "l": 509.0,
                      "short_name": "SBIN"}}]}

        client = make_client(handler)
        quotes = client.quotes(["SBIN"])
        self.assertIn("SBIN", quotes)
        quote = quotes["SBIN"]
        self.assertEqual(quote["ltp"], 512.5)
        self.assertEqual(quote["prev_close"], 510.0)
        self.assertAlmostEqual(quote["spread"], 0.2, places=4)
        self.assertEqual(quote["volume"], 123456)
        self.assertEqual(quote["raw"]["short_name"], "SBIN")

    def test_quotes_chunked_at_50_symbols(self):
        batches = []

        def handler(method, url, params):
            batches.append(len(params["symbols"].split(",")))
            return {"s": "ok", "d": []}

        client = make_client(handler)
        client.quotes([f"SYM{i}" for i in range(120)])
        self.assertEqual(batches, [50, 50, 20])

    def test_quotes_keyed_by_requested_symbol_for_index(self):
        def handler(method, url, params):
            return {"s": "ok", "d": [{
                "n": "NSE:NIFTY50-INDEX", "s": "ok",
                "v": {"lp": 23146.15, "chp": 0.65}}]}

        client = make_client(handler)
        quotes = client.quotes(["NIFTY50"])
        self.assertIn("NIFTY50", quotes)
        self.assertNotIn("NIFTY50-INDEX", quotes)
        self.assertEqual(quotes["NIFTY50"]["symbol"], "NIFTY50")


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def seed_prices(conn, symbol, closes):
    for date, close in closes:
        conn.execute(
            "INSERT OR REPLACE INTO prices_daily VALUES (?,?,?,?,?,?,?)",
            (symbol, date, close, close, close, close, 1000))
    conn.execute(
        "INSERT OR REPLACE INTO price_meta "
        "(symbol,last_date,rows,updated_at) VALUES (?,?,?,?)",
        (symbol, closes[-1][0], len(closes), "2026-10-10T00:00:00"))
    conn.commit()


class ResolutionTests(unittest.TestCase):
    def _conn(self):
        conn = memory_db()
        rows = [
            ("SBIN", "NSE:SBIN-EQ", "STATE BANK", "INE062A01020"),
            ("BAJAJ-AUTO", "NSE:BAJAJ-AUTO-EQ", "BAJAJ AUTO", "INE917I01010"),
            ("BAGMANE-RR", "NSE:BAGMANE-RR", "BAGMANE REIT", "INE0C3801015"),
            ("ACCENTMIC-SM", "NSE:ACCENTMIC-SM", "ACCENT", "INE0Q5D01015"),
            ("HEGAM", "NSE:HEGAM-EQ", "HEG ADVANCED", "INE545A01024"),
        ]
        conn.executemany(
            "INSERT INTO fyers_symbol_master "
            "(symbol,ticker,name,isin,fy_token,lot_size,tick_size,exchange,"
            "segment,source_updated,imported_at,raw) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(s, t, n, i, 1, 1, 0.05, "NSE", "CM", "2026-10-16", "now", "")
             for s, t, n, i in rows])
        conn.execute("CREATE TABLE scanx_fundamentals_snapshots "
                     "(symbol TEXT, isin TEXT)")
        conn.execute("INSERT INTO scanx_fundamentals_snapshots VALUES (?,?)",
                     ("HEG", "INE545A01024"))
        conn.commit()
        return conn

    def test_resolution_methods(self):
        conn = self._conn()
        result = ing.resolve_symbols(
            conn, ["SBIN", "BAJAJ_AUTO", "BAGMANE.RR", "HEG", "ZZZ"])
        resolved = result["resolved"]
        self.assertEqual(resolved["SBIN"], "NSE:SBIN-EQ")
        self.assertEqual(resolved["BAJAJ_AUTO"], "NSE:BAJAJ-AUTO-EQ")
        self.assertEqual(resolved["BAGMANE.RR"], "NSE:BAGMANE-RR")
        self.assertEqual(resolved["HEG"], "NSE:HEGAM-EQ")
        self.assertEqual(result["unresolved"], ["ZZZ"])
        self.assertEqual(result["by_method"]["isin"], 1)

    def test_resolution_never_guesses_unknown_ticker(self):
        conn = self._conn()
        result = ing.resolve_symbols(conn, ["NOTAREALSYMBOL"])
        self.assertEqual(result["resolved"], {})
        self.assertEqual(result["unresolved"], ["NOTAREALSYMBOL"])


class IngestTests(unittest.TestCase):
    def test_append_writes_only_new_dates_and_updates_meta(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-09", 100.0),
                                   ("2026-10-10", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-08"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-09"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-10"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-12"), 101, 102, 100, 101, 1100],
                [candle_epoch("2026-10-13"), 101, 103, 101, 102, 1200],
            ]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           include_today=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["written"], 2)
        rows = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol='SBIN' "
            "ORDER BY date").fetchall()
        self.assertEqual([r[0] for r in rows],
                         ["2026-10-09", "2026-10-10", "2026-10-12", "2026-10-13"])
        meta = conn.execute(
            "SELECT last_date, rows FROM price_meta WHERE symbol='SBIN'").fetchone()
        self.assertEqual(meta[0], "2026-10-13")
        self.assertEqual(meta[1], 4)

    def test_no_overlap_blocks_append(self):
        """Without shared dates the price basis cannot be proven -> no append."""
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-01-02", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-12"), 101, 102, 100, 101, 1000]]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           include_today=True)
        self.assertEqual(result["status"], "no_overlap")
        self.assertEqual(result["written"], 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0], 1)

    def test_seam_mismatch_blocks_append(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-09", 100.0),
                                   ("2026-10-10", 100.0)])

        def handler(method, url, params):
            # broker is raw, stored history was adjusted: 10% discontinuity
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-09"), 90, 90, 90, 90, 1000],
                [candle_epoch("2026-10-10"), 90, 90, 90, 90, 1000],
                [candle_epoch("2026-10-12"), 90, 91, 89, 90, 1000],
            ]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           include_today=True)
        self.assertEqual(result["status"], "seam_mismatch")
        self.assertEqual(result["written"], 0)
        rows = conn.execute(
            "SELECT date FROM prices_daily WHERE symbol='SBIN'").fetchall()
        self.assertEqual(len(rows), 2)

    def test_rebuild_backs_up_replaces_window_and_keeps_older_rows(self):
        conn = memory_db()
        # two rows older than the 5-year fetch window, two inside it
        seed_prices(conn, "SBIN", [("2019-01-01", 40.0),
                                   ("2019-01-02", 41.0),
                                   ("2026-10-09", 100.0),
                                   ("2026-10-10", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-12"), 50, 51, 49, 50, 1000],
                [candle_epoch("2026-10-13"), 50, 52, 49, 51, 1000],
            ]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           mode="rebuild",
                                           include_today=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["written"], 2)
        rows = conn.execute(
            "SELECT date, close FROM prices_daily WHERE symbol='SBIN' "
            "ORDER BY date").fetchall()
        # pre-window history is kept; only the fetched window is replaced
        self.assertEqual([r[0] for r in rows],
                         ["2019-01-01", "2019-01-02", "2026-10-09",
                          "2026-10-10", "2026-10-12", "2026-10-13"])
        self.assertEqual(rows[0][1], 40.0)
        self.assertEqual(result["basis"], "mixed_adjusted_then_raw")
        backup = Path(result["backup"])
        self.assertTrue(backup.exists())
        text = backup.read_text(encoding="utf-8")
        self.assertIn("2026-10-10", text)
        backup.unlink()

    def test_rebuild_refuses_a_shrunken_fetch(self):
        conn = memory_db()
        seed_prices(conn, "SBIN",
                    [(f"2026-09-{day:02d}", 100.0) for day in range(1, 11)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-12"), 100, 101, 99, 100, 1000],
                [candle_epoch("2026-10-13"), 100, 101, 99, 100, 1000],
            ]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           mode="rebuild",
                                           include_today=True)
        self.assertEqual(result["status"], "rebuild_shrunk")
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily WHERE symbol='SBIN'"
        ).fetchone()[0], 10)

    def test_first_new_bar_jump_blocks_append(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-09", 100.0),
                                   ("2026-10-10", 100.0)])

        def handler(method, url, params):
            # overlap matches (basis provable) but the next bar is a 30% gap:
            # the signature of a corporate action after the last stored bar
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-09"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-10"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-12"), 130, 132, 128, 130, 1000],
            ]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           include_today=True)
        self.assertEqual(result["status"], "seam_gap_suspect")
        self.assertEqual(result["written"], 0)
        self.assertAlmostEqual(result["first_new_gap_pct"], 30.0, places=1)

    def test_invalid_bars_are_skipped(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-10", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-10"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-12"), 100, 90, 101, 100, 1000],  # h<l
                [candle_epoch("2026-10-13"), 100, 101, 99, 400, 1000],  # +300%
                [candle_epoch("2026-10-14"), 100, 102, 99, 101, 1000],
            ]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           include_today=True)
        self.assertEqual(result["written"], 1)
        self.assertEqual(result["skipped_invalid"], 2)

    def test_dry_run_writes_nothing(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-10", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-10"), 100, 100, 100, 100, 1000],
                [candle_epoch("2026-10-12"), 100, 101, 99, 100, 1000]]}

        client = make_client(handler)
        result = ing.ingest_symbol_history(conn, client, "SBIN",
                                           dry_run=True, include_today=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["written"], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM fyers_sync_log").fetchone()[0], 0)

    def test_verify_flags_adjustment_mismatch(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-10", 100.0),
                                   ("2026-10-12", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-10"), 90, 90, 90, 90, 1000],
                [candle_epoch("2026-10-12"), 90, 90, 90, 90, 1000],
            ]}

        client = make_client(handler)
        report = ing.verify_symbol(conn, client, "SBIN", days=10)
        self.assertEqual(report["verdict"], "adjustment_mismatch")
        self.assertAlmostEqual(report["factor"], 0.9, places=4)

    def test_verify_match_when_prices_agree(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-10", 100.0)])

        def handler(method, url, params):
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-10"), 100, 100, 100, 100, 1000]]}

        client = make_client(handler)
        report = ing.verify_symbol(conn, client, "SBIN", days=10)
        self.assertEqual(report["verdict"], "match")
        self.assertEqual(report["new_dates"], 0)

    def test_master_refresh_upserts(self):
        conn = memory_db()
        line = ("101000000016921,20 MICRONS LTD,0,1,0.01,INE144J01027,"
                "0915-1530|1815-1915:,2026-10-16,,NSE:20MICRONS-EQ,10,10,"
                "16921,20MICRONS,16921,-1.0,XX,101000000016921,None,1,2.0")

        def handler(method, url, params):
            return FakeResponse(text=line)

        client = make_client(handler)
        stats = ing.refresh_symbol_master(conn, client)
        self.assertEqual(stats["parsed"], 1)
        row = conn.execute(
            "SELECT ticker, isin FROM fyers_symbol_master "
            "WHERE symbol='20MICRONS'").fetchone()
        self.assertEqual(row, ("NSE:20MICRONS-EQ", "INE144J01027"))
        # second refresh is an update, not a new row
        stats2 = ing.refresh_symbol_master(conn, client)
        self.assertEqual(stats2["new"], 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM fyers_symbol_master").fetchone()[0], 1)

    def test_quotes_snapshot_persists_raw(self):
        conn = memory_db()

        def handler(method, url, params):
            return {"s": "ok", "d": [{
                "n": "NSE:SBIN-EQ", "s": "ok",
                "v": {"lp": 512.5, "chp": 0.5, "vol": 1000}}]}

        client = make_client(handler)
        result = ing.snapshot_quotes(conn, client, ["SBIN"])
        self.assertEqual(result["written"], 1)
        row = conn.execute(
            "SELECT symbol, ltp, raw_json FROM fyers_quotes").fetchone()
        self.assertEqual(row[0], "SBIN")
        self.assertEqual(row[1], 512.5)
        self.assertIn("lp", row[2])

    def test_sync_status_reports_freshness(self):
        conn = memory_db()
        seed_prices(conn, "SBIN", [("2026-10-10", 100.0)])
        client = fc.FyersClient(app_id="APP-100", access_token="",
                                token_store=fc.TokenStore(
                                    Path("data") / "test_token_absent.json"))
        with mock.patch.dict(os.environ, {"FYERS_ACCESS_TOKEN": ""}):
            report = ing.status(conn, client)
        self.assertEqual(report["prices_latest_date"], "2026-10-10")
        self.assertIsInstance(report["prices_stale_days"], int)
        self.assertFalse(report["token_valid"])


class FakeClock:
    """Monotonic clock whose sleep actually advances time."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(seconds, 0.001)


class RateLimitTests(unittest.TestCase):
    def test_per_minute_cap_forces_a_wait(self):
        clock = FakeClock()
        limiter = fc.RateLimiter(max_per_sec=2, max_per_min=3,
                                 sleep=clock.sleep, clock=clock)
        for _ in range(4):
            limiter.acquire()
        self.assertGreaterEqual(clock.now, 59.0)

    def test_no_progress_clock_raises_instead_of_spinning(self):
        limiter = fc.RateLimiter(max_per_sec=1, max_per_min=10,
                                 sleep=lambda seconds: None,
                                 clock=lambda: 0.0)
        limiter.acquire()
        with self.assertRaises(fc.FyersRateLimitError):
            limiter.acquire()


class RetryTests(unittest.TestCase):
    def test_5xx_is_retried(self):
        calls = {"n": 0}

        def handler(method, url, params):
            calls["n"] += 1
            if calls["n"] < 3:
                return FakeResponse({"s": "error", "message": "bad gateway"},
                                    status_code=502)
            return {"s": "ok", "candles": [
                [candle_epoch("2026-10-15"), 100, 101, 99, 100, 1000]]}

        client = make_client(handler, sleep=lambda seconds: None)
        rows = client.history_candles("SBIN")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(len(rows), 1)


class ExchangeTests(unittest.TestCase):
    def test_exchange_posts_app_hash_without_authorization_and_stores_token(self):
        calls = []

        def handler(method, url, payload):
            calls.append((method, url, payload))
            if "/validate-authcode" in url:
                return {"s": "ok", "code": 200,
                        "access_token": "tok-xyz", "refresh_token": "ref-1"}
            if url.endswith("/profile"):
                return {"s": "ok", "data": {"display_name": "Tester"}}
            raise AssertionError(url)

        session = FakeSession(handler)
        client = fc.FyersClient(app_id="APP-100", access_token="",
                                session=session)
        store_path = Path("data") / "test_token_exchange.json"
        self.addCleanup(lambda: store_path.unlink() if store_path.exists() else None)
        expected_hash = fc.app_id_hash("APP-100", "sec")
        with mock.patch.dict(os.environ, {"FYERS_APP_ID": "APP-100",
                                          "FYERS_SECRET_ID": "sec",
                                          "FYERS_ACCESS_TOKEN": ""}):
            code = fc._cmd_exchange("my-code", client=client,
                                    store=fc.TokenStore(store_path))
        self.assertEqual(code, 0)
        post = next(c for c in session.calls if c[0] == "POST")
        _, post_url, post_body, post_headers = post
        self.assertIn("/validate-authcode", post_url)
        self.assertEqual(post_body["grant_type"], "authorization_code")
        self.assertEqual(post_body["appIdHash"], expected_hash)
        self.assertEqual(post_body["code"], "my-code")
        # the code exchange must not send an Authorization header
        self.assertFalse(any(k.lower() == "authorization"
                             for k in (post_headers or {})))
        profile = next(c for c in session.calls if c[1].endswith("/profile"))
        self.assertEqual(profile[3]["Authorization"], "APP-100:tok-xyz")
        saved = fc.TokenStore(store_path).load()
        self.assertEqual(saved["access_token"], "tok-xyz")

    def test_exchange_rejects_auth_code_without_network_transaction(self):
        def handler(method, url, payload):
            return FakeResponse({"s": "error", "code": -437,
                                 "message": "invalid auth code"},
                                status_code=400)

        client = fc.FyersClient(app_id="APP-100", access_token="",
                                session=FakeSession(handler))
        with mock.patch.dict(os.environ, {"FYERS_APP_ID": "APP-100",
                                          "FYERS_SECRET_ID": "sec"}):
            code = fc._cmd_exchange("used-code", client=client,
                                    store=fc.TokenStore(
                                        Path("data") / "unused_token.json"))
        self.assertEqual(code, 2)


class SyncEntrypointTests(unittest.TestCase):
    def test_no_resolved_symbols_is_not_ok(self):
        conn = memory_db()
        conn.execute(
            "INSERT INTO fyers_symbol_master (symbol,ticker,imported_at) "
            "VALUES ('SBIN','NSE:SBIN-EQ',?)",
            (ing.now_ist().isoformat(timespec="seconds"),))
        conn.commit()

        def handler(method, url, params):
            raise AssertionError("no network expected when universe is empty")

        client = make_client(handler)
        result = ing.sync_recent(conn=conn, client=client)
        self.assertFalse(result["ok"])
        self.assertEqual(result["resolved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
