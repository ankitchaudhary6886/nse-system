# NEW FEATURES BACKLOG

Registry of every feature/indicator used by the system.

**Purpose:** When a new book requests a feature, check here first.
If it exists → reuse. If it doesn't → add it below, implement, mark DONE.

**Status legend:** DONE · BACKLOG · IN PROGRESS · DEPRECATED

---

## A. Existing features (DONE — usable today)

### Price & bar primitives
- `close`, `open`, `high`, `low`, `volume`, `date`
- `prev_close`, `prev_high`, `prev_low` (prior-day references)
- `close_gt_open` — 1 if close > open else 0
- `inside_day` — 1 if inside bar else 0
- `gap_pct` — (today_open - prior_close) / prior_close

### Moving averages
- `dma20`, `dma50`, `dma200` — simple moving averages
- `ema10`, `ema20` — exponential moving averages
- `slope200` — 20-bar slope of EMA200
- `above20`, `above50`, `above200` — 1 if close above respective MA

### Momentum & volatility
- `mom_5d`, `mom_20d`, `mom_60d` — momentum over N sessions
- `rsi` — 14-period RSI
- `atr_14`, `atr_pct` — ATR and ATR as % of close
- `ret_std20` — 20-session return standard deviation
- `beta` — cov(sym, ^NSEI) / var(^NSEI) over 60-180 sessions

### Structure
- `impulse_pct_60d` — best 25-40% impulse in last 60 sessions
- `days_since_impulse_peak` — bars since the impulse peak
- `consolidation_range_pct` — high-low range since impulse peak / peak
- `distance_from_52w_high` — (52wHigh - close) / 52wHigh
- `distance_from_52w_low` — (close - 52wLow) / 52wLow
- `consolidation_vol_ratio` — avg volume since peak / avg volume during impulse

### Volume
- `avg_vol_20` — 20-session average volume
- `vol_ratio_20` — today's volume / avg_vol_20
- `delivery_pct` — NSE delivery percentage
- `amplitude_5d` — (max high - min low) / avg close over 5 sessions

### Pattern flags (from patterns.py)
- `pat_htf` — high tight flag
- `pat_tri` — ascending triangle
- `pat_db` — double bottom
- `pat_flag` — bull flag (currently disabled — failed gate)
- `pat_ihs` — inverse head & shoulders
- `pat_bear` — bearish H&S top warning
- `pat_any` — any bullish pattern flag

### Cross-sectional filters
- `sector_rs` — sector relative strength percentile (0-1)

### Fundamentals (source: TradingView India)
- `roce`, `roe`, `debt_to_equity`
- `pe`, `pb`
- `operating_margin`, `net_profit_margin`
- `profit_growth_3y`, `sales_growth_3y`
- `promoter_holding`
- `cfo_positive`
- `market_cap_cr`
- `beta_1y`, `eps_fy`, `book_value`
- `ev_ebitda`, `fcf_fy`, `net_debt_fy`

### Trader-specific: John Crane
- `reaction_swing_confirmed` — B→C completed
- `reverse_count` — bars from B to A
- `forward_projected_date` — next reversal projection
- `action_line_slope`, `center_line_slope`, `reaction_line_intercept`
- `two_day_rule` — 2 consecutive same-colour candles
- `peg_leg` — 20d extreme ≥3 days after prior pivot
- `gap_and_go` — 2-bar gap continuation
- `gap_reversal` — gap against prior bar's trend, close reverses
- `trail_day_confirmed` — close vs open on trailing bar
- `continuation_gap` — breakaway gap on reversal/trail day
- `major_reversal` — 10d extreme + ≥3 same-colour closes
- `ssto_k` — 20-period smoothed stochastic %K
- `ssto_divergence` — price vs SSTO divergence

### Trader-specific: Larry Spears
- `beta` — already listed above
- `amplitude_5d` — already listed above
- `gap_pct` — already listed above
- `ma_trend` — SMA10/20/50 stacked + slopes
- `counter_trend_bars` — count of lower highs / higher lows
- `force_index_13` — Elder's 13-period force index
- `force_index_3` — Elder's 3-period force index

