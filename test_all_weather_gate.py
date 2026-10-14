"""
Standalone tests for the ALL_WEATHER quality gates (all_weather.py v4).

WHY: all_weather used to buy anything >=25% below its 52-week high and within
15% of its 52-week low, with no trend, liquidity, sector or fundamental test —
68 of the 71 graded ledger trades came from that path at a 5.9% win rate. These
tests prove each of the four new gates really rejects, that the gate is the
thing doing the rejecting (we bypass it in the test, never by editing code),
and that a healthy candidate still gets through.

No network. No production database: every fixture is synthetic, and the
"database" tests run on an in-memory SQLite built from db.SCHEMA.

Run from the repo root:
    .\\env\\Scripts\\python.exe test_all_weather_gate.py
"""
import datetime as dt
import sqlite3
import unittest
from unittest.mock import patch

import pandas as pd

import all_weather as AW
import db

# Every gate switched off — used to show that a candidate passes when the
# specific gate under test is bypassed.
GATES_OFF = {"TREND_ENABLED": False, "LIQ_ENABLED": False,
             "SECTOR_ENABLED": False, "TIER_ENABLED": False}


# ----------------------------------------------------------------------
# synthetic fixtures
# ----------------------------------------------------------------------

def _rows(bars):
    """(o,h,l,c,v) bars -> rows shaped like prices_daily, with fake dates."""
    start = dt.date(2024, 1, 1)
    return [((start + dt.timedelta(days=k)).isoformat(), o, h, l, c, v)
            for k, (o, h, l, c, v) in enumerate(bars)]


def falling_knife_bars(n=260, volume=5_000_000.0):
    """A long decline ending in a hammer — the classic v3 ALL_WEATHER entry.

    It still passes the OLD rules (>=25% below the 52-week high, within 15% of
    the 52-week low, hammer, risk <=5%) and it is exactly the falling-knife
    shape the ledger says lost money.
    """
    bars = []
    for i in range(n - 2):
        px = 200.0 - 0.37 * i
        bars.append((px + 0.5, px + 1.0, px - 1.0, px, volume))
    bars.append((104.0, 105.0, 102.0, 103.0, volume))   # bar before the hammer
    bars.append((103.5, 105.0, 101.0, 104.6, volume))   # the hammer
    return bars


def clean_bars(n=260, volume=5_000_000.0):
    """Rising, liquid, orderly name: what the new gates should still allow."""
    bars = []
    for i in range(n):
        px = 100.0 + 0.5 * i
        bars.append((px, px + 1.0, px - 1.0, px + 0.5, volume))
    return bars


def knife_df(volume=5_000_000.0):
    return AW._bars_df(_rows(falling_knife_bars(volume=volume)))


def clean_df(volume=5_000_000.0):
    return AW._bars_df(_rows(clean_bars(volume=volume)))


SECTORS = {"FALLKNIFE": "IT", "CLEAN": "Realty"}
SECTOR_LOOKUP = SECTORS.get


def only(*enabled):
    """Overrides with just the named gates on."""
    out = {k: False for k in ("TREND_ENABLED", "LIQ_ENABLED",
                             "SECTOR_ENABLED", "TIER_ENABLED")}
    for name in enabled:
        out[name] = True
    return out


