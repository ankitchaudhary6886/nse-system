"""
Central strategy configuration.

EVERY tunable parameter for the swing strategy lives here.
To change behavior: edit ONE value in this file, restart the service.
No other file needs to be touched.

Sections:
  SETUP       — Gabani pullback detection thresholds
  SCREENER    — Stage-2 baseline + liquidity filters
  BACKTEST    — walk-forward simulator parameters
  REGIME      — market regime spectrum thresholds
  ALL_WEATHER — defensive-regime reversal detection
  SIZING      — capital allocation
  LEAGUE      — Trader League paper league + pre-deployment backtest

Note: this is a *measuring tool* config, not a recommendation set.
The owner decides what values to use based on their own research.
"""

# ============================================================
# SETUP — Gabani pullback detection (setup.py)
# ============================================================
SETUP = {
    "IMPULSE_LOOKBACK": 90,
    "IMPULSE_MIN_PCT": 0.18,         # v3.2: was 0.25
    "IMPULSE_MAX_PCT": 0.75,         # v3.2: was 0.50
    "EMA10_BREAK_TOL": 0.45,         # v3.3: was 0.35, v3.2: 0.25
    "PB_LOOKBACK": 25,
    "PB_MIN_PCT": 0.06,              # v3.3: was 0.08, v3.2: 0.12
    "PB_MAX_PCT": 0.25,              # v3.2: was 0.20
    "PB_MIN_DAYS": 6,
    "PB_MAX_DAYS": 20,               # v3.3: was 15
    "CRASH_WINDOW": 3,
    "CRASH_MAX_PCT": 0.15,
    "EMA10": 10,
    "EMA20": 20,
    "EMA_TOUCH_MULT": 0.03,
    "VOL_SMA_DAYS": 20,
    "TIGHT_ATR_MULT": 0.9,
    "TIGHT_MAX_RUN_BACK": 4,
    "TIGHT_MIN": 2,
    "MAX_STOP_PCT": 0.05,
    "TARGET_R_MULTIPLE": 3.0,        # measuring reference; owner decides
    "MAX_SHIFT": 2,
}

# ============================================================
# SCREENER — Stage-2 baseline + liquidity (scanner.py)
# ============================================================
SCREENER = {
    "EMA200": 200,
    "MIN_HISTORY": 220,
    "MOM_1M_MIN": 0.20,
    "MOM_3M_MIN": 0.30,
    "HIGH_52WK_MIN_RATIO": 0.75,
    "VOL_EXPLOSION_MULT": 2.5,
    "VOL_LOOKBACK": 60,
    "LIQ_DAYS": 20,
    "MIN_AVG_TURNOVER": 2e7,         # ₹2 cr average daily turnover
}

# ============================================================
# BACKTEST — walk-forward simulator (backtest.py)
# ============================================================
BACKTEST = {
    "HOLD_DAYS_MAX": 30,
    "ORDER_EXPIRY_BARS": 3,
    "TICK_SIZE": 0.05,
    "TARGET_R": 3.0,                 # default R for measurement
    "TRANCHES_ENABLED": False,
    "T_LEVEL_1": 2.0,
    "T_LEVEL_2": 3.0,
    "T_PCT_1": 0.33,
    "T_PCT_2": 0.33,
    "TRAIL_EMA": 10,
    "INITIAL_CAPITAL": 1_000_000,
    "SLIPPAGE_PCT": 0.001,
    "COMMISSION_PCT": 0.0005,
    "MAX_POSITIONS": 5,
    "MAX_PENDING_ORDERS": 20,
}

# ============================================================
# REGIME — spectrum classification (regime_spectrum.py)
# ============================================================
REGIME = {
    "STRONG_BULL_DIST_MIN": 0.02,    # 2% above EMA10
    "STRONG_BULL_BREADTH_MIN": 0.60,
    "EMA_PERIOD": 10,
    "EMA20_PERIOD": 20,
    "INDEX_CANDIDATES": ["^CNXSMALLCAP", "^CNXSC",
                         "NIFTY_SMALLCAP_100.NS", "^NSEI"],
}

