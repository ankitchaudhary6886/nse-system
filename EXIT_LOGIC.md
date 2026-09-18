# EXIT LOGIC — How Each Book Thinks About Exits

**Purpose:** narrative of the exit philosophy behind every trader.
Not formulae. Not codes. Just the logic the book teaches.

Complements the per-signal `raw.exits` block (R40 format) with a
trader-level document. Read this when a live exit fires and you want
to argue with it. Read it before trader work to understand what the
book actually expects from an exit.

**Rule R44:** every trader ships a section here when first added.
**Rule R45:** every book also ships a wisdom artifact that feeds
`MARKET_WISDOM.md`.

---

## Trader #1 — John Crane (Advanced Swing Trading, Swing)

**Exit philosophy:** exit on confirmation, not on stop-hit. The
trade has an expected duration (Reverse→Forward count); the exit is
the same technique that confirmed entry, in reverse.

**Where exits come from:**
- **Stop:** structural — below the prior swing low (for long).
- **Target:** none fixed — the next reaction swing's reversal date.
- **Trail:** trail-day confirmation — a bar that closes beyond the
  peak/reversal line.
- **Time:** Reverse count projects the reversal date; if the market
  hasn't confirmed by then, exit or reassess.
- **Opposite signal:** an opposite trail day, or an opposite
  reaction swing confirmation, kills the position.

**Book's exact reasoning:** The reversal date is a specific
calendar projection (holidays counted as full days). The trail day
is the confirmation. Missing the trail day costs the trade; taking
it too early is also a mistake.

**Where shipped in code:** `traders/john_crane.py` — methods
implement the setup-identification only (R30). Exit logic in the
book is documented here, not enforced by signals.

---

## Trader #2 — Larry Spears (Swing-trading methodology, Swing)

**Exit philosophy:** exit only after a *time invalidation* or an
*opposite force-index flip*. Position sizing carries the risk; the
stop is a soft trigger, not a hard bar.

**Where exits come from:**
- **Stop:** not specified in our extraction (R30 excluded — owner
  decides).
- **Target:** 5-day counter-trend invalidation roll-forward — if
  the counter-trend move extends beyond 5 days, the setup is dead.
- **Trail:** trailing stop logic excluded per R30.
- **Time:** 5-day invalidation window is the primary exit signal.
- **Opposite signal:** Force Index flip (FI13 and FI3 crossing the
  opposite direction).

**Book's exact reasoning:** The 5-day counter-trend window keeps
the setup time-bound. If it hasn't worked by day 5, the market is
telling you the read was wrong, independent of price.

**Where shipped in code:** `traders/larry_spears.py` — setup-only
(R30). Exits owner-managed.

---

## Trader #3 — James O'Shaughnessy (What Works on Wall Street, Funda)

**Exit philosophy:** annual rebalance. The exit is calendar-driven,
not price-driven. Positions are held for one year, then re-ranked.

**Where exits come from:**
- **Stop:** none — annual rebalance replaces stops.
- **Target:** next year's rebalance.
- **Trail:** none.
- **Time:** one year.
- **Opposite signal:** falling out of the top decile at rebalance.
- **Special rule:** Graham's "50% return OR two years" for the
  Graham Simple Value method (from Chapter 1 of the book).

**Book's exact reasoning:** Long-horizon value strategies are
measured in years, not weeks. Attempting to time exits within a
value position destroys the strategy's edge (curve-fitting).

**Where shipped in code:** `traders/oshaughnessy.py` — exit logic
as informational metadata on every signal (`raw.exits` suggested
per R40). Funda signals have entry/stop/target as None.

---

## Trader #4 — Gray & Carlisle (Quantitative Value, Funda)

**Exit philosophy:** annual rebalance. Same calendar discipline as
O'Shaughnessy. Fundamental deterioration between rebalances is
tolerated; the model re-ranks annually.

**Where exits come from:**
- **Stop:** none.
- **Target:** next annual rebalance.
- **Trail:** none.
- **Time:** one year.
- **Opposite signal:** falling out of the top decile by combined
  score. Elimination thresholds (top 5% PROBM/PFD/STA/SNOA) remove
  a stock permanently.

