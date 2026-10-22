# Strategy Playbook

**Status:** implemented and verified locally. Not deployed. The local price
database ends on **2026-10-16**, so every number below is a research snapshot,
not production truth.

**What it is:** a standalone rule book that scans the NSE universe and answers
three questions:

1. Which named swing strategy does this stock match today?
2. What are the exact entry, stop, target, and book exit for *this* stock?
3. Does the rule have a positive walk-forward expectancy after costs?

**What it is not:** an order generator, a portfolio allocator, or a League
trader. The Playbook does not register in `traders/__init__.py`, so the League
stays at 14 players and no League replay is triggered. Every signal is
identification-only. Rule R43 still applies: no shorting; a death cross is a
`TOP_WARNING`, never a short entry.

---

## 1. Where it lives

| File | Responsibility |
|---|---|
| `playbook.py` | 12-rule registry, book priors, live detectors, R40 exit blocks, overlap notes, VCP zigzag, pivot helpers. |
| `playbook_engine.py` | Universe loading, split adjustment, seam guard, cross-sectional ranks, scan/persist, signals/tags APIs, walk-forward simulation, job status. |
| `terminal_api.py` | Seven `/api/playbook/*` routes (catalogue, signals, symbol tags, scan, scan status, backtest, backtest status/history). |
| `db.py` | `strategy_signals` and `strategy_backtests` tables, indexes, idempotent `indicators` column migration. |
| `terminal/static/playbook.js` | Cards, click-to-filter, symbol lookup, detail panel, scan/backtest polling, backtest table. |
| `terminal/static/playbook.css` | Scoped Playbook layout; no global selectors. |
| `terminal/static/index.html` | Playbook top-level tab, nav entry, section markup, asset tags. |
| `terminal/static/app.js` | View switching, title hooks, Playbook refresh on tab entry. |
| `test_playbook.py` | 30 synthetic unit tests (rules, exits, data integrity, rank direction). |
| `docs/STRATEGY_PLAYBOOK.md` | This document. |

The module is intentionally **not** a `traders/` package: it has no
`scan()`/`replay()` plugin contract, no League ledger, and no position sizing.
It shares the price database and the `universe_helper.band_universe` universe
only.

---

## 2. Quick start

### From the UI

1. Open the terminal and select **Playbook** in the top navigation.
2. Press **Run scan** (whole universe, one job at a time). The status line
   refreshes every 2.5 s and the page reloads the tags when the scan finishes.
3. Click **Show matches** on a card to filter the tag table to that rule.
   Click **All tags** to clear the filter.
4. Type a symbol (for example `DELTACORP`) and press **Find tags** to see every
   strategy that stock carries on the latest scan date.
5. Click a tag row to open the detail panel: exact levels, risk, hold, measured
   indicators, R40 exits, and the book reason.
6. Press **Run backtest** for the whole universe (8 backtestable rules) or use
   the API with a `strategies` list for a subset.

### From the API

```powershell
# Rule catalogue + live tag counts + latest backtest per rule
Invoke-RestMethod http://127.0.0.1:8010/api/playbook/strategies | ConvertTo-Json -Depth 8

# Tags for one rule
Invoke-RestMethod "http://127.0.0.1:8010/api/playbook/signals?strategy=donchian_20" | ConvertTo-Json -Depth 8

# One stock's tags
Invoke-RestMethod http://127.0.0.1:8010/api/playbook/symbol/DELTACORP | ConvertTo-Json -Depth 8

# Start a scan, then poll
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/playbook/scan
Invoke-RestMethod http://127.0.0.1:8010/api/playbook/scan/status

# Start a backtest (whole universe, every bar)
Invoke-RestMethod -Method Post -ContentType 'application/json' `
  -Body '{"limit":900,"years":3,"step":1}' `
  http://127.0.0.1:8010/api/playbook/backtest
Invoke-RestMethod http://127.0.0.1:8010/api/playbook/backtest/status
```

A scan and a backtest may not run at the same time as another job of the same
type. The second request returns `{"started": false, "already_running": true}`.

---

## 3. The 12 rules

