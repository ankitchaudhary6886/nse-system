"""Offline tests for the free official NSE EOD ingestion (18 Oct 2026)."""
import io
import sqlite3
import unittest
import zipfile
from unittest import mock

import db
import nse_eod_ingest as ne


SEC_BHAV_CSV = """SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
SBIN, EQ, 16-Oct-2026, 1042.90, 1045.00, 1060.00, 1040.00, 1055.00, 1056.00, 1050.00, 1000000, 10500.00, 5000, 600000, 60.00
TCS, EQ, 16-Oct-2026, 2248.40, 2250.00, 2270.00, 2240.00, 2260.00, 2261.00, 2255.00, 500000, 11275.00, 3000, 200000, 40.00
SOMESME, SM, 16-Oct-2026, 10.0, 10.0, 11.0, 10.0, 10.5, 10.5, 10.5, 1000, 1.0, 10, 100, 10.0
"""

INDEX_CSV = """Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,Points Change,Change(%),Volume
NIFTY 50,16-10-2026,23000.00,23200.00,22950.00,23146.15,148.80,0.65,1000000
NIFTY 500,16-10-2026,21000.00,21100.00,20900.00,21050.00,50.00,0.24,900000
NIFTY BANK,16-10-2026,50000.00,50200.00,49800.00,50100.00,100.00,0.20,800000
"""

MASTER_CSV = """SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,MARKET LOT,ISIN NUMBER,FACE VALUE
SBIN,State Bank of India,EQ,01-Mar-1995,1,1,INE062A01020,1
TCS,Tata Consultancy Services,EQ,25-Aug-2004,1,1,INE467B01029,1
"""

LEGACY_CSV = """SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN
SBIN,EQ,100,110,99,105,105,100,1000,100000,17-AUG-2021,50,INE062A01020
TCS,EQ,200,210,199,205,205,200,500,100000,17-AUG-2021,25,INE467B01029
"""


def memory_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    db._migrate(conn)
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("INSERT OR REPLACE INTO universe_broad "
                 "(symbol,mcap_cr,updated_at) VALUES ('SBIN',2000,'2026-10-18')")
    conn.execute("INSERT OR REPLACE INTO universe_broad "
                 "(symbol,mcap_cr,updated_at) VALUES ('TCS',2000,'2026-10-18')")
    conn.commit()
    return conn


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code
        self.text = content.decode("utf-8", "replace") if isinstance(
            content, bytes) else ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, mapping):
        self.mapping = mapping
        self.headers = {}

    def get(self, url, timeout=None):
        for fragment, content in self.mapping.items():
            if fragment in url:
                if content is None:
                    return FakeResponse(b"", status_code=404)
                return FakeResponse(content.encode() if isinstance(content, str)
                                    else content)
        return FakeResponse(b"", status_code=404)


class ParseTests(unittest.TestCase):
    def test_parse_sec_bhav(self):
        rows = ne.parse_sec_bhav(SEC_BHAV_CSV)
        self.assertEqual(len(rows), 2)  # SM row dropped
        sbin = rows[0]
        self.assertEqual(sbin["symbol"], "SBIN")
        self.assertEqual(sbin["date"], "2026-10-16")
        self.assertEqual(sbin["close"], 1056.0)
        self.assertEqual(sbin["delivery_pct"], 60.0)

    def test_parse_index_close(self):
        rows = ne.parse_index_close(INDEX_CSV)
        self.assertEqual(len(rows), 3)
        by_symbol = {row["symbol"]: row for row in rows}
        self.assertEqual(by_symbol["NIFTY50"]["close"], 23146.15)
        self.assertEqual(by_symbol["NIFTY500"]["change_pct"], 0.24)

    def test_parse_equity_master(self):
        rows = ne.parse_equity_master(MASTER_CSV)
        self.assertEqual(rows[0]["isin"], "INE062A01020")
        self.assertEqual(len(rows), 2)

    def test_parse_legacy_bhav(self):
        rows = ne.parse_legacy_bhav(LEGACY_CSV)
        self.assertEqual(rows[0]["close"], 105.0)
        self.assertEqual(rows[1]["symbol"], "TCS")


