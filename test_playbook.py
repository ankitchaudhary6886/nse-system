"""Unit tests for the Playbook rule engine.

Each pattern is built synthetically so the expected answer is known. A pattern
test asserts the rule fires somewhere inside the constructed shape; the
negative test asserts the same rule stays silent on directionless chop.

The repo uses unittest (no pytest dependency).

Run:  .\\env\\Scripts\\python.exe -m unittest test_playbook -v
"""

from __future__ import annotations

import datetime as dt
import inspect
import sqlite3
import unittest
from unittest import mock

import numpy as np

import db
import playbook
import playbook_engine


# ============================================================
# Helpers
# ============================================================
def make_bars(closes, volumes=None, spread=0.01):
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) * (1 + spread)
    l = np.minimum(o, c) * (1 - spread)
    if volumes is None:
        v = np.full(len(c), 1_000_000.0)
    else:
        v = np.asarray(volumes, dtype=float)
    return o, h, l, c, v


def ctx_at(bars, i, symbol="TEST"):
    o, h, l, c, v = bars
    return {
        "sym": symbol,
        "date": [f"2024-01-{1 + (j % 27):02d}" for j in range(len(c))],
        "o": o, "h": h, "l": l, "c": c, "v": v,
        "ind": playbook.build_indicators(o, h, l, c, v),
        "i": int(i),
    }


def first_fire(detector, bars, lo, hi):
    for i in range(int(lo), int(hi)):
        sig = detector(ctx_at(bars, i))
        if sig is not None:
            return i, sig
    return None, None


def chop(n=320, seed=11):
    rng = np.random.default_rng(seed)
    c = 100 + np.cumsum(rng.normal(0, 0.15, n))
    return make_bars(c)


# ============================================================
# Builders
# ============================================================
def cup_bars():
    rng = np.random.default_rng(5)
    up = np.linspace(100, 180, 140)
    down = np.linspace(180, 150, 40)[1:]
    back = np.linspace(150, 178, 40)[1:]
    handle = np.linspace(177.5, 175.5, 14)[1:]
    c = np.concatenate([up, down, back, handle, [181.0]])
    c = c + rng.normal(0, 0.15, len(c))
    c[-1] = 181.0
    v = np.full(len(c), 1e6)
    v[-15:-1] = 5e5
    v[-1] = 3e6
    return make_bars(c, v, spread=0.003)


def vcp_bars():
    seg = list(np.full(70, 95.0))
    seg += list(np.linspace(100, 120, 60))
    seg += list(np.linspace(120, 90, 20))[1:]
    seg += list(np.linspace(90, 130, 30))[1:]
    seg += list(np.linspace(130, 114, 15))[1:]
    seg += list(np.linspace(114, 140, 25))[1:]
    seg += list(np.linspace(140, 133, 10))[1:]
    seg += list(np.linspace(133, 142, 15))[1:]
    seg += [144.0]
    c = np.array(seg)
    v = np.full(len(c), 1e6)
    v[-10:-1] = 3e5
    v[-1] = 1.5e6
    return make_bars(c, v, spread=0.006)

def htf_bars():
    c = np.concatenate([
        np.full(40, 50.0),
        np.linspace(50, 110, 20),
        np.linspace(110, 106, 18),
        [112.0],
    ])
    v = np.concatenate([
        np.full(40, 1e6), np.full(20, 2e6),
        np.full(18, 6e5), [3e6],
    ])
    return make_bars(c, v, spread=0.008)


def flat_bars():
    rng = np.random.default_rng(9)
    c = np.concatenate([
        np.linspace(100, 160, 120),
        155 + rng.normal(0, 1.2, 40),
        [163.0],
    ])
    v = np.full(len(c), 1e6)
    v[-41:-1] = 4e5
    v[-1] = 2.5e6
    return make_bars(c, v, spread=0.002)


