"""Playbook — exact, book-sourced swing setups as machine-checkable rules.

WHY THIS FILE EXISTS
--------------------
The Trader League answers "which book made money". It cannot answer "which
stocks satisfy a specific rule today, and why". This module is the rule layer:
one pure function per setup, every threshold named, every number returned in
``params`` so the UI and the backtester use the *same* definition.

DESIGN CONTRACT
---------------
* Pure functions only: no DB, no file I/O, no logging side effects.
* Input is a numpy view of one symbol's adjusted daily bars plus precomputed
  indicators. ``i`` is the decision bar; windows that the book defines as
  "prior N bars" end at ``i-1``.
* A detector returns ``None`` or a signal dict. It never invents a missing
  input; ``status="data_pending"`` strategies simply never emit.
* Exits are SUGGESTIVE (owner rule R30): they describe the book's exit
  philosophy in R40 shape. They are not orders.
* Every signal carries ``tags`` (for the search engine) and ``params``
  (the exact numbers that triggered it), so a row can always be audited.

NOT A TRADER BOOK
-----------------
This module is intentionally NOT registered in ``traders/__init__.py``.
Registering it would add a 15th League player and force a multi-hour replay.
It imports nothing from ``traders`` and can be promoted later if the owner
wants it scored in the League.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# Registry
# ============================================================
# prior_win / prior_payoff are the published ranges from the books. They are
# shown in the UI only until the local backtest produces a real number; the
# UI labels them "book prior" so they can never be mistaken for measured.
STRATEGIES = [
    {
        "id": "donchian_20",
        "name": "Donchian 20-Day Breakout",
        "short": "Turtle S1",
        "family": "Breakout",
        "book": "Turtle System 1 — Dennis / Eckhardt",
        "status": "live",
        "direction": "LONG",
        "hold": 120,
        "prior_win": 0.38,
        "prior_payoff": 3.0,
        "formula": "C > max(H, 20 prior) · stop = entry − 2·ATR20 · exit < min(L, 10 prior)",
        "params": {"breakout_days": 20, "exit_days": 10, "stop_atr": 2.0},
    },
    {
        "id": "high_52w",
        "name": "52-Week High Breakout",
        "short": "52W high",
        "family": "Breakout",
        "book": "O'Neil CAN SLIM / Minervini trend template",
        "status": "live",
        "direction": "LONG",
        "hold": 40,
        "prior_win": 0.41,
        "prior_payoff": 2.5,
        "formula": "C > max(H, 252 prior) + 0.1% · Minervini trend template (incl. RS ≥70th pct) · V ≥ 1.4×V50 · close in top 25% of range · stop = max(−7.5%, 10-day low) · target +22.5%",
        "params": {"lookback": 252, "vol_mult": 1.4, "stop_pct": 0.075,
                   "target_pct": 0.225, "rs_min": 0.70},
    },
    {
        "id": "cup_handle",
        "name": "Cup with Handle",
        "short": "Cup + handle",
        "family": "Base",
        "book": "William J. O'Neil — How to Make Money in Stocks",
        "status": "live",
        "direction": "LONG",
        "hold": 60,
        "prior_win": 0.50,
        "prior_payoff": 2.5,
        "formula": "cup depth 12–33% · 7–65 wks · right side ≥70% of depth · handle ≤ min(12%, ⅓ cup) and in upper half · handle V ≤ 0.80× cup V · breakout V ≥ 1.4×V50 · stop = max(−7.5%, handle low) · target +22.5%",
        "params": {"depth_min": 0.12, "depth_max": 0.33, "min_weeks": 7,
                   "max_weeks": 65, "handle_max": 0.12,
                   "right_side_min": 0.70, "vol_mult": 1.4,
                   "stop_pct": 0.075, "target_pct": 0.225},
    },
    {
        "id": "vcp",
        "name": "Volatility Contraction Pattern",
        "short": "VCP",
        "family": "Base",
        "book": "Mark Minervini — Trade Like a Stock Market Wizard",
        "status": "live",
        "direction": "LONG",
        "hold": 40,
        "prior_win": 0.42,
        "prior_payoff": 2.75,
        "formula": "2–6 contractions, each ≤0.80× prior, last ≤8% and ≤0.50× first, lows rising · dry-up V ≤0.80× · breakout V ≥1.4× · stop = max(0.5% below final low, −7%) · target 2.5R",
        "params": {"min_contractions": 2, "max_contractions": 6,
                   "shrink_ratio": 0.80, "final_max": 0.08,
                   "total_squeeze": 0.50, "vol_mult": 1.40,
                   "dryup_ratio": 0.80, "zigzag_pct": 0.04,
                   "stop_cap": 0.07, "target_r": 2.5},
    },
    {
        "id": "high_tight_flag",
        "name": "High Tight Flag",
        "short": "HTF",
        "family": "Momentum",
        "book": "William J. O'Neil — How to Make Money in Stocks",
        "status": "live",
        "direction": "LONG",
        "hold": 30,
        "prior_win": 0.40,
        "prior_payoff": 4.0,
        "formula": "pole ≥100% in ≤8 wks · flag 15–25 bars · retrace ≤25% · flag V ≤0.70× pole V · breakout V ≥1.4×V50 · stop = max(−6%, flag low) · target = pole height",
        "params": {"pole_min": 1.00, "pole_max_bars": 40,
                   "flag_min_bars": 15, "flag_max_bars": 25,
                   "flag_max_depth": 0.25, "vol_mult": 1.4,
                   "stop_pct": 0.06},
    },
    {
        "id": "flat_base",
        "name": "Flat Base",
        "short": "Flat base",
        "family": "Base",
        "book": "William J. O'Neil — How to Make Money in Stocks",
        "status": "live",
        "direction": "LONG",
        "hold": 45,
        "prior_win": 0.45,
        "prior_payoff": 2.0,
        "formula": "40-bar base (8 wks) · depth ≤15% · prior 120-bar uptrend ≥30% · pivot = base high · V ≥1.4×V50 · stop = max(base low, −5%) · target 2R",
        "params": {"base_bars": 40, "max_depth": 0.15,
                   "prior_uptrend": 0.30, "vol_mult": 1.4,
                   "stop_pct": 0.05, "target_r": 2.0},
    },
    {
        "id": "ascending_base",
        "name": "Ascending Base",
        "short": "Ascending base",
        "family": "Base",
        "book": "O'Neil / Minervini — three rising pullbacks",
        "status": "live",
        "direction": "LONG",
        "hold": 50,
        "prior_win": 0.46,
        "prior_payoff": 2.25,
        "formula": "3 rising pullback lows, each 10–20% · 45–80 bars · pivot = base high · V ≥1.4×V50 · stop = max(third low, −5%) · target 2.25R",
        "params": {"min_bars": 45, "max_bars": 80,
                   "pullback_min": 0.10, "pullback_max": 0.20,
                   "vol_mult": 1.4, "stop_pct": 0.05,
                   "target_r": 2.25},
    },
    {
        "id": "ma_50_200",
        "name": "50/200 Golden Cross",
        "short": "Golden cross",
        "family": "Trend",
        "book": "Classical trend following (Faber variant documented)",
        "status": "live",
        "direction": "LONG",
        "hold": 250,
        "prior_win": 0.40,
        "prior_payoff": 3.0,
        "formula": "SMA50 crosses above SMA200 · first confirmation within 20 bars (SMA50 >1.01×SMA200, C > SMA200) · stop = max(−8%, 3% below SMA200) · exit reverse cross",
        "params": {"fast": 50, "slow": 200, "slope_lookback": 22,
                   "buffer": 0.01, "stop_pct": 0.08, "target_r": 3.0},
    },
    {
        "id": "momentum_12_1",
        "name": "12-1 Momentum",
        "short": "12-1 mom",
        "family": "Cross-sectional",
        "book": "Jegadeesh & Titman (1993)",
        "status": "live",
        "direction": "LONG",
        "hold": 60,
        "prior_win": 0.55,
        "prior_payoff": 2.0,
        "backtestable": False,
        "backtest_note": "Cross-sectional portfolio rule; needs a ranked "
                         "universe per date, so it is scan-only for now.",
        "formula": "R = C[t−21] / C[t−252] − 1 · top decile of universe",
        "params": {"skip_days": 21, "lookback": 252, "top_pct": 0.10,
                   "stop_atr": 2.0, "target_atr": 4.0},
    },
    {
        "id": "low_vol_momentum",
        "name": "Low-Volatility Momentum",
        "short": "Low-vol mom",
        "family": "Cross-sectional",
        "book": "Low-volatility anomaly + momentum",
        "status": "live",
        "direction": "LONG",
        "hold": 60,
        "prior_win": 0.55,
        "prior_payoff": 2.0,
        "backtestable": False,
        "backtest_note": "Cross-sectional portfolio rule; scan-only for now.",
        "formula": "top 20% momentum · bottom 50% sigma(60) · 2·ATR stop",
        "params": {"skip_days": 21, "lookback": 252, "top_pct": 0.20,
                   "vol_window": 60, "vol_max_pct": 0.50,
                   "stop_atr": 2.0, "target_atr": 4.0},
    },
    {
        "id": "pead",
        "name": "Post-Earnings Drift",
        "short": "PEAD",
        "family": "Event",
        "book": "Ball & Brown (1968) / Bernard & Thomas (1989)",
        "status": "data_pending",
        "direction": "LONG",
        "hold": 40,
        "prior_win": 0.57,
        "prior_payoff": 2.0,
        "formula": "EPS surprise ≥ +10% · next-day gap < 8% · hold 20–60 bars",
        "params": {"surprise_min": 0.10, "gap_max": 0.08, "hold": 40},
        "data_need": "earnings_surprise (actual vs consensus) with filing dates",
    },
    {
        "id": "promoter_buying",
        "name": "Promoter / Insider Buying Cluster",
        "short": "Promoter buys",
        "family": "Event",
        "book": "Indian disclosure-flow research",
        "status": "data_pending",
        "direction": "LONG",
        "hold": 60,
        "prior_win": 0.56,
        "prior_payoff": 2.0,
        "formula": "≥3 insiders or promoter stake +1% in 30 days · no pledge increase",
        "params": {"min_insiders": 3, "promoter_delta": 0.01,
                   "window_days": 30},
        "data_need": "shareholding history (pledge_ingest stores latest only)",
    },
]

STRATEGY_BY_ID = {s["id"]: s for s in STRATEGIES}
LIVE_IDS = [s["id"] for s in STRATEGIES if s["status"] == "live"]
PENDING_IDS = [s["id"] for s in STRATEGIES if s["status"] != "live"]


# ============================================================
# Constants and small helpers
# ============================================================
DEFAULT_MIN_BARS = 260
DEFAULT_MIN_PRICE = 20.0
# A structural stop closer than 1.5% to entry is inside the noise band; a
# normal gap would then score as a -5R "loss" that the book never intended.
# Widening to 1.5% keeps R comparable across strategies.
MIN_RISK_PCT = 0.015


def tick_size(price: float) -> float:
    """NSE tick band, same bands as traders/base.py."""
    try:
        p = float(price)
    except (TypeError, ValueError):
        return 0.05
    if p < 1000:
        return 0.05 if p < 500 else 0.10
    return 0.50 if p < 5000 else 1.00


def _sma(values: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) < n or n <= 0:
        return out
    cs = np.cumsum(np.insert(np.asarray(values, dtype=float), 0, 0.0))
    out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def _atr_wilder(h: np.ndarray, l: np.ndarray, c: np.ndarray,
                n: int = 20) -> np.ndarray:
    """Wilder ATR. First value is the SMA of the first n true ranges."""
    m = len(c)
    out = np.full(m, np.nan, dtype=float)
    if m < n + 1:
        return out
    tr = np.empty(m, dtype=float)
    tr[0] = float(h[0] - l[0])
    for i in range(1, m):
        tr[i] = max(float(h[i] - l[i]),
                    abs(float(h[i] - c[i - 1])),
                    abs(float(l[i] - c[i - 1])))
    out[n - 1] = float(np.mean(tr[:n]))
    for i in range(n, m):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def build_indicators(o, h, l, c, v) -> dict:
    """Every rolling series the detectors need, computed once per symbol.

    ``shift(1)`` is deliberate: a window defined as "the prior N bars" must
    not contain the decision bar, or a breakout would be compared with itself.
    """
    hs = pd.Series(h, dtype=float)
    ls = pd.Series(l, dtype=float)
    vs = pd.Series(v, dtype=float)
    vol50_prev = vs.rolling(50).mean().shift(1).to_numpy()
    vol20_prev = vs.rolling(20).mean().shift(1).to_numpy()
    return {
        "atr20": _atr_wilder(h, l, c, 20),
        "sma50": _sma(c, 50),
        "sma150": _sma(c, 150),
        "sma200": _sma(c, 200),
        "hh20": hs.rolling(20).max().shift(1).to_numpy(),
        "hh252": hs.rolling(252).max().shift(1).to_numpy(),
        "ll10": ls.rolling(10).min().shift(1).to_numpy(),
        "vol50_prev": vol50_prev,
        "vol20_prev": vol20_prev,
        "vol50_now": vs.rolling(50).mean().to_numpy(),
        "vol10_now": vs.rolling(10).mean().to_numpy(),
    }


# ============================================================
# Exit text (R40 shape)
# ============================================================
_EXIT_TEXT = {
    "donchian_20": {
        "stop": "Two ATRs below entry is the Turtle noise stop. It is wide on purpose: the same volatility that created the 20-day high must not stop the trade.",
        "target": "No fixed target in the book — the 10-day low exit lets a trend run. The research target here is 3R, for comparability only.",
        "offset": "Reduce or exit when the index loses its 200-day average; the setup needs a trend, not a stock-picker's opinion.",
        "invalidation": "Close below the 10-day low, or a close back under the 20-day breakout level.",
        "exhaustion": "A blow-off day (range > 3×ATR, volume > 3× average) after a long run is a trim signal, not an add.",
    },
    "high_52w": {
        "stop": "Cut at 7.5% below entry, or the 10-day low if that is tighter; never wider than 7.5%. O'Neil's rule caps the loss before a failed breakout becomes a position.",
        "target": "Take 20–25% into strength (the simulation uses the fixed +22.5% and a 40-bar cap). If the stock gains 20% in under 3 weeks, hold to 8 weeks instead — that is a leader, not a swing.",
        "offset": "If the index prints 4–5 distribution days in 4 weeks, sell into strength and raise cash.",
        "invalidation": "Close below the 50-day average or back under the breakout pivot.",
        "exhaustion": "Largest daily gain of the move on heaviest volume, or an exhaustion gap — tighten stops.",
    },
    "cup_handle": {
        "stop": "7.5% below entry or below the handle low, whichever is tighter.",
        "target": "20–25% above entry (the simulation uses the fixed +22.5%); the book also allows trailing the 50-day average once the trade is 20% up.",
        "offset": "A market correction voids the setup regardless of the stock's shape.",
        "invalidation": "Close under the handle low, or a handle that forms in the lower half of the cup.",
        "exhaustion": "Volume climax on the breakout day followed by an immediate reversal.",
    },
    "vcp": {
        "stop": "Below the final contraction low, capped at 7% risk.",
        "target": "2.5R in the simulation; the book also allows the measured move from the final contraction.",
        "offset": "If the index loses its 50-day average, halve size; the pattern needs a Stage-2 tape.",
        "invalidation": "Close below the final contraction low, or volume expanding while the range contracts (distribution).",
        "exhaustion": "A wide-range breakout bar that closes in the lower half of its range.",
    },
    "high_tight_flag": {
        "stop": "6% below entry or below the flag low, whichever is tighter. This setup fails fast.",
        "target": "Measured move: add the pole height to the breakout point.",
        "offset": "If the flag is older than 25 bars, drop it — the setup decays with time.",
        "invalidation": "Close below the flag low, or a retracement deeper than 25% of the pole.",
        "exhaustion": "First distribution day after the breakout; the pole already spent the move.",
    },
    "flat_base": {
        "stop": "Below the base low, capped at 5% risk.",
        "target": "2R in the simulation. Flat bases are slow; demanding more turns winners into round trips.",
        "offset": "A market correction during the base invalidates it.",
        "invalidation": "Close below the base low, or base depth expanding past 15%.",
        "exhaustion": "Breakout volume below average — the move has no sponsorship.",
    },
    "ascending_base": {
        "stop": "Below the third pullback low, capped at 5% risk.",
        "target": "2.25R in the simulation; the book also allows trailing the 20-day average.",
        "offset": "If the third pullback undercuts the second, the ascending structure is broken.",
        "invalidation": "Any low below the prior low in the sequence.",
        "exhaustion": "Breakout on below-average volume.",
    },
    "ma_50_200": {
        "stop": "Tighter of 8% below entry and 3% below the 200-day average. A close back under the 200-DMA is the invalidation warning.",
        "target": "The book exit is the reverse cross; the 3R target is research-only and is not simulated. This is a regime trade, slow by design.",
        "offset": "Exit on the death cross even if the stop has not been hit.",
        "invalidation": "SMA50 crossing back below SMA200.",
        "exhaustion": "Not applicable — the signal is a regime change, not a momentum burst.",
    },
    "momentum_12_1": {
        "stop": "Two ATRs below entry.",
        "target": "Four ATRs, or monthly rebalance out of the decile.",
        "offset": "Exit when the stock leaves the top quintile of 12-1 momentum.",
        "invalidation": "Close below the 200-day average.",
        "exhaustion": "Momentum crash: the decile's breadth deteriorates sharply.",
    },
    "low_vol_momentum": {
        "stop": "Two ATRs below entry.",
        "target": "Four ATRs, or monthly rebalance.",
        "offset": "Exit when volatility expands into the top half of the universe.",
        "invalidation": "Close below the 200-day average.",
        "exhaustion": "Volatility spike while price stalls.",
    },
}


def _exit_block(sid: str, entry: float, stop: float, target: float,
                hold: int, direction: str = "LONG_ENTRY") -> dict:
    t = _EXIT_TEXT.get(sid, {})
    long_side = direction == "LONG_ENTRY"
    stop_cond = (f"close ≤ ₹{stop:.2f}" if long_side
                 else f"close ≥ ₹{stop:.2f}")
    target_cond = (f"close ≥ ₹{target:.2f}" if long_side
                   else f"close ≤ ₹{target:.2f}")
    return {
        "stop_out": {
            "thesis": t.get("stop", "Exit where the setup is proven wrong."),
            "hard_number": round(float(stop), 2),
            "condition": stop_cond,
        },
        "target": {
            "thesis": t.get("target", "Take profit at the research target."),
            "hard_number": round(float(target), 2),
            "condition": target_cond,
        },
        "offset": {
            "thesis": t.get("offset", "Market regime overrides the setup."),
            "trigger": "index regime turns against the trade",
        },
        "invalidation": {
            "thesis": t.get("invalidation", "Structure broken."),
            "condition": "see thesis",
        },
        "exhaustion": {
            "thesis": t.get("exhaustion", "Climax behaviour."),
            "rule": "trim or tighten",
        },
        "time_exit": {
            "thesis": "Time stop keeps capital from sitting in a dead idea.",
            "sessions": int(hold),
        },
    }


def _warning_exit_block(entry: float, stop: float, target: float,
                        hold: int) -> dict:
    """R40 block for a TOP_WARNING. It is not a short (R43)."""
    return {
        "stop_out": {
            "thesis": "The warning is invalidated if price reclaims the "
                      "upside level. This is not a stop-loss because there is "
                      "no short position.",
            "hard_number": round(float(stop), 2),
            "condition": f"close ≥ ₹{stop:.2f}",
        },
        "target": {
            "thesis": "Downside objective is informational only. R43 forbids "
                      "shorting; use it to review long exposure.",
            "hard_number": round(float(target), 2),
            "condition": f"close ≤ ₹{target:.2f}",
        },
        "offset": {
            "thesis": "Reduce long exposure on the death cross even if the "
                      "stop has not been hit.",
            "trigger": "index regime turns against the trade",
        },
        "invalidation": {
            "thesis": "SMA50 crossing back above SMA200.",
            "condition": "see thesis",
        },
        "exhaustion": {
            "thesis": "Not applicable — the signal is a regime change, not a "
                      "momentum burst.",
            "rule": "trim or tighten",
        },
        "time_exit": {
            "thesis": "The warning stays active until the cross reverses or "
                      "the review period ends.",
            "sessions": int(hold),
        },
    }


def _signal(ctx, sid, entry, stop, target, confidence, notes, raw,
            direction="LONG_ENTRY", signal_type="BREAKOUT",
            exit_mode=None):
    i = ctx["i"]
    meta = STRATEGY_BY_ID[sid]
    entry = float(entry)
    stop = float(stop)
    target = float(target)
    if direction == "LONG_ENTRY":
        if not (stop < entry < target):
            return None
    else:
        if not (target < entry < stop):
            return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if direction == "LONG_ENTRY" and risk / entry < MIN_RISK_PCT:
        stop = entry * (1.0 - MIN_RISK_PCT)
        risk = entry - stop
        if not (stop < entry < target):
            return None
    hold = int(meta.get("hold", 40))
    raw = dict(raw or {})
    raw["exits"] = _exit_block(sid, entry, stop, target, hold,
                               direction=direction)
    raw["params"] = dict(meta.get("params", {}))
    raw["indicators"] = raw.get("indicators", {})
    if exit_mode:
        raw["exit_mode"] = exit_mode
    return {
        "symbol": ctx["sym"],
        "method": sid,
        "name": meta["name"],
        "family": meta["family"],
        "direction": direction,
        "signal_type": signal_type,
        "date": ctx["date"][i],
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "rr": round((target - entry) / risk, 2),
        "risk_pct": round(risk / entry, 4),
        "confidence": confidence,
        "notes": notes,
        "tags": list(meta.get("tags") or [
            meta["family"].lower(),
            meta["short"].lower().replace(" ", "-"),
        ]),
        "hold": hold,
        "raw": raw,
    }


def _vol_ok(v, ind, i, mult, key="vol50_prev"):
    base = ind[key][i]
    if base is None or not np.isfinite(base) or base <= 0:
        return False, 0.0
    ratio = float(v[i]) / float(base)
    return ratio >= mult, ratio


def _near_high(o, h, l, c, i, frac=0.75):
    rng = float(h[i] - l[i])
    if rng <= 0:
        return False
    return float(c[i] - l[i]) >= frac * rng


def _trend_template(c, l, h, ind, i, rs_pct=None):
    """Minervini's trend template. Returns (ok, detail)."""
    s50, s150, s200 = ind["sma50"][i], ind["sma150"][i], ind["sma200"][i]
    if not all(np.isfinite(x) for x in (s50, s150, s200)):
        return False, "insufficient moving-average history"
    if not (c[i] > s150 and c[i] > s200):
        return False, "price below 150/200 DMA"
    if not s150 > s200:
        return False, "150 DMA below 200 DMA"
    if not ind["sma200"][i - 22] > 0 or not s200 > ind["sma200"][i - 22]:
        return False, "200 DMA not rising"
    if not s50 > s150:
        return False, "50 DMA below 150 DMA"
    if not c[i] > s50:
        return False, "price below 50 DMA"
    lo = float(np.min(l[max(0, i - 251):i + 1]))
    hi = float(np.max(h[max(0, i - 251):i + 1]))
    if lo <= 0 or hi <= 0:
        return False, "no 52-week range"
    if c[i] < 1.30 * lo:
        return False, "less than 30% above 52-week low"
    if c[i] < 0.75 * hi:
        return False, "more than 25% below 52-week high"
    if rs_pct is not None and rs_pct < 0.70:
        return False, "relative strength below 70th percentile"
    return True, "trend template passed"