# ============================================================
# ALL_WEATHER — defensive-regime reversal detection (all_weather.py)
#
# v4 (2026-10-15): four quality gates added, because measurement showed this
# was where the system bled. On the production (VM) ledger 149 of 155 signals
# were ALL_WEATHER; 68 of the 71 graded trades were ALL_WEATHER at a 5.9% win
# rate, contributing -52R of the -55R total. Its entries sat a median 35.5%
# below the 52-week high and 4.3% above the 52-week low -- it was buying
# falling knives in a defensive tape, with a 3R target.
#
# The SWING path requires the Stage-2 trend + liquidity screen and the sector
# gate. This path required none of them. Now it does.
#
# NOTE ON THE DEFAULTS: with the values below, ALL_WEATHER effectively stops
# emitting signals, because the trend gate rejects ~100% of the v3 population
# by construction -- a stock 25% below its 52-week high cannot simultaneously
# be above a rising EMA200. That is deliberate and evidence-backed, not an
# accident. To bring the mode back to life the one measured setting that still
# leaves signals is TREND_EMA=50 with TIER_ENABLED=False (~1.4% of candidates
# survived the audit replay). TREND_ENABLED=False restores old behaviour.
# ============================================================
ALL_WEATHER = {
    "BELOW_52W_MIN": 0.25,
    "NEAR_LOW_MAX": 0.15,
    "MAX_RISK_PCT": 0.05,
    # v4 (2026-10-15): 3.0 -> 1.0. Two independent samples both put 3.0R at the
    # BOTTOM of the 0.25-3.0R grid for this module:
    #   live episode (71 graded ALL_WEATHER trades): 3.0R = -0.775R per idea,
    #     1.0R = -0.718R, 0.25R = -0.296R
    #   multi-year regeneration (173 traded): 3.0R = -0.052R, 0.75-1.0R = +0.012R
    # Reason: no losing trade ever reached +2R. The best any loser printed was
    # +1.98R and only ~9% reached +1R, so a 3R target sits outside the
    # distribution of what these entries actually do.
    # NOTE: with the gates above enabled this path emits no signals at all, so
    # this value only bites if ALL_WEATHER is re-enabled. It is set to the
    # best-evidenced value so that re-enabling cannot silently reintroduce the
    # old mistake. (SETUP["TARGET_R_MULTIPLE"] is a DIFFERENT question and stays
    # at 3.0 -- the Gabani swing setup has a right-skewed MFE distribution where
    # a small target throws away the tail that pays for the loss rate.)
    "TARGET_R": 1.0,
    "TICK": 0.05,

    # --- gate 1: trend (the decisive one) ------------------------------
    "TREND_ENABLED": True,
    "TREND_EMA": 200,              # close must be above this EMA
    "TREND_REQUIRE_RISING": True,  # ...and that EMA must be rising
    "TREND_SLOPE_DAYS": 20,        # lookback used to decide "rising"

    # --- gate 2: liquidity --------------------------------------------
    # None = inherit SCREENER.LIQ_DAYS / MIN_AVG_TURNOVER so those numbers
    # live in exactly ONE place. Do not copy the literals here.
    "LIQ_ENABLED": True,
    "LIQ_DAYS": None,
    "MIN_AVG_TURNOVER": None,

    # --- gate 3: sector leadership ------------------------------------
    "SECTOR_ENABLED": True,
    "SECTOR_TOP_N": None,          # None = inherit sector_gate.TOP_N

    # --- gate 4: fundamental tier -------------------------------------
    # Uses all_weather._tier(), which until now was computed and then never
    # read by anything. NOTE: in the audit this behaves as a DATA-AVAILABILITY
    # gate rather than a quality gate -- band-universe fundamentals coverage is
    # empty, so nearly everything rates UNK and is blocked. Fix that coverage
    # before treating this gate as a measure of quality.
    "TIER_ENABLED": True,
    "MIN_TIER": "MED",             # HIGH passes, MED passes, UNK rejected
}

# ============================================================
# SIZING — capital allocation (sizing.py)
# ============================================================
SIZING = {
    "B_PAYOFF": 3.0,
    "MAX_ALLOC": 0.25,
    "RISK_PER_TRADE": 0.01,
    "DEFAULT_CAPITAL": 1_000_000,
    "FALLBACK_WINRATE": 0.35,
    # shape_score -> multiplier, first match wins (descending)
    "QUALITY_TIERS": [
        (80, 1.20),
        (60, 1.00),
        (40, 0.80),
        (0,  0.60),
    ],
}


# ============================================================
# LEAGUE — Trader League (trader_league.py): 14 books + our system,
# Rs 10 lakh play money each. Used by the backtest AND the live league.
# ============================================================
LEAGUE = {
    "CAPITAL": 1_000_000,            # Rs 10 lakh per player
    "RISK_PER_TRADE": 0.01,          # 1% of equity lost if the stop hits
    "MAX_POSITIONS": 10,
    "MAX_POSITION_PCT": 0.20,        # no stock above 20% of equity
    "MAX_STOP_PCT": 0.15,            # skip trades with a stop > 15% away
    "ORDER_VALID_BARS": 3,           # unfilled buy orders expire
    "MAX_HOLD_BARS": 60,             # safety time stop (books without one)
    "SLIPPAGE_PCT": 0.002,           # 0.2% per side, small/mid caps
    "INTRABAR": "path",              # "worst" = stop always first (stress)
    # Indian equity-delivery charges (Zerodha, verified Sep 2026)
    "BROKERAGE_PER_ORDER": 0.0,      # set 20 if your broker charges Rs 20
    "BROKERAGE_PCT": 0.0,
    "STT_PCT": 0.001,                # 0.1% on buy AND sell
    "STAMP_PCT": 0.00015,            # 0.015% on buy
    "EXCH_PCT": 0.0000297,           # NSE transaction charge
    "SEBI_PCT": 0.000001,            # Rs 10 per crore
    "GST_PCT": 0.18,
    "DP_CHARGE": 15.93,              # per stock per sell day
    "MIN_PRICE": 20.0,
    "MIN_TURNOVER": 1e7,             # Rs 1 cr avg daily value (point in time)
    "REPLAY_YEARS": 3,
    "REPLAY_SYMBOLS": 300,           # band stocks for the books' replay
    "LIVE_START": None,              # "YYYY-MM-DD" or None = first evening
    "BENCHMARK": "^NSEI",
    # real-money checklist thresholds
    "READY_MIN_TRADES": 50,
    "READY_MIN_PF": 1.3,
    "READY_MAX_DD": 0.25,
    "READY_MC_DD95": 0.35,
    "READY_MIN_LIVE_TRADES": 30,
}

def dump():
    """Print entire config for inspection."""
    import json
    print(json.dumps({
        "SETUP": SETUP,
        "SCREENER": SCREENER,
        "BACKTEST": BACKTEST,
        "REGIME": REGIME,
        "ALL_WEATHER": ALL_WEATHER,
        "SIZING": SIZING,
        "LEAGUE": LEAGUE,
    }, indent=2, default=str))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
        dump()
    else:
        dump()