def memory_db(symbol="FALLKNIFE", sector="IT", roce=18.0, fund_score=80.0,
              bars=None, trade_date=None, store_signal=False):
    """In-memory SQLite with the same schema the real app uses."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.SCHEMA)
    # swing_live.ensure() adds this column on the real DB; mirror it here so
    # the audit can be exercised without touching data/app.db.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(swing_signals)")]
    if "mode" not in cols:
        conn.execute("ALTER TABLE swing_signals "
                     "ADD COLUMN mode TEXT DEFAULT 'SWING'")

    bars = bars if bars is not None else falling_knife_bars()
    rows = _rows(bars)
    conn.execute("INSERT INTO universe_broad(symbol, mcap_cr) VALUES (?,?)",
                 (symbol, 2000.0))
    conn.executemany(
        "INSERT INTO prices_daily(symbol, date, open, high, low, close, "
        "volume) VALUES (?,?,?,?,?,?,?)",
        [(symbol, r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows])
    if sector is not None:
        conn.execute("INSERT INTO stocks(symbol, sector, active) "
                     "VALUES (?,?,1)", (symbol, sector))
    if roce is not None:
        conn.execute("INSERT INTO fundamentals(symbol, roce) VALUES (?,?)",
                     (symbol, roce))
    if fund_score is not None:
        conn.execute("INSERT INTO scan_results(scan_date, symbol, "
                     "fundamental_score) VALUES (?,?,?)",
                     ("2024-12-31", symbol, fund_score))
    if store_signal:
        conn.execute(
            "INSERT INTO swing_signals(signal_date, symbol, entry_trigger, "
            "stop, target, risk_pct, pullback, impulse, ema_zone, outcome, "
            "updated_at, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (rows[-1][0], symbol, 105.05, 99.99, 120.0, 4.82, 0.48, 0.0,
             "HAMMER", "PENDING", "2024-12-31", "ALL_WEATHER"))
    conn.commit()
    return conn


class AllWeatherGateTests(unittest.TestCase):

    # ---------------- the old rules still accept the falling knife --------
    def test_old_v3_rules_still_accept_the_falling_knife(self):
        """Baseline: v3 detect() trades this name, so the gates are the
        only thing standing between the ledger and more falling knives."""
        det = AW.detect("FALLKNIFE", knife_df())
        self.assertIsNotNone(det)
        self.assertEqual(det["pattern"], "HAMMER")
        self.assertLessEqual(det["risk_pct"], AW.MAX_RISK_PCT)

    def test_replay_matches_detect_on_the_same_bar(self):
        """_setup_at() (used by the audit replay) must agree with detect()."""
        rows = _rows(falling_knife_bars())
        ent = AW._setup_at(rows, len(rows) - 1)
        det = AW.detect("FALLKNIFE", AW._bars_df(rows))
        self.assertIsNotNone(ent)
        for key in ("entry", "stop", "target", "risk_pct", "pattern"):
            self.assertEqual(ent[key], det[key], key)

    # ---------------- gate 1: trend --------------------------------------
    def test_trend_gate_rejects_downtrend(self):
        df = knife_df()
        ok, reasons = AW.gate("FALLKNIFE", df, 80, 18, "HIGH", {"IT"},
                             SECTOR_LOOKUP, only("TREND_ENABLED"))
        self.assertFalse(ok)
        self.assertTrue(any(r.startswith("trend:") for r in reasons), reasons)
        # bypassing the gate (as if it had been removed) flips the verdict
        ok_off, _ = AW.gate("FALLKNIFE", df, 80, 18, "HIGH", {"IT"},
                            SECTOR_LOOKUP, GATES_OFF)
        self.assertTrue(ok_off)

    def test_trend_gate_lets_a_rising_name_through(self):
        ok, reasons = AW.gate("CLEAN", clean_df(), 80, 18, "HIGH",
                              {"Realty"}, SECTOR_LOOKUP, only("TREND_ENABLED"))
        self.assertTrue(ok, reasons)

    # ---------------- gate 2: liquidity ----------------------------------
    def test_liquidity_gate_rejects_illiquid_name(self):
        thin = clean_df(volume=100.0)          # Rs 23k a day, not Rs 2 cr
        ok, reasons = AW.gate("CLEAN", thin, 80, 18, "HIGH", {"Realty"},
                              SECTOR_LOOKUP, only("LIQ_ENABLED"))
        self.assertFalse(ok)
        self.assertTrue(any(r.startswith("liquidity:") for r in reasons),
                        reasons)
        ok_off, _ = AW.gate("CLEAN", thin, 80, 18, "HIGH", {"Realty"},
                            SECTOR_LOOKUP, GATES_OFF)
        self.assertTrue(ok_off)

    def test_liquidity_uses_the_screener_numbers_not_a_copy(self):
        """The threshold must come from strategy_config.SCREENER."""
        thin = clean_df(volume=100.0)
        lowered = {"LIQ_DAYS": 20, "MIN_AVG_TURNOVER": 1e4}
        with patch.object(AW, "SCREENER_CFG", lowered):
            ok, _ = AW.gate("CLEAN", thin, 80, 18, "HIGH", {"Realty"},
                            SECTOR_LOOKUP, only("LIQ_ENABLED"))
        self.assertTrue(ok)

    # ---------------- gate 3: sector -------------------------------------
    def test_sector_gate_rejects_non_leadership_sector(self):
        ok, reasons = AW.gate("FALLKNIFE", clean_df(), 80, 18, "HIGH",
                              {"Realty"}, SECTOR_LOOKUP, only("SECTOR_ENABLED"))
        self.assertFalse(ok)
        self.assertTrue(any(r.startswith("sector:") for r in reasons),
                        reasons)
        ok_off, _ = AW.gate("FALLKNIFE", clean_df(), 80, 18, "HIGH",
                            {"Realty"}, SECTOR_LOOKUP, GATES_OFF)
        self.assertTrue(ok_off)

    def test_sector_gate_allows_leadership_sector(self):
        ok, reasons = AW.gate("CLEAN", clean_df(), 80, 18, "HIGH",
                              {"Realty"}, SECTOR_LOOKUP, only("SECTOR_ENABLED"))
        self.assertTrue(ok, reasons)

    def test_unknown_or_erroring_sector_data_never_blocks(self):
        """No sector row (or a broken lookup) must not stop a trade."""
        ok, _ = AW.gate("NODATA", clean_df(), 80, 18, "HIGH", {"Realty"},
                        SECTOR_LOOKUP, only("SECTOR_ENABLED"))
        self.assertTrue(ok)

        def boom(_sym):
            raise RuntimeError("sector source down")

        ok2, _ = AW.gate("CLEAN", clean_df(), 80, 18, "HIGH", {"Realty"},
                         boom, only("SECTOR_ENABLED"))
        self.assertTrue(ok2)

    # ---------------- gate 4: fundamental tier ---------------------------
    def test_tier_gate_rejects_unrated_name(self):
        """_tier() says UNK (no fundamentals) -> conservative default blocks."""
        ok, reasons = AW.gate("FALLKNIFE", clean_df(), None, None, "UNK",
                              {"Realty"}, SECTOR_LOOKUP, only("TIER_ENABLED"))
        self.assertFalse(ok)
        self.assertTrue(any(r.startswith("tier:") for r in reasons), reasons)
        ok_off, _ = AW.gate("FALLKNIFE", clean_df(), None, None, "UNK",
                            {"Realty"}, SECTOR_LOOKUP, GATES_OFF)
        self.assertTrue(ok_off)

    def test_tier_gate_accepts_high_and_med(self):
        for score, roce, tier in ((80, None, "HIGH"), (None, 18, "HIGH"),
                                  (55, None, "MED"), (None, 11, "MED")):
            ok, reasons = AW.gate("CLEAN", clean_df(), score, roce,
                                  AW._tier(score, roce), {"Realty"},
                                  SECTOR_LOOKUP, only("TIER_ENABLED"))
            self.assertTrue(ok, f"{tier} {score} {roce}: {reasons}")

    def test_tier_floor_is_configurable(self):
        ok, _ = AW.gate("CLEAN", clean_df(), 55, None, "MED", {"Realty"},
                        SECTOR_LOOKUP,
                        dict(only("TIER_ENABLED"), MIN_TIER="HIGH"))
        self.assertFalse(ok)

    # ---------------- all gates together ---------------------------------
    def test_clean_candidate_passes_all_four_gates(self):
        ok, reasons = AW.gate("CLEAN", clean_df(), 80, 18, "HIGH",
                              {"Realty"}, SECTOR_LOOKUP, None)
        self.assertTrue(ok, reasons)

    def test_falling_knife_is_rejected_by_the_default_gate_set(self):
        ok, reasons = AW.gate("FALLKNIFE", knife_df(), None, None, "UNK",
                              {"IT"}, SECTOR_LOOKUP, None)
        self.assertFalse(ok)
        self.assertTrue(any(r.startswith("trend:") for r in reasons), reasons)
        self.assertTrue(any(r.startswith("tier:") for r in reasons), reasons)

    # ---------------- house rules ----------------------------------------
    def test_missing_config_keys_cannot_crash(self):
        """A half-written strategy_config must not break the scan."""
        with patch.object(AW, "CFG", {}):
            self.assertEqual(AW._gcfg("TREND_EMA", 200, None), 200)
            ok, reasons = AW.gate("CLEAN", clean_df(), 80, 18, "HIGH",
                                  {"Realty"}, SECTOR_LOOKUP, None)
        self.assertTrue(ok, reasons)

    def test_a_gate_that_raises_does_not_block(self):
        with patch.object(AW, "trend_ok",
                          side_effect=RuntimeError("ema exploded")):
            ok, _ = AW.gate("CLEAN", clean_df(), 80, 18, "HIGH", {"Realty"},
                            SECTOR_LOOKUP, only("TREND_ENABLED"))
        self.assertTrue(ok)

    # ---------------- end to end through candidates() --------------------
    def test_candidates_applies_the_trend_gate_end_to_end(self):
        conn = memory_db()
        try:
            stats = {}
            out = AW.candidates(conn, limit=10, sector_allowed={"IT"},
                                stats=stats)
            self.assertEqual(len(out), 0)
            self.assertEqual(stats["raw"], 1)      # v3 band did accept it
            self.assertEqual(stats["trend"], 1)    # the trend gate stopped it
            self.assertEqual(stats["kept"], 0)
        finally:
            conn.close()

    def test_candidates_keeps_the_name_when_the_trend_gate_is_switched_off(self):
        """Same data, trend gate off: the other three gates all pass it."""
        conn = memory_db()
        try:
            stats = {}
            out = AW.candidates(conn, limit=10, sector_allowed={"IT"},
                                overrides={"TREND_ENABLED": False},
                                stats=stats)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0][0], "FALLKNIFE")
            self.assertEqual(out[0][4], "HIGH")
            self.assertEqual(stats["kept"], 1)
        finally:
            conn.close()

    def test_candidates_skips_names_outside_the_52_week_band(self):
        """The gates are added on top; the v3 band still applies."""
        conn = memory_db(bars=clean_bars())
        try:
            stats = {}
            out = AW.candidates(conn, limit=10, sector_allowed={"IT"},
                                overrides=GATES_OFF, stats=stats)
            self.assertEqual(out, [])
            self.assertEqual(stats["raw"], 0)
        finally:
            conn.close()

    # ---------------- the audit the owner asked for ----------------------
    def test_audit_stored_rejects_the_stored_signal(self):
        conn = memory_db(store_signal=True)
        try:
            res = AW.audit_stored(conn, sector_allowed={"IT"})
            self.assertEqual(res["stored"], 1)
            self.assertEqual(res["rejected"], 1)
            self.assertEqual(res["trend"], 1)
            # with every gate bypassed the same stored row passes, which
            # proves the gates are what rejected it
            res_off = AW.audit_stored(conn, overrides=GATES_OFF,
                                      sector_allowed={"IT"})
            self.assertEqual(res_off["passed"], 1)
            self.assertEqual(res_off["rejected"], 0)
        finally:
            conn.close()

    def test_audit_stored_on_an_empty_ledger_is_zero_not_an_error(self):
        conn = memory_db()
        try:
            res = AW.audit_stored(conn, sector_allowed={"IT"})
            self.assertEqual(res["stored"], 0)
            self.assertEqual(res["rejected"], 0)
        finally:
            conn.close()

    def test_audit_replay_finds_and_gates_the_historic_signal(self):
        conn = memory_db()
        try:
            res = AW.audit_replay(conn, limit=10, step=1,
                                  sector_allowed={"IT"})
            self.assertEqual(res["signals"], 1)
            self.assertEqual(res["rejected"], 1)
            self.assertEqual(res["trend"], 1)
            self.assertEqual(res["passed"], 0)
            res_off = AW.audit_replay(conn, limit=10, step=1,
                                      overrides=GATES_OFF,
                                      sector_allowed={"IT"})
            self.assertEqual(res_off["passed"], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
