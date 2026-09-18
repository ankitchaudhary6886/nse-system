# NEW FEATURES BACKLOG

Registry of every feature/indicator used by the system.

**Status legend:** DONE · BACKLOG · IN PROGRESS · DEPRECATED

---

## A. Existing features (DONE — usable today)

(prior list unchanged)

### Trader-specific — Aseem Singhal (added #085)
All indicators computed inline in `traders/singhal.py`:
- `_bollinger(closes, 20, 2)` — BB upper/lower/mid/width
- `_bb_width_series(closes)` — rolling widths
- `_williams_r(highs, lows, closes, 14)`
- `_macd(closes, 12, 26, 9)` — MACD line + signal
- `_fib_levels(high, low)` — 38.2/50/61.8 retracement levels
- `_at_fib(price, fib_dict)` — tolerance check
- `_ichimoku(highs, lows, closes)` — tenkan/kijun/span_a/span_b/cloud
- `_supertrend(df, 10, 3)` — Supertrend line + direction
- `_pivot_points(h, l, c)` — classic P/R1/R2/S1/S2
- `_is_pin_bar(shape)` — small body, one dominant wick
- `_vcp(df, min_pullbacks)` — successive pullback shortening
- `_detect_two_leg_pullback(df)` — 3 higher highs + 3 higher lows
- `_rsi`, `_rsi_series`, `_sma`, `_ema`, `_atr`, `_consolidation`,
  `_vol_ratio`, `_pivots`, `_candle_shape`

**Note:** MACD was previously computed inline in Nison. It now
lives in two modules. If a third module needs it, promote to
`traders/shared_indicators.py`.

---

## B. Requested features (BACKLOG)

### Existing requests as previously logged
(O'Shaughnessy, Gray & Carlisle, Lowe, Parikh, O'Neil).

### Requested by: Ishaan Agnihotri / Nison / Chande / McAllen
None — all inline.

### Requested by: Aseem Singhal
- **RBI repo rate** — external macro data (DR-23).
  Method 49 silently returns zero until supplied.

---

## C. Feature count summary

**Traders with zero data blocks:** John Crane, Larry Spears,
Way of the Turtle, 7 Simple Strategies, Ishaan Agnihotri,
Steve Nison, Tushar Chande, Fred McAllen.

**Total features requested (BACKLOG):** ~41 (added repo rate).

**Single biggest unblocker:** `fundamentals_history` (DR-01).

**Second-biggest:** Nifty 500 index daily (DR-20).