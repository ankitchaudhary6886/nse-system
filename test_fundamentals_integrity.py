import json
import sqlite3
import unittest

from fundamentals_store import integrity_report, merge
from fundamentals_tv import _fundamentals_values
from fundamentals_refresh import ALIASES, _upsert


class FundamentalsIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE fundamentals (
                symbol TEXT PRIMARY KEY, name TEXT, sector TEXT,
                current_price REAL, market_cap_cr REAL, pe REAL, pb REAL,
                roe REAL, roce REAL, roic REAL, debt_to_equity REAL,
                interest_coverage REAL, operating_margin REAL,
                net_profit_margin REAL, sales_growth_3y REAL,
                profit_growth_3y REAL, promoter_holding REAL,
                pledge_pct REAL, fii_holding REAL, dividend_yield REAL,
                cfo_positive INTEGER, uploaded_at TEXT, beta_1y REAL,
                eps_fy REAL, book_value REAL, ev_ebitda REAL, fcf_fy REAL,
                net_debt_fy REAL, data_source TEXT, field_sources TEXT,
                field_updated_at TEXT, data_quality_flags TEXT,
                source_metadata TEXT
            )
        """)

    def tearDown(self):
        self.conn.close()

    def test_tradingview_roic_is_not_mislabeled_as_roce_or_cfo(self):
        metrics = {
            "close": 100, "book_value_per_share_fy": 50,
            "return_on_equity_fy": 12,
            "return_on_invested_capital_fy": 16,
            "free_cash_flow_fy": -5,
        }
        values = _fundamentals_values(
            "EXAMPLE", metrics, {}, "2026-09-30T12:00:00+00:00")

        self.assertEqual(values["roic"], 16)
        self.assertNotIn("roce", values)
        self.assertNotIn("cfo_positive", values)
        self.assertEqual(values["fcf_fy"], -5)

    def test_merge_preserves_missing_fields_and_tracks_each_field_source(self):
        merge(self.conn, {
            "symbol": "EXAMPLE", "roe": 12, "pe": 18,
        }, source="source_a", observed_at="2026-09-29")
        merge(self.conn, {
            "symbol": "EXAMPLE", "roe": None, "pe": 20,
        }, source="source_b", observed_at="2026-09-30")

        row = self.conn.execute(
            "SELECT roe,pe,data_source,field_sources,field_updated_at "
            "FROM fundamentals WHERE symbol='EXAMPLE'").fetchone()
        self.assertEqual(row[:3], (12, 20, "source_b"))
        self.assertEqual(json.loads(row[3]), {"pe": "source_b", "roe": "source_a"})
        self.assertEqual(
            json.loads(row[4]),
            {"pe": "2026-09-30", "roe": "2026-09-29"})

    def test_csv_refresh_maps_roe_and_market_cap_to_distinct_columns(self):
        self.assertEqual(ALIASES["return_on_equity"], "roe")
        self.assertEqual(ALIASES["return_on_capital_employed"], "roce")
        self.assertEqual(ALIASES["mcap_cr"], "market_cap_cr")

        _upsert(self.conn, {"symbol": "EXAMPLE", "roe": 14},
                "fundamentals_csv")
        merge(self.conn, {"symbol": "EXAMPLE", "roce": 9},
              source="calculated")
        row = self.conn.execute(
            "SELECT roe,roce FROM fundamentals WHERE symbol='EXAMPLE'"
        ).fetchone()
        self.assertEqual(row, (14, 9))

    def test_integrity_report_flags_legacy_tradingview_proxy_values(self):
        merge(self.conn, {
            "symbol": "LEGACY", "roce": 15, "cfo_positive": 1,
        }, source="tradingview")
        report = integrity_report(self.conn)

        self.assertTrue(report["remediation_needed"])
        self.assertEqual(report["rows"][0]["symbol"], "LEGACY")
        self.assertIn(
            "cfo_positive may be an historical FCF sign proxy",
            report["rows"][0]["reasons"])
        self.assertIn(
            "roce may contain return_on_invested_capital_fy",
            report["rows"][0]["reasons"])


if __name__ == "__main__":
    unittest.main()
