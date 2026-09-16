# NEW FEATURES BACKLOG

Registry of every feature/indicator used by the system.

**Status legend:** DONE · BACKLOG · IN PROGRESS · DEPRECATED

---

## A. Existing features (DONE — usable today)

### Price & bar primitives, MAs, momentum, volume, patterns,
### fundamentals — as previously listed.

### Trader-specific — John Crane, Larry Spears, O'Shaughnessy,
### Gray & Carlisle, Janet Lowe, Way of the Turtle,
### 7 Simple Strategies, Ishaan Agnihotri, Steve Nison,
### Tushar Chande — as previously listed.

### Trader-specific — William O'Neil (added #081)
All indicators computed inline in `traders/oneil.py`:
- `_detect_cup_with_handle(df)` — O'Neil's cup detector
- `_detect_double_bottom_w(df)` — O'Neil's W detector (distinct
  from `patterns.py`)
- `_detect_flat_base(df)` — flat-base detector
- `_detect_high_tight_flag(df)` — HTF detector
- `_detect_ascending_base(df)` — ascending-base detector
- `_compute_market_regime(conn)` — distribution-day + follow-
  through logic (requires index data — DR-20)
- `_atr(df, 20)`, `_sma(arr, n)`, `_pivots(values, k, lookback)`

**Note:** the base detectors are O'Neil's own logic. They do NOT
call `patterns.py` — R42 forbids proxies.

---

## B. Requested features (BACKLOG)

### Requested by: O'Shaughnessy
As previously listed.

### Requested by: Gray & Carlisle
As previously listed.

### Requested by: Janet Lowe
As previously listed.

### Requested by: Apurva Parikh
As previously listed.

### Requested by: Ishaan Agnihotri
None — all inline.

### Requested by: Steve Nison
None — all inline.

### Requested by: Tushar Chande
None — all inline.

### Requested by: William O'Neil — NEW (trader #12)

- **`eps_growth_current_qtr`** — YoY % change in most recent
  quarterly EPS. M. Blocks CAN SLIM composite. DR-21.
- **`sales_growth_current_qtr`** — YoY % change in most recent
  quarterly sales. M. DR-21.
- **`eps_growth_3yr`** — 3-year annual EPS growth rate. M. DR-21.
- **`eps_acceleration`** — 2+ consecutive quarters of increasing
  EPS growth rate. M. DR-21.
- **`rs_rating_52w`** — O'Neil-style Relative Price Strength
  Rating (1-99 percentile of 52w price performance across
  Nifty 500). S. DR-22.
- **`sponsorship_change`** — change in FII+DII holdings QoQ. M.
  DR-22. Overlaps with `promoter_holding` need in Lowe/Parikh.
- **`industry_rank`** — stock's rank within its industry group by
  earnings growth. M. DR-22.
- **`market_regime`** — O'Neil's confirmed-uptrend / correction /
  rally-attempt classification. S. DR-20 (index data).
- **`distribution_day`** — boolean, index closes down > 0.2% on
  higher volume. S. DR-20.
- **`distribution_day_count`** — rolling count over 4-5 weeks.
  S. DR-20.
- **`follow_through_day`** — index up ≥ 1.5% on higher volume
  after a rally-attempt setup. S. DR-20.

---

## C. Feature count summary

**Traders with zero data blocks:** John Crane, Larry Spears,
Way of the Turtle, 7 Simple Strategies, Ishaan Agnihotri,
Steve Nison, Tushar Chande.

**Total features requested (BACKLOG):** ~40 (was ~28, +12 from
O'Neil).

**Single biggest unblocker:** `fundamentals_history` (DR-01).

**Second-biggest:** Nifty 500 index daily (DR-20) — unlocks all
of O'Neil's methods with one small fetch.