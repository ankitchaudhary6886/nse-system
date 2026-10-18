"""Offline tests for announcements.py: no network, no data/app.db, in-memory SQLite."""
import csv
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import announcements as A


def mem():
    """Empty in-memory DB with the announcements table (never data/app.db)."""
    conn = sqlite3.connect(":memory:")
    A.ensure_tables(conn)
    return conn


def ago(days):
    """IST wall-clock stamp `days` in the past, in the module's canonical format."""
    return (dt.datetime.now(A.IST) - dt.timedelta(days=days)).strftime(A.FMT)


def item(symbol, announced_at, subject, **extra):
    row = {"symbol": symbol, "announced_at": announced_at, "subject": subject}
    row.update(extra)
    return row


class ClassifyTests(unittest.TestCase):
    HIGH = [
        ("Resignation of Statutory Auditor", "auditor_resignation"),
        ("Auditor resignation and appointment of new auditor", "auditor_resignation"),
        ("Qualified Opinion issued by the Statutory Auditors", "auditor_qualification"),
        ("Auditor notes material uncertainty on going concern basis",
         "auditor_qualification"),
        ("Pledge of promoter shares for bank facility", "promoter_pledge"),
        ("Default on interest payment on NCDs", "payment_default"),
        ("SEBI imposes penalty of Rs 10 lakh", "sebi_action"),
        ("Initiation of CIRP under IBC before NCLT", "insolvency"),
        ("Suspension of trading in equity shares", "trading_suspension"),
        ("Fraud detected in accounts of subsidiary", "fraud"),
    ]
    MEDIUM = [
        ("Credit rating downgrade by CARE Ratings", "rating_downgrade"),
        ("Resignation of Chief Financial Officer", "key_person_resignation"),
        ("Impairment of goodwill in subsidiary", "profit_warning"),
        ("Related party transaction approved", "related_party"),
        ("Approval from regulator delayed by a quarter", "regulatory_delay"),
    ]
    LOW = [
        ("Board Meeting Intimation for quarterly results", "board_meeting"),
        ("Record Date for Dividend of Rs 5", "dividend"),
        ("Financial Results for the quarter ended June", "financial_results"),
        ("Name change of the company", "name_change"),
        ("AGM notice and postal ballot", "meeting_notice"),
        ("Board approves bonus issue and share split", "capital_action"),
    ]

    def test_high_cases(self):
        for subject, flag in self.HIGH:
            verdict = A.classify(subject)
            self.assertEqual(verdict["severity"], "high", subject)
            self.assertIn(flag, verdict["flags"], subject)

    def test_medium_cases(self):
        for subject, flag in self.MEDIUM:
            verdict = A.classify(subject)
            self.assertEqual(verdict["severity"], "medium", subject)
            self.assertIn(flag, verdict["flags"], subject)

    def test_low_cases(self):
        for subject, flag in self.LOW:
            verdict = A.classify(subject)
            self.assertEqual(verdict["severity"], "low", subject)
            self.assertIn(flag, verdict["flags"], subject)

    def test_none_and_unrelated(self):
        verdict = A.classify("Trading window closure for insiders")
        self.assertEqual(verdict, {"severity": "none", "flags": []})

    def test_desc_contributes(self):
        verdict = A.classify("Intimation under Regulation 30",
                             "Resignation of the statutory auditor accepted")
        self.assertEqual(verdict["severity"], "high")
        self.assertIn("auditor_resignation", verdict["flags"])

    def test_case_insensitive(self):
        verdict = A.classify("RESIGNATION OF STATUTORY AUDITOR")
        self.assertEqual(verdict["severity"], "high")

    def test_highest_severity_wins_and_all_flags_kept(self):
        verdict = A.classify("Board Meeting Intimation to consider pledge of promoter shares")
        self.assertEqual(verdict["severity"], "high")
        self.assertIn("board_meeting", verdict["flags"])
        self.assertIn("promoter_pledge", verdict["flags"])

    def test_never_raises_on_non_string_input(self):
        for value in (None, 42, 3.5, b"pledge of promoter shares", [], {}, object()):
            verdict = A.classify(value)
            self.assertIn(verdict["severity"], A.RANK)
            self.assertIsInstance(verdict["flags"], list)

    def test_sebi_action_matches_both_word_orders(self):
        for subject in ("SEBI imposes penalty of Rs 10 lakh",
                        "Order passed by SEBI in the matter of insider trading"):
            self.assertEqual(A.classify(subject)["severity"], "high", subject)
            self.assertIn("sebi_action", A.classify(subject)["flags"], subject)

    def test_sebi_compliance_filings_are_not_sebi_actions(self):
        # ~2.2k of every 30 days of NSE filings look like this: routine certificates.
        for subject in ("Certificate under SEBI (Depositories and Participants) Regulations, 2018",
                        "Disclosure under SEBI Takeover Regulations"):
            verdict = A.classify(subject)
            self.assertNotIn("sebi_action", verdict["flags"], subject)
            self.assertNotEqual(verdict["severity"], "high", subject)

    def test_license_suspension_is_not_a_trading_suspension(self):
        # Real NSE category text; "suspension" here is about licences, not trading.
        verdict = A.classify("Granting/withdrawal/surrender/cancellation/suspension of key "
                             "licenses/ regulatory approvals")
        self.assertNotIn("trading_suspension", verdict["flags"])
        self.assertNotEqual(verdict["severity"], "high")