**Book's exact reasoning:** The whole book is about *never
overriding the model*. Exits are as mechanical as entries.

**Where shipped in code:** `traders/quantitative_value.py` —
`raw.exits` on every signal as informational (R40). No live exits.

---

## Trader #5 — Janet Lowe (Value Investing Made Easy, Funda)

**Exit philosophy:** sell on **fundamental deterioration**. This
is the book's signature exit rule — one of the few value books
that formalizes it.

**Where exits come from:**
- **Stop:** none fixed.
- **Target:** intrinsic value (Graham's formula), 50% gain for
  net-nets.
- **Trail:** none.
- **Time:** Graham's 2-year rule if 50% not achieved.
- **Opposite signal:** fundamental deterioration.

**The 3 tiers of fundamental-deterioration exits (from the book):**

*Tier 1 — any 2+ for 2 consecutive quarters/years:*
- sales_growth < 10%
- profit_growth < 10% or negative
- roe < 10%
- roce < 15%
- d/e > 0.50
- cfo_positive == false OR ocf/net_income < 0.5
- promoter_holding < 50%
- pledge_pct > 20%
- pe > 1.5 × industry_pe

*Tier 2 — trend deterioration (any 1):*
- rsi < 40
- trend turns down (lower highs + lower lows)
- close below SMA50 or SMA200

*Tier 3 — thesis break (any 1):*
- leadership fraud or regulatory action
- auditor resignation
- business model disruption

**Book's exact reasoning:** "Never go for downward averaging —
without proper research on why a stock is going down continuously,
never purchase stock on every downfall. Cut down your losses and
ride the winner stocks."

**Where shipped in code:** `traders/value_investing_made_easy.py`
— full `EXIT_RULES` block attached to every signal's `raw.exits`.
This was our first trader to ship any exit logic (as informational
metadata).

---

## Trader #6 — Curtis Faith (Way of the Turtle, Multi)

**Exit philosophy:** two independent exits — a **2N stop** (trade
management) and a **10-day/20-day opposite breakout** (trend exit).
The 2N is capital protection; the opposite breakout is trend
confirmation ending.

**Where exits come from:**
- **Stop:** 2N (2× ATR) below entry — the same distance that sized
  the position. Not a technical level.
- **Target:** none fixed — trend followers let the trend exit.
- **Trail:** none as such; the opposite breakout acts as the trail.
- **Time:** none (though an 80-day time exit is an optional
  variant for Donchian Trend).
- **Opposite signal:** 10-day low after a long (for System 1) or
  20-day low (System 2). Same rule that fired the entry, mirrored.

**Book's exact reasoning:** The book is emphatic that stops and
exits are two different things. The 2N stop protects against
catastrophe; the opposite breakout tells you the trend has ended.
Missing the trend exit costs the year's gain.

**Where shipped in code:** `traders/way_of_the_turtle.py` — the
Turtle methods ship `stop=None` per R30 (book excludes stops from
setup identification). The 2N stop is out of scanner scope.

---

## Trader #7 — Patel & Kiri (7 Simple Strategies, Swing)

**Exit philosophy:** "Love your small losses." Volatility-based
stop (2× ATR), targets at the next resistance, trail once in
profit. Exit is capital preservation first, profit second.

**Where exits come from:**
- **Stop:** 2× ATR below entry (or structural low).
- **Target:** next resistance (mean line, channel top, prior swing
  high).
- **Trail:** trail once the trade is in profit — to the setup
  candle's low, or to the 9 EMA.
- **Time:** none fixed. Intraday methods exit at 3:15 PM.
- **Opposite signal:** exit on opposite EMA cross or opposite
  pattern at resistance.

**Book's exact reasoning:** "A 10% loss requires an 11.1% gain to
recover; a 50% loss requires a 100% gain." Position sizing and
stops matter more than entries.

**Where shipped in code:** `traders/seven_simple_strategies.py` —
exits as informational metadata. **10% of this book is exit
philosophy** and it's worth reading Chapter 8 in full.

---

## Trader #8 — Apurva Parikh (11 Secrets, Funda)

**Exit philosophy:** sell on **fundamental deterioration** — the
same rule Lowe teaches, adapted for the Indian market.

**Where exits come from:**
- **Stop:** none fixed.
- **Target:** intrinsic value / sector-relative valuation.
- **Trail:** none.
- **Time:** rebalance quarterly for fundamental filters, monthly
  for valuation/trend filters.
- **Opposite signal:** any of the 9 tier-1 conditions failing
  (see Lowe above — Parikh's book teaches the same frame).

**Book's exact reasoning:** "Monitor your stock portfolio
periodically but not frequently. Hold the stock giving good
performance; sell the shares which lead to loss."

**Where shipped in code:** `traders/apurva_parikh.py` — full
`EXIT_RULES` block on every signal's `raw.exits`.

---

## Trader #9 — Ishaan Agnihotri (A Technical Trader's Handbook, Swing)

**Exit philosophy:** mental stop below the swing low, take profits
at resistance. Candlestick and MACD exits close the position when
the pattern's reason for existing disappears.

**Where exits come from:**
- **Stop:** below swing low or reversal candle low (mental stop).
- **Target:** next resistance / swing high.
- **Trail:** 9 EMA once the position is above it — "close below 9
  EMA" is the exit signal.
- **Time:** no fixed exit.
- **Opposite signal:** MACD bearish cross, or an opposite candle
  pattern at resistance.

**Book's exact reasoning:** "Wait for confirmation — never buy a
breakout until the candle closes above the level and the 9 EMA."
Symmetric: exit when the confirmation fails.

**Where shipped in code:** `traders/ishaan_agnihotri.py` — exits
as informational metadata.

---

## Trader #10 — Steve Nison (Beyond Candlesticks, Multi)

**Exit philosophy:** structured exits. Stop at the reversal
candle's low (or window bottom); target at next resistance;
offset on opposite candle signal; invalidation on close back
inside the pattern.

**Where exits come from:**
- **Stop:** reversal candle's low / pattern structural low.
- **Target:** next resistance / prior swing high / measured move.
- **Trail:** none specific — the pattern-invalidation exit acts as
  a trail.
- **Time:** setup-specific validity windows (3 sessions for
  candles, 10 sessions for long white candle zone).
- **Opposite signal:** opposite candle pattern at resistance.

**Book's exact reasoning:** "Where the pattern appears matters
more than the pattern itself." Exits follow the same rule —
where the reversal appears determines where you exit.

**Where shipped in code:** `traders/nison.py` — **first trader
with full structured `raw.exits`** (R38 format, now R40).

---

## Trader #11 — Tushar Chande (Beyond Technical Analysis, Multi)

**Exit philosophy:** each method has its own exit logic — 3cc
opposite, trailing stop, time exit. But the common principle is
mechanism over discretion. Exits are part of the system, not a
choice made mid-trade.

**Where exits come from:**
- **Stop:** 2-3× ATR (2% equity floor).
- **Target:** method-specific (e.g., recent 20-day high for CB-PB).
- **Trail:** 5-day low after +2R (bottom-fishing); 10-day low
  after +2R (Chande's variant); 40-day low (CB-PB long-term).
- **Time:** 14 days for 65sma-3cc, 20 days for ADX burst, 50 days
  for CB-PB intermediate, 20 days for bottom-fishing, 20 days for
  extraordinary.
- **Opposite signal:** 3 consecutive closes below 65-SMA kills
  65sma-3cc; ADX reversal kills ADX burst.

**Book's exact reasoning:** "Positive expectation — the average
trade must be profitable after costs." That defines what exits
must achieve: preserve the expectancy over many trades. Individual
trade outcomes are noise.

**Where shipped in code:** `traders/chande.py` — full structured
`raw.exits` with thesis + hard number + condition (R40 format).

---

## Trader #12 — William O'Neil (How to Make Money in Stocks, Multi)

**Exit philosophy:** the most explicit exit framework of any book
in our library. Cut every loss at 7-8% without exception. Take
20-25% profits into strength. Never let a 15-20% gain become a
loss. Hold big leaders (20% in <3 weeks) for at least 8 weeks.

**Where exits come from:**
- **Stop:** 7-8% below entry — the insurance-premium rule.
- **Target:** 20-25% into strength. If +20% in <3 weeks, override
  to an 8-week minimum hold.
- **Trail:** 10-week (50-day) MA as the trend exit for leaders.
- **Time:** no fixed exit; the 8-week override is the exception.
- **Opposite signal:** climax top signals (largest daily run-up,
  heaviest volume, exhaustion gap, stock split).

**Book's exact reasoning:** "The whole secret to winning in the
stock market is not being smart but being consistent and following
a sound, proven system." The 7-8% stop is the single most
important rule.

**Where shipped in code:** `traders/oneil.py` — full structured
`raw.exits` via `_oneil_exits_block()`.

---

## Trader #13 — Fred McAllen (Charting and Technical Analysis, Multi)

**Exit philosophy:** stop at the pattern's structural low;
target at the next resistance; exit on pattern invalidation.
The book is emphatic that a stop-loss must be placed immediately
after entry, before the trader has any emotional attachment.

**Where exits come from:**
- **Stop:** pattern structural low (saucer low, island low,
  candle low, first soldier's low).
- **Target:** measured move (island height, saucer depth) or next
  resistance.
- **Trail:** none explicit — pattern invalidation is the trail.
- **Time:** setup-specific windows (10-20 sessions).
- **Opposite signal:** for TOP_WARNING signals, exit longs on
  the pattern's confirmation (e.g., three black crows → sell).

**Book's exact reasoning:** "Always use a stop loss immediately
after entry; protect capital first." Exit discipline is the
single most-repeated theme in the book.

**Where shipped in code:** `traders/mcallen.py` — full structured
`raw.exits` (R40 format). Top-warning signals carry exit-side
logic explicitly.

---

## Trader #14 — Aseem Singhal (51 Trading Strategies, Multi)

**Exit philosophy:** strict per-method exits. Stop at structural
low; target at 1:2 minimum R/R (book insists on 1:2 to 1:4);
trail once in profit. Every method in the book carries an explicit
exit rule.

**Where exits come from:**
- **Stop:** structural (setup candle low, pattern low, cloud
  bottom, Supertrend line, lower Bollinger band).
- **Target:** 1:2 minimum, often 1:3 or 1:4. Resistance levels,
  pivot points, or measured moves.
- **Trail:** to Supertrend, to 9 EMA, to 5-day low.
- **Time:** 3-5 sessions for swing; 10 sessions for positional;
  20 for VCP and positional BO.
- **Opposite signal:** Supertrend flip, EMA cross, opposite candle
  at resistance.

**Book's exact reasoning:** "No indicator alone can help you
become a profitable trader." Confluence is the rule — for
entries *and* exits. Trailing stops lock in gains; fixed stops
prevent catastrophic loss.

**Where shipped in code:** `traders/singhal.py` — full structured
`raw.exits` via `_mk_exits()` (R40 format).

---

## Cross-cutting exit themes (observed across all 14 traders)

1. **Structural stops beat fixed-% stops** — 9 of 14 books place
   stops below the pattern's structural low.
2. **Volatility-based sizing** — 4 books (Turtle, Patel, Chande,
   Singhal) size by 2× ATR.
3. **Time-based exits are common** — 5 books (Nison, Chande,
   O'Neil, McAllen, Singhal) use session-count windows.
4. **Opposite-signal exits** — 7 books (Crane, Spears, Nison,
   Chande, O'Neil, McAllen, Singhal) exit when the setup's
   reason disappears.
5. **Trail, don't target** — for trend-following setups (Turtle,
   O'Neil leaders, Chande extraordinary).
6. **Never let a gain become a loss** — Patel, O'Neil both
   emphasize this. McAllen echoes it.
7. **Fundamental-deterioration exits** — Lowe and Parikh are the
   only two funda books with structured exit rules.

---

## How to use this file

- **Before taking a trade** — read the trader's section to know
  what exit the book actually intends.
- **When a stop fires** — check the trader's section: is this a
  structural exit (expected) or a rule violation (unexpected)?
- **When you want to hold past the book's exit** — you're on
  your own. This file is the book's voice, not the owner's.

Rule R44 makes this file mandatory. Every new trader adds a
section before shipping.