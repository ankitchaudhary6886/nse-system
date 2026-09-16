# NEW FEATURES BACKLOG

Registry of every feature/indicator used by the system.

**Purpose:** When a new book requests a feature, check here first.
If it exists → reuse. If it doesn't → add it below, implement, mark DONE.

**Status legend:** DONE · BACKLOG · IN PROGRESS · DEPRECATED

---

## A. Existing features (DONE — usable today)

### Price & bar primitives
- `close`, `open`, `high`, `low`, `volume`, `date`
- `prev_close`, `prev_high`, `prev_low`
- `close_gt_open`, `inside_day`, `gap_pct`

### Moving averages
- `dma20`, `dma50`, `dma200`, `ema10`, `ema20`
- `slope200`, `above20`, `above50`, `above200`

### Momentum & volatility
- `mom_5d`, `mom_20d`, `mom_60d`, `rsi`
- `atr_14`, `atr_pct`, `ret_std20`, `beta`

### Structure
- `impulse_pct_60d`, `days_since_impulse_peak`
- `consolidation_range_pct`, `distance_from_52w_high`, `distance_from_52w_low`

### Volume
- `avg_vol_20`, `vol_ratio_20`, `delivery_pct`, `amplitude_5d`

### Pattern flags
- `pat_htf`, `pat_tri`, `pat_db`, `pat_flag`, `pat_ihs`, `pat_bear`, `pat_any`

### Cross-sectional
- `sector_rs`

### Fundamentals (source: TradingView India)
- `roce`, `roe`, `debt_to_equity`, `pe`, `pb`
- `operating_margin`, `net_profit_margin`
- `cfo_positive`, `market_cap_cr`, `beta_1y`, `eps_fy`, `book_value`
- `ev_ebitda`, `fcf_fy`, `net_debt_fy`, `dividend_yield`

### Trader-specific — John Crane
Reaction swing, reverse count, forward projection, action/reaction
lines, two-day rule, peg-leg, gap-and-go, gap reversal, trail day,
continuation gap, major reversal, SSTO %K, SSTO divergence.

### Trader-specific — Larry Spears
Beta filter, amplitude filter, gap classification, MA trend alignment,
counter-trend retracement, force index (13 / 3 period).

### Trader-specific — O'Shaughnessy (computable today)
- `price_appreciation_1y`, `mom_120d`, `market_cap_percentile`

### Trader-specific — Gray & Carlisle (computable today)
- `earnings_yield`, `book_to_market`, `roce_quality_gate`

### Trader-specific — Janet Lowe (computable today)
- `graham_intrinsic_value` (inline)

### Trader-specific — Way of the Turtle (computable today — inline)
`highest_high_prior_{10,20,55}d`, `lowest_low_prior_{10,20,55}d`,
`atr_20`, `sma_{100,150,250,350}`, `ema_{25,350}`,
`rolling_std_350d`, `channel_{top,bottom}` (ATR & Bollinger),
`swing_high_level`, `swing_low_level`.

### Trader-specific — 7 Simple Strategies (computable today — inline)
All indicators computed inline in `seven_simple_strategies.py`:
- `atr_14_wilder` — Wilder-style ATR (14-period EMA of true range)
- `ema_9` — 9-period EMA
- `dma_16`, `dma_24` — 16- and 24-period SMAs
- `mean_100d` — 100-day simple mean (used as the mean-reversion line)
- `trend_line` — line fitted through last 2 pivot lows/highs
- `channel_lines` — parallel trend lines through pivots
- `pivot_lows`, `pivot_highs` — pivot detection (k=3)
- `hammer_pattern` — lower shadow >= 2x body, upper <= 0.2x body,
  close in upper 25% of range
- `bullish_doji_pattern` — body <= 0.5 x ATR, close > open,
  close in upper 50% of range
- `three_lower_closes` — 3 consecutive lower closes

**Note:** the pivot/trend-line primitives are the same pattern used
by John Crane's trendline helpers in `traders/base.py`. If a third
module needs them, promote to `traders/base.py` to avoid duplication.

---

## B. Requested features (BACKLOG)

### Requested by: *What Works on Wall Street* (O'Shaughnessy)

- **price_to_sales** — M. Blocks oshaughnessy: low_psr_value,
  low_psr_plus_rs, cornerstone_growth_original,
  cornerstone_growth_improved
- **eps_growth_1y** — M. Blocks oshaughnessy:
  worst_earnings_gains, cornerstone_growth_original,
  cornerstone_growth_improved
- **shareholder_yield** — M. Blocks oshaughnessy:
  cornerstone_value_improved
- **price_to_cashflow** — M. Blocks oshaughnessy: low_pcf_value
- **sales_ttm** — M.
- **cashflow_fy** — M. Blocks oshaughnessy:
  market_leaders_universe (full), low_pcf_value
- **shares_outstanding** — S.

### Requested by: *Quantitative Value* (Gray & Carlisle)

- **ebit** — M. Blocks quantitative_value:
  ebit_enterprise_multiple, magic_formula_proxy,
  quantitative_value_model
- **total_enterprise_value (tev)** — M.
- **gross_profit** — M.
- **total_assets** — S. Blocks quantitative_value: STA, SNOA,
  F_SCORE, FS_SCORE
- **current_assets** — S.
- **current_liabilities** — S.
- **cash_and_equivalents** — S.
- **fundamentals_history** — yearly snapshot (multi-year storage).
  **L — single largest unblocker.** Unlocks ~11 methods across
  QV, O'Shaughnessy, Lowe.
- **insider_trades** — SEBI SAST. L.
- **short_interest** — NSE feed. M.
- **activist_13d_filings** — SEBI SAST. L.

### Requested by: *Value Investing Made Easy* (Janet Lowe)

- **ncav_per_share** — M.
- **tangible_book_value** — S.
- **net_quick_liquidation_value** — M.
- **quick_ratio** — S.
- **current_ratio** — S.
- **interest_coverage** — M.
- **payout_ratio** — S.
- **promoter_holding** — S (not in TV India).
- **roce_5yr_avg** — M.
- **sector_median_roce** — S.
- **eps_growth_10yr** — L.
- **earnings_decline_years** — L.
- **dividend_years** — M.
- **aaa_bond_yield** — S (currently hardcoded 7.5%).
- **offer_price / months_to_close** — L.
- **liquidation_value** — L.
- **bond_price / bond_rating / current_yield / yield_to_maturity /
  face_value** — L.
- **conversion_premium** — L.
- **preferred_dividend_yield** — M.
- **underwriter_fees** — M.
- **normal_value** — L.

### Requested by: *Way of the Turtle* (Curtis Faith)

None. All Turtle indicators are computed inline.

### Requested by: *7 Simple Strategies* (Patel & Kiri)

None. All indicators (ATR, EMAs, SMAs, pivots, trend lines,
channels, hammer, doji) are computed inline in the module.

---

## C. Feature count summary

**Total features registered:** 100
- **DONE (usable today):** 72 (includes all Turtle + 7SS indicators)
- **BACKLOG (requested, awaiting ID52):** 28
  - O'Shaughnessy: 7
  - Gray & Carlisle: 13
  - Lowe: 8 net-new

**Single biggest unblocker:** `fundamentals_history` — the multi-year
snapshot table. Unlocks ~11 funda methods across three traders.

**Traders with zero data blocks:** John Crane, Larry Spears,
Way of the Turtle, 7 Simple Strategies — full coverage.