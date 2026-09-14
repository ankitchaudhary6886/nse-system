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
- `consolidation_vol_ratio`

### Volume
- `avg_vol_20`, `vol_ratio_20`, `delivery_pct`, `amplitude_5d`

### Pattern flags
- `pat_htf`, `pat_tri`, `pat_db`, `pat_flag`, `pat_ihs`, `pat_bear`, `pat_any`

### Cross-sectional filters
- `sector_rs`

### Fundamentals (source: TradingView India)
- `roce`, `roe`, `debt_to_equity`, `pe`, `pb`
- `operating_margin`, `net_profit_margin`
- `cfo_positive` (derived from free_cash_flow_fy sign)
- `market_cap_cr`, `beta_1y`, `eps_fy`, `book_value`
- `ev_ebitda`, `fcf_fy`, `net_debt_fy`, `dividend_yield`

### Trader-specific — John Crane (14 methods)
Reaction swing, reverse count, forward projection, action/reaction lines,
two-day rule, peg-leg, gap-and-go, gap reversal, trail day, continuation
gap, major reversal, SSTO %K, SSTO divergence.

### Trader-specific — Larry Spears (7 methods)
Beta filter, amplitude filter, gap classification, MA trend alignment,
counter-trend retracement, force index (13 / 3 period).

### Trader-specific — O'Shaughnessy (computable today)
- `price_appreciation_1y`, `mom_120d`, `market_cap_percentile`

### Trader-specific — Gray & Carlisle (computable today)
- `earnings_yield`, `book_to_market`, `roce_quality_gate`

### Trader-specific — Janet Lowe (computable today)
- `graham_intrinsic_value` (inline in value_investing_made_easy.py)

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
- **sales_ttm** — trailing 12-month revenue. M. Underpins PSR
- **cashflow_fy** — operating income + D&A. M. Blocks
  oshaughnessy: market_leaders_universe (full), low_pcf_value
- **shares_outstanding** — diluted shares. S. Blocks
  oshaughnessy: market_leaders_universe (full), cornerstone_value_improved

### Requested by: *Quantitative Value* (Gray & Carlisle)

- **ebit** — Earnings Before Interest and Taxes. M. Blocks
  quantitative_value: ebit_enterprise_multiple, magic_formula_proxy,
  quantitative_value_model
- **total_enterprise_value (tev)** — mcap + debt − excess cash + pref +
  minority. M. Blocks quantitative_value: ebit_enterprise_multiple
- **gross_profit** — revenue − COGS. M. Blocks
  quantitative_value: quality_and_price (full)
- **total_assets** — balance-sheet total. S. Blocks
  quantitative_value: STA, SNOA, F_SCORE, FS_SCORE
- **current_assets** — balance-sheet current portion. S. Blocks
  quantitative_value: STA, F_SCORE, FS_SCORE
- **current_liabilities** — balance-sheet current portion. S. Blocks
  quantitative_value: STA, F_SCORE, FS_SCORE
- **cash_and_equivalents** — cash + ST investments. S. Blocks
  quantitative_value: SNOA, ebit_enterprise_multiple
- **fundamentals_history** — yearly snapshot of all fundamentals
  fields (multi-year storage). **L — single largest unblocker.**
  Blocks quantitative_value: F_SCORE, FS_SCORE, franchise_power,
  PROBM, PFD, STA, SNOA, buyback_yield; ALSO unblocks
  oshaughnessy and value_investing_made_easy historical methods
- **insider_trades** — SEBI SAST disclosures. L. Blocks
  quantitative_value: insider_buying_opportunistic
- **short_interest** — NSE short interest / shares. M. Blocks
  quantitative_value: low_short_interest
- **activist_13d_filings** — SEBI SAST acquisition disclosures. L.
  Blocks quantitative_value: activist_13d_filing

### Requested by: *Value Investing Made Easy* (Janet Lowe)

- **ncav_per_share** — (CA − CL − LTD) / shares. M. Blocks
  value_investing_made_easy: net_current_asset_value
- **tangible_book_value** — Total Assets − Intangibles − Liabilities.
  S. Blocks value_investing_made_easy: graham_ten_attributes (crit 4, 6)
- **net_quick_liquidation_value** — CA − Inventory − CL. M. Blocks
  value_investing_made_easy: graham_ten_attributes (crit 5, 8)
- **quick_ratio** — (CA − Inventory) / CL. S. Blocks
  value_investing_made_easy: balance_sheet_safety (full)
- **current_ratio** — CA / CL. S. Blocks
  value_investing_made_easy: defensive_investor_strategy,
  graham_ten_attributes (crit 7)
- **interest_coverage** — EBIT / Interest Expense. M. Blocks
  value_investing_made_easy: balance_sheet_safety,
  preferred_stock_value
- **payout_ratio** — DPS / EPS. S. Blocks
  value_investing_made_easy: dividend_yield_assessment (full)
- **promoter_holding** — % held by promoters. S (not in TV India).
  Blocks value_investing_made_easy: management_quality_roic (full),
  also useful for fund_veto
- **roce_5yr_avg** — 5-year average ROCE. M. Blocks
  value_investing_made_easy: management_quality_roic (full)
- **sector_median_roce** — sector cross-sectional median. S. Blocks
  value_investing_made_easy: management_quality_roic (full)
- **eps_growth_10yr** — 10-year CAGR in EPS. L. Blocks
  value_investing_made_easy: earnings_stability_growth,
  graham_ten_attributes (crit 9)
- **earnings_decline_years** — count of >5% declines in last 10yr. L.
  Blocks value_investing_made_easy: earnings_stability_growth,
  graham_ten_attributes (crit 10)
- **dividend_years** — consecutive years of dividend payments. M.
  Blocks value_investing_made_easy: defensive_investor_strategy
- **aaa_bond_yield** — Indian AAA corporate yield. S (can be a config
  constant; currently hardcoded as 7.5%). Used by
  value_investing_made_easy: graham_earnings_yield,
  graham_dividend_yield, intrinsic_value_formula
- **offer_price / months_to_close** — open-offer data (SAST). L.
  Blocks value_investing_made_easy: merger_takeover_arbitrage
- **liquidation_value** — realizable asset value minus liabilities. L.
  Blocks value_investing_made_easy: liquidation_arbitrage
- **bond_price / bond_rating / current_yield / yield_to_maturity /
  face_value** — corporate bond market feed. L. Blocks
  value_investing_made_easy: junk_bond_value, bankruptcy_arbitrage
- **conversion_premium** — convertibles feed. L. Blocks
  value_investing_made_easy: convertible_securities_value
- **preferred_dividend_yield** — preference-share feed. M. Blocks
  value_investing_made_easy: preferred_stock_value
- **underwriter_fees** — IPO feed. M. Blocks
  value_investing_made_easy: ipo_value_assessment
- **normal_value** — 7-10yr avg PE × avg earnings. L. Blocks
  value_investing_made_easy: babson_pricing_method,
  enterprising_investor_1975

---

## C. Feature count summary

**Total features registered:** 72
- **DONE (usable today):** 44
- **BACKLOG (requested, awaiting ID52):** 28
  - O'Shaughnessy: 7
  - Gray & Carlisle: 13
  - Lowe: 8 (net-new; some overlap with the other traders)

**Single biggest unblocker:** `fundamentals_history` — the multi-year
snapshot table. Unlocks 3 funda traders' historical methods at once.
Phase 4 (ID52) is the gate.