# ============================================================
# Detectors — each takes ctx and returns a signal or None
# ============================================================
def detect_donchian_20(ctx):
    """Turtle System 1: 20-day breakout, 2N stop, 10-day exit."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 21:
        return None
    hh20 = ind["hh20"][i]
    if not np.isfinite(hh20):
        return None
    tick = tick_size(c[i])
    if c[i] <= hh20 + tick:
        return None
    # Fresh cross only: yesterday must not already have been above its channel.
    hh20_y = ind["hh20"][i - 1]
    if np.isfinite(hh20_y) and c[i - 1] > hh20_y + tick:
        return None
    atr = ind["atr20"][i - 1]
    if not np.isfinite(atr) or atr <= 0:
        return None
    stop = c[i] - 2.0 * atr
    target = c[i] + 6.0 * atr
    if stop <= 0:
        return None
    vol_ok, vol_ratio = _vol_ok(v, ind, i, 1.0)
    conf = "HIGH" if vol_ok else "MED"
    return _signal(
        ctx, "donchian_20", c[i], stop, target, conf,
        f"20d high ₹{hh20:,.2f} cleared · N=₹{atr:,.2f} · "
        f"stop 2N=₹{stop:,.2f} · volume {vol_ratio:.2f}×",
        {"indicators": {"hh20": hh20, "atr20": atr,
                        "vol_ratio": round(vol_ratio, 3)},
         "overlap_note": "Father of most breakout methods; overlaps high_52w."},
         exit_mode="ll10",
    )


def detect_high_52w(ctx):
    """52-week (or all-time) high with trend template and volume."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 253:
        return None
    hh = ind["hh252"][i]
    if not np.isfinite(hh):
        return None
    tick = tick_size(c[i])
    if c[i] <= hh * 1.001 + tick:
        return None
    if np.isfinite(ind["hh252"][i - 1]) and c[i - 1] > ind["hh252"][i - 1]:
        return None
    ok, why = _trend_template(c, l, h, ind, i, ctx.get("rs_pct"))
    if not ok:
        return None
    vok, vr = _vol_ok(v, ind, i, 1.4)
    if not vok or not _near_high(ctx["o"], h, l, c, i):
        return None
    entry = c[i]
    stop = max(entry * 0.925, float(np.min(l[i - 10:i])) - tick)
    target = entry * 1.225
    return _signal(
        ctx, "high_52w", entry, stop, target, "HIGH",
        f"52w high ₹{hh:,.2f} cleared · {why} · volume {vr:.2f}× · "
        f"stop −{100 * (entry - stop) / entry:.1f}%",
        {"indicators": {"hh252": hh, "vol_ratio": round(vr, 3),
                        "rs_pct": ctx.get("rs_pct")},
         "overlap_note": "Nests inside donchian_20 when both fire."},
    )