class IngestTests(unittest.TestCase):
    def test_ingest_date_writes_prices_delivery_and_indices(self):
        conn = memory_db()
        session = FakeSession({"sec_bhavdata_full": SEC_BHAV_CSV,
                               "ind_close_all": INDEX_CSV})
        result = ne.ingest_date(conn, "2026-10-16", session=session)
        self.assertEqual(result["status"], "ok")
        row = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol='SBIN' "
            "AND date='2026-10-16'").fetchone()
        self.assertEqual(row[0], 1056.0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM delivery_daily").fetchone()[0], 2)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM index_daily").fetchone()[0], 3)
        basis = conn.execute(
            "SELECT basis FROM price_meta WHERE symbol='SBIN'").fetchone()[0]
        self.assertEqual(basis, "nse_bhavdata_raw")

    def test_ingest_date_records_mixed_basis_when_older_history_exists(self):
        conn = memory_db()
        conn.execute("INSERT INTO prices_daily VALUES "
                     "('SBIN','2026-10-15',100,100,100,100,1000)")
        conn.commit()
        session = FakeSession({"sec_bhavdata_full": SEC_BHAV_CSV,
                               "ind_close_all": INDEX_CSV})
        ne.ingest_date(conn, "2026-10-16", session=session)
        basis = conn.execute(
            "SELECT basis FROM price_meta WHERE symbol='SBIN'").fetchone()[0]
        self.assertEqual(basis, "mixed_adjusted_then_raw")

    def test_ingest_date_records_holiday_on_404(self):
        conn = memory_db()
        session = FakeSession({})  # everything 404s
        result = ne.ingest_date(conn, "2026-10-15", session=session)
        self.assertEqual(result["status"], "holiday")
        sync = conn.execute(
            "SELECT status FROM nse_eod_sync WHERE date='2026-10-15'").fetchone()
        self.assertEqual(sync[0], "holiday")

    def test_ingest_skips_foreign_symbols(self):
        conn = memory_db()
        text = SEC_BHAV_CSV.replace("SBIN", "FOREIGN").replace("TCS", "OTHER")
        session = FakeSession({"sec_bhavdata_full": text,
                               "ind_close_all": INDEX_CSV})
        result = ne.ingest_date(conn, "2026-10-16", session=session)
        self.assertEqual(result["prices"]["rows"], 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0], 0)

    def test_reingest_is_idempotent(self):
        conn = memory_db()
        session = FakeSession({"sec_bhavdata_full": SEC_BHAV_CSV,
                               "ind_close_all": INDEX_CSV})
        ne.ingest_date(conn, "2026-10-16", session=session)
        ne.ingest_date(conn, "2026-10-16", session=session)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0], 2)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM index_daily").fetchone()[0], 3)

    def test_catch_up_skips_recorded_dates(self):
        conn = memory_db()
        conn.execute("INSERT OR REPLACE INTO nse_eod_sync (date,status) "
                     "VALUES ('2026-10-16','ok')")
        conn.commit()
        session = FakeSession({"sec_bhavdata_full": SEC_BHAV_CSV,
                               "ind_close_all": INDEX_CSV})
        with mock.patch.object(ne.dt, "date", wraps=ne.dt.date) as _:
            result = ne.catch_up(conn, days_back=2, session=session)
        # the already-ok date must not be fetched again
        attempted = [r["date"] for r in result["details"]]
        self.assertNotIn("2026-10-16", attempted)


class HistoryTests(unittest.TestCase):
    def _zip(self, csv_text):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("cm17AUG2021bhav.csv", csv_text)
        return buffer.getvalue()

    def test_history_probe_counts_rows_without_writing(self):
        conn = memory_db()
        session = FakeSession({"sec_bhavdata_full": SEC_BHAV_CSV})
        result = ne.fetch_history(conn, "2021-08-17", "2021-08-17",
                                  apply=False, sleep=0, session=session)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["rows"], 2)
        self.assertEqual(result["sources"]["sec_bhavdata_full"], 1)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM prices_daily").fetchone()[0], 0)

    def test_history_apply_writes_raw_and_backup(self):
        conn = memory_db()
        conn.execute("INSERT INTO prices_daily VALUES "
                     "('SBIN','2021-08-17',1,1,1,1,1)")
        conn.commit()
        session = FakeSession({"sec_bhavdata_full": SEC_BHAV_CSV})
        result = ne.fetch_history(conn, "2021-08-17", "2021-08-17",
                                  apply=True, sleep=0, session=session)
        self.assertIsNotNone(result["backup_table"])
        row = conn.execute(
            "SELECT close FROM prices_daily WHERE symbol='SBIN'").fetchone()
        self.assertEqual(row[0], 1056.0)

    def test_history_falls_back_to_legacy_zip(self):
        conn = memory_db()
        session = FakeSession({"sec_bhavdata_full": None,
                               "cm17AUG2021bhav": self._zip(LEGACY_CSV)})
        result = ne.fetch_history(conn, "2021-08-17", "2021-08-17",
                                  apply=False, sleep=0, session=session)
        self.assertEqual(result["ok"], 1)
        self.assertEqual(result["sources"]["legacy_bhavcopy"], 1)
        self.assertEqual(result["rows"], 2)


class ReportTests(unittest.TestCase):
    def test_report_shapes(self):
        conn = memory_db()
        report = ne.report(conn)
        self.assertIn("recent_sync", report)
        self.assertEqual(report["delivery_rows"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