def ascending_bars():
    c = np.concatenate([
        np.full(20, 95.0),
        np.linspace(100, 120, 15),
        np.linspace(120, 102, 10)[1:],
        np.linspace(102, 130, 12)[1:],
        np.linspace(130, 112, 10)[1:],
        np.linspace(112, 140, 12)[1:],
        np.linspace(140, 122, 10)[1:],
        np.linspace(122, 146, 12)[1:],
        [148.0],
    ])
    v = np.full(len(c), 1e6)
    v[-1] = 3e6
    return make_bars(c, v, spread=0.003)


def cross_bars():
    c = np.concatenate([np.linspace(140, 80, 120),
                        np.linspace(80, 86, 250),
                        np.linspace(86, 180, 150)])
    return make_bars(c)


# ============================================================
# Tests
# ============================================================
class RegistryTests(unittest.TestCase):
    def test_registry_is_complete(self):
        ids = [s["id"] for s in playbook.STRATEGIES]
        self.assertEqual(len(ids), len(set(ids)))
        for s in playbook.STRATEGIES:
            for key in ("id", "name", "family", "book", "status",
                        "formula", "params"):
                self.assertIn(key, s, f"{s.get('id')} missing {key}")
        self.assertGreaterEqual(len(playbook.LIVE_IDS), 10)

    def test_no_duplicate_top_level_functions(self):
        """The singhal._detect_vcp shadowing bug must never recur."""
        names = [n for n, obj in inspect.getmembers(playbook, inspect.isfunction)
                 if obj.__module__ == playbook.__name__]
        self.assertEqual(len(names), len(set(names)))


class DonchianTests(unittest.TestCase):
    def test_fires_on_clean_breakout(self):
        rng = np.random.default_rng(7)
        c = 100 + rng.normal(0, 0.4, 100)
        c[-1] = 110
        v = np.full(100, 1e6)
        v[-1] = 2e6
        i, sig = first_fire(playbook.detect_donchian_20,
                            make_bars(c, v), 95, 100)
        self.assertEqual(i, 99)
        self.assertIsNotNone(sig)
        self.assertLess(sig["stop"], sig["entry"])
        self.assertLess(sig["entry"], sig["target"])
        self.assertAlmostEqual(sig["rr"], 3.0, places=1)

    def test_silent_in_chop(self):
        _, sig = first_fire(playbook.detect_donchian_20, chop(), 260, 320)
        self.assertIsNone(sig)


class High52Tests(unittest.TestCase):
    def test_fires_on_trend_template(self):
        rng = np.random.default_rng(3)
        c = np.linspace(100, 150, 300) + rng.normal(0, 0.3, 300)
        c[-1] = 160
        v = np.full(300, 1e6)
        v[-1] = 4e6
        bars = make_bars(c, v, spread=0.004)
        sig = playbook.detect_high_52w(ctx_at(bars, 299))
        self.assertIsNotNone(sig)
        self.assertLess(sig["stop"], sig["entry"])

    def test_needs_volume(self):
        rng = np.random.default_rng(3)
        c = np.linspace(100, 150, 300) + rng.normal(0, 0.3, 300)
        c[-1] = 160
        bars = make_bars(c, np.full(300, 1e6), spread=0.004)
        self.assertIsNone(playbook.detect_high_52w(ctx_at(bars, 299)))


class CupTests(unittest.TestCase):
    def test_fires(self):
        bars = cup_bars()
        sig = playbook.detect_cup_handle(ctx_at(bars, len(bars[3]) - 1))
        self.assertIsNotNone(sig)
        depth = sig["raw"]["indicators"]["cup_depth"]
        self.assertGreaterEqual(depth, 0.12)
        self.assertLessEqual(depth, 0.33)
        self.assertAlmostEqual(sig["target"], sig["entry"] * 1.225, places=1)

    def test_rejects_shallow_cup(self):
        c = np.concatenate([np.linspace(100, 180, 140),
                            np.linspace(180, 176, 40)[1:],
                            np.linspace(176, 179, 40)[1:],
                            np.linspace(178, 177, 14)[1:], [181.0]])
        bars = make_bars(c)
        self.assertIsNone(
            playbook.detect_cup_handle(ctx_at(bars, len(c) - 1)))