def detect_cup_handle(ctx):
    """O'Neil cup with handle. U-shape, handle in the upper half."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 120:
        return None
    window = min(325, i + 1)
    start = i - window + 1
    # Left rim: highest high in the first 60% of the window (not the handle).
    rim_end = start + max(20, int(window * 0.60))
    hi_idx = start + int(np.argmax(h[start:rim_end]))
    hi = float(h[hi_idx])
    if hi_idx >= i - 25:
        return None
    lo_idx = hi_idx + int(np.argmin(l[hi_idx:i + 1]))
    lo = float(l[lo_idx])
    if hi <= 0 or lo <= 0:
        return None
    depth = (hi - lo) / hi
    if not (0.12 <= depth <= 0.33):
        return None
    weeks = (i - hi_idx) / 5.0
    if not (7.0 <= weeks <= 65.0):
        return None
    if float(np.max(c[lo_idx:i + 1])) < lo + 0.70 * (hi - lo):
        return None
    if i - lo_idx < 8:
        return None
    # The handle is the pre-breakout consolidation. Today is the breakout bar,
    # so it must not be inside the handle (its high would become the pivot).
    handle_n = 10
    handle_start = max(lo_idx + 1, i - handle_n)
    if i - handle_start < 5:
        return None
    hh_h = float(np.max(h[handle_start:i]))
    hl_h = float(np.min(l[handle_start:i]))
    if hh_h <= 0:
        return None
    d_h = (hh_h - hl_h) / hh_h
    if d_h > min(0.12, depth / 3.0):
        return None
    if hl_h < lo + 0.50 * (hi - lo):
        return None
    cup_vol = float(np.mean(v[hi_idx:i]))
    handle_vol = float(np.mean(v[handle_start:i]))
    if cup_vol <= 0 or handle_vol > 0.80 * cup_vol:
        return None
    pivot = hh_h
    if c[i] <= pivot * 1.0005:
        return None
    vok, vr = _vol_ok(v, ind, i, 1.4)
    if not vok or not _near_high(ctx["o"], h, l, c, i):
        return None
    entry = c[i]
    stop = max(entry * 0.925, hl_h - tick_size(entry))
    target = entry * 1.225
    return _signal(
        ctx, "cup_handle", entry, stop, target, "HIGH",
        f"cup {depth * 100:.0f}% / {weeks:.0f}wk · handle {d_h * 100:.1f}% · "
        f"pivot ₹{pivot:,.2f} · volume {vr:.2f}×",
        {"indicators": {"cup_high": hi, "cup_low": lo,
                        "cup_depth": round(depth, 4),
                        "cup_weeks": round(weeks, 1),
                        "handle_depth": round(d_h, 4),
                        "pivot": pivot, "vol_ratio": round(vr, 3)}},
    )


def _pivots(values: np.ndarray, start: int, end: int, k: int = 3,
            kind: str = "low") -> list:
    """Local extrema, collapsed so a flat bottom is one pivot, not two."""
    out = []
    for j in range(max(start + k, k), min(end, len(values) - k)):
        win = values[j - k:j + k + 1]
        v = values[j]
        hit = ((kind == "low" and v == np.min(win))
               or (kind == "high" and v == np.max(win)))
        if not hit:
            continue
        if out and j - out[-1] <= k:
            # Adjacent plateaus produce two equal extrema; keep the extreme.
            if ((kind == "low" and values[j] <= values[out[-1]])
                    or (kind == "high" and values[j] >= values[out[-1]])):
                out[-1] = j
            continue
        out.append(j)
    return out


def _zigzag(h: np.ndarray, l: np.ndarray, start: int, end: int,
            pct: float = 0.03) -> list:
    """Alternating swing pivots, confirmed by a minimum reversal.

    Local-extrema detection sees every 3-bar wiggle inside a pullback. A VCP
    contraction is a swing, not a wiggle, so we walk the series and only
    confirm a high/low after price reverses by ``pct``. Returns
    ``[(index, "H"|"L", price), ...]`` in chronological order.
    """
    piv = []
    if end <= start:
        return piv
    direction = 1                      # 1 = tracking a high, -1 = tracking a low
    hi_idx, hi = start, float(h[start])
    lo_idx, lo = start, float(l[start])
    for j in range(start + 1, end + 1):
        if direction == 1:
            if h[j] >= hi:
                hi_idx, hi = j, float(h[j])
            if l[j] <= hi * (1.0 - pct):
                piv.append((hi_idx, "H", hi))
                direction = -1
                lo_idx, lo = j, float(l[j])
        else:
            if l[j] <= lo:
                lo_idx, lo = j, float(l[j])
            if h[j] >= lo * (1.0 + pct):
                piv.append((lo_idx, "L", lo))
                direction = 1
                hi_idx, hi = j, float(h[j])
    if direction == 1:
        piv.append((hi_idx, "H", hi))
    else:
        piv.append((lo_idx, "L", lo))
    return piv


def detect_vcp(ctx):
    """Minervini VCP: 2–6 contractions, each at most 0.80× the prior."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 120:
        return None
    ok, why = _trend_template(c, l, h, ind, i, ctx.get("rs_pct"))
    if not ok:
        return None
    start = max(0, i - 120)
    piv = _zigzag(h, l, start, i, pct=0.04)
    piv_h = [(j, p) for j, t, p in piv if t == "H"]
    piv_l = [(j, p) for j, t, p in piv if t == "L"]
    if len(piv_h) < 2 or len(piv_l) < 2:
        return None
    depths = []
    lows = []
    low_px = []
    run_max = 0.0
    for idx, (pj, ph) in enumerate(piv_h):
        run_max = max(run_max, ph)
        # A failed rally far below the base high belongs to the prior
        # contraction, not to a new one.
        if ph < run_max * 0.95:
            continue
        nxt = piv_h[idx + 1][0] if idx + 1 < len(piv_h) else i + 1
        inside = [(k, q) for k, q in piv_l if pj < k < nxt]
        if not inside:
            continue
        k, q = min(inside, key=lambda z: z[1])
        if ph <= 0:
            continue
        d = (ph - q) / ph
        # A sub-2% dip is noise, not a contraction.
        if d < 0.02:
            continue
        depths.append(d)
        lows.append(k)
        low_px.append(q)
    if len(depths) < 2:
        return None
    depths = depths[-6:]
    lows = lows[-6:]
    low_px = low_px[-6:]
    # VCP lows must rise (a 2% undercut is tolerated as noise).
    if not all(y >= x * 0.98 for x, y in zip(low_px, low_px[1:])):
        return None
    for a, b in zip(depths, depths[1:]):
        if not b < a:
            return None
        if b > 0.80 * a:
            return None
    if depths[-1] > 0.08:
        return None
    if depths[-1] > 0.50 * depths[0]:
        return None
    # Volume dry-up INTO the pivot — measured before today's breakout bar,
    # whose expansion would otherwise hide the contraction it is confirming.
    if i < 50:
        return None
    dry = float(np.mean(v[i - 10:i]))
    base_v = float(np.mean(v[i - 50:i]))
    if base_v <= 0 or dry > 0.80 * base_v:
        return None
    final_low_idx = lows[-1]
    final_low = float(np.min(l[final_low_idx:i + 1]))
    pivot = float(np.max(h[final_low_idx:i]))
    if c[i] <= pivot * 1.001:
        return None
    vok, vr = _vol_ok(v, ind, i, 1.4)
    if not vok:
        return None
    entry = c[i]
    stop = max(final_low * 0.995, entry * 0.93)
    if stop >= entry:
        return None
    target = entry + 2.5 * (entry - stop)
    return _signal(
        ctx, "vcp", entry, stop, target, "HIGH",
        f"{len(depths)} contractions {', '.join(f'{d * 100:.1f}%' for d in depths)} · "
        f"final {depths[-1] * 100:.1f}% · pivot ₹{pivot:,.2f} · "
        f"volume {vr:.2f}×",
        {"indicators": {"contractions": [round(d, 4) for d in depths],
                        "final_low": final_low, "pivot": pivot,
                        "vol_ratio": round(vr, 3),
                        "trend": why}},
    )


