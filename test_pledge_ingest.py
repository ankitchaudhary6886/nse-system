"""Offline tests for pledge_ingest: in-memory SQLite only, never data/app.db.

No network is used anywhere here: the NSE fetcher is exercised through a fake
session that returns HTML, which is exactly what NSE serves to a blocked IP.
"""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pledge_ingest
from pledge_ingest import (
    PledgeFetchError,
    apply_to_fundamentals,
    ensure_tables,
    fetch_nse_pledge_xbrl,
    fetch_nse_shareholding,
    fetch_shareholding,
    import_csv,
    parse_shareholding_xbrl,
    report,
)


def seed_fundamentals(conn, symbol=None, **fields):
    """Create the fundamentals row/table shape db.py migrates to."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS fundamentals ("
        "symbol TEXT PRIMARY KEY, name TEXT, sector TEXT, current_price REAL, "
        "market_cap_cr REAL, pe REAL, pb REAL, roe REAL, roce REAL, "
        "debt_to_equity REAL, interest_coverage REAL, operating_margin REAL, "
        "net_profit_margin REAL, sales_growth_3y REAL, profit_growth_3y REAL, "
        "promoter_holding REAL, pledge_pct REAL, fii_holding REAL, "
        "dividend_yield REAL, cfo_positive INTEGER, uploaded_at TEXT, "
        "data_source TEXT, field_sources TEXT, field_updated_at TEXT, "
        "data_quality_flags TEXT, source_metadata TEXT)")
    if symbol:
        keys = ", ".join(["symbol"] + list(fields))
        marks = ",".join("?" * (len(fields) + 1))
        conn.execute(f"INSERT INTO fundamentals ({keys}) VALUES ({marks})",
                     [symbol] + list(fields.values()))
    conn.commit()


def seed_universe(conn, rows):
    conn.execute("CREATE TABLE IF NOT EXISTS universe_broad ("
                 "symbol TEXT PRIMARY KEY, name TEXT, mcap_cr REAL)")
    conn.executemany("INSERT OR REPLACE INTO universe_broad (symbol, mcap_cr) "
                     "VALUES (?,?)", rows)
    conn.commit()


class FakeResponse:
    def __init__(self, text="<html>blocked</html>", status_code=200, payload=None):
        self.text, self.status_code, self._payload = text, status_code, payload

    def json(self):
        if self._payload is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


class FakeSession:
    """Returns HTML for every URL, like NSE does to a cloud IP."""

    def __init__(self):
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        return FakeResponse()


# --- inline XBRL fixtures (no network, no files) ---------------------------
SHP_NS = "http://www.bseindia.com/xbrl/taxonomy/2022-03-31/in-bse-shp"
PROMOTER_CTX = "ShareholdingOfPromoterAndPromoterGroup_ContextI"
PATTERN_CTX = "ShareholdingPattern_ContextI"
PROMOTER_MEMBER = "in-bse-shp:ShareholdingOfPromoterAndPromoterGroupMember"
PATTERN_MEMBER = "in-bse-shp:ShareholdingPatternMember"
PLEDGE_PCT = "EncumberedShareUnderPledgedAsPercentageOfTotalNumberOfShares"
PLEDGE_SHARES = "NumberOfSharesEncumberedUnderPledged"
HOLDING_PCT = "ShareholdingAsAPercentageOfTotalNumberOfShares"
TOTAL_SHARES = "NumberOfShares"


def shp_xbrl(facts, contexts=None, prefix="in-bse-shp", ns=SHP_NS, default_ns=True):
    """A minimal BSE/NSE shareholding XBRL instance as a string.

    *facts*: ``(tag, contextRef, text)`` triples. *contexts*: ``id -> {"instant"|"end",
    "member"}``. The prefix/namespace knobs exist so the parser can be shown instances
    that do not look byte-identical to the ones NSE serves today.
    """
    contexts = contexts if contexts is not None else {
        PROMOTER_CTX: {"instant": "2026-06-30", "member": PROMOTER_MEMBER}}
    head = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
            f'xmlns:{prefix}="{ns}"'
            + (' xmlns="http://www.xbrl.org/2003/instance"' if default_ns else "")
            + '>']
    body = []
    for context_id, spec in contexts.items():
        member = (f'<xbrli:segment><xbrldi:explicitMember dimension="{prefix}:Axis">'
                  f"{spec['member']}</xbrldi:explicitMember></xbrli:segment>"
                  if spec.get("member") else "")
        if spec.get("end"):
            period = (f'<xbrli:period><xbrli:startDate>{spec.get("start", "2026-04-01")}'
                      f'</xbrli:startDate><xbrli:endDate>{spec["end"]}</xbrli:endDate>'
                      '</xbrli:period>')
        else:
            period = (f'<xbrli:period><xbrli:instant>{spec["instant"]}</xbrli:instant>'
                      '</xbrli:period>')
        body.append(f'<xbrli:context id="{context_id}"><xbrli:entity><xbrli:identifier '
                    f'scheme="http://www.bseindia.com/ICAI">INE351F01018'
                    f'</xbrli:identifier>{member}</xbrli:entity>{period}</xbrli:context>')
    for tag, context_id, value in facts:
        body.append(f'<{prefix}:{tag} contextRef="{context_id}">{value}</{prefix}:{tag}>')
    return "".join(head + body) + "</xbrl>"


def jppower_xbrl():
    """JPPOWER's live facts, reduced: the same pledge count in four contexts, and the
    promoter block's ratio (0.7299 = 1200509465/1644830118) next to the whole-pattern
    ratio (0.1752) that a careless parser would pick up instead."""
    facts = [(PLEDGE_SHARES, PROMOTER_CTX, "1200509465"),
             (PLEDGE_PCT, PROMOTER_CTX, "0.7299"),
             (TOTAL_SHARES, PROMOTER_CTX, "1644830118"),
             (HOLDING_PCT, PROMOTER_CTX, "0.24"),
             (PLEDGE_SHARES, PATTERN_CTX, "1200509465"),
             (PLEDGE_PCT, PATTERN_CTX, "0.1752"),
             (TOTAL_SHARES, PATTERN_CTX, "6853458827"),
             (HOLDING_PCT, PATTERN_CTX, "1")]
    contexts = {PROMOTER_CTX: {"instant": "2026-06-30", "member": PROMOTER_MEMBER},
                PATTERN_CTX: {"instant": "2026-06-30", "member": PATTERN_MEMBER}}
    return shp_xbrl(facts, contexts)


def master_record(date="30-JUN-2026", xbrl="https://nsearchives.nseindia.com/corporate/xbrl/"
                                           "JPPOWER.xml", pr="24", submitted="13-JUL-2026"):
    """One record of the corporate-share-holdings-master JSON feed."""
    return {"date": date, "xbrl": xbrl, "pr_and_prgrp": pr, "symbol": "JPPOWER",
            "submissionDate": submitted, "broadcastDate": "13-JUL-2026 15:57:22",
            "xbrlFileSize": 134337}


class XmlResponse:
    """A 200 XML body carrying both bytes and text, like requests does."""

    def __init__(self, document, status_code=200):
        self.text, self.content, self.status_code = document, document.encode("utf-8"), status_code


class FakeNseSession:
    """Warmed-session stand-in: the master JSON feed and XBRL archives, routed by URL."""

    def __init__(self, masters=None, xbrl=None, broken=()):
        self.calls, self.masters, self.xbrl = [], masters or {}, xbrl or {}
        self.broken = set(broken)

    def get(self, url, timeout=None):
        self.calls.append(url)
        symbol = url.rsplit("symbol=", 1)[-1] if "symbol=" in url else ""
        if symbol and symbol in self.broken:
            raise RuntimeError("connection reset")
        if "corporate-share-holdings-master" in url:
            return FakeResponse(payload=self.masters.get(symbol, []), text="")
        for name, document in self.xbrl.items():
            if name in url:
                return XmlResponse(document)
        return FakeResponse()  # HTML, like a blocked endpoint


class TableTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_ensure_tables_is_idempotent(self):
        ensure_tables(self.conn)
        ensure_tables(self.conn)
        columns = [row[1] for row in self.conn.execute(
            "PRAGMA table_info(shareholding_pledge)")]
        self.assertEqual(columns, ["symbol", "as_of_date", "promoter_pledge_pct",
                                   "promoter_holding_pct", "source", "imported_at", "raw"])
        indexes = [row[1] for row in self.conn.execute(
            "PRAGMA index_list(shareholding_pledge)")]
        self.assertTrue(any("symbol" in name for name in indexes))
        primary = [row[1] for row in self.conn.execute(
            "PRAGMA table_info(shareholding_pledge)") if row[5]]
        self.assertEqual(primary, ["symbol", "as_of_date"])


class CsvImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_tables(self.conn)
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()
        self.conn.close()

    def write_csv(self, rows, header="symbol,as_of_date,promoter_pledge_pct,promoter_holding_pct"):
        path = Path(self.temp.name) / "pledge.csv"
        path.write_text("\n".join([header] + rows) + "\n", encoding="utf-8")
        return path

    def test_valid_rows_import_and_upsert(self):
        path = self.write_csv(["abc,2026-06-30,12.5,55", "BBB,31-Mar-2026,0,48.2"])
        result = import_csv(self.conn, path)
        self.assertEqual(result, {"rows_seen": 2, "imported": 2, "skipped": 0,
                                  "symbols": ["ABC", "BBB"]})
        row = self.conn.execute(
            "SELECT symbol, as_of_date, promoter_pledge_pct, promoter_holding_pct, source "
            "FROM shareholding_pledge WHERE symbol='ABC'").fetchone()
        self.assertEqual(row, ("ABC", "2026-06-30", 12.5, 55.0, "manual_csv"))

    def test_holding_column_is_optional(self):
        path = self.write_csv(["ABC,2026-06-30,7.25"], header="symbol,as_of_date,promoter_pledge_pct")
        self.assertEqual(import_csv(self.conn, path)["imported"], 1)
        self.assertIsNone(self.conn.execute(
            "SELECT promoter_holding_pct FROM shareholding_pledge").fetchone()[0])

    def test_invalid_rows_are_skipped_not_fatal(self):
        path = self.write_csv([
            "ABC,2026-06-30,12.5,55",       # good
            "ABC,2026-06-30,140,55",        # pledge out of range
            "ABC,not-a-date,12,55",         # bad date
            ",2026-06-30,12,55",            # no symbol
            "ABC,2026-06-30,12,abc",        # holding not a number
            "ABC,2026-06-30,,55",           # pledge missing
        ])
        result = import_csv(self.conn, path)
        self.assertEqual(result["rows_seen"], 6)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skipped"], 5)
        self.assertEqual(result["symbols"], ["ABC"])
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM shareholding_pledge").fetchone()[0], 1)

    def test_out_of_range_pledge_is_rejected(self):
        path = self.write_csv(["ABC,2026-06-30,140"])
        result = import_csv(self.conn, path)
        self.assertEqual(result["imported"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM shareholding_pledge").fetchone()[0], 0)

    def test_reimport_is_idempotent(self):
        path = self.write_csv(["ABC,2026-06-30,12.5,55"])
        first = import_csv(self.conn, path)
        second = import_csv(self.conn, path)
        self.assertEqual(first, second)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM shareholding_pledge").fetchone()[0], 1)
        self.assertEqual(self.conn.execute(
            "SELECT promoter_pledge_pct FROM shareholding_pledge").fetchone()[0], 12.5)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            import_csv(self.conn, Path(self.temp.name) / "absent.csv")


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_tables(self.conn)
        seed_fundamentals(self.conn)
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()
        self.conn.close()

    def import_rows(self, rows):
        path = Path(self.temp.name) / "p.csv"
        path.write_text("symbol,as_of_date,promoter_pledge_pct,promoter_holding_pct\n"
                        + "\n".join(rows) + "\n", encoding="utf-8")
        return import_csv(self.conn, path)

    def test_dry_run_writes_nothing(self):
        self.import_rows(["ABC,2026-06-30,18.4,52"])
        seed_fundamentals(self.conn, "ABC")
        result = apply_to_fundamentals(self.conn, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["candidates"], 1)
        self.assertEqual(result["pledge_filled"], 1)
        self.assertEqual(result["rows_touched"], 1)
        self.assertEqual(result["coverage_after"]["pledge_pct"], 1)  # projected
        row = self.conn.execute(
            "SELECT pledge_pct, promoter_holding FROM fundamentals WHERE symbol='ABC'").fetchone()
        self.assertEqual(row, (None, None))

    def test_apply_writes_value_source_and_flags(self):
        self.import_rows(["ABC,2026-06-30,18.4,52"])
        seed_fundamentals(self.conn, "ABC")
        result = apply_to_fundamentals(self.conn, dry_run=False)
        self.assertFalse(result["dry_run"])
        self.assertEqual(result["rows_touched"], 1)
        row = self.conn.execute(
            "SELECT pledge_pct, promoter_holding, field_sources, data_quality_flags "
            "FROM fundamentals WHERE symbol='ABC'").fetchone()
        self.assertEqual(row[0], 18.4)
        self.assertEqual(row[1], 52.0)
        sources = json.loads(row[2])
        self.assertEqual(sources["pledge_pct"], "shareholding:2026-06-30")
        self.assertEqual(sources["promoter_holding"], "shareholding:2026-06-30")
        flags = set(json.loads(row[3])["flags"])
        self.assertEqual(flags, {"filed_shareholding", "point_in_time"})
        self.assertEqual(result["coverage_after"], {"pledge_pct": 1, "promoter_holding": 1})

    def test_existing_promoter_holding_is_kept_unless_overwrite(self):
        self.import_rows(["ABC,2026-06-30,18.4,52"])
        seed_fundamentals(self.conn, "ABC", promoter_holding=55.0)
        result = apply_to_fundamentals(self.conn, dry_run=False)
        self.assertEqual(result["kept_existing"], 1)
        self.assertEqual(result["promoter_filled"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT promoter_holding FROM fundamentals WHERE symbol='ABC'").fetchone()[0], 55.0)
        forced = apply_to_fundamentals(self.conn, overwrite=True, dry_run=False)
        self.assertEqual(forced["promoter_filled"], 1)
        self.assertEqual(forced["kept_existing"], 0)
        self.assertEqual(self.conn.execute(
            "SELECT promoter_holding FROM fundamentals WHERE symbol='ABC'").fetchone()[0], 52.0)

    def test_latest_as_of_row_wins(self):
        self.import_rows(["ABC,2026-03-31,5.0,50", "ABC,2026-06-30,9.5,49"])
        seed_fundamentals(self.conn, "ABC")
        apply_to_fundamentals(self.conn, dry_run=False)
        row = self.conn.execute(
            "SELECT pledge_pct, field_sources FROM fundamentals WHERE symbol='ABC'").fetchone()
        self.assertEqual(row[0], 9.5)
        self.assertEqual(json.loads(row[1])["pledge_pct"], "shareholding:2026-06-30")

    def test_apply_without_rows_warns_instead_of_crashing(self):
        seed_fundamentals(self.conn, "ABC")
        result = apply_to_fundamentals(self.conn, dry_run=False)
        self.assertEqual(result["candidates"], 0)
        self.assertIn("holds no rows", result["warning"])

    def test_apply_creates_a_sparse_row_when_symbol_is_unknown(self):
        self.import_rows(["NEWCO,2026-06-30,4.2,60"])
        apply_to_fundamentals(self.conn, dry_run=False)
        self.assertEqual(self.conn.execute(
            "SELECT pledge_pct FROM fundamentals WHERE symbol='NEWCO'").fetchone()[0], 4.2)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        ensure_tables(self.conn)
        seed_fundamentals(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_report_maths_and_high_pledge_list(self):
        seed_fundamentals(self.conn, "HIGH", pledge_pct=40.0)
        seed_fundamentals(self.conn, "LOW", pledge_pct=5.0)
        seed_fundamentals(self.conn, "NONE")
        seed_universe(self.conn, [("HIGH", 2000.0), ("LOW", 3000.0)])
        self.conn.executemany(
            "INSERT OR REPLACE INTO shareholding_pledge (symbol, as_of_date, "
            "promoter_pledge_pct, promoter_holding_pct, source, imported_at, raw) "
            "VALUES (?,?,?,?,?,?,?)",
            [("HIGH", "2026-06-30", 40.0, 60.0, "nse", "2026-07-16", "{}"),
             ("LOW", "2026-03-31", 5.0, 50.0, "manual_csv", "2026-04-02", "{}")])
        self.conn.commit()
        out = report(self.conn)
        self.assertEqual(out["rows"], 2)
        self.assertEqual(out["symbols"], 2)
        self.assertEqual(out["latest_as_of"], "2026-06-30")
        self.assertEqual(out["sources"], {"nse": 1, "manual_csv": 1})
        self.assertEqual(out["fundamentals_rows"], 3)
        self.assertEqual(out["coverage"]["pledge_pct"]["non_null"], 2)
        self.assertEqual(out["coverage"]["pledge_pct"]["pct"], 66.7)
        self.assertEqual(out["band"]["total"], 2)
        self.assertEqual(out["band"]["pledge_pct"]["covered"], 2)
        self.assertEqual(out["band"]["pledge_pct"]["pct"], 100.0)
        self.assertEqual(out["veto_threshold"], 25.0)
        self.assertEqual(out["high_pledge"], [{"symbol": "HIGH", "pledge_pct": 40.0,
                                               "as_of_date": "2026-06-30", "source": "nse"}])
        self.assertIn("age_days", out["freshness"])
        self.assertEqual(out["freshness"]["by_source"]["manual_csv"], "2026-03-31")
        self.assertTrue(out["pit_valid"])

    def test_report_on_an_empty_database_is_read_only_and_safe(self):
        out = report(self.conn)
        self.assertEqual(out["rows"], 0)
        self.assertEqual(out["coverage"]["pledge_pct"]["non_null"], 0)
        self.assertEqual(out["high_pledge"], [])
        self.assertIsNone(out["latest_as_of"])
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM shareholding_pledge").fetchone()[0], 0)


class FetchTests(unittest.TestCase):
    def test_fetch_raises_pledge_fetch_error_on_html(self):
        session = FakeSession()
        with self.assertRaises(PledgeFetchError) as caught:
            fetch_nse_shareholding(["INFY"], session=session, sleep_seconds=0)
        message = str(caught.exception)
        self.assertIn("import --file", message)
        self.assertIn("INFY", message)
        self.assertGreaterEqual(len(session.calls), 2)  # every candidate was tried

    def test_batch_survives_a_single_bad_symbol(self):
        class HalfBroken(FakeSession):
            def get(self, url, timeout=None):
                self.calls.append(url)
                if "symbol=BAD" in url:
                    raise RuntimeError("connection reset")
                return FakeResponse(payload=[{"date": "30-JUN-2026", "pr_and_prgrp": "13.82",
                                              "promoterPledgePercentage": "0.73"}])

        rows = fetch_nse_shareholding(["BAD", "GOOD"], session=HalfBroken(), sleep_seconds=0)
        self.assertEqual([row["symbol"] for row in rows], ["GOOD"])
        self.assertEqual(rows[0]["as_of_date"], "2026-06-30")
        self.assertEqual(rows[0]["promoter_holding_pct"], 13.82)
        self.assertEqual(rows[0]["promoter_pledge_pct"], 0.73)
        self.assertEqual(rows[0]["source"], "nse")

    def test_no_symbols_is_an_actionable_error(self):
        with self.assertRaises(PledgeFetchError):
            fetch_nse_shareholding(["", "  "], session=FakeSession(), sleep_seconds=0)


class PercentHeuristicTests(unittest.TestCase):
    def test_percent_versus_fraction_versus_reject(self):
        pct = pledge_ingest._pct
        self.assertEqual(pct("13.82"), 13.82)            # NSE JSON quotes percent
        self.assertEqual(pct("0.73%"), 0.73)             # explicit unit wins
        self.assertEqual(pct(1.0), 1.0)                  # 1% is not 100%
        self.assertEqual(pct(0.42, key="promoterPledgeRatio"), 42.0)  # fraction
        self.assertIsNone(pct(140))                      # never clamped
        self.assertIsNone(pct("1200509465"))             # share count, not a rate
        self.assertIsNone(pct(None))
        self.assertIsNone(pct("n/a"))


class XbrlParseTests(unittest.TestCase):
    """The XBRL instance is where the pledge lives; these are all inline strings."""

    @staticmethod
    def parse(facts, contexts=None, **kwargs):
        return parse_shareholding_xbrl(shp_xbrl(facts, contexts, **kwargs))

    def test_promoter_context_pledge_percentage_is_extracted(self):
        parsed = parse_shareholding_xbrl(jppower_xbrl())
        # 0.7299 is a fraction of the promoter block: 1200509465/1644830118 == 72.99%,
        # and the master JSON's 0.24 == 24% proves the instance stores fractions.
        self.assertAlmostEqual(parsed["promoter_pledge_pct"], 72.99, places=4)
        self.assertAlmostEqual(parsed["promoter_holding_pct"], 24.0, places=4)
        self.assertEqual(parsed["raw"]["pledge_context"], PROMOTER_CTX)
        self.assertTrue(parsed["raw"]["pledge_context_promoter"])
        self.assertEqual(parsed["raw"]["pledge_pct_fact"], 0.7299)  # raw stays untouched
        self.assertAlmostEqual(parsed["raw"]["pledge_pct_from_shares"], 72.9869, places=3)

    def test_share_count_is_never_a_percentage(self):
        parsed = self.parse([(PLEDGE_SHARES, PROMOTER_CTX, "1200509465")])
        self.assertIsNone(parsed["promoter_pledge_pct"])  # no denominator -> unknown
        self.assertEqual(parsed["raw"]["pledge_shares"], 1200509465)
        self.assertIsNone(parsed["raw"]["pledge_pct_fact"])

    def test_shares_and_promoter_total_compute_the_percentage(self):
        parsed = self.parse([(PLEDGE_SHARES, PROMOTER_CTX, "7300000"),
                             (TOTAL_SHARES, PROMOTER_CTX, "1000000000")])
        self.assertAlmostEqual(parsed["promoter_pledge_pct"], 0.73, places=4)
        self.assertIsNone(parsed["raw"]["pledge_pct_fact"])

    def test_no_pledge_tags_is_none_not_zero(self):
        parsed = self.parse([(TOTAL_SHARES, PROMOTER_CTX, "1000000000"),
                             (HOLDING_PCT, PROMOTER_CTX, "0.24")])
        self.assertIsNone(parsed["promoter_pledge_pct"])
        self.assertNotEqual(parsed["promoter_pledge_pct"], 0.0)
        self.assertEqual(parsed["promoter_holding_pct"], 24.0)

    def test_out_of_range_pledge_is_rejected_not_clamped(self):
        self.assertIsNone(self.parse([(PLEDGE_PCT, PROMOTER_CTX, "140")])
                          ["promoter_pledge_pct"])
        implied = self.parse([(PLEDGE_SHARES, PROMOTER_CTX, "1400000000"),
                              (TOTAL_SHARES, PROMOTER_CTX, "1000000000")])
        self.assertIsNone(implied["promoter_pledge_pct"])

    def test_as_of_date_is_the_period_end(self):
        contexts = {PROMOTER_CTX: {"end": "2026-06-30", "member": PROMOTER_MEMBER}}
        parsed = self.parse([(PLEDGE_PCT, PROMOTER_CTX, "0.5")], contexts)
        self.assertEqual(parsed["as_of_date"], "2026-06-30")
        self.assertAlmostEqual(parsed["promoter_pledge_pct"], 50.0, places=4)
        # an explicit date (the master record's own period end) wins over the instance
        named = parse_shareholding_xbrl(shp_xbrl([(PLEDGE_PCT, PROMOTER_CTX, "0.5")]),
                                       as_of_date="31-MAR-2026")
        self.assertEqual(named["as_of_date"], "2026-03-31")

    def test_namespace_and_prefix_variations_parse(self):
        facts = [(PLEDGE_PCT, PROMOTER_CTX, "0.42")]
        renamed = shp_xbrl(facts, prefix="shp", ns="http://www.nseindia.com/xbrl/shp/2024",
                           default_ns=False)
        self.assertAlmostEqual(parse_shareholding_xbrl(renamed)["promoter_pledge_pct"],
                               42.0, places=4)
        bare = ('<xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">'
                f'<xbrli:context id="{PROMOTER_CTX}"><xbrli:period><xbrli:startDate>'
                '2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate>'
                f'</xbrli:period></xbrli:context><{PLEDGE_PCT} contextRef="{PROMOTER_CTX}">'
                f'0.42</{PLEDGE_PCT}></xbrl>')
        parsed = parse_shareholding_xbrl(bare)
        self.assertAlmostEqual(parsed["promoter_pledge_pct"], 42.0, places=4)
        self.assertEqual(parsed["as_of_date"], "2026-06-30")

    def test_non_xml_document_is_none_not_an_exception(self):
        self.assertIsNone(parse_shareholding_xbrl("<html>blocked</html>"))
        self.assertIsNone(parse_shareholding_xbrl(b""))
        self.assertIsNone(parse_shareholding_xbrl(None))


class XbrlFetchTests(unittest.TestCase):
    def test_one_bad_symbol_survives(self):
        session = FakeNseSession(masters={"GOOD": [master_record()], "BAD": [master_record()]},
                                 xbrl={"JPPOWER.xml": jppower_xbrl()}, broken={"BAD"})
        rows = fetch_nse_pledge_xbrl(["BAD", "GOOD"], session=session, sleep_seconds=0)
        self.assertEqual([row["symbol"] for row in rows], ["GOOD"])
        row = rows[0]
        self.assertEqual(row["source"], "nse_xbrl")
        self.assertEqual(row["as_of_date"], "2026-06-30")  # the master record's period end
        self.assertAlmostEqual(row["promoter_pledge_pct"], 72.99, places=4)
        self.assertAlmostEqual(row["promoter_holding_pct"], 24.0, places=4)
        raw = json.loads(row["raw"])
        self.assertTrue(raw["xbrl"].endswith("JPPOWER.xml"))
        self.assertEqual(raw["submission"], "2026-07-13")
        self.assertEqual(raw["pledge_context"], PROMOTER_CTX)
        self.assertEqual(raw["pledge_shares"], 1200509465)

    def test_latest_record_that_has_an_xbrl_url_wins(self):
        undated = {"date": "30-SEP-2026", "pr_and_prgrp": "24", "xbrl": None,
                   "submissionDate": "14-OCT-2026"}
        session = FakeNseSession(masters={"JPPOWER": [undated, master_record()]},
                                 xbrl={"JPPOWER.xml": jppower_xbrl()})
        rows = fetch_nse_pledge_xbrl(["JPPOWER"], session=session, sleep_seconds=0)
        self.assertEqual(rows[0]["as_of_date"], "2026-06-30")  # the newest WITH an instance

    def test_dead_master_feed_raises_pledge_fetch_error(self):
        with self.assertRaises(PledgeFetchError) as caught:
            fetch_nse_pledge_xbrl(["INFY"], session=FakeSession(), sleep_seconds=0)
        self.assertIn("import --file", str(caught.exception))

    def test_limit_and_duplicates_are_handled(self):
        session = FakeNseSession(masters={"JPPOWER": [master_record()]},
                                 xbrl={"JPPOWER.xml": jppower_xbrl()})
        rows = fetch_nse_pledge_xbrl(["jppower", "JPPOWER"], session=session,
                                     sleep_seconds=0, limit=1)
        self.assertEqual([row["symbol"] for row in rows], ["JPPOWER"])

    def test_auto_merge_prefers_the_pledge_bearing_row(self):
        session = FakeNseSession(masters={"JPPOWER": [master_record()]},
                                 xbrl={"JPPOWER.xml": jppower_xbrl()})
        rows = fetch_shareholding(["JPPOWER"], source="auto", session=session,
                                  sleep_seconds=0)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertAlmostEqual(row["promoter_pledge_pct"], 72.99, places=4)  # from the XBRL
        self.assertAlmostEqual(row["promoter_holding_pct"], 24.0, places=4)  # from the feed
        self.assertEqual(row["source"], "nse_xbrl")
        raw = json.loads(row["raw"])
        self.assertTrue(raw["merged"])
        self.assertTrue(raw["xbrl"]["xbrl"].endswith("JPPOWER.xml"))
        self.assertEqual(raw["json"]["record"]["pr_and_prgrp"], "24")

    def test_auto_keeps_pledge_null_when_no_source_states_it(self):
        quiet = shp_xbrl([(TOTAL_SHARES, PROMOTER_CTX, "1000000000"),
                          (HOLDING_PCT, PROMOTER_CTX, "0.24")])
        session = FakeNseSession(masters={"JPPOWER": [master_record()]},
                                 xbrl={"JPPOWER.xml": quiet})
        row = fetch_shareholding(["JPPOWER"], source="auto", session=session,
                                 sleep_seconds=0)[0]
        self.assertIsNone(row["promoter_pledge_pct"])  # NULL, never 0.0
        self.assertAlmostEqual(row["promoter_holding_pct"], 24.0, places=4)

    def test_source_json_keeps_the_old_feed_behaviour(self):
        session = FakeNseSession(masters={"GOOD": [master_record(pr="13.82")]})
        rows = fetch_shareholding(["GOOD"], source="json", session=session, sleep_seconds=0)
        self.assertEqual(rows[0]["source"], "nse")
        self.assertEqual(rows[0]["promoter_holding_pct"], 13.82)
        self.assertIsNone(rows[0]["promoter_pledge_pct"])

    def test_source_xbrl_skips_the_json_feed(self):
        session = FakeNseSession(masters={"JPPOWER": [master_record()]},
                                 xbrl={"JPPOWER.xml": jppower_xbrl()})
        rows = fetch_shareholding(["JPPOWER"], source="xbrl", session=session,
                                 sleep_seconds=0)
        self.assertEqual(rows[0]["source"], "nse_xbrl")
        self.assertEqual(len(session.calls), 2)  # master listing + the instance

    def test_fetched_rows_reach_apply_and_report(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        ensure_tables(conn)
        seed_fundamentals(conn, "JPPOWER")
        session = FakeNseSession(masters={"JPPOWER": [master_record()]},
                                 xbrl={"JPPOWER.xml": jppower_xbrl()})
        rows = fetch_shareholding(["JPPOWER"], source="auto", session=session,
                                  sleep_seconds=0)
        pledge_ingest._store(conn, rows)  # fetch writes shareholding_pledge only
        self.assertIsNone(conn.execute(
            "SELECT pledge_pct FROM fundamentals WHERE symbol='JPPOWER'").fetchone()[0])
        applied = apply_to_fundamentals(conn, dry_run=False)
        self.assertEqual(applied["pledge_filled"], 1)
        self.assertEqual(conn.execute("SELECT pledge_pct FROM fundamentals "
                                      "WHERE symbol='JPPOWER'").fetchone()[0], 72.99)
        self.assertEqual(report(conn)["sources"], {"nse_xbrl": 1})


if __name__ == "__main__":
    unittest.main()
