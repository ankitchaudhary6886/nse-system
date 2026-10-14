"""Offline tests for the NSE archive feed and its ingestion into prices_daily.

Run it exactly like the other repo tests:

    cd C:\\Users\\Ankit\\Desktop\\nse_system
    .\\env\\Scripts\\python.exe test_nse_archives.py

NO NETWORK IS USED.  NSE is blocked, throttled or simply having a bad day often
enough that a test which needs it would be a test nobody trusts.  Instead:

  * the CSV bodies below are REAL header layouts captured from NSE's archives
    (legacy ``cm...bhav.csv``, UDiFF ``BhavCopy_NSE_CM_...`` and
    ``sec_bhavdata_full``), and
  * downloads are replaced by an in-memory opener, and
  * the database is a throw-away SQLite file in the OS temp folder, so the
    production ``data/app.db`` is never touched.

What is covered: every parse path, the format switch on 2024-07-08, honest
failure when a download breaks, provider registration, the golden-rule-7
behaviour when a third-party package is missing, the upsert, and idempotency
(re-running does not duplicate rows).
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date

# Make the repo importable when this file is run directly / from anywhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nse_archive_ingest as ingest                                 # noqa: E402
from data_sources.adapters import (                                 # noqa: E402
    jugaad,
    nse_archives,
    nseindiaapi,
    nselib_src,
    nsemine_src,
    pnsea_src,
)
from data_sources.core import SourceRegistry                        # noqa: E402


# --------------------------------------------------------------------- fixtures
# Real UDiFF column list (checked against NSE's published file on 2026-10-13).
UDIFF_HEADER = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
    "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,"
    "ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,"
    "ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,"
    "Rmks,Rsvd01,Rsvd02,Rsvd03,Rsvd04"
)

# Legacy bhavcopy header.  NSE pads some cells with spaces and leaves a trailing
# comma; both quirks are kept here on purpose.
LEGACY_HEADER = (
    " SYMBOL, SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,"
    "TIMESTAMP,TOTALTRADES,ISIN,"
)

# The plain-CSV delivery file, exactly as NSE spaces it.
SECBHAV_HEADER = (
    "SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, "
    "LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, "
    "NO_OF_TRADES, DELIV_QTY, DELIV_PER"
)


def _rows_csv(header: str, rows) -> str:
    """Render dict rows against an exact header, so field order cannot drift."""
    names = [name.strip() for name in header.split(",")]
    lines = [header]
    for row in rows:
        lines.append(",".join(str(row.get(name, "")) for name in names))
    return "\n".join(lines) + "\n"


def udiff_fixture() -> str:
    """One session: two real equities plus three rows that must be skipped."""
    def row(symbol, series, instr_type, open_, high, low, close, volume,
            day="2026-10-13"):
        return {
            "TradDt": day, "BizDt": day, "Sgmt": "CM", "Src": "NSE",
            "FinInstrmTp": instr_type, "FinInstrmId": "19078",
            "ISIN": "INE009A01021", "TckrSymb": symbol, "SctySrs": series,
            "FinInstrmNm": f"{symbol} LIMITED", "OpnPric": open_,
            "HghPric": high, "LwPric": low, "ClsPric": close,
            "LastPric": close, "PrvsClsgPric": open_, "UndrlygPric": close,
            "TtlTradgVol": volume, "TtlTrfVal": "1234.5",
            "TtlNbOfTxsExctd": "1000", "SsnId": "F1", "NewBrdLotQty": "1",
        }

    return _rows_csv(UDIFF_HEADER, [
        row("INFY", "EQ", "STK", 1500.00, 1520.50, 1495.25, 1512.75, 1000000),
        row("IDEA", "BE", "STK", 10.10, 10.60, 10.00, 10.45, 250000),
        # gold bond: real row, wrong series -> skipped
        row("SGBJUN28", "GB", "STK", 14650.01, 14700.00, 14650.01, 14698.75, 184),
        # right series but not a stock instrument -> skipped
        row("SOMEDEBT", "EQ", "IDF", 100.0, 101.0, 99.0, 100.5, 5000),
        # placeholder row with a padded ticker -> skipped
        row(" DUMMY$", "EQ", "STK", 1.0, 1.0, 1.0, 1.0, 1),
    ])


def legacy_fixture() -> str:
    """Legacy-format rows, including one with a blank TIMESTAMP."""
    lines = [
        LEGACY_HEADER,
        "RELIANCE,EQ,2500.00,2550.00,2490.00,2540.00,2539.00,2480.00,"
        "5000000,12500000000,02-JAN-2023,120000,INE002A01018,",
        " TCS ,EQ,3300.00,3350.00,3280.00,3345.50,3345.00,3290.00,"
        "1200000,4000000000,02-JAN-2023,90000,INE467B01029,",
        # blank timestamp: the caller must supply the date from the URL
        "WIPRO,EQ,400.00,405.00,398.00,402.50,402.00,399.00,"
        "800000,320000000,,50000,INE075A01022,",
        # a bond series: must be skipped
        "1018GS2026,GS,118,118,118,118,118,116,648,76464,02-JAN-2023,4,"
        "IN0020010081,",
    ]
    return "\n".join(lines) + "\n"


def secbhav_fixture() -> str:
    """sec_bhavdata_full: every row carries its own date in DATE1."""
    return "\n".join([
        SECBHAV_HEADER,
        "20MICRONS,EQ,13-Oct-2026,198.59,199.32,201.49,193.10,199.98,197.19,"
        "195.68,94682,185.27,2816,41489,43.82",
        "RELIANCE,EQ,13-Oct-2026,2500.00,2510.00,2525.00,2495.00,2520.00,"
        "2519.50,2505.00,7000000,175000.00,150000,3500000,50.00",
    ]) + "\n"


def monthly_fixture() -> str:
    """Legacy monthly file: several sessions inside ONE download."""
    return "\n".join([
        LEGACY_HEADER,
        "RELIANCE,EQ,2400.00,2450.00,2390.00,2440.00,2439.00,2380.00,"
        "4000000,9000000000,03-JAN-2023,100000,INE002A01018,",
        "RELIANCE,EQ,2440.00,2470.00,2425.00,2465.00,2464.00,2440.00,"
        "3500000,8000000000,04-JAN-2023,95000,INE002A01018,",
    ]) + "\n"


def canonical(symbol, day, open_, high, low, close, volume):
    """A record exactly as the canonical bhavcopy shape defines it."""
    return {"symbol": symbol, "date": day, "open": open_, "high": high,
            "low": low, "close": close, "volume": volume}


# ------------------------------------------------------------ parsing the files

class BhavcopyParsingTests(unittest.TestCase):
    def test_udiff_daily_bhavcopy_parses_equity_rows_only(self):
        rows = nse_archives.parse_bhavcopy_text(udiff_fixture())
        self.assertEqual([row["symbol"] for row in rows], ["IDEA", "INFY"])
        infy = {row["symbol"]: row for row in rows}["INFY"]
        self.assertEqual(infy["date"], "2026-10-13")
        self.assertEqual(infy["open"], 1500.00)
        self.assertEqual(infy["high"], 1520.50)
        self.assertEqual(infy["low"], 1495.25)
        self.assertEqual(infy["close"], 1512.75)
        self.assertEqual(infy["volume"], 1000000.0)

    def test_legacy_daily_bhavcopy_tolerates_padded_columns(self):
        rows = nse_archives.parse_bhavcopy_text(
            legacy_fixture(), default_date="2023-01-02")
        by_symbol = {row["symbol"]: row for row in rows}
        self.assertEqual(set(by_symbol), {"RELIANCE", "TCS", "WIPRO"})
        self.assertEqual(by_symbol["RELIANCE"]["close"], 2540.00)
        self.assertEqual(by_symbol["TCS"]["volume"], 1200000.0)
        # the padded ticker was cleaned, and the blank TIMESTAMP fell back
        self.assertEqual(by_symbol["WIPRO"]["date"], "2023-01-02")
        self.assertEqual(by_symbol["WIPRO"]["close"], 402.50)

    def test_sec_bhavdata_full_uses_the_date_inside_each_row(self):
        rows = nse_archives.parse_bhavcopy_text(secbhav_fixture())
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["date"] for row in rows}, {"2026-10-13"})
        self.assertEqual(rows[0]["symbol"], "20MICRONS")
        self.assertEqual(rows[0]["volume"], 94682.0)

    def test_monthly_bhavcopy_carries_every_session_of_the_month(self):
        rows = nse_archives.parse_bhavcopy_text(monthly_fixture())
        self.assertEqual([row["date"] for row in rows],
                         ["2023-01-03", "2023-01-04"])

    def test_html_error_page_yields_no_rows_instead_of_raising(self):
        for junk in ("", "   ", "<html><body>Access Denied</body></html>",
                     "not,a,bhavcopy,file\n1,2,3,4"):
            self.assertEqual(nse_archives.parse_bhavcopy_text(junk), [])

    def test_bad_numbers_and_missing_prices_are_skipped_never_guessed(self):
        text = "\n".join([
            LEGACY_HEADER,
            "GOODCO,EQ,10.00,11.00,9.50,10.50,10.40,10.00,1000,10000,"
            "02-JAN-2023,10,INE000000001,",
            "NOCLOSE,EQ,10.00,11.00,9.50,-,10.40,10.00,1000,10000,"
            "02-JAN-2023,10,INE000000002,",
            "BADDATE,EQ,10.00,11.00,9.50,10.50,10.40,10.00,1000,10000,"
            "99-XXX-2023,10,INE000000003,",
        ]) + "\n"
        rows = nse_archives.parse_bhavcopy_text(text)
        self.assertEqual([row["symbol"] for row in rows], ["GOODCO"])

    def test_duplicate_symbol_and_date_keeps_the_last_row(self):
        text = "\n".join([
            LEGACY_HEADER,
            "DUPE,EQ,10.00,11.00,9.50,10.50,10.40,10.00,1000,10000,"
            "02-JAN-2023,10,INE000000001,",
            "DUPE,EQ,10.00,11.00,9.50,10.75,10.70,10.00,2000,20000,"
            "02-JAN-2023,20,INE000000001,",
        ]) + "\n"
        rows = nse_archives.parse_bhavcopy_text(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["close"], 10.75)
        self.assertEqual(rows[0]["volume"], 2000.0)


class DateAndUrlTests(unittest.TestCase):
    def test_urls_switch_format_on_the_2024_07_08_changeover(self):
        legacy = nse_archives.daily_bhavcopy_urls(date(2024, 7, 5))
        modern = nse_archives.daily_bhavcopy_urls(date(2024, 7, 8))
        self.assertTrue(any("cm05JUL2024bhav.csv.zip" in url for url in legacy))
        self.assertFalse(any("BhavCopy_NSE_CM" in url for url in legacy))
        self.assertTrue(any("BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv.zip" in url
                            for url in modern))
        self.assertFalse(any("cm08JUL2024bhav" in url for url in modern))
        # the plain-CSV delivery file is always the last resort
        self.assertTrue(legacy[-1].endswith("sec_bhavdata_full_05072024.csv"))

    def test_monthly_url_uses_the_month_abbreviation(self):
        urls = nse_archives.monthly_bhavcopy_urls(2023, 1)
        self.assertTrue(all(url.endswith("/2023/JAN/cmJAN2023bhav.csv.zip")
                            for url in urls))

    def test_nse_date_spellings_are_all_understood(self):
        for text in ("2024-07-08", "08-JUL-2024", "08-Jul-2024", "08JUL2024"):
            self.assertEqual(nse_archives.parse_nse_date(text), "2024-07-08")
        self.assertEqual(nse_archives.parse_nse_date(date(2024, 7, 8)),
                         "2024-07-08")
        self.assertIsNone(nse_archives.parse_nse_date(""))
        self.assertIsNone(nse_archives.parse_nse_date("not-a-date"))

    def test_utc_instants_are_converted_to_the_ist_trading_date(self):
        """The bug this guards: jugaad returns 18:30 UTC for the next IST day.

        Its DATE column for the 2026-10-13 session reads ``2026-10-12 18:30:00``
        (naive, i.e. IST midnight expressed in UTC).  Taking ``.date()`` blindly
        would file every row one day early, silently corrupting the series.
        """
        import datetime as _dt

        import pandas as pd

        naive = _dt.datetime(2026, 10, 12, 18, 30, 0)
        self.assertEqual(nse_archives.parse_nse_date(naive), "2026-10-13")
        self.assertEqual(
            nse_archives.parse_nse_date("2026-10-12 18:30:00"), "2026-10-13")
        self.assertEqual(
            nse_archives.parse_nse_date(pd.Timestamp("2026-10-12 18:30:00")),
            "2026-10-13")
        # a timezone-aware IST midnight is already the right day
        aware = _dt.datetime(2026, 10, 13, tzinfo=nse_archives.IST)
        self.assertEqual(nse_archives.parse_nse_date(aware), "2026-10-13")
        # plain midnight and plain dates must NOT move
        self.assertEqual(
            nse_archives.parse_nse_date(_dt.datetime(2026, 10, 13, 0, 0)),
            "2026-10-13")
        self.assertEqual(nse_archives.parse_nse_date("2026-10-13"), "2026-10-13")

    def test_numpy_nanosecond_timestamps_are_understood(self):
        import numpy as np

        self.assertEqual(
            nse_archives.parse_nse_date(np.datetime64("2026-10-13T00:00:00")),
            "2026-10-13")

    def test_vendor_datetime_rows_land_on_the_right_trading_date(self):
        import datetime as _dt

        rows = [{"CH_SYMBOL": "INFY", "CH_SERIES": "EQ",
                 "CH_TIMESTAMP": _dt.datetime(2026, 10, 12, 18, 30),
                 "CH_OPENING_PRICE": 1.0, "CH_TRADE_HIGH_PRICE": 2.0,
                 "CH_TRADE_LOW_PRICE": 0.5, "CH_CLOSING_PRICE": 1.5,
                 "CH_TOT_TRADED_QTY": 10}]
        self.assertEqual(nse_archives.normalize_price_records(rows)[0]["date"],
                         "2026-10-13")


class CacheDirectoryTests(unittest.TestCase):
    def test_cache_directory_returns_a_writable_folder(self):
        folder = nse_archives.cache_directory("unit_test_feed")
        self.assertTrue(folder, "expected a writable cache folder")
        self.assertTrue(os.path.isdir(folder))
        # the probe file must have been cleaned up again
        self.assertFalse(os.path.exists(os.path.join(folder, ".write_probe")))

    def test_operator_override_wins(self):
        original = os.environ.get("NSE_ADAPTER_CACHE_DIR")
        target = os.path.join(tempfile.mkdtemp(prefix="nse_cache_over_"),
                              "feed")
        os.environ["NSE_ADAPTER_CACHE_DIR"] = target
        nse_archives._CACHE_DIRS.clear()          # forget the cached answer
        try:
            folder = nse_archives.cache_directory("override_feed")
            self.assertEqual(folder, os.path.join(target, "override_feed"))
        finally:
            nse_archives._CACHE_DIRS.clear()
            if original is None:
                os.environ.pop("NSE_ADAPTER_CACHE_DIR", None)
            else:
                os.environ["NSE_ADAPTER_CACHE_DIR"] = original

    def test_jugaad_cache_env_var_is_pointed_at_our_folder(self):
        original = os.environ.pop("J_CACHE_DIR", None)
        try:
            folder = jugaad.use_local_cache_dir()
            self.assertTrue(folder)
            self.assertEqual(os.environ.get("J_CACHE_DIR"), folder)
        finally:
            if original is not None:
                os.environ["J_CACHE_DIR"] = original
            else:
                os.environ.pop("J_CACHE_DIR", None)


class DownloadBehaviourTests(unittest.TestCase):
    """Downloads are replaced by a fake opener: no network, fully deterministic."""

    def test_first_working_url_wins_and_later_ones_are_not_called(self):
        calls = []

        def opener(url, timeout):
            calls.append(url)
            if "BhavCopy_NSE_CM" in url:
                return udiff_fixture().encode("utf-8")
            raise OSError("should not be reached")

        rows = nse_archives.fetch_bhavcopy_day(
            date(2026, 10, 13), opener=opener)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(calls), 1)

    def test_zipped_body_is_unzipped_transparently(self):
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("cm02JAN2023bhav.csv", legacy_fixture())
        payload = buffer.getvalue()

        def opener(url, timeout):
            if url.endswith(".zip"):
                return payload
            raise FileNotFoundError("404")

        rows = nse_archives.fetch_bhavcopy_day(
            date(2023, 1, 2), opener=opener)
        self.assertEqual({row["symbol"] for row in rows},
                         {"RELIANCE", "TCS", "WIPRO"})

    def test_falls_through_to_the_plain_csv_when_zips_are_missing(self):
        """The last-resort URL (sec_bhavdata_full) must be tried and used."""
        plain_csv = "\n".join([
            SECBHAV_HEADER,
            "RELIANCE,EQ,13-Jul-2024,2500.00,2510.00,2525.00,2495.00,"
            "2520.00,2519.50,2505.00,7000000,175000.00,150000,3500000,50.00",
        ]) + "\n"
        tried = []

        def opener(url, timeout):
            tried.append(url)
            if url.endswith("sec_bhavdata_full_13072024.csv"):
                return plain_csv.encode("utf-8")
            raise FileNotFoundError(f"{url} -> 404 (holiday or not published yet)")

        rows = nse_archives.fetch_bhavcopy_day(
            date(2024, 7, 13), opener=opener)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "RELIANCE")
        self.assertEqual(rows[0]["date"], "2024-07-13")
        self.assertTrue(tried[-1].endswith("sec_bhavdata_full_13072024.csv"))


class FailureHonestyTests(unittest.TestCase):
    def test_every_url_failing_raises_with_the_urls_in_the_message(self):
        def opener(url, timeout):
            raise OSError("connection reset")

        with self.assertRaises(RuntimeError) as error:
            nse_archives.fetch_bhavcopy_day(date(2026, 10, 13), opener=opener)
        message = str(error.exception)
        self.assertIn("connection reset", message)
        self.assertIn("BhavCopy_NSE_CM", message)

    def test_wrong_dated_file_is_rejected_not_written(self):
        """A file for another day must never be stored under today's date."""

        def opener(url, timeout):
            return udiff_fixture().encode("utf-8")      # always 2026-10-13

        with self.assertRaises(RuntimeError) as error:
            nse_archives.fetch_bhavcopy_day(date(2026, 10, 12), opener=opener)
        self.assertIn("carried dates", str(error.exception))

    def test_adapter_health_records_the_failure(self):
        adapter = nse_archives.NseArchiveBhavcopyAdapter()
        original = nse_archives.download
        nse_archives.download = lambda url, timeout=30: (_ for _ in ()).throw(
            OSError("offline"))
        try:
            with self.assertRaises(RuntimeError):
                adapter.fetch(date(2026, 10, 13))
        finally:
            nse_archives.download = original
        health = adapter.health()
        self.assertEqual(health.state, "unavailable")
        self.assertEqual(health.failures, 1)
        self.assertIn("offline", health.last_error or "")