class VcpTests(unittest.TestCase):
    def test_fires_and_contracts_shrink(self):
        bars = vcp_bars()
        sig = playbook.detect_vcp(ctx_at(bars, len(bars[3]) - 1))
        self.assertIsNotNone(sig)
        contractions = sig["raw"]["indicators"]["contractions"]
        self.assertGreaterEqual(len(contractions), 3)
        for a, b in zip(contractions, contractions[1:]):
            self.assertLess(b, a)
        self.assertLessEqual(contractions[-1], 0.08)

    def test_silent_in_chop(self):
        _, sig = first_fire(playbook.detect_vcp, chop(), 260, 320)
        self.assertIsNone(sig)


class HighTightFlagTests(unittest.TestCase):
    def test_fires(self):
        bars = htf_bars()
        sig = playbook.detect_high_tight_flag(ctx_at(bars, len(bars[3]) - 1))
        self.assertIsNotNone(sig)
        self.assertGreater(sig["target"], sig["entry"])

    def test_rejects_weak_pole(self):
        c = np.concatenate([np.full(40, 100.0), np.linspace(100, 130, 20),
                            np.linspace(130, 127, 18), [132.0]])
        bars = make_bars(c)
        self.assertIsNone(
            playbook.detect_high_tight_flag(ctx_at(bars, len(c) - 1)))


class FlatBaseTests(unittest.TestCase):
    def test_fires(self):
        bars = flat_bars()
        sig = playbook.detect_flat_base(ctx_at(bars, len(bars[3]) - 1))
        self.assertIsNotNone(sig)
        self.assertLessEqual(sig["raw"]["indicators"]["base_depth"], 0.15)

    def test_rejects_wide_range(self):
        c = np.concatenate([np.linspace(100, 160, 120),
                            np.linspace(150, 170, 40), [171.0]])
        bars = make_bars(c)
        self.assertIsNone(
            playbook.detect_flat_base(ctx_at(bars, len(c) - 1)))


class AscendingBaseTests(unittest.TestCase):
    def test_fires(self):
        bars = ascending_bars()
        i, sig = first_fire(playbook.detect_ascending_base, bars,
                            len(bars[3]) - 1, len(bars[3]))
        self.assertIsNotNone(sig)
        lows = sig["raw"]["indicators"]["lows"]
        self.assertLess(lows[0], lows[1])
        self.assertLess(lows[1], lows[2])

    def test_rejects_falling_lows(self):
        c = np.concatenate([np.full(20, 95.0), np.linspace(100, 120, 15),
                            np.linspace(120, 95, 10)[1:],
                            np.linspace(95, 130, 12)[1:],
                            np.linspace(130, 90, 10)[1:],
                            np.linspace(90, 140, 12)[1:], [145.0]])
        bars = make_bars(c)
        self.assertIsNone(
            playbook.detect_ascending_base(ctx_at(bars, len(c) - 1)))


class MovingAverageTests(unittest.TestCase):
    def test_golden_cross_fires_exactly_once(self):
        bars = cross_bars()
        hits = [i for i in range(225, len(bars[3]))
                if playbook.detect_ma_50_200(ctx_at(bars, i)) is not None]
        self.assertEqual(len(hits), 1)
        sig = playbook.detect_ma_50_200(ctx_at(bars, hits[0]))
        self.assertIn("sma50", sig["raw"]["indicators"])

    def test_death_cross_is_a_warning(self):
        c = np.concatenate([np.linspace(80, 150, 160),
                            np.linspace(150, 80, 160)])
        bars = make_bars(c)
        hits = [playbook.detect_death_cross(ctx_at(bars, i))
                for i in range(222, len(c))]
        hits = [s for s in hits if s]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["direction"], "TOP_WARNING")
        self.assertIsNone(hits[0]["rr"])
        self.assertIsNone(hits[0]["risk_pct"])
        exits = hits[0]["raw"]["exits"]
        # A warning is not a long: the upside level is invalidation and the
        # downside level is the objective, so the inequalities must reverse.
        self.assertIn("≥", exits["stop_out"]["condition"])
        self.assertIn("≤", exits["target"]["condition"])
        self.assertIn("R43", exits["target"]["thesis"])