| # | id | Rule | Book | Family | Status | Backtest |
|---|---|---|---|---|---|---|
| 1 | `donchian_20` | Donchian 20-Day Breakout (Turtle S1) | Dennis / Eckhardt | Breakout | live | yes |
| 2 | `high_52w` | 52-Week High Breakout | O'Neil / Minervini | Breakout | live | yes |
| 3 | `cup_handle` | Cup with Handle | O'Neil | Base | live | yes |
| 4 | `vcp` | Volatility Contraction Pattern | Minervini | Base | live | yes |
| 5 | `high_tight_flag` | High Tight Flag | O'Neil | Momentum | live | yes |
| 6 | `flat_base` | Flat Base | O'Neil | Base | live | yes |
| 7 | `ascending_base` | Ascending Base | O'Neil / Minervini | Base | live | yes |
| 8 | `ma_50_200` | 50/200 Golden Cross | Classical trend following | Trend | live | yes |
| 9 | `momentum_12_1` | 12-1 Momentum | Jegadeesh & Titman (1993) | Cross-sectional | live | scan only |
| 10 | `low_vol_momentum` | Low-Volatility Momentum | Low-vol anomaly + momentum | Cross-sectional | live | scan only |
| 11 | `pead` | Post-Earnings Drift | Ball & Brown / Bernard & Thomas | Event | data pending | no |
| 12 | `promoter_buying` | Promoter / Insider Buying Cluster | Indian disclosure-flow research | Event | data pending | no |

**Book priors.** Each card shows `book 38% / 3.0R`. These are *editorial
priors* taken from the source books, not measured results. They are displayed
before a backtest exists and are not used in any score. The backtest columns are
the measured numbers.

**Status meanings.**

- `live` - the detector runs on every scan and, where `backtestable` is true,
  on every backtest bar.
- `data_pending` - the detector is deliberately inert because the required
  point-in-time field is not stored. The UI shows what is missing and never
  fabricates a tag.

---

## 4. Exact rule specifications

All shape rules require at least **260 bars** (`DEFAULT_MIN_BARS`) and a latest
close of at least **₹20** (`DEFAULT_MIN_PRICE`). A >45% single-session residual
move after split adjustment excludes the symbol from that run. Entry, stop, and
target are in ₹; `risk_pct = (entry - stop) / entry`.

A **fresh-cross** rule requires the prior bar not to have already satisfied the
same breakout, so a stock does not stay tagged for weeks while it drifts above
an old pivot.

### 4.1 Donchian 20-Day Breakout (`donchian_20`, Turtle S1)

- **Setup:** close > the highest high of the prior 20 bars, plus one tick;
  the prior close must not already be above its own prior-20 high.
- **Entry:** signal close.
- **Stop:** `entry - 2 × ATR20(prior bar)` (the Turtle "2N" noise stop).
- **Research target:** `entry + 6 × ATR20` (3R, for comparison only).
- **Exit mode:** `ll10` - close below the lowest low of the prior 10 bars; max
  hold 120 bars; the stop is checked first. The target is **not** simulated.
- **Volume:** not a gate. Volume ≥ 1.0× its 50-day average raises confidence
  from MED to HIGH.
- **Why:** the 10-day channel exit is the book's trend exit. A fixed 3R target
  would cut the fat tail that pays for the many small losses.
- **Overlap:** the parent of most breakout methods; often tags the same stock
  as `high_52w` and the base rules.

### 4.2 52-Week High Breakout (`high_52w`)

- **Setup:** close > prior 252-bar high × 1.001 + one tick; prior close must
  not already be above its prior 252-bar high.
- **Trend template (Minervini):**
  - close > SMA50, SMA150, SMA200;
  - SMA150 > SMA200; SMA50 > SMA150;
  - SMA200 higher than 22 bars ago;
  - close ≥ 1.30× the 52-week low;
  - close within 25% of the 52-week high;
  - relative-strength percentile ≥ 0.70 (scan only; see §6.4).
- **Confirmation:** volume ≥ 1.4× the prior 50-day average, and the close is in
  the top 25% of the day's range.
- **Stop:** `max(entry × 0.925, min(low, last 10 bars) - tick)` - the tighter of
  the 7.5% cap and the 10-day low, never wider than 7.5%.
- **Target:** `entry × 1.225` (+22.5%, nominally 3R).
- **Exit:** first touch of stop or target (stop first if both are touched in
  one bar), or 40 bars.
- **Why:** O'Neil's loss cap and 20-25% profit-taking rule, with the RS gate
  keeping the breakout in a leadership stock rather than a random high.

### 4.3 Cup with Handle (`cup_handle`)

- **Window:** up to 325 bars (65 weeks); at least 120 bars of history.
- **Left rim:** the highest high in the first 60% of the window, at least 25
  bars before today.
- **Cup:** depth 12-33%; duration `(today - rim) / 5` between 7 and 65 weeks;
  the right side must recover at least 70% of the cup depth; at least 8 bars
  after the low.
- **Handle:** the last 10 bars before the breakout bar (minimum 5). Handle depth
  ≤ `min(12%, cup depth / 3)`; the handle low must sit in the upper half of the
  cup (`low ≥ cup low + 50% of depth`); handle volume ≤ 0.80× cup volume.