class VendorRecordTests(unittest.TestCase):
    """The ``nse``/jugaad/pnsea families return CH_* style rows."""

    VENDOR_ROWS = [
        {"CH_SYMBOL": "HDFCBANK", "CH_SERIES": "EQ", "CH_TIMESTAMP": "2026-10-13",
         "CH_OPENING_PRICE": 1000.0, "CH_TRADE_HIGH_PRICE": 1010.0,
         "CH_TRADE_LOW_PRICE": 995.0, "CH_CLOSING_PRICE": 1005.0,
         "CH_TOT_TRADED_QTY": 123456, "COP_DELIV_PERC": 55.5},
        {"CH_SYMBOL": "SBIN", "CH_SERIES": "EQ", "mTIMESTAMP": "13-Oct-2026",
         "CH_OPENING_PRICE": 800.0, "CH_TRADE_HIGH_PRICE": 810.0,
         "CH_TRADE_LOW_PRICE": 795.0, "CH_CLOSING_PRICE": 805.0,
         "CH_TOT_TRADED_QTY": 999},
    ]

    def test_vendor_column_spellings_map_to_canonical_records(self):
        rows = nse_archives.normalize_price_records(self.VENDOR_ROWS)
        self.assertEqual([row["symbol"] for row in rows], ["HDFCBANK", "SBIN"])
        hdfc = {row["symbol"]: row for row in rows}["HDFCBANK"]
        self.assertEqual(hdfc["date"], "2026-10-13")
        self.assertEqual(hdfc["close"], 1005.0)
        self.assertEqual(hdfc["volume"], 123456.0)

    def test_yahoo_shaped_frame_is_a_drop_in_for_the_price_ingester(self):
        frame = nse_archives.records_to_yahoo_frame(
            [canonical("INFY", "2026-10-13", 1.0, 2.0, 0.5, 1.5, 10.0)])
        self.assertEqual(list(frame.columns),
                         ["Open", "High", "Low", "Close", "Volume"])
        # ingest_prices.py does str(idx.date()) and df["Close"]
        self.assertEqual(str(frame.index[0].date()), "2026-10-13")
        self.assertEqual(float(frame["Close"].iloc[0]), 1.5)

    def test_pandas_dataframes_from_vendors_are_accepted(self):
        import pandas as pd

        frame = pd.DataFrame([
            {"date": "2026-10-13", "symbol": "TCS", "series": "EQ",
             "open": 3300.0, "high": 3350.0, "low": 3280.0, "close": 3345.5,
             "volume": 1200000},
        ])
        rows = nse_archives.normalize_price_records(frame)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "TCS")
        self.assertEqual(rows[0]["close"], 3345.5)

    def test_single_symbol_frames_without_a_symbol_column_are_accepted(self):
        """nsemine's chart feed returns candles and never repeats the ticker."""
        import datetime as _dt

        import pandas as pd

        frame = pd.DataFrame([
            {"datetime": _dt.datetime(2026, 10, 12, 18, 30), "open": 1029.2,
             "high": 1065.0, "low": 1027.0, "close": 1062.1,
             "volume": 21781113},
        ])
        result = nse_archives.records_to_yahoo_frame(frame, default_symbol="INFY")
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result.index[0].date()), "2026-10-13")
        self.assertEqual(float(result["Close"].iloc[0]), 1062.1)

    def test_unnormalisable_rows_raise_instead_of_looking_like_success(self):
        """Empty data must not masquerade as a good answer (registry would stop
        trying the next provider)."""
        self.assertEqual(
            len(nse_archives.records_to_yahoo_frame([])), 0)
        with self.assertRaises(ValueError):
            nse_archives.records_to_yahoo_frame(
                [{"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
                  "volume": 10}])       # no symbol, no default symbol