def detect_high_tight_flag(ctx):
    """O'Neil high tight flag: 100% pole, 3–5 week tight flag."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 60:
        return None
    pole_hi = None
    pole_lo = None
    pole_idx = None
    best_gain = 0.0
    for j in range(max(0, i - 42), i - 14):
        lo_j = max(0, j - 40)
        base = float(np.min(l[lo_j:j + 1]))
        if base <= 0:
            continue
        gain = (float(h[j]) - base) / base
        if gain >= 1.00 and gain > best_gain:
            best_gain = gain
            pole_hi, pole_lo, pole_idx = float(h[j]), base, j
    if pole_hi is None or pole_idx is None:
        return None
    flag_start = pole_idx + 1
    # Today is the breakout bar, not part of the flag.
    flag_len = i - flag_start
    if not (15 <= flag_len <= 25):
        return None
    flag_h = float(np.max(h[flag_start:i]))
    flag_l = float(np.min(l[flag_start:i]))
    if flag_h <= 0:
        return None
    depth = (flag_h - flag_l) / flag_h
    if depth > 0.25:
        return None
    pole_vol = float(np.mean(v[max(0, pole_idx - 20):pole_idx + 1]))
    flag_vol = float(np.mean(v[flag_start:i + 1]))
    if pole_vol <= 0 or flag_vol > 0.70 * pole_vol:
        return None
    pivot = float(np.max(h[flag_start:i]))
    if c[i] <= pivot * 1.001:
        return None
    vok, vr = _vol_ok(v, ind, i, 1.4)
    if not vok:
        return None
    entry = c[i]
    stop = max(entry * 0.94, flag_l * 0.995)
    if stop >= entry:
        return None
    target = entry + (pole_hi - pole_lo)
    return _signal(
        ctx, "high_tight_flag", entry, stop, target, "HIGH",
        f"pole +{100 * (pole_hi - pole_lo) / pole_lo:.0f}% · "
        f"flag {flag_len} bars / {depth * 100:.1f}% · "
        f"pivot ₹{pivot:,.2f} · volume {vr:.2f}×",
        {"indicators": {"pole_high": pole_hi, "pole_low": pole_lo,
                        "flag_bars": flag_len,
                        "flag_depth": round(depth, 4),
                        "pivot": pivot, "vol_ratio": round(vr, 3)}},
    )


def detect_flat_base(ctx):
    """O'Neil flat base: five-plus weeks sideways, depth ≤15%."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 160:
        return None
    base_len = 40
    b0, b1 = i - base_len, i  # [b0, b1) excludes today
    base_h = float(np.max(h[b0:b1]))
    base_l = float(np.min(l[b0:b1]))
    if base_h <= 0:
        return None
    depth = (base_h - base_l) / base_h
    if depth > 0.15:
        return None
    prior_low = float(np.min(l[max(0, b0 - 120):b0]))
    if prior_low <= 0 or c[b0] < 1.30 * prior_low:
        return None
    pivot = base_h
    if c[i] <= pivot + tick_size(c[i]):
        return None
    vok, vr = _vol_ok(v, ind, i, 1.4)
    if not vok or not _near_high(ctx["o"], h, l, c, i):
        return None
    entry = c[i]
    stop = max(base_l * 0.995, entry * 0.95)
    if stop >= entry:
        return None
    target = entry + 2.0 * (entry - stop)
    return _signal(
        ctx, "flat_base", entry, stop, target, "MED",
        f"{base_len} bars flat · depth {depth * 100:.1f}% · "
        f"pivot ₹{pivot:,.2f} · volume {vr:.2f}×",
        {"indicators": {"base_bars": base_len,
                        "base_depth": round(depth, 4),
                        "pivot": pivot, "vol_ratio": round(vr, 3)}},
    )


