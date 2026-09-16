# NEW FEATURES BACKLOG

Registry of every feature/indicator used by the system.

**Status legend:** DONE · BACKLOG · IN PROGRESS · DEPRECATED

---

## A. Existing features (DONE — usable today)

### Price & bar primitives
`close`, `open`, `high`, `low`, `volume`, `date`, `prev_close`,
`prev_high`, `prev_low`, `close_gt_open`, `inside_day`, `gap_pct`

### Moving averages
`dma20`, `dma50`, `dma200`, `ema10`, `ema20`, `slope200`,
`above20`, `above50`, `above200`

### Momentum & volatility
`mom_5d`, `mom_20d`, `mom_60d`, `rsi`, `atr_14`, `atr_pct`,
`ret_std20`, `beta`

### Structure
`impulse_pct_60d`, `days_since_impulse_peak`,
`consolidation_range_pct`, `distance_from_52w_high`,
`distance_from_52w_low`, `consolidation_vol_ratio`

### Volume
`avg_vol_20`, `vol_ratio_20`, `delivery_pct`, `amplitude_5d`

### Pattern flags (patterns.py)
`pat_htf`, `pat_tri`, `pat_db`, `pat_flag`, `pat_ihs`, `pat_bear`,
`pat_any`

### Cross-sectional
`sector_rs`

### Fundamentals (TradingView India)
`roce`, `roe`, `debt_to_equity`, `pe`, `pb`, `operating_margin`,
`net_profit_margin`, `cfo_positive`, `market_cap_cr`, `beta_1y`,
`eps_fy`, `book_value`, `ev_ebitda`, `fcf_fy`, `net_debt_fy`,
`dividend_yield`

### Trader-specific — John Crane
Reaction swing, reverse count, forward projection, action/reaction
lines, two-day rule, peg-leg, gap-and-go, gap reversal, trail day,
continuation gap, major reversal, SSTO %K, SSTO divergence.

### Trader-specific — Larry Spears
Beta filter, amplitude filter, gap classification, MA trend,
counter-trend retracement, force index (13/3).

### Trader-specific — O'Shaughnessy (inline)
`price_appreciation_1y`, `mom_120d`, `market_cap_percentile`

### Trader-specific — Gray & Carlisle (inline)
`earnings_yield`, `book_to_market`, `roce_quality_gate`

### Trader-specific — Janet Lowe (inline)
`graham_intrinsic_value`

### Trader-specific — Way of the Turtle (inline)
`highest_high_prior_{10,20,55}d`, `lowest_low_prior_{10,20,55}d`,
`atr_20`, `sma_{100,150,250,350}`, `ema_{25,350}`,
`rolling_std_350d`, pivots, channel bands.

### Trader-specific — 7 Simple Strategies (inline)
`atr_14_wilder`, `ema_9`, `dma_16`, `dma_24`, `mean_100d`,
trend_line, channel_lines, `hammer_pattern`,
`bullish_doji_pattern`, `three_lower_closes`.

### Trader-specific — Apurva Parikh (inline)
Composite 11-secret screen.

### Trader-specific — Ishaan Agnihotri (inline)
`ema_9`, `ema_21`, `macd`, `macd_signal`, `rsi_divergence`,
`dma_180`, `support_level`, `resistance_level`,
chart-pattern detectors, candle patterns.

### Trader-specific — Steve Nison (inline)
Candle patterns, disparity index, golden cross 13/26 EMA,
TLB / Renko / Kagi state machines.

### Trader-specific — Tushar Chande (inline — added #080)
All indicators computed inline in `traders/chande.py`:
- `sma_65` — 65-day SMA (Method 1)
- `consecutive_closes_above_sma65` — 3cc check (Method 1)
- `ravi` — Range Action Verification Index = |100 × (SMA7 − SMA65) / SMA65|
- `sma_3`, `sma_7`, `sma_12`, `sma_50` — short SMAs (Methods 3, 5)
- `adx_18` — Wilder's ADX with DI+/DI− (Method 3)
- `highest_high_20` — 20-day rolling high (Methods 2, 5)
- `lowest_low_5` — 5-day rolling low (Methods 2, 4)
- `lowest_low_40` — 40-day rolling low (Method 2 trail)
- `days_since_20d_high` — Methods 2
- `days_since_20d_low` — Method 4
- `high_low_range` — today's range (Method 4)
- `close_open_range` — today's body (Method 4)
- `band_top_3pct` — 1.03 × SMA50 (Method 5)

**Note:** ADX is now inline. If another trader needs it, promote
to a shared indicator module.

---

## B. Requested features (BACKLOG)

### Requested by: O'Shaughnessy
- `price_to_sales` — M. Blocks 4 methods.
- `eps_growth_1y` — M. Blocks 3 methods.
- `shareholder_yield` — M. Blocks 1 method.
- `price_to_cashflow` — M. Blocks 1 method.
- `sales_ttm` — M.
- `cashflow_fy` — M. Blocks 2 methods.
- `shares_outstanding` — S.

### Requested by: Gray & Carlisle
- `ebit` — M. Blocks 3 methods.
- `tev` — M.
- `gross_profit` — M.
- `total_assets` — S. Blocks 4 methods.
- `current_assets` — S.
- `current_liabilities` — S.
- `cash_and_equivalents` — S.
- **`fundamentals_history`** — yearly snapshot. **L — single
  largest unblocker. Unlocks ~20 methods across 4 traders.**
- `insider_trades` — L.
- `short_interest` — M.
- `activist_13d_filings` — L.

### Requested by: Janet Lowe
`ncav_per_share`, `tangible_book_value`,
`net_quick_liquidation_value`, `quick_ratio`, `current_ratio`,
`interest_coverage`, `payout_ratio`, `promoter_holding`,
`roce_5yr_avg`, `sector_median_roce`, `eps_growth_10yr`,
`earnings_decline_years`, `dividend_years`, `aaa_bond_yield`,
`offer_price` / `months_to_close`, `liquidation_value`,
`bond_price` / `bond_rating` / `current_yield` /
`yield_to_maturity` / `face_value`, `conversion_premium`,
`preferred_dividend_yield`, `underwriter_fees`, `normal_value`.

### Requested by: Apurva Parikh
`promoter_holding` + `pledged_pct`, `nifty_pe`, `business_age`.

### Requested by: Ishaan Agnihotri
None — all inline.

### Requested by: Steve Nison
None — all inline.

### Requested by: Tushar Chande
**None.** All indicators inline.

---

## C. Feature count summary

**Traders with zero data blocks:** John Crane, Larry Spears,
Way of the Turtle, 7 Simple Strategies, Ishaan Agnihotri,
Steve Nison, Tushar Chande.

**Total features requested (BACKLOG):** ~28

**Single biggest unblocker:** `fundamentals_history`.