---

## B. Requested features (BACKLOG)

When a book requests a feature we don't have, add an entry:

```markdown
### <feature_name>  ·  [BOOK SOURCE]
- **Status:** BACKLOG
- **Formula:** [exact mathematical definition]
- **Why it matters:** [which method depends on it]
- **Requested by:** [book title / author]
- **Effort estimate:** S | M | L

### price_to_sales  ·  [What Works on Wall Street — O'Shaughnessy]
- **Status:** BACKLOG
- **Formula:** market_cap / trailing_12m_sales
- **Why it matters:** Required by Methods 6, 12, 14, 15 of the
  O'Shaughnessy trader. The book calls PSR "the king of value factors."
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** M (requires revenue/sales feed — not on TV India)
- **Blocks:** O'Shaughnessy methods low_psr_value, low_psr_plus_rs,
  cornerstone_growth_original, cornerstone_growth_improved

### eps_growth_1y  ·  [What Works on Wall Street]
- **Status:** BACKLOG
- **Formula:** (EPS_t − EPS_t−1) / |EPS_t−1|
- **Why it matters:** Cornerstone Growth (Methods 14, 15) and
  Worst-Earnings-Gains (Method 8) need YoY EPS change.
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** M (needs EPS history, not just latest FY)
- **Blocks:** O'Shaughnessy methods worst_earnings_gains,
  cornerstone_growth_original, cornerstone_growth_improved

### shareholder_yield  ·  [What Works on Wall Street]
- **Status:** BACKLOG
- **Formula:** dividend_yield + net_buyback_yield
  where net_buyback_yield = (shares_prior − shares_current) / shares_prior
- **Why it matters:** Method 17 (Improved Cornerstone Value). Book's
  highest-Sharpe value method (Sharpe 71).
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** M (needs shares-outstanding history)
- **Blocks:** O'Shaughnessy method cornerstone_value_improved

### price_to_cashflow  ·  [What Works on Wall Street]
- **Status:** BACKLOG
- **Formula:** market_cap / (net_income + depreciation_amortization)
- **Why it matters:** Method 5 (Low P/CF) and several multifactor variants.
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** M (needs clean cashflow feed; current `fcf_fy`
  units unverified)
- **Blocks:** O'Shaughnessy method low_pcf_value

### sales_ttm  ·  [What Works on Wall Street]
- **Status:** BACKLOG
- **Formula:** trailing 12-month revenue
- **Why it matters:** Underpins PSR (see price_to_sales).
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** M

### cashflow_fy  ·  [What Works on Wall Street]
- **Status:** BACKLOG
- **Formula:** operating income + depreciation & amortization
- **Why it matters:** Market Leaders universe (Method 1) filter +
  Low P/CF (Method 5).
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** M

### shares_outstanding  ·  [What Works on Wall Street]
- **Status:** BACKLOG
- **Formula:** diluted shares outstanding (latest)
- **Why it matters:** Market Leaders universe filter (Method 1).
  Also foundational for shareholder_yield.
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** S (available via TV but not stored)

### price_appreciation_1y  ·  [What Works on Wall Street]
- **Status:** DONE (computable)
- **Formula:** close_t / close_t−252 − 1
- **Why it matters:** Relative strength factor (Methods 9, 10, 11, 12,
  14, 15). Computed inline in oshaughnessy.py.
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** S
- **Note:** computed on the fly; promote to a persistent feature if
  other traders need it.

### mom_120d  ·  [What Works on Wall Street]
- **Status:** DONE (computable)
- **Formula:** close_t / close_t−120 − 1
- **Why it matters:** Improved Cornerstone Growth (Method 15) 6-month
  RS filter.
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** S

### market_cap_percentile  ·  [What Works on Wall Street]
- **Status:** DONE (computable)
- **Formula:** cross-sectional percentile rank of market_cap within
  reference universe (Nifty 500 or band).
- **Why it matters:** Market Leaders universe (Method 1) +
  "40th percentile" gate used across all methods.
- **Requested by:** James P. O'Shaughnessy
- **Effort estimate:** S
- **Note:** computed inline per scan.