- **Pivot:** the handle high; close must clear it by 0.05% plus one tick.
- **Confirmation:** volume ≥ 1.4× the prior 50-day average and a close in the
  top 25% of the day's range.
- **Stop:** `max(entry × 0.925, handle low - tick)` - tighter of 7.5% and the
  handle low.
- **Target:** `entry × 1.225` (+22.5%, nominally 3R).
- **Exit:** fixed stop/target, or 60 bars.
- **Why:** the handle is the last shakeout before the pivot; a wide or
  high-volume handle is supply, not a setup.

### 4.4 Volatility Contraction Pattern (`vcp`)

- **History:** at least 120 bars; Minervini trend template (the RS percentile
  gate is applied in scans only).
- **Swing detection:** a 4% zigzag over the last 120 bars. A wiggle smaller than
  4% is not a contraction.
- **Contractions:** from swing highs that are within 5% of the running base
  high, measure the drop to the lowest swing low before the next high.
  - at least 2 and at most 6 contractions;
  - each depth ≥ 2% (smaller is noise);
  - each depth < the prior depth and ≤ 0.80× the prior depth;
  - the final depth ≤ 8% and ≤ 0.50× the first depth;
  - the contraction lows must rise, with a 2% undercut tolerance.
- **Volume dry-up:** mean volume of the last 10 bars (before the breakout bar)
  ≤ 0.80× the mean of the prior 50 bars.
- **Pivot:** highest high from the final low to the day before the breakout;
  close must clear it by 0.1%.
- **Breakout volume:** ≥ 1.4× the prior 50-day average.
- **Stop:** `max(final low × 0.995, entry × 0.93)` - tighter of 0.5% below the
  final low and a 7% cap.
- **Target:** `entry + 2.5 × (entry - stop)`.
- **Exit:** fixed stop/target, or 40 bars.
- **Why:** each leg should be quieter than the last; the final contraction plus
  dry-up is the supply exhaustion that lets a small amount of demand move price.

### 4.5 High Tight Flag (`high_tight_flag`)

- **History:** at least 60 bars.
- **Pole:** search the high in the window 42 to 14 bars ago whose low over the
  prior 40 bars gives a gain ≥ 100%; choose the largest gain. This is the
  "100% in at most 8 weeks" idea, with the low allowed to precede the high.
- **Flag:** the bars after the pole high, **excluding the breakout day**:
  - 15-25 bars;
  - depth ≤ 25% from flag high to flag low;
  - mean flag volume ≤ 0.70× the mean pole volume (20 bars ending at the pole
    high). The breakout day is included in the flag-volume mean, which is the
    conservative reading.
- **Pivot:** the flag high; close must clear it by 0.1%.
- **Breakout volume:** ≥ 1.4× the prior 50-day average.
- **Stop:** `max(entry × 0.94, flag low × 0.995)` - tighter of 6% and the flag
  low.
- **Target:** `entry + (pole high - pole low)` - a measured move, **not** a
  fixed R multiple.
- **Exit:** fixed stop/target, or 30 bars.
- **Why:** the flag is a tight pause after a violent advance; the measured move
  is the book's objective, and a flag deeper than 25% is a failed pole.

### 4.6 Flat Base (`flat_base`)

- **History:** at least 160 bars.
- **Base:** the last 40 bars before the breakout bar (8 weeks). Depth ≤ 15%.
- **Prior uptrend:** the close at the start of the base is ≥ 1.30× the lowest
  low of the 120 bars before the base.
- **Pivot:** the base high; close must clear it by one tick.
- **Confirmation:** volume ≥ 1.4× the prior 50-day average and a close in the
  top 25% of the day's range.
- **Stop:** `max(base low × 0.995, entry × 0.95)` - tighter of the base low and
  a 5% cap.
- **Target:** `entry + 2.0 × (entry - stop)`.
- **Exit:** fixed stop/target, or 45 bars.
- **Why:** a flat base is a time correction, not a price correction. The prior
  uptrend proves demand; the tight range proves supply has stopped lifting
  offers.

### 4.7 Ascending Base (`ascending_base`)

- **History:** at least 90 bars; examine the last 80.
- **Pullbacks:** the last three swing lows (3-bar pivot) must be strictly rising.
  For each low, the drop from the immediately preceding swing high must be
  10-20%.
- **Base length:** from the first of the three lows to today, 45-80 bars.
- **Pivot:** the highest high in the 80-bar window; close must clear it by one
  tick.
