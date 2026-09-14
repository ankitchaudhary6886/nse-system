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
- `graham_intrinsic_value` (inline in the module)

### Trader-specific — Way of the Turtle (computable today)
All Turtle indicators computed inline in `way_of_the_turtle.py`:
- `highest_high_prior_10d`, `highest_high_prior_20d`,
  `highest_high_prior_55d`
- `lowest_low_prior_10d`, `lowest_low_prior_20d`,
  `lowest_low_prior_55d`
- `atr_20` (Wilder-style EMA of true range)
- `sma_100`, `sma_150`, `sma_250`, `sma_350`
- `ema_25`, `ema_350`
- `rolling_std_350d` (population std of close over 350 bars)
- `channel_top_atr` = 350MA + 7 × ATR
- `channel_bottom_atr` = 350MA − 3 × ATR
- `channel_top_boll` = 350MA + 2.5 × σ
- `channel_bottom_boll` = 350MA − 2.5 × σ
- `swing_high_level`, `swing_low_level` (twice-tested pivot clusters)

**Note:** these are computed inline per scan for performance. If
other traders also need them (e.g. a future Ichimoku or a Keltner
channel trader), promote them to a shared price-features module.

---

## B. Requested features (BACKLOG)

### Requested by: *What Works on Wall Street* (O'Shaughnessy)

- **price_to_sales** — market_cap / trailing_12m_sales. M. Blocks
  oshaughnessy: low_psr_value, low_psr_plus_rs,
  cornerstone_growth_original, cornerstone_growth_improved
- **eps_growth_1y** — (EPS_t − EPS_t−1) / |EPS_t−1|. M. Blocks
  oshaughnessy: worst_earnings_gains, cornerstone_growth_original,
  cornerstone_growth_improved
- **shareholder_yield** — dividend_yield + net_buyback_yield. M.
  Blocks oshaughnessy: cornerstone_value_improved
- **price_to_cashflow** — market_cap / (net_income + D&A). M. Blocks
  oshaughnessy: low_pcf_value
- **sales_ttm** — trailing 12-month revenue. M.
- **cashflow_fy** — operating income + D&A. M. Blocks
  oshaughnessy: market_leaders_universe (full), low_pcf_value
- **shares_outstanding** — diluted shares. S.

### Requested by: *Quantitative Value* (Gray & Carlisle)

- **ebit** — M. Blocks quantitative_value: ebit_enterprise_multiple,
  magic_formula_proxy, quantitative_value_model
- **total_enterprise_value (tev)** — M. Blocks
  quantitative_value: ebit_enterprise_multiple
- **gross_profit** — M. Blocks
  quantitative_value: quality_and_price (full)
- **total_assets** — S. Blocks
  quantitative_value: STA, SNOA, F_SCORE, FS_SCORE
- **current_assets** — S. Blocks quantitative_value: STA, F_SCORE
- **current_liabilities** — S. Blocks quantitative_value: STA, F_SCORE
- **cash_and_equivalents** — S. Blocks
  quantitative_value: SNOA, ebit_enterprise_multiple
- **fundamentals_history** — yearly snapshot of all fundamentals.
  **L — single largest unblocker.** Unlocks ~11 methods across
  QV, O'Shaughnessy, Lowe.
- **insider_trades** — SEBI SAST. L. Blocks
  quantitative_value: insider_buying_opportunistic
- **short_interest** — NSE feed. M. Blocks
  quantitative_value: low_short_interest
- **activist_13d_filings** — SEBI SAST. L. Blocks
  quantitative_value: activist_13d_filing

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

None. All Turtle indicators are computed inline. No external feeds
or historical series required.

---

## C. Feature count summary

**Total features registered:** 88
- **DONE (usable today):** 60 (includes all Turtle indicators)
- **BACKLOG (requested, awaiting ID52):** 28
  - O'Shaughnessy: 7
  - Gray & Carlisle: 13
  - Lowe: 8 net-new

**Single biggest unblocker:** `fundamentals_history` — the multi-year
snapshot table. Unlocks ~11 funda methods across three traders.

**Traders with zero data blocks:** John Crane, Larry Spears,
Way of the Turtle — full coverage.