def detect_ascending_base(ctx):
    """Three rising pullbacks, each 10–20%, then a breakout."""
    h, l, c, v, ind, i = (ctx["h"], ctx["l"], ctx["c"], ctx["v"],
                          ctx["ind"], ctx["i"])
    if i < 90:
        return None
    start = max(0, i - 80)
    piv_l = _pivots(l, start, i, k=3, kind="low")[-3:]
    piv_h = _pivots(h, start, i, k=3, kind="high")
    if len(piv_l) < 3 or len(piv_h) < 3:
        return None
    lo1, lo2, lo3 = [float(l[j]) for j in piv_l]
    if not (lo1 < lo2 < lo3):
        return None
    depths = []
    for pj in piv_l:
        before = [x for x in piv_h if x < pj]
        if not before:
            return None
        hi = float(h[before[-1]])
        if hi <= 0:
            return None
        d = (hi - float(l[pj])) / hi
        if not (0.10 <= d <= 0.20):
            return None
        depths.append(d)
    base_len = i - piv_l[0]
    if not (45 <= base_len <= 80):
        return None
    pivot = float(np.max(h[start:i]))
    if c[i] <= pivot + tick_size(c[i]):
        return None
    vok, vr = _vol_ok(v, ind, i, 1.4)
    if not vok or not _near_high(ctx["o"], h, l, c, i):
        return None
    entry = c[i]
    stop = max(lo3 * 0.995, entry * 0.95)
    if stop >= entry:
        return None
    target = entry + 2.25 * (entry - stop)
    return _signal(
        ctx, "ascending_base", entry, stop, target, "MED",
        f"3 rising lows ₹{lo1:,.2f} → ₹{lo2:,.2f} → ₹{lo3:,.2f} · "
        f"pullbacks {', '.join(f'{d * 100:.0f}%' for d in depths)} · "
        f"pivot ₹{pivot:,.2f}",
        {"indicators": {"lows": [lo1, lo2, lo3],
                        "pullbacks": [round(d, 4) for d in depths],
                        "pivot": pivot, "vol_ratio": round(vr, 3)}},
    )