- **Confirmation:** volume ≥ 1.4× the prior 50-day average and a close in the
  top 25% of the day's range.
- **Stop:** `max(third low × 0.995, entry × 0.95)` - tighter of the third low
  and a 5% cap.
- **Target:** `entry + 2.25 × (entry - stop)`.
- **Exit:** fixed stop/target, or 50 bars.
- **Why:** three higher lows with contained pullbacks show demand stepping up
  into a rising pivot; each shakeout is bought higher than the last.

### 4.8 50/200 Golden Cross (`ma_50_200`)

- **History:** at least 225 bars.
- **Cross:** SMA50 crossed above SMA200 within the last 20 bars.
- **Confirmation:** close > SMA200 and SMA50 > 1.01 × SMA200. Only the **first**
  bar that satisfies both is tagged; a cross yields one entry, not 20.
- **Context, not a gate:** the 200-DMA slope (22 bars) is displayed. The rule
  does **not** require a rising 200-DMA; that is a filter left to the reader.
- **Stop:** `max(SMA200 × 0.97, entry × 0.92)` - tighter of 3% below the
  200-DMA and an 8% cap.
- **Research target:** `entry + 3R`.
- **Exit mode:** `reverse_cross` - close of the first bar where SMA50 < SMA200;
  max hold 250 bars; stop first. The 3R target is **not** simulated.
- **Death cross:** SMA50 crossing below SMA200 emits a `TOP_WARNING` with
  `direction = TOP_WARNING`, `rr = null`, `risk_pct = null`. Its R40 block
  labels the upside level as warning invalidation and the downside level as a
  downside objective, not a stop and target for a short. It is not a short.

### 4.9 12-1 Momentum (`momentum_12_1`, scan only)

- **Momentum:** `C[t-21] / C[t-252] - 1` (skip the most recent 21 bars).
- **Rank:** percentile rank of momentum across the scanned universe, where
  **0 = weakest and 1 = strongest**. The rule keeps the **top decile**:
  `rank >= 0.90`.
- **Entry:** signal close.
- **Stop / target:** `entry - 2 × ATR20` and `entry + 4 × ATR20`.
- **Hold:** 60 bars.
- **Why scan only:** the rule is defined by a cross-sectional rank on each
  date. A per-symbol walk-forward would silently turn it into a different rule.
- **Implementation note:** an earlier build had the comparator reversed and
  selected the bottom decile. The fix and a regression test are in
  `test_playbook.CrossSectionalTests`. Any result produced before
  2026-10-23 02:21 IST used the inverted rank and must be discarded.

### 4.10 Low-Volatility Momentum (`low_vol_momentum`, scan only)

- **Momentum:** same 12-1 measure; keep the top 20%: `rank >= 0.80`.
- **Volatility:** standard deviation of 60 daily returns. Keep the bottom 50%:
  `vol_rank <= 0.50` (again, 0 = lowest volatility).
- **Entry:** signal close.
- **Stop / target:** `entry - 2 × ATR20` and `entry + 4 × ATR20`.
- **Hold:** 60 bars.
- **Why scan only:** same cross-sectional reason as 12-1 momentum.

### 4.11 Post-Earnings Drift (`pead`, data pending)

- **Formula:** EPS surprise ≥ +10% versus consensus; next-day gap < 8%; hold
  20-60 bars.
- **Missing data:** `earnings_surprise` (actual vs consensus) with filing dates.
- **Status:** inert. No tag is produced until a dated surprise series exists.
  A code comment or a later price move is not a substitute.

### 4.12 Promoter / Insider Buying Cluster (`promoter_buying`, data pending)

- **Formula:** at least 3 insiders, or promoter stake +1% in 30 days, with no
  pledge increase.
- **Missing data:** shareholding history. `pledge_ingest` stores the latest
  snapshot only, so a cluster cannot be reconstructed point-in-time.
- **Status:** inert. No tag is produced.

---

## 5. Scan semantics

`playbook_engine.scan()`:

1. Loads the band universe (`band_universe`, limit 900 by default).
2. Loads each symbol's bars, split-adjusts them, rejects short history and
   residual seams.
3. Finds the maximum last-traded date across the loaded symbols. **Symbols whose
   last bar is not that date are dropped from the scan.** This prevents a stock
   that stopped trading 40 days ago from receiving today's `as_of` and looking
   fresh.
4. Computes 12-1 momentum and 60-day volatility on the surviving bars, then
   percentile-ranks them. The ranks are supplied to the two cross-sectional
   detectors.
5. Runs every live detector plus `detect_warnings` (death cross).
6. Persists one row per `(as_of, symbol, strategy)`; a re-scan of the same date
   deletes and replaces that date's rows, never other dates.

