import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scanx_import import (
    _apply,
    _snapshot_values,
    _zero_sentinel_fields,
)


class ScanXImportTests(unittest.TestCase):
    def _item(self, row):
        return {
            "scanx_name": "Example Co",
            "symbol": "EXAMPLE",
            "isin": "INE000A01000",
            "company_name": "Example Company Limited",
            "match_method": "normalized_exact",
            "row": row,
        }

    def test_sentinel_and_outlier_values_are_audited_but_not_promoted(self):
        row = {
            "Name": "Example Co",
            "Payout Ratio": "0",
            "Change in promoter holding": "0",
            "Average ROE 3Years": "14.2",
            "ROE Growth % (5 Year)": "5800",
            "YoY last Quarterly Sales Growth": "4266000",
            "Free Cash Flow": "1,234.50",
        }
        sentinel_fields = _zero_sentinel_fields([row])
        snapshot = _snapshot_values(
            self._item(row), "2026-09-26", sentinel_fields)
        flags = set(json.loads(snapshot["data_quality_flags"]))

        self.assertEqual(sentinel_fields, {
            "Payout Ratio", "Change in promoter holding"})
        self.assertIsNone(snapshot["payout_ratio"])
        self.assertIsNone(snapshot["promoter_holding_change"])
        self.assertEqual(snapshot["roe_avg_3y"], 14.2)
        self.assertIsNone(snapshot["roe_growth_5y"])
        self.assertIsNone(snapshot["quarter_sales_yoy_growth"])
        self.assertEqual(snapshot["free_cash_flow"], 1234.5)
        self.assertIn("out_of_range:roe_growth_5y", flags)
        self.assertIn(
            "out_of_range:quarter_sales_yoy_growth", flags)
        self.assertIn("unavailable_sentinel:payout_ratio", flags)
        self.assertEqual(json.loads(snapshot["raw_json"]), row)
        self.assertIsNone(snapshot["financial_period_end"])
        self.assertIsNone(snapshot["published_at"])

    def test_import_migrates_snapshots_without_mutating_fundamentals(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "test.db"
            conn = sqlite3.connect(database)
            conn.executescript("""
                CREATE TABLE fundamentals (
                    symbol TEXT PRIMARY KEY,
                    pe REAL,
                    uploaded_at TEXT
                );
                INSERT INTO fundamentals VALUES ('EXAMPLE', 12.5, 'legacy');
                CREATE TABLE scanx_fundamentals_snapshots (
                    as_of_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    isin TEXT,
                    scanx_name TEXT,
                    company_name TEXT,
                    sector TEXT,
                    current_price REAL,
                    market_cap_cr REAL,
                    pe REAL,
                    pb REAL,
                    roe REAL,
                    roce REAL,
                    debt_to_equity REAL,
                    operating_margin REAL,
                    net_profit_margin REAL,
                    promoter_holding REAL,
                    fii_holding REAL,
                    dii_holding REAL,
                    dividend_yield REAL,
                    operating_cash_flow REAL,
                    cfo_positive INTEGER,
                    raw_json TEXT NOT NULL,
                    match_method TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY (as_of_date, symbol)
                );
            """)
            conn.commit()
            conn.close()

            source_row = {
                "Name": "Example Co",
                "Average ROE 3Years": "14.2",
                "Free Cash Flow": "500",
            }
            snapshot = _snapshot_values(
                self._item(source_row), "2026-09-26")
            _apply(database, [snapshot], "scanx.csv")
            snapshot["free_cash_flow"] = 600
            _apply(database, [snapshot], "scanx.csv")

            conn = sqlite3.connect(database)
            self.assertEqual(
                conn.execute(
                    "SELECT pe, uploaded_at FROM fundamentals "
                    "WHERE symbol='EXAMPLE'").fetchone(),
                (12.5, "legacy"))
            self.assertEqual(
                conn.execute(
                    "SELECT count(*) FROM scanx_fundamentals_snapshots "
                    "WHERE as_of_date='2026-09-26'").fetchone()[0],
                1)
            self.assertEqual(
                conn.execute(
                    "SELECT free_cash_flow, roe_avg_3y "
                    "FROM scanx_fundamentals_snapshots "
                    "WHERE as_of_date='2026-09-26'").fetchone(),
                (600.0, 14.2))
            columns = {row[1] for row in conn.execute(
                "PRAGMA table_info(scanx_fundamentals_snapshots)")}
            self.assertIn("financial_period_end", columns)
            self.assertIn("data_quality_flags", columns)
            conn.close()


if __name__ == "__main__":
    unittest.main()
