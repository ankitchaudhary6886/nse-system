"""Offline tests for the corporate-action book (corporate_actions.py).

WHY: every number this module writes is either money-adjacent or a candidate
someone will act on, so the three behaviours that must never drift are pinned
here: (1) gap detection grades a split but refuses to invent one for a crash,
(2) a bad CSV row is skipped and counted instead of poisoning the book, and
(3) nothing in the "detect"/"explain"/"summary" paths writes or fetches.

No network, no production database. yfinance is never imported or called: the
fixtures are synthetic SQLite built from db.SCHEMA and a CSV in a temp folder.

Run from the repo root:
    .\\env\\Scripts\\python.exe -m unittest test_corporate_actions -v
"""
import datetime as dt
import os
import sqlite3
import tempfile
import unittest

import corporate_actions as CA
import db


def memory_db():
    """The real schema, in memory: data/app.db is never opened."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    return conn


def add_prices(conn, symbol, closes, start="2024-01-01"):
    """Consecutive daily closes for one symbol -> prices_daily rows."""
    day = dt.date.fromisoformat(start)
    rows = []
    for close in closes:
        rows.append((symbol, day.isoformat(), close))
        day += dt.timedelta(days=1)
    conn.executemany("INSERT OR REPLACE INTO prices_daily(symbol, date, close) "
                     "VALUES (?,?,?)", rows)
    conn.commit()
    return [row[1] for row in rows]


def write_csv(directory, lines, name="actions.csv"):
    path = os.path.join(directory, name)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.conn = memory_db()
        self.addCleanup(self.conn.close)

    def count(self, table="corporate_actions"):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ----------------------------------------------------------------------
# detect_price_gaps -- read-only, candidate-not-fact
# ----------------------------------------------------------------------

class DetectTest(Base):
    def test_synthetic_1_to_10_split(self):
        add_prices(self.conn, "SPLITCO", [100.0, 100.0, 10.0])
        found = CA.detect_price_gaps(self.conn)
        self.assertEqual(len(found), 1)
        gap = found[0]
        self.assertEqual(gap["symbol"], "SPLITCO")
        self.assertEqual(gap["date"], "2024-01-03")
        self.assertAlmostEqual(gap["prev_close"], 100.0)
        self.assertAlmostEqual(gap["close"], 10.0)
        self.assertAlmostEqual(gap["move_pct"], -90.0, places=2)
        self.assertAlmostEqual(gap["implied_ratio"], 10.0, places=3)
        self.assertEqual(gap["ratio_match"], 10.0)
        self.assertEqual(gap["direction"], "down")
        self.assertEqual(gap["kind_guess"], "split_or_bonus")

    def test_no_candidate_for_five_percent_move(self):
        add_prices(self.conn, "QUIET", [100.0, 105.0, 99.75])
        self.assertEqual(CA.detect_price_gaps(self.conn), [])

    def test_unexplained_crash_is_unknown_event(self):
        add_prices(self.conn, "CRASH", [100.0, 75.0])
        found = CA.detect_price_gaps(self.conn)
        self.assertEqual(len(found), 1)
        gap = found[0]
        self.assertAlmostEqual(gap["move_pct"], -25.0, places=2)
        self.assertAlmostEqual(gap["implied_ratio"], 1.3333, places=4)
        self.assertIsNone(gap["ratio_match"])
        self.assertEqual(gap["kind_guess"], "unknown_event")

    def test_up_move_is_recorded_as_up_direction(self):
        add_prices(self.conn, "JUMP", [100.0, 130.0])
        gap = CA.detect_price_gaps(self.conn)[0]
        self.assertEqual(gap["direction"], "up")
        self.assertLess(gap["implied_ratio"], 1.0)
        self.assertIsNone(gap["ratio_match"])
        self.assertEqual(gap["kind_guess"], "unknown_event")

    def test_empty_db_returns_empty_list(self):
        self.assertEqual(CA.detect_price_gaps(self.conn), [])

    def test_detect_writes_nothing(self):
        add_prices(self.conn, "SPLITCO", [100.0, 10.0])
        self.assertEqual(len(CA.detect_price_gaps(self.conn)), 1)
        self.assertEqual(self.count(), 0)

    def test_limit_caps_symbols_alphabetically(self):
        add_prices(self.conn, "ZZZ", [100.0, 10.0])
        add_prices(self.conn, "AAA", [100.0, 10.0])
        found = CA.detect_price_gaps(self.conn, limit=1)
        self.assertEqual([gap["symbol"] for gap in found], ["AAA"])

    def test_symbols_filter_is_normalised(self):
        add_prices(self.conn, "AAA", [100.0, 10.0])
        add_prices(self.conn, "ZZZ", [100.0, 10.0])
        found = CA.detect_price_gaps(self.conn, symbols=[" aaa "])
        self.assertEqual([gap["symbol"] for gap in found], ["AAA"])


# ----------------------------------------------------------------------
# import_csv -- authoritative only when a human typed it
# ----------------------------------------------------------------------

BAD_CSV = [
    "Symbol,Ex_Date,Kind,Ratio,Amount",       # header is case-insensitive
    "ABC,2024-06-14,split,10,",               # valid
    "ABC,2024-07-01,dividend,,5",             # valid
    "ABC,14-06-2024,split,10,",               # bad date
    "XYZ,2024-06-14,merger,2,",               # unknown kind
    "XYZ,2024-06-14,split,-2,",               # negative ratio
    "XYZ,2024-06-14,dividend,,",              # missing amount
    "A$B,2024-06-14,split,2,",                # bad symbol
]


class ImportCsvTest(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = write_csv(self.tmp.name, BAD_CSV)

    def test_valid_rows_imported_bad_rows_counted(self):
        result = CA.import_csv(self.conn, self.path)
        self.assertEqual(result["file"], self.path)
        self.assertEqual(result["rows_seen"], 7)
        self.assertEqual(result["imported"], 2)
        self.assertEqual(result["skipped"], 5)
        self.assertEqual(result["by_kind"], {"split": 1, "dividend": 1})
        self.assertEqual(self.count(), 2)

        split = self.conn.execute(
            "SELECT ratio, amount, source, status, recorded_at, raw "
            "FROM corporate_actions WHERE symbol='ABC' AND kind='split'"
        ).fetchone()
        self.assertAlmostEqual(split[0], 10.0)
        self.assertIsNone(split[1])
        self.assertEqual(split[2], "manual_csv")
        self.assertEqual(split[3], "confirmed_source")
        self.assertTrue(split[4])
        self.assertIn("ABC", split[5])

        dividend = self.conn.execute(
            "SELECT ratio, amount FROM corporate_actions "
            "WHERE symbol='ABC' AND kind='dividend'").fetchone()
        self.assertIsNone(dividend[0])
        self.assertAlmostEqual(dividend[1], 5.0)

    def test_second_import_is_idempotent(self):
        CA.import_csv(self.conn, self.path)
        again = CA.import_csv(self.conn, self.path)
        self.assertEqual(again["imported"], 2)
        self.assertEqual(again["skipped"], 5)
        self.assertEqual(self.count(), 2)   # primary key, not duplicates

    def test_missing_header_column_raises(self):
        path = write_csv(self.tmp.name, ["symbol,ex_date", "ABC,2024-06-14"],
                         name="bad_header.csv")
        with self.assertRaises(ValueError):
            CA.import_csv(self.conn, path)
        self.assertEqual(self.count(), 0)


# ----------------------------------------------------------------------
# merge_actions -- provenance comes from the caller
# ----------------------------------------------------------------------

class MergeTest(Base):
    def test_inserted_then_updated(self):
        actions = [
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "split",
             "ratio": 10.0, "source": "yfinance", "status": "unconfirmed"},
            {"symbol": "ABC", "ex_date": "2024-07-01", "kind": "dividend",
             "amount": 5.0, "source": "manual_csv",
             "status": "confirmed_source"},
        ]
        first = CA.merge_actions(self.conn, actions)
        self.assertEqual(first, {"inserted": 2, "updated": 0})

        actions[0]["ratio"] = 5.0
        second = CA.merge_actions(self.conn, actions)
        self.assertEqual(second, {"inserted": 0, "updated": 2})
        self.assertEqual(self.count(), 2)
        row = self.conn.execute(
            "SELECT ratio, source, status FROM corporate_actions "
            "WHERE symbol='ABC' AND kind='split'").fetchone()
        self.assertAlmostEqual(row[0], 5.0)
        self.assertEqual(row[1], "yfinance")     # preserved, not overwritten
        self.assertEqual(row[2], "unconfirmed")

    def test_unusable_actions_are_dropped(self):
        counts = CA.merge_actions(self.conn, [
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "split",
             "ratio": -10.0},
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "dividend"},
            {"symbol": "A$B", "ex_date": "2024-06-14", "kind": "split",
             "ratio": 2.0},
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "merger",
             "ratio": 2.0},
        ])
        self.assertEqual(counts, {"inserted": 0, "updated": 0})
        self.assertEqual(self.count(), 0)


# ----------------------------------------------------------------------
# explain -- what the ingest guards print when they refuse
# ----------------------------------------------------------------------

class ExplainTest(Base):
    def setUp(self):
        super().setUp()
        add_prices(self.conn, "ABC", [100.0] * 30, start="2024-06-01")
        CA.merge_actions(self.conn, [
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "split",
             "ratio": 10.0, "source": "manual_csv",
             "status": "confirmed_source"}])

    def test_action_within_window(self):
        answer = CA.explain(self.conn, "abc", "2024-06-16")
        self.assertEqual(answer["symbol"], "ABC")
        self.assertEqual(answer["date"], "2024-06-16")
        self.assertEqual(answer["days_apart"], 2)
        self.assertEqual(answer["action"]["kind"], "split")
        self.assertAlmostEqual(answer["action"]["ratio"], 10.0)
        dates = [row["date"] for row in answer["closes"]]
        self.assertIn("2024-06-16", dates)
        self.assertEqual(dates, sorted(dates))
        self.assertTrue(all("2024-06-06" <= d <= "2024-06-26" for d in dates))

    def test_no_action_outside_window(self):
        answer = CA.explain(self.conn, "ABC", "2024-08-30")
        self.assertIsNone(answer["action"])
        self.assertIsNone(answer["days_apart"])
        self.assertEqual(answer["closes"], [])

    def test_rejected_action_is_not_an_explanation(self):
        CA.merge_actions(self.conn, [
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "bonus",
             "ratio": 2.0, "status": "rejected"}])
        answer = CA.explain(self.conn, "ABC", "2024-06-14")
        self.assertEqual(answer["action"]["kind"], "split")

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            CA.explain(self.conn, "ABC", "14-06-2024")


# ----------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------

class SummaryTest(Base):
    def test_counts_by_status_and_kind(self):
        CA.merge_actions(self.conn, [
            {"symbol": "ABC", "ex_date": "2024-06-14", "kind": "split",
             "ratio": 10.0, "source": "yfinance", "status": "unconfirmed"},
            {"symbol": "ABC", "ex_date": "2024-07-01", "kind": "dividend",
             "amount": 5.0, "source": "manual_csv",
             "status": "confirmed_source"},
            {"symbol": "XYZ", "ex_date": "2024-05-02", "kind": "bonus",
             "ratio": 2.0, "source": "yfinance", "status": "rejected"},
        ])
        report = CA.summary(self.conn)
        self.assertEqual(report["actions"], 3)
        self.assertEqual(report["by_status"],
                         {"confirmed_source": 1, "rejected": 1,
                          "unconfirmed": 1})
        self.assertEqual(report["by_kind"],
                         {"bonus": 1, "dividend": 1, "split": 1})
        self.assertEqual(report["by_source"], {"manual_csv": 1, "yfinance": 2})
        self.assertEqual(report["earliest_ex_date"], "2024-05-02")
        self.assertEqual(report["latest_ex_date"], "2024-07-01")
        self.assertEqual(report["symbols"], 2)
        self.assertEqual(report["gap_candidates_60s"], 0)
        self.assertEqual(report["gap_scan"]["method"], "no_prices")

    def test_recent_gap_candidates_are_counted(self):
        add_prices(self.conn, "GAPCO", [100.0, 100.0, 10.0])
        report = CA.summary(self.conn)
        self.assertEqual(report["gap_candidates_60s"], 1)
        self.assertEqual(report["gap_scan"]["method"], "window_sql")
        self.assertEqual(report["gap_scan"]["sessions"], 3)


# ----------------------------------------------------------------------
# offline guarantee
# ----------------------------------------------------------------------

class OfflineTest(unittest.TestCase):
    def test_yfinance_is_never_imported_at_module_level(self):
        with open(CA.__file__, encoding="utf-8") as handle:
            top_level = [line for line in handle.read().splitlines()
                         if line.startswith(("import yfinance",
                                            "from yfinance"))]
        self.assertEqual(top_level, [])
        self.assertFalse(hasattr(CA, "yf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