class StoreTests(unittest.TestCase):
    def test_dedupe_same_row_twice(self):
        conn = mem()
        rows = [item("AAA", ago(1), "Resignation of Statutory Auditor"),
                item("BBB", ago(2), "Board Meeting Intimation")]
        first = A.store(conn, rows)
        second = A.store(conn, rows)
        self.assertEqual((first["seen"], first["inserted"], first["skipped"]), (2, 2, 0))
        self.assertEqual((second["seen"], second["inserted"], second["skipped"]), (2, 0, 2))
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM corporate_announcements").fetchone()[0], 2)

    def test_severity_and_flags_json_are_stored(self):
        conn = mem()
        A.store(conn, [item("AAA", ago(1), "Pledge of promoter shares",
                            url="https://x/1.pdf")])
        severity, flags, url, source, fetched = conn.execute(
            "SELECT severity, flags, url, source, fetched_at FROM "
            "corporate_announcements").fetchone()
        self.assertEqual(severity, "high")
        self.assertEqual(json.loads(flags), ["promoter_pledge"])
        self.assertEqual(url, "https://x/1.pdf")
        self.assertEqual(source, "nse_api")
        stamp = dt.datetime.strptime(fetched, A.FMT)
        now = dt.datetime.now(A.IST).replace(tzinfo=None)
        self.assertLess(abs((now - stamp).total_seconds()), 120)

    def test_malformed_rows_are_skipped_not_fatal(self):
        conn = mem()
        rows = [item("AAA", ago(1), "Board Meeting Intimation"),
                "not a dict", None, 7,
                {"symbol": "", "announced_at": ago(1), "subject": "Dividend"},
                {"symbol": "BBB", "announced_at": "not-a-date", "subject": "Dividend"},
                {"symbol": "CCC", "announced_at": ago(1), "subject": ""}]
        result = A.store(conn, rows)
        self.assertEqual(result["seen"], 7)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["skipped"], 6)
        self.assertEqual(result["by_severity"]["low"], 1)
        self.assertEqual(result["by_severity"]["high"], 0)

    def test_empty_input(self):
        conn = mem()
        result = A.store(conn, [])
        self.assertEqual(result["seen"], 0)
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(result["by_severity"],
                         {"none": 0, "low": 0, "medium": 0, "high": 0})
        self.assertEqual(A.store(conn, None)["seen"], 0)

    def test_source_is_preserved(self):
        conn = mem()
        A.store(conn, [item("AAA", ago(1), "Dividend", source="manual_csv")])
        self.assertEqual(conn.execute(
            "SELECT source FROM corporate_announcements").fetchone()[0], "manual_csv")

    def test_dates_are_normalised_to_iso(self):
        conn = mem()
        A.store(conn, [item("AAA", "26-Sep-2025 18:30:00", "Dividend")])
        self.assertEqual(conn.execute(
            "SELECT announced_at FROM corporate_announcements").fetchone()[0],
            "2025-09-26 18:30:00")