def detect_ma_50_200(ctx):
    """Golden cross, confirmed within 20 bars.

    The cross bar itself can never satisfy a 1% buffer (SMA50 equals SMA200 by
    definition there), so the rule is: a cross happened recently, and this is
    the first bar where the buffer and price>200 both hold. The 200-DMA slope
    is reported as context, not used as a hard gate.
    """
    c, ind, i = ctx["c"], ctx["ind"], ctx["i"]
    if i < 225:
        return None
    s50, s200 = ind["sma50"], ind["sma200"]
    if not all(np.isfinite(x) for x in (s50[i], s200[i],
                                        s50[i - 1], s200[i - 1])):
        return None
    cross_at = None
    for j in range(i, max(1, i - 20) - 1, -1):
        if (np.isfinite(s50[j]) and np.isfinite(s200[j])
                and s50[j - 1] <= s200[j - 1] and s50[j] > s200[j]):
            cross_at = j
            break
    if cross_at is None or i - cross_at > 20:
        return None
    if c[i] <= s200[i]:
        return None
    if s50[i] <= 1.01 * s200[i]:
        return None
    # First confirmation only, so one cross yields one signal.
    if i - 1 >= cross_at and i - 23 >= 0:
        prev_ok = (c[i - 1] > s200[i - 1]
                   and s50[i - 1] > 1.01 * s200[i - 1])
        if prev_ok:
            return None
    entry = c[i]
    stop = max(s200[i] * 0.97, entry * 0.92)
    target = entry + 3.0 * (entry - stop)
    slope = ((s200[i] / s200[i - 22] - 1.0) * 100.0
             if np.isfinite(s200[i - 22]) and s200[i - 22] > 0 else 0.0)
    return _signal(
        ctx, "ma_50_200", entry, stop, target, "MED",
        f"SMA50 ₹{s50[i]:,.2f} > SMA200 ₹{s200[i]:,.2f} "
        f"({i - cross_at} bars after the cross) · 200DMA slope "
        f"{slope:+.1f}%/mo · stop ₹{stop:,.2f}",
        {"indicators": {"sma50": round(float(s50[i]), 2),
                        "sma200": round(float(s200[i]), 2),
                        "sma200_slope_22": round(float(slope), 3),
                        "bars_since_cross": int(i - cross_at)}},
        signal_type="CROSS", exit_mode="reverse_cross",
    )


