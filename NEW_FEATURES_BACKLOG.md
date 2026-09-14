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
- `profit_growth_3y`, `sales_growth_3y` (currently null on TV India)
- `promoter_holding` (currently null on TV India)
- `cfo_positive` — derived from free_cash_flow_fy sign
- `market_cap_cr`
- `beta_1y`, `eps_fy`, `book_value`
- `ev_ebitda`, `fcf_fy`, `net_debt_fy`
- `dividend_yield`

### Trader-specific: John Crane (14 methods)
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

### Trader-specific: Larry Spears (7 methods)
- `beta` — already listed above
- `amplitude_5d` — already listed above
- `gap_pct` — already listed above
- `ma_trend` — SMA10/20/50 stacked + slopes
- `counter_trend_bars` — count of lower highs / higher lows
- `force_index_13` — Elder's 13-period force index
- `force_index_3` — Elder's 3-period force index

### Trader-specific: James O'Shaughnessy — computable today
- `price_appreciation_1y` — close_t / close_t−252 − 1
  (computed inline in oshaughnessy.py)
- `mom_120d` — close_t / close_t−120 − 1 (6-month RS)
- `market_cap_percentile` — cross-sectional percentile of mcap
  within band universe (computed inline)

### Trader-specific: Gray & Carlisle — computable today
- `earnings_yield` — 1/PE (proxy for EBIT/TEV)
- `book_to_market` — 1/PB
- `roce_quality_gate` — ROCE ≥15% (proxy for "franchise quality")

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
- **Blocks:** [which methods auto-activate once available]