class CrossSectionalTests(unittest.TestCase):
    def _ctx(self):
        bars = make_bars(np.linspace(50, 120, 260))
        ctx = ctx_at(bars, 259)
        ctx.update(mom_12_1=0.25, mom_rank=0.95, vol_rank=0.20)
        return ctx

    def test_momentum_takes_top_decile_not_bottom(self):
        ctx = self._ctx()
        self.assertIsNotNone(playbook.detect_momentum_12_1(ctx))
        ctx["mom_rank"] = 0.05
        self.assertIsNone(playbook.detect_momentum_12_1(ctx))

    def test_low_vol_needs_top_momentum_and_low_vol(self):
        ctx = self._ctx()
        self.assertIsNotNone(playbook.detect_low_vol_momentum(ctx))
        ctx["vol_rank"] = 0.80
        self.assertIsNone(playbook.detect_low_vol_momentum(ctx))
        ctx["vol_rank"] = 0.20
        ctx["mom_rank"] = 0.10
        self.assertIsNone(playbook.detect_low_vol_momentum(ctx))


class ExitAndSimulationTests(unittest.TestCase):
    def test_every_signal_carries_r40_exits(self):
        rng = np.random.default_rng(7)
        c = 100 + rng.normal(0, 0.4, 100)
        c[-1] = 110
        bars = make_bars(c)
        sig = playbook.detect_donchian_20(ctx_at(bars, 99))
        exits = sig["raw"]["exits"]
        for key in ("stop_out", "target", "offset", "invalidation",
                    "exhaustion", "time_exit"):
            self.assertIn(key, exits)
        self.assertEqual(exits["stop_out"]["hard_number"], sig["stop"])
        self.assertEqual(exits["target"]["hard_number"], sig["target"])
        for key in ("stop_out", "target"):
            self.assertTrue(exits[key]["thesis"])
            self.assertTrue(exits[key]["condition"])

    def test_simulation_assumes_stop_first(self):
        bars = {
            "o": np.array([100.0, 100.0, 100.0]),
            "h": np.array([101.0, 111.0, 101.0]),
            "l": np.array([99.0, 94.0, 99.0]),
            "c": np.array([100.0, 100.0, 100.0]),
            "v": np.full(3, 1e6), "n": 3,
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        }
        sig = {"entry": 100, "stop": 95, "target": 110, "hold": 2}
        trade = playbook_engine._simulate(bars, 0, sig)
        self.assertEqual(trade["exit"], 95)

    def test_gap_through_target_is_not_a_trade(self):
        # The open is inside the 5% chase limit but already above the target.
        # Booking the same open as an instant win would be a phantom trade.
        bars = {
            "o": np.array([100.0, 103.0, 100.0]),
            "h": np.array([101.0, 104.0, 101.0]),
            "l": np.array([99.0, 102.0, 99.0]),
            "c": np.array([100.0, 103.0, 100.0]),
            "v": np.full(3, 1e6), "n": 3,
            "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        }
        sig = {"entry": 100, "stop": 90, "target": 102, "hold": 2}
        self.assertIsNone(playbook_engine._simulate(bars, 0, sig))

    def test_min_risk_floor_widens_tiny_stop(self):
        rng = np.random.default_rng(1)
        bars = make_bars(100 + rng.normal(0, 0.3, 80))
        ctx = ctx_at(bars, 79)
        sig = playbook._signal(ctx, "flat_base", 100.0, 99.5, 110.0,
                               "MED", "tight structural stop", {})
        self.assertIsNotNone(sig)
        self.assertGreaterEqual(sig["risk_pct"], playbook.MIN_RISK_PCT - 0.0001)

    def test_stats_math(self):
        trades = [{"r": 2.0, "hold": 5}, {"r": -1.0, "hold": 3},
                  {"r": 2.0, "hold": 7}, {"r": -1.0, "hold": 4}]
        row = playbook_engine._stats_row("t", "donchian_20",
                                         trades, 3, 100, 5)
        self.assertEqual(row["win_rate"], 0.5)
        self.assertAlmostEqual(row["expectancy_r"], 0.5, places=2)
        self.assertAlmostEqual(row["profit_factor"], 2.0, places=2)
        self.assertEqual(row["median_hold"], 4)


class DataIntegrityTests(unittest.TestCase):
    """A split is a corporate action, not a 50% loss. Either adjust it or drop
    the symbol; never let the seam become a trade."""

    def _conn(self, closes, split_at=None):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE prices_daily (symbol TEXT, date TEXT, open REAL, "
            "high REAL, low REAL, close REAL, volume REAL)")
        conn.execute(
            "CREATE TABLE corporate_actions (symbol TEXT, ex_date TEXT, "
            "kind TEXT, ratio REAL)")
        start = dt.date(2023, 1, 2)
        rows = []
        for i, px in enumerate(closes):
            day = (start + dt.timedelta(days=i)).isoformat()
            rows.append(("TEST", day, px, px * 1.01, px * 0.99, px,
                         1_000_000.0))
        conn.executemany(
            "INSERT INTO prices_daily VALUES (?,?,?,?,?,?,?)", rows)
        if split_at is not None:
            ex = (start + dt.timedelta(days=split_at)).isoformat()
            conn.execute(
                "INSERT INTO corporate_actions VALUES "
                "('TEST', ?, 'split', 2.0)", (ex,))
        conn.commit()
        return conn

    def test_split_is_back_adjusted(self):
        conn = self._conn([200.0] * 160 + [100.0] * 160, split_at=160)
        bars = playbook_engine.load_arrays(conn, "TEST")
        self.assertIsNotNone(bars)
        # The whole series is on today's share basis: no 200 -> 100 cliff.
        self.assertAlmostEqual(float(bars["c"][0]), 100.0, places=4)
        self.assertAlmostEqual(float(bars["c"][-1]), 100.0, places=4)
        self.assertAlmostEqual(float(bars["o"][0]), 100.0, places=4)
        # Volume is scaled the other way so turnover is unchanged.
        self.assertAlmostEqual(float(bars["v"][0]), 2_000_000.0, places=2)
        self.assertAlmostEqual(float(bars["v"][-1]), 1_000_000.0, places=2)
        conn.close()

    def test_unadjusted_seam_is_rejected(self):
        conn = self._conn([200.0] * 160 + [100.0] * 160)
        self.assertIsNone(playbook_engine.load_arrays(conn, "TEST"))
        conn.close()


class TrailingExitTests(unittest.TestCase):
    def _bars(self, closes, lows=None):
        c = np.asarray(closes, dtype=float)
        o = np.concatenate([[c[0]], c[:-1]])
        h = np.maximum(o, c) + 1.0
        l = (np.asarray(lows, dtype=float) if lows is not None
             else np.minimum(o, c) - 1.0)
        return {"o": o, "h": h, "l": l, "c": c,
                "v": np.full(len(c), 1e6), "n": len(c),
                "date": [f"2024-02-{i + 1:02d}" for i in range(len(c))]}

    def test_ll10_exits_on_a_close_below_the_prior_ten_day_low(self):
        bars = self._bars([100, 100, 100, 100, 100, 85, 85],
                          lows=[99, 99, 99, 99, 99, 84, 84])
        sig = {"entry": 100.0, "stop": 80.0, "target": 130.0, "hold": 20,
               "raw": {"exit_mode": "ll10"}}
        trade = playbook_engine._simulate(bars, 0, sig)
        self.assertIsNotNone(trade)
        self.assertEqual(trade["exit"], 85.0)
        self.assertEqual(trade["hold"], 5)
        self.assertEqual(trade["exit_date"], "2024-02-06")

    def test_reverse_cross_ignores_the_research_target(self):
        bars = self._bars([100, 100, 100, 100, 100, 95, 95],
                          lows=[97, 97, 97, 97, 97, 96, 96])
        bars["ind"] = {
            "sma50": np.array([110, 110, 110, 110, 110, 99, 99], float),
            "sma200": np.array([100] * 7, float),
        }
        sig = {"entry": 100.0, "stop": 80.0, "target": 130.0, "hold": 20,
               "raw": {"exit_mode": "reverse_cross"}}
        trade = playbook_engine._simulate(bars, 0, sig)
        self.assertIsNotNone(trade)
        self.assertEqual(trade["exit"], 95.0)
        self.assertEqual(trade["hold"], 5)


class ZigzagTests(unittest.TestCase):
    def test_alternates_and_ignores_subthreshold_wiggles(self):
        h = np.array([100, 101, 102, 101.5, 101, 100, 99, 100, 101, 102, 103],
                     dtype=float)
        piv = playbook._zigzag(h, h - 1.0, 0, len(h) - 1, pct=0.03)
        types = [p[1] for p in piv]
        self.assertEqual(types, ["H", "L", "H"])
        for a, b in zip(types, types[1:]):
            self.assertNotEqual(a, b)


class BacktestSelectionTests(unittest.TestCase):
    def test_shape_prefilter_keeps_an_htf_breakout_below_the_pole_high(self):
        n = 300
        c = np.full(n, 100.0)
        h = np.full(n, 101.0)
        # Pole high 150, flag retraces to 120, breakout at 120. That is 80% of
        # the 60-bar high: a valid HTF, but a 97% prefilter would delete it.
        h[250] = 150.0
        c[-2] = 120.0
        bars = {"c": c, "h": h, "n": n}
        idx = playbook_engine._candidates(bars, "high_tight_flag", 1)
        self.assertIn(n - 2, idx)

    def test_52w_candidate_window_starts_at_bar_252(self):
        n = 300
        c = np.full(n, 100.0)
        c[252] = 120.0
        bars = {"c": c, "h": np.full(n, 101.0), "n": n,
                "ind": {"hh252": np.full(n, 100.0)}}
        idx = playbook_engine._candidates(bars, "high_52w", 1)
        self.assertIn(252, idx)

    def test_cross_sectional_rs_ranks_each_date(self):
        dates = [f"2024-{1 + (i // 28):02d}-{1 + (i % 28):02d}"
                 for i in range(260)]
        c1 = np.linspace(100, 200, 260)
        c2 = np.full(260, 100.0)
        b1 = {"symbol": "AAA", "date": dates, "c": c1, "n": 260}
        b2 = {"symbol": "BBB", "date": dates, "c": c2, "n": 260}
        playbook_engine._cross_sectional_rs([b1, b2])
        self.assertAlmostEqual(float(b1["_rs"][259]), 1.0, places=6)
        self.assertAlmostEqual(float(b2["_rs"][259]), 0.0, places=6)
        self.assertTrue(np.isnan(b1["_rs"][251]))

    def test_vcp_rejects_more_than_six_contractions(self):
        bars = make_bars(np.linspace(100, 120, 130))
        ctx = ctx_at(bars, 129)
        piv = []
        for k in range(7):
            piv.append((10 + k * 10, "H", 100.0 + k))
            piv.append((15 + k * 10, "L", 90.0 + k))
        piv.append((90, "H", 106.0))
        with mock.patch.object(playbook, "_zigzag", return_value=piv), \
             mock.patch.object(playbook, "_trend_template",
                               return_value=(True, "ok")):
            self.assertIsNone(playbook.detect_vcp(ctx))


class ScanPersistenceTests(unittest.TestCase):
    DDL = """CREATE TABLE strategy_signals (
        as_of TEXT, symbol TEXT, strategy TEXT, direction TEXT,
        status TEXT, confidence TEXT, entry REAL, stop REAL, target REAL,
        rr REAL, risk_pct REAL, hold INTEGER, tags TEXT, notes TEXT,
        params TEXT, indicators TEXT, exits TEXT, overlaps TEXT,
        created_at TEXT,
        PRIMARY KEY(as_of, symbol, strategy, direction))"""

    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(self.DDL)
        return conn

    def _bars(self, day):
        n = 260
        c = np.linspace(100, 120, n)
        return {"symbol": "AAA", "date": [day] * n,
                "o": c, "h": c * 1.01, "l": c * 0.99, "c": c,
                "v": np.full(n, 1e6), "n": n,
                "ind": playbook.build_indicators(c, c * 1.01, c * 0.99, c,
                                                 np.full(n, 1e6))}

    def test_empty_rescan_deletes_the_same_days_old_tags(self):
        conn = self._conn()
        conn.execute(
            "INSERT INTO strategy_signals(as_of, symbol, strategy, direction) "
            "VALUES('2026-10-23','AAA','donchian_20','LONG_ENTRY')")
        conn.commit()
        with mock.patch.object(playbook_engine, "load_arrays",
                               return_value=self._bars("2026-10-23")), \
             mock.patch.object(playbook, "detect_all", return_value=[]), \
             mock.patch.object(playbook, "detect_warnings", return_value=[]):
            result = playbook_engine.scan(conn, symbols=["AAA"])
        self.assertEqual(result["signals"], 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM strategy_signals").fetchone()[0], 0)

    def test_unexpected_load_failure_clears_running_state(self):
        playbook_engine._set_scan(running=False, status="idle")
        with mock.patch.object(playbook_engine.db, "get_conn",
                               side_effect=RuntimeError("db unavailable")):
            with self.assertRaises(RuntimeError):
                playbook_engine.scan()
        status = playbook_engine.scan_status()
        self.assertFalse(status["running"])
        self.assertEqual(status["status"], "error")


class SignalKeyMigrationTests(unittest.TestCase):
    OLD = """CREATE TABLE strategy_signals (
        as_of TEXT, symbol TEXT, strategy TEXT, direction TEXT,
        status TEXT, confidence TEXT, entry REAL, stop REAL, target REAL,
        rr REAL, risk_pct REAL, hold INTEGER, tags TEXT, notes TEXT,
        params TEXT, indicators TEXT, exits TEXT, overlaps TEXT,
        created_at TEXT,
        PRIMARY KEY(as_of, symbol, strategy))"""

    def test_direction_becomes_part_of_the_key(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(self.OLD)
        conn.execute(
            "INSERT INTO strategy_signals(as_of, symbol, strategy, direction) "
            "VALUES('2026-10-23','AAA','ma_50_200','LONG_ENTRY')")
        conn.commit()
        db._migrate_signal_pk(conn)
        pk = [r[1] for r in sorted(
            conn.execute("PRAGMA table_info(strategy_signals)").fetchall(),
            key=lambda r: r[5]) if r[5]]
        self.assertIn("direction", pk)
        conn.execute(
            "INSERT INTO strategy_signals(as_of, symbol, strategy, direction) "
            "VALUES('2026-10-23','AAA','ma_50_200','TOP_WARNING')")
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM strategy_signals").fetchone()[0], 2)


class EdgeSimulationTests(unittest.TestCase):
    def _bars(self, n):
        c = np.full(n, 100.0)
        return {"o": c.copy(), "h": c + 1, "l": c - 1, "c": c,
                "v": np.full(n, 1e6), "n": n,
                "date": [f"2024-03-{i + 1:02d}" for i in range(n)]}

    def test_open_trade_is_not_force_closed_at_the_data_edge(self):
        sig = {"entry": 100.0, "stop": 90.0, "target": 110.0, "hold": 10}
        self.assertIsNone(playbook_engine._simulate(self._bars(4), 0, sig))

    def test_time_exit_is_used_when_the_window_is_complete(self):
        sig = {"entry": 100.0, "stop": 90.0, "target": 110.0, "hold": 3}
        trade = playbook_engine._simulate(self._bars(4), 0, sig)
        self.assertIsNotNone(trade)
        self.assertEqual(trade["hold"], 3)


class FlagVolumeTests(unittest.TestCase):
    def test_breakout_bar_volume_is_not_part_of_flag_supply(self):
        bars = htf_bars()
        o, h, l, c, v = bars
        v = v.copy()
        # A huge breakout bar must pass the 1.4x gate, not poison the flag
        # average (which is measured before the breakout).
        v[-1] = 1e9
        sig = playbook.detect_high_tight_flag(
            ctx_at((o, h, l, c, v), len(c) - 1))
        self.assertIsNotNone(sig)


if __name__ == "__main__":
    unittest.main(verbosity=2)