class RegistrationTests(unittest.TestCase):
    NEW_PROVIDERS = {
        "nse_archives": ("prices.bhavcopy_daily",),
        "nse_archives_monthly": ("prices.bhavcopy_monthly",),
        "nse_india_api": ("prices.daily_history",),
        "nse_india_api_bhavcopy": ("prices.bhavcopy_daily",),
        "jugaad_data": ("prices.daily_history",),
        "jugaad_data_bhavcopy": ("prices.bhavcopy_daily",),
        "nselib": ("prices.bhavcopy_daily",),
        "nselib_delivery": ("prices.price_volume_delivery",),
        "nsemine": ("prices.bhavcopy_daily",),
        "nsemine_history": ("prices.daily_history",),
        "pnsea": ("prices.daily_history",),
        "pnsea_delivery": ("prices.price_volume_delivery",),
    }

    def test_every_new_provider_registers_without_touching_the_network(self):
        registry = SourceRegistry()
        registry.discover()          # auto-imports every adapter module
        health = {item["provider"]: item for item in registry.health()}
        for name, datasets in self.NEW_PROVIDERS.items():
            self.assertIn(name, health, f"{name} did not register")
            self.assertEqual(tuple(health[name]["datasets"]), datasets)
            self.assertEqual(health[name]["state"], "not_checked")
            self.assertEqual(health[name]["calls"], 0)
            self.assertEqual(health[name]["failures"], 0)

    def test_bhavcopy_providers_all_declare_the_same_dataset(self):
        """Fallback only works if the providers agree on the dataset name."""
        registry = SourceRegistry()
        registry.discover()
        health = {item["provider"]: item for item in registry.health()}
        fallbacks = [name for name, item in health.items()
                     if "prices.bhavcopy_daily" in item["datasets"]]
        self.assertTrue({"nse_archives", "nselib", "nsemine",
                         "jugaad_data_bhavcopy", "nse_india_api_bhavcopy"}
                        .issubset(set(fallbacks)))

    def test_missing_package_is_a_clean_error_not_an_import_crash(self):
        """Golden rule 7: a missing third-party package must not break the app."""
        cases = [
            (nseindiaapi.NseApiPriceHistoryAdapter(), "nse", "TCS"),
            (jugaad.JugaadPriceHistoryAdapter(), "jugaad_data", "TCS"),
            (nselib_src.NselibBhavcopyAdapter(), "nselib", "2026-10-13"),
            (nsemine_src.NsemineBhavcopyAdapter(), "nsemine", "2026-10-13"),
            (pnsea_src.PnseaPriceHistoryAdapter(), "pnsea", "TCS"),
        ]
        for adapter, package, argument in cases:
            blocked = sys.modules.get(package, "absent")
            sys.modules[package] = None       # makes `import <package>` fail
            try:
                with self.assertRaises(RuntimeError) as error:
                    if adapter.datasets == ("prices.daily_history",):
                        adapter.fetch(argument, "2026-01-01")
                    else:
                        adapter.fetch(argument)
                self.assertIn("pip install", str(error.exception))
            finally:
                if blocked == "absent":
                    sys.modules.pop(package, None)
                else:
                    sys.modules[package] = blocked

    def test_adapters_survive_a_broken_response_without_raising_at_import(self):
        """An empty vendor result must become an error the registry can route."""
        original = nselib_src.fetch_bhavcopy
        nselib_src.fetch_bhavcopy = lambda day: None
        try:
            adapter = nselib_src.NselibBhavcopyAdapter()
            with self.assertRaises(ValueError):
                adapter.fetch("2026-10-13")
        finally:
            nselib_src.fetch_bhavcopy = original