class ImportCsvTests(unittest.TestCase):
    HEADER = ["symbol", "announced_at", "subject", "category", "url", "severity"]

    def _write(self, path, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.HEADER)
            writer.writerows(rows)

    def test_valid_and_invalid_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "announcements.csv"
            self._write(path, [
                ["AAA", "26-Sep-2025 10:00:00", "Resignation of Statutory Auditor",
                 "Company Update", "https://x/1.pdf", "banana"],
                ["BBB", "31-02-2025 10:00:00", "Board Meeting Intimation", "Others", "", ""],
                ["", "2025-09-26 10:00:00", "Dividend", "Others", "", "low"],
                ["AA A", "2025-09-26 10:00:00", "Dividend", "Others", "", "low"],
                ["CCC", "2025-09-26 10:00:00", "", "Others", "", "high"],
                ["DDD", "26-Sep-2025 11:15:00", "Pledge of promoter shares",
                 "Company Update", "", "medium"],
            ])
            conn = mem()
            result = A.import_csv(conn, str(path))
            self.assertEqual(result["rows_read"], 6)
            self.assertEqual(result["invalid"], 4)  # bad date, blank symbol, "AA A", no subject
            self.assertEqual(result["inserted"], 2)
            # File severity ("banana") is ignored: severity is recomputed from subject.
            severity, flags, source = conn.execute(
                "SELECT severity, flags, source FROM corporate_announcements "
                "WHERE symbol='AAA'").fetchone()
            self.assertEqual(severity, "high")
            self.assertEqual(json.loads(flags), ["auditor_resignation"])
            self.assertEqual(source, "manual_csv")
            self.assertEqual(conn.execute(
                "SELECT severity FROM corporate_announcements WHERE symbol='DDD'"
            ).fetchone()[0], "high")

    def test_reimport_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "announcements.csv"
            self._write(path, [
                ["AAA", "2025-09-26 10:00:00", "Dividend", "Others", "", ""],
                ["BBB", "2025-09-27 10:00:00", "Board Meeting Intimation", "Others", "", ""],
            ])
            conn = mem()
            first = A.import_csv(conn, str(path))
            second = A.import_csv(conn, str(path))
            self.assertEqual((first["inserted"], first["invalid"]), (2, 0))
            self.assertEqual((second["inserted"], second["skipped"]), (0, 2))
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM corporate_announcements").fetchone()[0], 2)

    def test_column_names_are_case_and_space_insensitive(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "announcements.csv"
            with open(path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([" Symbol ", "ANNOUNCED_AT", "Subject"])
                writer.writerow([" aaa ", "2025-09-26", "Dividend"])
            conn = mem()
            self.assertEqual(A.import_csv(conn, str(path))["inserted"], 1)
            self.assertEqual(conn.execute(
                "SELECT symbol, announced_at FROM corporate_announcements").fetchone(),
                ("AAA", "2025-09-26 00:00:00"))


class RedFlagTests(unittest.TestCase):
    def test_window_excludes_old_announcements(self):
        conn = mem()
        A.store(conn, [item("OLD", ago(400), "Fraud detected in accounts"),
                       item("NEW", ago(3), "Pledge of promoter shares")])
        flagged = A.red_flags(conn, days=365)
        self.assertNotIn("OLD", flagged)
        self.assertIn("NEW", flagged)
        self.assertEqual(flagged["NEW"]["announcements"], 1)
        self.assertEqual(flagged["NEW"]["severity"], "high")
        self.assertEqual(flagged["NEW"]["flags"], ["promoter_pledge"])
        # days <= 0 means all history, so the old row comes back.
        self.assertIn("OLD", A.red_flags(conn, days=0))

    def test_severity_filter(self):
        conn = mem()
        A.store(conn, [item("MED", ago(1), "Impairment of goodwill"),
                       item("HIGH", ago(1), "Pledge of promoter shares")])
        default = A.red_flags(conn)
        self.assertEqual(set(default), {"MED", "HIGH"})
        only_high = A.red_flags(conn, severities=("high",))
        self.assertEqual(set(only_high), {"HIGH"})
        self.assertEqual(A.red_flags(conn, severities=("low",)), {})

    def test_latest_flags_merge_and_highest_severity_wins(self):
        conn = mem()
        A.store(conn, [item("AAA", ago(10), "Pledge of promoter shares"),
                       item("AAA", ago(2), "Credit rating downgrade by CARE"),
                       item("AAA", ago(5), "Board Meeting Intimation")])
        entry = A.red_flags(conn)["AAA"]
        self.assertEqual(entry["announcements"], 2)  # low board meeting not counted
        self.assertEqual(entry["severity"], "high")
        self.assertEqual(entry["latest"], ago(2))
        self.assertEqual(sorted(entry["flags"]), ["promoter_pledge", "rating_downgrade"])

    def test_empty_table_returns_empty_mapping(self):
        self.assertEqual(A.red_flags(sqlite3.connect(":memory:")), {})


class ReportTests(unittest.TestCase):
    def test_counts_and_sample(self):
        conn = mem()
        A.store(conn, [item(f"HH{i}", ago(i + 1), "Pledge of promoter shares")
                       for i in range(12)] +
                      [item("MM1", ago(1), "Credit rating downgrade"),
                       item("LL1", ago(1), "Board Meeting Intimation")])
        result = A.report(conn, days=365)
        self.assertEqual(result["total"], 14)
        self.assertEqual(result["by_severity"],
                         {"none": 0, "low": 1, "medium": 1, "high": 12})
        self.assertEqual(result["by_flag"]["promoter_pledge"], 12)
        self.assertEqual(result["symbols"], 14)
        self.assertLessEqual(len(result["high_risk_sample"]), 10)
        self.assertTrue(all(row["flags"] for row in result["high_risk_sample"]))
        self.assertIsNotNone(result["latest_fetch"])

    def test_empty_and_absent_table_return_clean_zeros(self):
        for conn in (mem(), sqlite3.connect(":memory:")):
            result = A.report(conn)
            self.assertEqual(result["total"], 0)
            self.assertEqual(result["by_severity"],
                             {"none": 0, "low": 0, "medium": 0, "high": 0})
            self.assertEqual(result["by_flag"], {})
            self.assertIsNone(result["latest_fetch"])
            self.assertEqual(result["symbols"], 0)
            self.assertEqual(result["high_risk_sample"], [])

    def test_ensure_tables_is_idempotent(self):
        conn = mem()
        A.ensure_tables(conn)
        A.ensure_tables(conn)
        columns = {row[1] for row in conn.execute(
            "PRAGMA table_info(corporate_announcements)")}
        self.assertEqual(columns, {"symbol", "announced_at", "subject", "category",
                                   "severity", "flags", "url", "source",
                                   "fetched_at", "raw"})


class FakeResponse:
    def __init__(self, text="", status=200, headers=None, payload=None):
        self.text = text
        self.status_code = status
        self.headers = headers if headers is not None else {
            "Content-Type": "application/json"}
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not JSON")
        return self._payload


class FakeSession:
    """Stands in for requests.Session: records calls, never opens a socket."""
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, headers=None, timeout=None, params=None):
        self.calls.append((url, dict(params or {})))
        if url.endswith("/api/corporate-announcements"):
            return self.response
        return FakeResponse("<html>home</html>",
                            headers={"Content-Type": "text/html"})

    def close(self):
        pass


class FetchTests(unittest.TestCase):
    def test_error_type_exists(self):
        self.assertTrue(issubclass(A.AnnouncementFetchError, Exception))
        self.assertIn("AnnouncementFetchError", A.__dict__)

    def test_html_response_raises(self):
        session = FakeSession(FakeResponse(
            "<html><body>Access Denied</body></html>",
            headers={"Content-Type": "text/html"}))
        with self.assertRaises(A.AnnouncementFetchError):
            A.fetch_nse("2025-09-01", "2025-09-26", session=session)

    def test_forbidden_and_empty_payloads_raise(self):
        for response in (FakeResponse("", status=403),
                         FakeResponse("[]", payload=[]),
                         FakeResponse("{}", payload={}),
                         FakeResponse("not json", payload=None)):
            session = FakeSession(response)
            with self.assertRaises(A.AnnouncementFetchError):
                A.fetch_nse("2025-09-01", "2025-09-26", session=session)

    def test_bad_date_range_raises_before_any_call(self):
        session = FakeSession(FakeResponse("[]", payload=[]))
        with self.assertRaises(A.AnnouncementFetchError):
            A.fetch_nse("nonsense", "2025-09-26", session=session)
        self.assertEqual(session.calls, [])

    def test_successful_payload_is_normalised_and_weird_rows_dropped(self):
        payload = [
            {"symbol": "reliance", "desc": "Resignation of Statutory Auditor",
             "an_dt": "26-Sep-2025 18:30:00", "attchmntFile": "/attach/1.pdf",
             "category": "Company Update"},
            {"symbol": None, "desc": "no symbol"},
            "junk",
            {"symbol": "INFY", "subject": "Board Meeting Intimation",
             "an_dt": "01-10-2025", "attchmntFile": "//cdn.nseindia.com/2.pdf"},
        ]
        session = FakeSession(FakeResponse("payload", payload=payload))
        items = A.fetch_nse("2025-09-01", "2025-10-01", session=session)
        self.assertEqual([row["symbol"] for row in items], ["RELIANCE", "INFY"])
        first, second = items
        self.assertEqual(first["announced_at"], "2025-09-26 18:30:00")
        self.assertEqual(first["url"], "https://www.nseindia.com/attach/1.pdf")
        self.assertEqual(first["source"], "nse_api")
        self.assertEqual(first["category"], "Company Update")
        self.assertEqual(json.loads(first["raw"])["symbol"], "reliance")
        self.assertEqual(second["url"], "https://cdn.nseindia.com/2.pdf")
        self.assertEqual(second["announced_at"], "2025-10-01 00:00:00")
        api_calls = [call for call in session.calls
                     if call[0].endswith("/api/corporate-announcements")]
        self.assertEqual(len(api_calls), 1)
        self.assertEqual(api_calls[0][1], {"index": "equities",
                                           "from_date": "01-09-2025",
                                           "to_date": "01-10-2025"})
        self.assertEqual(len(session.calls), 2)  # warm-up + API


if __name__ == "__main__":
    unittest.main(verbosity=2)