def detect_death_cross(ctx):
    """TOP_WARNING on a 50/200 death cross (R43: no shorting)."""
    c, ind, i = ctx["c"], ctx["ind"], ctx["i"]
    if i < 222:
        return None
    s50, s200 = ind["sma50"], ind["sma200"]
    if not all(np.isfinite(x) for x in (s50[i], s200[i],
                                        s50[i - 1], s200[i - 1])):
        return None
    if not (s50[i - 1] >= s200[i - 1] and s50[i] < s200[i]):
        return None
    entry = c[i]
    stop = entry * 1.08      # upside invalidation: warning proven wrong
    target = entry * 0.85    # downside objective, informational only
    sig = _signal(
        ctx, "ma_50_200", entry, stop, target, "HIGH",
        f"Death cross: SMA50 ₹{s50[i]:,.2f} fell through SMA200 "
        f"₹{s200[i]:,.2f} — review existing positions",
        {"indicators": {"sma50": round(float(s50[i]), 2),
                        "sma200": round(float(s200[i]), 2)}},
        direction="TOP_WARNING", signal_type="CROSS",
    )
    if sig:
        # A warning is not a trade; risk fields are informational only.
        sig["rr"] = None
        sig["risk_pct"] = None
        sig["raw"]["exits"] = _warning_exit_block(entry, stop, target,
                                                  sig["hold"])
    return sig