# ------------------------------------------------------------------ ingestion

class IngestDatabaseTests(unittest.TestCase):
    """A throw-away SQLite file stands in for data/app.db."""

    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="nse_archive_test_")
        self.db_path = os.path.join(self.folder, "test.db")
        self.conn = sqlite3.connect(self.db_path)
        ingest.ensure_tables(self.conn)
        self.real_fetch = ingest.fetch_bhavcopy
        self.fetch_calls = []

    def tearDown(self):
        ingest.fetch_bhavcopy = self.real_fetch
        self.conn.close()
        try:
            os.remove(self.db_path)
            os.rmdir(self.folder)
        except OSError:
            pass

    def _stub_fetch(self, rows):
        def fake(day, providers=ingest.DEFAULT_PROVIDERS):
            self.fetch_calls.append(day)
            return list(rows), "nse_archives"

        ingest.fetch_bhavcopy = fake

    def count(self, where=""):
        return self.conn.execute(
            f"SELECT COUNT(*) FROM prices_daily {where}").fetchone()[0]

    def test_ensure_tables_creates_but_never_drops(self):
        self.conn.execute(
            "INSERT INTO prices_daily VALUES ('KEEP','2020-01-01',1,1,1,1,1)")
        self.conn.commit()
        ingest.ensure_tables(self.conn)
        self.assertEqual(self.count(), 1)

    def test_upsert_writes_rows_and_is_idempotent(self):
        rows = [canonical("INFY", "2026-10-13", 1500.0, 1520.5, 1495.25,
                          1512.75, 1000000),
                canonical("IDEA", "2026-10-13", 10.1, 10.6, 10.0, 10.45, 250000)]
        first = ingest.upsert_ohlcv(self.conn, rows)
        self.assertEqual(first, 2)
        self.assertEqual(self.count(), 2)

        again = ingest.upsert_ohlcv(self.conn, rows)
        self.assertEqual(again, 2)                  # rewritten, not duplicated
        self.assertEqual(self.count(), 2)           # <- idempotency

    def test_upsert_overwrites_a_corrected_price(self):
        ingest.upsert_ohlcv(self.conn, [
            canonical("INFY", "2026-10-13", 1500.0, 1520.5, 1495.25,
                      1512.75, 1000000)])
        ingest.upsert_ohlcv(self.conn, [
            canonical("INFY", "2026-10-13", 1500.0, 1520.5, 1495.25,
                      1513.00, 1000500)])
        row = self.conn.execute(
            "SELECT close, volume FROM prices_daily WHERE symbol='INFY'"
        ).fetchone()
        self.assertEqual(row, (1513.00, 1000500.0))
        self.assertEqual(self.count(), 1)

    def test_symbol_filter_keeps_only_the_symbols_we_track(self):
        rows = [canonical("INFY", "2026-10-13", 1, 1, 1, 1, 1),
                canonical("OBSCURE_ETF", "2026-10-13", 1, 1, 1, 1, 1)]
        written = ingest.upsert_ohlcv(self.conn, rows, symbols={"INFY"})
        self.assertEqual(written, 1)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.conn.execute(
            "SELECT symbol FROM prices_daily").fetchone()[0], "INFY")

    def test_price_meta_is_refreshed_for_touched_symbols_only(self):
        ingest.upsert_ohlcv(self.conn, [
            canonical("INFY", "2026-10-13", 1, 1, 1, 1, 1),
            canonical("INFY", "2026-10-12", 1, 1, 1, 1, 1)])
        ingest.refresh_price_meta(self.conn, ["INFY"])
        row = self.conn.execute(
            "SELECT symbol, last_date, rows FROM price_meta").fetchone()
        self.assertEqual(row, ("INFY", "2026-10-13", 2))

    def test_ingest_day_writes_rows_and_reports_the_provider(self):
        self._stub_fetch([
            canonical("INFY", "2026-10-13", 1500.0, 1520.5, 1495.25,
                      1512.75, 1000000)])
        report = ingest.ingest_day(self.conn, date(2026, 10, 13))
        self.assertIsNone(report["error"])
        self.assertEqual(report["provider"], "nse_archives")
        self.assertEqual(report["upserted"], 1)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.conn.execute(
            "SELECT last_date FROM price_meta WHERE symbol='INFY'"
        ).fetchone()[0], "2026-10-13")

    def test_dry_run_downloads_but_writes_nothing(self):
        self._stub_fetch([
            canonical("INFY", "2026-10-13", 1500.0, 1520.5, 1495.25,
                      1512.75, 1000000)])
        report = ingest.ingest_day(self.conn, date(2026, 10, 13), dry_run=True)
        self.assertEqual(report["fetched"], 1)
        self.assertEqual(report["upserted"], 0)
        self.assertEqual(self.count(), 0)

    def test_a_provider_failure_is_reported_and_writes_nothing(self):
        from data_sources.core import ProviderFetchError

        def broken(day, providers=ingest.DEFAULT_PROVIDERS):
            self.fetch_calls.append(day)
            raise ProviderFetchError("prices.bhavcopy_daily",
                                     {"nse_archives": "offline"})

        ingest.fetch_bhavcopy = broken
        report = ingest.ingest_day(self.conn, date(2026, 10, 13))
        self.assertIsNotNone(report["error"])
        self.assertIn("offline", report["error"])
        self.assertEqual(self.count(), 0)

    def test_date_command_skips_a_date_that_already_looks_loaded(self):
        # 60 rows is above the "already loaded" threshold
        self.conn.executemany(
            "INSERT INTO prices_daily VALUES (?,?,1,1,1,1,1)",
            [(f"SYM{i}", "2026-10-13") for i in range(60)])
        self.conn.commit()
        self._stub_fetch([canonical("INFY", "2026-10-13", 1, 1, 1, 1, 1)])

        args = ingest.build_parser().parse_args(
            ["date", "2026-10-13", "--sleep", "0"])
        exit_code = ingest.command_date(self.conn, args, None,
                                        ingest.DEFAULT_PROVIDERS)
        self.assertEqual(exit_code, 0)
        self.assertEqual(self.fetch_calls, [])      # nothing was downloaded
        self.assertEqual(self.count(), 60)          # nothing was rewritten

    def test_force_redownloads_an_already_loaded_date(self):
        self.conn.executemany(
            "INSERT INTO prices_daily VALUES (?,?,1,1,1,1,1)",
            [(f"SYM{i}", "2026-10-13") for i in range(60)])
        self.conn.commit()
        self._stub_fetch([canonical("INFY", "2026-10-13", 2, 2, 2, 2, 2)])

        args = ingest.build_parser().parse_args(
            ["date", "2026-10-13", "--force", "--sleep", "0"])
        ingest.command_date(self.conn, args, None, ingest.DEFAULT_PROVIDERS)
        self.assertEqual(len(self.fetch_calls), 1)

    def test_backfill_respects_the_download_limit(self):
        self._stub_fetch([canonical("INFY", "2026-10-13", 1, 1, 1, 1, 1)])
        args = ingest.build_parser().parse_args(
            ["backfill", "--days", "14", "--limit", "2", "--sleep", "0",
             "--end", "2026-10-13"])
        ingest.command_backfill(self.conn, args, None, ingest.DEFAULT_PROVIDERS)
        self.assertEqual(len(self.fetch_calls), 2)
        for day in self.fetch_calls:
            self.assertLess(day.weekday(), 5, f"{day} is a weekend")

    def test_range_command_only_walks_weekdays(self):
        self._stub_fetch([canonical("INFY", "2026-10-13", 1, 1, 1, 1, 1)])
        args = ingest.build_parser().parse_args(
            ["range", "2026-10-12", "2026-10-18", "--sleep", "0",
             "--limit", "0"])
        ingest.command_range(self.conn, args, None, ingest.DEFAULT_PROVIDERS)
        self.assertEqual([day.isoformat() for day in self.fetch_calls],
                         ["2026-10-12", "2026-10-13", "2026-10-14",
                          "2026-10-15", "2026-10-16"])

    def test_a_blocked_feed_stops_after_consecutive_failures(self):
        """A blocked NSE must not make us hammer every date in the range."""
        from data_sources.core import ProviderFetchError

        def broken(day, providers=ingest.DEFAULT_PROVIDERS):
            self.fetch_calls.append(day)
            raise ProviderFetchError("prices.bhavcopy_daily",
                                     {"nse_archives": "blocked"})

        ingest.fetch_bhavcopy = broken
        args = ingest.build_parser().parse_args(
            ["range", "2026-10-12", "2026-10-23", "--sleep", "0",
             "--limit", "0", "--max-failures", "2"])
        code = ingest.command_range(self.conn, args, None,
                                    ingest.DEFAULT_PROVIDERS)
        self.assertEqual(len(self.fetch_calls), 2)      # stopped early
        self.assertEqual(code, 1)                       # and reported failure

    def test_status_command_runs_offline_without_writing(self):
        args = ingest.build_parser().parse_args(["status"])
        self.assertEqual(ingest.command_status(self.conn, args, None, ()), 0)
        self.assertEqual(self.count(), 0)


class CliDefaultsTests(unittest.TestCase):
    def test_defaults_are_deliberately_polite_to_nse(self):
        args = ingest.build_parser().parse_args(["backfill"])
        self.assertEqual(args.sleep, 1.5)
        self.assertEqual(args.limit, 5)
        self.assertEqual(args.symbols, "existing")
        self.assertFalse(args.force)
        self.assertFalse(args.dry_run)
        self.assertEqual(args.providers.split(",")[0], "nse_archives")

    def test_no_subcommand_prints_help_and_exits_zero(self):
        self.assertEqual(ingest.main([]), 0)

    def test_limit_zero_means_no_limit(self):
        self.assertIsNone(ingest.normalise_limit(0))
        self.assertIsNone(ingest.normalise_limit(-3))
        self.assertIsNone(ingest.normalise_limit("junk"))
        self.assertEqual(ingest.normalise_limit(7), 7)
        # the CLI applies the same rule through argparse
        self.assertIsNone(ingest.build_parser().parse_args(
            ["date", "2026-10-13", "--limit", "0"]).limit)
        self.assertEqual(ingest.build_parser().parse_args(
            ["date", "2026-10-13", "--limit", "3"]).limit, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