What a tag contains:

- `entry`, `stop`, `target`, `rr`, `risk_pct`, `hold`;
- `notes` (the human reason with the measured pivot/ATR/volume);
- `params` (the rule's exact parameter block);
- `indicators` (the measured values used by the detector);
- `exits` (the R40 block: stop, target, offset, invalidation, exhaustion,
  time exit);
- `overlaps` (other rules that tagged the same symbol, R41: mark, don't prune);
- `direction` (`LONG_ENTRY` or `TOP_WARNING`) and `status`
  (`BREAKOUT`, `CROSS`, `MOMENTUM`, etc.).

A blank day is a valid answer. In particular, VCP, HTF, cup, ascending base,
and 52-week breakouts are rare; zero live tags on a single date is not
automatically a bug. The backtest trade counts prove the detectors fire over
history.

### Local snapshot, 2026-10-16

- 865 names requested, 591 usable, 274 skipped (short history or a residual
  split seam).
- 87 tags across 5 rules:
  - 12-1 momentum: 60
  - low-vol momentum: 13
  - Donchian 20: 8
  - golden cross: 5 (3 entries + 2 `TOP_WARNING`)
  - flat base: 1
- The other shape rules legitimately had no tag on this date. Their historical
  backtests did fire (see §7).

The 591/274 split is a data statement, not a scanner failure. The local
database is stale (max date 2026-10-16); many short histories are real, and
part of the 274 are symbols with an unexplained price seam.

---

## 6. Walk-forward backtest

### 6.1 No look-ahead

For a signal evaluated on bar `i` (using only data through `i`):

- entry is the **next bar's open**, `i + 1`;
- if the next open is more than **5% above** the signal close, the trade is
  skipped (chase guard);
- if the next open is at or below the stop, the trade is skipped;
- if the next open is already at or above the research target (fixed-target
  rules only), the trade is skipped - otherwise the same open would book an
  instant, untradeable win;
- stops and targets are checked from the entry bar forward using that bar's
  OHLC. If both are touched in one bar, the **stop** is assumed first;
- a gap through a level fills at the open, not at the level;
- the time exit is the close of the final allowed bar (`entry_index + hold - 1`).

### 6.2 Costs and statistics

- **Cost:** 30 bps round trip, charged as
  `(0.0030 × entry) / risk` R. There is no separate slippage model, STT, impact
  cost, or borrow cost.
- **R:** `(exit - entry) / (entry - stop) - cost_R`.
- **Win:** `R > 0` after costs. A flat trade counts as a loss.
- **Expectancy:** mean R across all trades.
- **Profit factor:** gross winning R / absolute gross losing R.
- **Max drawdown:** cumulative R of closed trades ordered by **exit date**
  (realization order). Trades from different symbols overlap, so this is an
  approximation, not a portfolio margin curve.
- **Median hold:** bars from entry to exit, inclusive.
- **Best / worst:** single-trade R.

### 6.3 Execution model

- One open trade per symbol per strategy at a time. After a trade closes, the
  next signal for that symbol/rule may enter; the block ends at
  `signal_index + actual_hold + 1`.
- Shape rules are evaluated on **every bar** (`step = 1`) by default. The old
  every-5-bars shortcut under-sampled the rare bases.
- The backtest window is `max(260, n - years × 252)` per symbol, with a 3-year
  default. The 260-bar warmup is always available before the first signal.
- `universe_n` in the result is the number of symbols actually loaded (591
  locally), not the 865 requested.
- The 8 backtestable rules are the shape/trend rules. The two cross-sectional
  rules are scan-only; PEAD and promoter buying are data-pending. The UI labels
  this as `8 backtested · 2 scan-only · 2 data pending`.

### 6.4 Data handling and known bias

- **Split adjustment:** `prices_daily` is raw bhavdata. For every
  `corporate_actions` row with `kind='split'` and `ratio > 1`, all bars strictly
  before the ex-date are divided by the ratio and volume is multiplied by it.
  The result is on today's share basis.
- **Seam guard:** after adjustment, any single-session move >45% excludes the
  symbol from the run. An unrecorded split or bonus is not repaired by
  guesswork. MBAPL is the known local example (an unexplained ~20× jump).
- **No bonus/rights/dividend adjustment:** only `kind='split'` is applied.
  A bonus recorded under another kind can still trip the seam guard.
- **Survivorship bias:** the universe is today's listed companies. Delisted,
  merged, and suspended names are absent, so long-run returns are optimistic.
- **RS gate:** the scan passes a cross-sectional relative-strength percentile
  to the 52-week and VCP trend templates. The backtest is per-symbol and does
  **not** compute that percentile, so the RS gate is absent in the walk-forward.
  The backtest still applies the price/MA/30%-above-low/within-25%-of-high
  parts of the template. Do not treat the backtest trade count as the same rule
  the live scan runs.
- **Stale data:** the local snapshot ends 2026-10-16. The terminal's own
  top-picks gate reports four missing weekdays after that date. Fix the price
  ingest before drawing any live conclusion.
- **No market regime filter:** the scan is always on. The book's distribution-day
  and index rules are documented as exits/context but are not gates.
- **No position sizing, capital, or portfolio construction:** all results are
  in R, not rupees. Overlapping trades are not netted.
- **One trade per symbol/rule:** this avoids pseudo-replication but also means
  the backtest does not model pyramiding or multiple entries.

---

## 7. Local verification results

Run on 2026-10-23 02:45-02:46 IST (`run_at 2026-10-23T02:46:37`) against the
local database (max price date 2026-10-16). Parameters: 900 requested, 591
loaded, 3 years, `step=1`, 30 bps, next-open entries. These are **not
production results**.

| Rule | Trades | Win rate | Expectancy | Profit factor | Max DD (R) | Median hold |
|---|---:|---:|---:|---:|---:|---:|
| Donchian 20 | 5,451 | 28.6% | +0.07R | 1.12 | 734.3 | 14 b |
| 50/200 cross | 1,036 | 14.5% | +0.04R | 1.05 | 594.3 | 18 b |
| 52-week high | 911 | 29.2% | -0.11R | 0.85 | 167.1 | 10 b |
| Flat base | 102 | 29.4% | -0.33R | 0.58 | 40.1 | 5 b |
| Cup with handle | 56 | 26.8% | -0.33R | 0.57 | 25.1 | 21 b |
| HTF | 9 | 0.0% | -1.13R* | 0.00 | 10.2 | 7 b |
| Ascending base | 1 | 0.0% | -1.06R* | 0.00 | 1.1 | 1 b |
| VCP | 1 | 100.0% | +2.12R* | - | 0.0 | 10 b |

`*` fewer than 20 trades: anecdotal, not evidence. A single VCP trade with a
100% win rate is not a 100% win-rate rule.

Reading the table honestly:

- Donchian is the only rule with a large sample and a positive expectancy, and
  even that is +0.07R per trade with a 734.3R closed-trade drawdown. The edge
  is thin and the path is brutal.
- The golden cross has a low win rate and a positive expectancy because the
  winners are large; the sample is 1,036 trades, but the rule is slow and the
  closed-trade drawdown is 594.3R.
- The 52-week breakout is negative on this sample after 30 bps and without the
  scan's RS gate. That is a warning, not a verdict on O'Neil.
- Cup, flat base, HTF, ascending, and VCP are too rare on 591 current names
  over 3 years to rank. Their counts are consistent with the detectors working;
  they are not a basis for capital allocation.
- The universe is survivorship-biased and the data is stale. Treat the whole
  table as a pipeline test with a research hint, not a live track record.

The previous runs (01:52 and 02:24) remain in `strategy_backtests` as history;
the UI uses the latest `run_at` per rule. The 02:46 run changed only the max
drawdown ordering (realization at exit, not entry); trade counts, wins, and
expectancy are unchanged. The gap-through-target guard did not change any trade
in this sample. The cross-sectional tags from before 02:21 were inverted and
have been replaced; the latest scan is 02:51 and has the same 87-tag set with
the corrected exit text.

---

## 8. API reference

All routes are under `/api/playbook`. The API server runs on port 8010 in the
local verification setup; production uses the terminal's configured port.

| Method | Path | Purpose |
|---|---|---|
| GET | `/strategies` | 12-rule catalogue + live counts + latest backtest per rule. |
| GET | `/signals` | Tags for the latest scan. Filters: `strategy`, `symbol`, `direction`, `as_of`, `limit` (default 500, max 2000). |
| GET | `/symbol/{symbol}` | All tags for one symbol on the latest scan date, plus the scan date. |
| POST | `/scan?limit=900` | Start a whole-universe scan in a daemon thread. `limit` 10-2000. |
| GET | `/scan/status` | In-memory job status and last result summary. |
| POST | `/backtest` | Body `{limit, years, step, strategies}`. Defaults: limit 150, years 3, step 1, all backtestable rules. `strategies` may be a list or comma string. |
| GET | `/backtest/status` | In-memory job status (`done`/`total` are symbol-rule work units). |
| GET | `/backtests?strategy=&limit=100` | Latest row per backtestable rule (filtered by `strategy` when supplied) plus raw run history (max 500). Scan-only and data-pending rows are excluded. |

**Restart behavior:** the job dictionaries are module-level and are lost when
the API process restarts. The persisted rows are not. If the UI sees
`status: idle` but rows exist, it shows "Latest saved scan: ..." and "Latest
saved backtest: ..." instead of claiming nothing has ever run. The status line
is not a scheduler; there is no cron entry for the Playbook.

**One job at a time:** `_LOCK` guards the status dicts. A scan and a backtest
can run concurrently with each other, but two scans (or two backtests) cannot.
Both are daemon threads inside the API process; a process restart kills a
running job. There is no external queue.

---

## 9. UI guide

- **Cards** show the rule id/short name, full name, book, status badge, exact
  formula, family/direction/hold/book prior, tags today, trades tested, and
  expectancy. A `*` on expectancy means fewer than 20 trades.
- **Show matches** filters the tag table to that rule and scrolls to it.
  **All tags** clears the filter and restores the full latest scan.
- **Rule & exits** expands the exact JSON parameters, the R40 exit narrative,
  and the formula. This is the auditable part of the card; no number is hidden
  behind a tooltip only.
- **Symbol box**: type a symbol and press **Find tags**. The results title
  becomes `Tags for <SYMBOL>` and the count shows the number of tags. The detail
  panel opens for the first matching tag.
- **Tag table columns**: symbol, rule, entry, stop, target, R:R, risk,
  confidence, why. Date and direction were removed from the table because all
  rows in a filtered view share the scan date; a `W` badge in the rule cell
  marks a death-cross warning, and the detail panel shows the full direction.
  The why cell is clamped to two lines with the full text in the title.
- **Detail panel**: signal/date, levels, risk, hold, confidence, measured
  indicators, R40 exit narrative, and the exact params JSON. `Close` hides it.
- **Scan / backtest** buttons disable while their job runs, the status line
  polls every 2.5 s, and the page reloads the catalogue/tags when the job
  completes. A scan preserves the current filter; the user can clear it with
  **All tags**.
- **Narrow screens**: at a 912 CSS-px viewport the strategy grid is two columns
  and the tag/backtest tables fit without a horizontal scrollbar. The layout
  collapses to one column below 680 px.
- **Restart fallback**: see §8; persisted dates are shown when the in-memory
  job state is idle.

---

## 10. Data model

```sql
CREATE TABLE strategy_signals (
  as_of TEXT, symbol TEXT, strategy TEXT,
  direction TEXT, status TEXT, confidence TEXT,
  entry REAL, stop REAL, target REAL, rr REAL, risk_pct REAL,
  hold INTEGER, tags TEXT, notes TEXT, params TEXT, indicators TEXT,
  exits TEXT, overlaps TEXT, created_at TEXT,
  PRIMARY KEY(as_of, symbol, strategy)
);

CREATE TABLE strategy_backtests (
  run_at TEXT, strategy TEXT, years REAL, universe_n INTEGER,
  signals INTEGER, wins INTEGER, losses INTEGER,
  win_rate REAL, avg_win_r REAL, avg_loss_r REAL,
  expectancy_r REAL, profit_factor REAL, max_dd_r REAL,
  median_hold INTEGER, best_r REAL, worst_r REAL,
  cost_bps REAL, step_bars INTEGER, params TEXT, created_at TEXT,
  PRIMARY KEY(run_at, strategy)
);
```

Indexes: `(as_of, strategy)` and `(symbol, as_of)` on `strategy_signals`.
The `indicators` column is created by an idempotent migration for existing
databases; new databases get it from `SCHEMA`.

`params`, `indicators`, `exits`, `tags`, and `overlaps` are JSON text. The API
parses them before returning; the raw columns are useful for audit.

---

## 11. Tests

```powershell
.\env\Scripts\python.exe -m unittest test_playbook -v
```

30 tests, all passing on 2026-10-23. Coverage:

- registry completeness and no duplicate top-level detector names;
- Donchian breakout and chop rejection;
- 52-week trend-template firing and volume requirement;
- cup depth/handle rejection;
- VCP contraction shrink and chop rejection;
- HTF pole weakness rejection;
- flat base depth rejection;
- ascending base rising-low requirement;
- golden cross fires once; death cross is a `TOP_WARNING` with no R:R;
- every signal carries the six R40 exit fields;
- stop-first simulation; gap-through-target skip; minimum-risk floor;
- stats math (win rate, expectancy, PF, median hold);
- split back-adjustment, volume inverse scaling, unadjusted seam rejection;
- `ll10` and `reverse_cross` exit modes;
- zigzag alternation and sub-threshold wiggle rejection;
- cross-sectional rank direction (top decile momentum, top-20%/bottom-50%
  low-vol), the regression for the inverted-rank bug.

Not covered by unit tests: the live API polling, the full 591-symbol scan, the
50-second backtest, and browser layout. Those were exercised manually (see
§7 and §9).

---

## 12. Known limitations and next steps

1. **RS gate is missing from the walk-forward** for 52-week and VCP. The
   correct fix is a per-date cross-sectional RS series, not a per-symbol proxy.
   Until then, label those backtests "without RS gate".
2. **PEAD and promoter buying are inert.** They need dated earnings surprises
   and shareholding history. Do not implement them with a latest-snapshot
   substitute.
3. **Survivorship bias.** The universe is current listings. A point-in-time
   membership table is required for a credible long-run result.
4. **Corporate actions.** Only splits are adjusted. Bonus/rights/dividends and
   unrecorded seams are excluded, not repaired. The MBAPL case is still open.
5. **Stale data.** The local DB ends 2026-10-16; the terminal's own gate reports
   missing weekdays. Fix the ingest before promoting any tag.
6. **No portfolio layer.** R-based expectancy, no capital, no position sizing,
   no sector caps, no correlation, no regime filter.
7. **Drawdown is approximate.** Closed trades ordered by exit date, not a
   mark-to-market equity curve; overlapping symbols are not netted.
8. **No slippage beyond 30 bps.** No impact model, no liquidity cap, no
   borrow/STT.
9. **One trade per symbol/rule.** No pyramiding, no re-entry modeling beyond the
   block window.
10. **The two cross-sectional rules are scan-only.** They are deliberately not
    forced into the per-symbol engine. A proper portfolio backtest is a
    separate build.
11. **No scheduler.** The Playbook scan/backtest are on-demand jobs; the
    existing EOD cron does not call them. If they are added to cron, they must
    run after the price ingest and must not overlap.

---

## 13. Deploy and rollback

The Playbook adds no Python package dependency (it uses `numpy`, `pandas`,
`sqlite3`, and the existing FastAPI app). The database migration is additive and
idempotent.

**Deploy order:**

1. Back up the database (the `strategy_*` tables are additive, but a backup is
   still mandatory before a schema change).
2. Copy `playbook.py`, `playbook_engine.py`, `terminal_api.py`, `db.py`,
   `terminal/static/playbook.js`, `terminal/static/playbook.css`,
   `terminal/static/index.html`, `terminal/static/app.js`,
   `test_playbook.py`, and this document.
3. Restart the API process (Python modules are imported once; static files are
   read per request, but versioned URLs need a hard refresh).
4. Open the terminal, hard-refresh, select **Playbook**, and verify the
   catalogue loads. Run a small scan (`limit=50`) before the full scan.
5. Run the 30 unit tests on the target.
6. Run a full scan, then a full backtest; confirm the status lines and the
   latest rows.
7. Only then consider a commit/push. The owner has not approved a commit yet.

**Rollback:**

1. Revert the commit (or restore the prior files) and restart the API.
2. The `strategy_signals` / `strategy_backtests` tables can remain; they are
   not read by any other module. If a clean rollback is required, drop the two
   tables and their indexes after a backup.
3. Hard-refresh the browser so the old `app.js`/HTML is loaded.

The exact copy-paste deploy blocks (laptop PowerShell / SSH / VM) are prepared
separately under the owner's deploy rules (R47) and must be verified on the
target before success is claimed.

---

## 14. Change log

- **2026-10-23** - Playbook module, engine, API, UI, schema, tests, docs.
  - 12-rule registry, 8 backtestable shape/trend rules, 2 scan-only
    cross-sectional rules, 2 data-pending event rules.
  - Split back-adjustment + >45% seam guard.
  - Walk-forward next-open simulation, 30 bps, stop-first, 5% chase cap,
    gap-through-target skip, one open trade per symbol/rule.
  - `ll10` and `reverse_cross` exit modes.
  - Max drawdown ordered by exit date (realization order), not entry date.
  - Warning exit blocks reverse the stop/target inequalities; a death cross
    is an upside invalidation and a downside objective, never a short.
  - Fixed inverted cross-sectional ranks (bottom decile -> top decile; bottom
    20% -> top 20%) and added regression tests.
  - Fixed the UI `0.0%` risk and `0.00R` rendering for null warning fields.
  - Fixed the UI restart fallback, detail-panel header, table widths, small-n
    markers, and the duplicated scan date.
  - Appended the Playbook exit modes to `EXIT_LOGIC.md`.