# Cross-sectional detectors are executed by the engine, which owns the ranks.
# These functions build the signal once the caller supplies the percentile.
def detect_momentum_12_1(ctx):
    mom = ctx.get("mom_12_1")
    rank = ctx.get("mom_rank")
    # _pct_rank is ascending: 1.0 is the strongest momentum, so the top decile
    # is rank >= 0.90. Reversing this silently selects the laggards.
    if mom is None or rank is None or rank < 0.90:
        return None
    if i_bars(ctx) < 253:
        return None
    c, ind, i = ctx["c"], ctx["ind"], ctx["i"]
    atr = ind["atr20"][i - 1]
    if not np.isfinite(atr) or atr <= 0:
        return None
    entry = c[i]
    stop = entry - 2.0 * atr
    target = entry + 4.0 * atr
    return _signal(
        ctx, "momentum_12_1", entry, stop, target, "MED",
        f"12-1 momentum {mom * 100:.1f}% · percentile {rank * 100:.0f} (top decile)",
        {"indicators": {"momentum_12_1": round(mom, 4),
                        "percentile": round(rank, 4)}},
        signal_type="MOMENTUM",
    )


def detect_low_vol_momentum(ctx):
    mom = ctx.get("mom_12_1")
    rank = ctx.get("mom_rank")
    vol_rank = ctx.get("vol_rank")
    if mom is None or rank is None or vol_rank is None:
        return None
    # Top 20% momentum (rank >= 0.80) and bottom 50% volatility (rank <= 0.50).
    if rank < 0.80 or vol_rank > 0.50:
        return None
    if i_bars(ctx) < 253:
        return None
    c, ind, i = ctx["c"], ctx["ind"], ctx["i"]
    atr = ind["atr20"][i - 1]
    if not np.isfinite(atr) or atr <= 0:
        return None
    entry = c[i]
    stop = entry - 2.0 * atr
    target = entry + 4.0 * atr
    return _signal(
        ctx, "low_vol_momentum", entry, stop, target, "MED",
        f"12-1 momentum {mom * 100:.1f}% (percentile {rank * 100:.0f}) · "
        f"volatility percentile {vol_rank * 100:.0f} (bottom half)",
        {"indicators": {"momentum_12_1": round(mom, 4),
                        "mom_rank": round(rank, 4),
                        "vol_rank": round(vol_rank, 4)}},
        signal_type="MOMENTUM",
    )


def i_bars(ctx) -> int:
    return int(ctx["i"]) + 1


DETECTORS = {
    "donchian_20": detect_donchian_20,
    "high_52w": detect_high_52w,
    "cup_handle": detect_cup_handle,
    "vcp": detect_vcp,
    "high_tight_flag": detect_high_tight_flag,
    "flat_base": detect_flat_base,
    "ascending_base": detect_ascending_base,
    "ma_50_200": detect_ma_50_200,
    "momentum_12_1": detect_momentum_12_1,
    "low_vol_momentum": detect_low_vol_momentum,
}


def detect_all(ctx, include=None) -> list:
    """Run every live detector, then mark overlaps (R41: mark, don't prune)."""
    ids = include or list(DETECTORS)
    out = []
    for sid in ids:
        fn = DETECTORS.get(sid)
        if fn is None:
            continue
        try:
            sig = fn(ctx)
        except Exception:
            sig = None
        if sig is not None:
            out.append(sig)
    if len(out) > 1:
        names = [s["method"] for s in out]
        for s in out:
            s["raw"]["overlaps_with"] = [n for n in names if n != s["method"]]
    return out


def detect_warnings(ctx) -> list:
    """Warnings are separate from entries so the UI can label them."""
    try:
        sig = detect_death_cross(ctx)
    except Exception:
        sig = None
    return [sig] if sig else []


def strategy_meta(sid: str) -> dict:
    return dict(STRATEGY_BY_ID.get(sid, {}))
