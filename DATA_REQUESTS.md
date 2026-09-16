# DATA REQUESTS — Owner Action List

**Purpose:** single, live list of every data element the owner must
provide to unlock the remaining methods across all traders. This is
the *actionable* view. The technical registry lives in
NEW_FEATURES_BACKLOG.md. New-session AI reads this file to know
exactly what's pending on the owner.

**Last updated:** 2026-09-17
**Owner:** Ankit
**Status legend:** OPEN · PARTIAL · DELIVERED · DEPRECATED

---

## How to read this file

Each request shows:
- **Field(s)** — what we call it + formula
- **Trader impact** — which traders/methods need it (with counts)
- **Why** — plain-English thesis
- **Impact** — how many methods activate + rough signal lift
- **Relevance** — how central vs. niche
- **Duplication** — overlaps with other requests (one fetch, many unlocks)
- **Priority** — P0 (critical) / P1 (high) / P2 (nice)
- **Owner action** — how to obtain
- **Effort** — S / M / L (for owner, not for coding)

---

## P0 — Critical (unblocks the most methods)

### DR-01 · fundamentals_history (multi-year snapshots)
- **Status:** OPEN
- **Field(s):** yearly row per symbol containing: `revenue`,
  `gross_profit`, `ebit`, `net_income`, `eps`, `total_assets`,
  `current_assets`, `current_liabilities`, `cash_and_equivalents`,
  `total_debt`, `shareholders_equity`, `book_value_per_share`,
  `cfo`, `capex`, `fcf`, `shares_outstanding`,
  `dividend_per_share`, `depreciation_amortization`
- **Years needed:** 10 minimum, 20 ideal (Lowe's defensive-investor
  needs 20y dividends)
- **Trader impact:**
  - O'Shaughnessy: unlocks 4 methods (PSR, EPS-growth-1y,
    shareholder_yield via shares delta, P/CF)
  - Gray-Carlisle: unlocks 8 methods (F_SCORE, FS_SCORE,
    Franchise Power, PROBM, PFD, STA, SNOA, buyback_yield)
  - Lowe: unlocks 6 methods (NCAV, Graham 10-attribute full,
    Defensive Investor, Enterprising Investor, Earnings Stability,
    Babson Pricing)
  - **Total: ~18 methods**
- **Why:** every "change over time" and "average over N years"
  signal needs historical snapshots. The current `fundamentals`
  table only stores the latest snapshot. This is the single largest
  unblocker across all three funda traders.
- **Impact:** turns ~18 of 22 flagged funda methods live.
  Estimated +60–120 additional signals per scan.
- **Relevance:** CRITICAL — without this, 3 traders are half-
  implemented.
- **Duplication:** this request subsumes DR-02 (balance-sheet
  line items) and DR-03 (shares-outstanding history) — one export
  delivers all three.
- **Priority:** P0
- **Owner action:** export from Screener.in (premium plan, ~₹6k/yr),
  Tickertape, or manually curate from MoneyControl for the top
  ~200 band symbols. Format: one CSV per symbol, one row per FY.
  Loader to be written after first CSV arrives.
- **Effort:** M (one-time setup) + S (quarterly refresh)

### DR-02 · balance_sheet_line_items (latest snapshot)
- **Status:** OPEN — subsumed by DR-01
- **Field(s):** `total_assets`, `current_assets`,
  `current_liabilities`, `cash_and_equivalents`, `total_debt`,
  `gross_profit`, `ebit`, `tangible_book_value`
- **Trader impact:**
  - Gray-Carlisle: 3 methods (EBIT/TEV, magic_formula full,
    quality_and_price full)
  - Lowe: 3 methods (balance_sheet_safety full, NCAV,
    quick_ratio)
- **Why:** TEV denominator, NCAV numerator, quick-ratio math —
  all need balance-sheet line items.
- **Impact:** turns ~6 methods live once DR-01's latest row is
  parsed.
- **Relevance:** HIGH
- **Duplication:** latest row of DR-01
- **Priority:** P0 (solved by DR-01)
- **Owner action:** none separately — comes with DR-01
- **Effort:** 0 (if DR-01 delivered)

### DR-03 · aaa_bond_yield (live value)
- **Status:** PARTIAL — currently hardcoded at 7.5% in
  `value_investing_made_easy.py`
- **Field(s):** Indian AAA corporate bond yield (%),
  equivalent to 10-year G-sec + ~100 bps
- **Trader impact:**
  - Lowe: 3 methods (graham_earnings_yield,
    graham_dividend_yield, intrinsic_value_formula)
- **Why:** Graham's thresholds are all expressed relative to the
  AAA yield. If the yield drifts (rate regime change), every
  threshold shifts.
- **Impact:** improves signal *accuracy*, not count.
- **Relevance:** MEDIUM — current 7.5% is a fair approximation.
- **Duplication:** none
- **Priority:** P0 (but trivially solvable)
- **Owner action:** update `AAA_BOND_YIELD_PCT` constant quarterly
  in `traders/value_investing_made_easy.py` — owner tells me the
  current value and I ship the edit; OR leave hardcoded and accept
  approximation.
- **Effort:** S

---

## P1 — High value (unblocks meaningful methods)

### DR-04 · shares_outstanding (current + 5-year history)
- **Status:** OPEN — partially covered by DR-01
- **Field(s):** `shares_outstanding` (diluted), plus 5-year
  history for buyback-yield calculation
- **Trader impact:**
  - O'Shaughnessy: 2 methods (market_leaders_universe full,
    cornerstone_value_improved)
  - Gray-Carlisle: 1 method (buyback_yield)
- **Why:** Market Leaders filter requires shares-above-average
  test; shareholder yield = dividend + buyback = requires
  shares-delta over time.
- **Impact:** turns 3 methods live, sharpens 1.
- **Relevance:** MEDIUM-HIGH
- **Duplication:** if DR-01 delivered, only 5-year history is
  net-new — current value already in latest row.
- **Priority:** P1
- **Owner action:** Screener has this; or parse from annual reports.
- **Effort:** S (if DR-01 covers most) / M (standalone)

### DR-05 · dividend_history (10–20 years)
- **Status:** OPEN — partially covered by DR-01
- **Field(s):** `dividend_per_share` per FY + `dividend_cut_years`
  (count of cuts)
- **Trader impact:**
  - Lowe: 2 methods (defensive_investor_strategy 20y check,
    dividend_yield_assessment full)
  - O'Shaughnessy: sharpens 2 methods (high_dividend_yield,
    dogs_of_the_dow) — currently uses trailing only
- **Why:** Defensive Investor requires "20 years of continuous
  dividend payments". Dividend-cut history is a financial-
  strength filter.
- **Impact:** turns 2 methods live, adds confidence to 2.
- **Relevance:** MEDIUM
- **Duplication:** DR-01's dividend column, if populated
- **Priority:** P1
- **Owner action:** Screener provides dividend history per symbol.
- **Effort:** S (if DR-01 covers)

### DR-06 · price_to_sales_ttm (trailing 12-month revenue)
- **Status:** OPEN — needs `revenue` from DR-01
- **Field(s):** `sales_ttm` = trailing 12-month revenue
- **Trader impact:**
  - O'Shaughnessy: 4 methods (low_psr_value, low_psr_plus_rs,
    cornerstone_growth_original, cornerstone_growth_improved)
- **Why:** PSR is the book's "king of value factors". Currently
  zero hits because sales data is null.
- **Impact:** turns 4 methods live.
- **Relevance:** HIGH (the book calls it the single best ratio)
- **Duplication:** derived from DR-01's `revenue` column
- **Priority:** P1
- **Owner action:** comes with DR-01 — no separate fetch
- **Effort:** 0 (if DR-01 delivered)

### DR-07 · eps_growth_1y (YoY EPS change)
- **Status:** OPEN — needs EPS history from DR-01
- **Field(s):** `eps_growth_1y` = (EPS_t − EPS_t−1) / |EPS_t−1|
- **Trader impact:**
  - O'Shaughnessy: 3 methods (worst_earnings_gains,
    cornerstone_growth_original, cornerstone_growth_improved)
- **Why:** Cornerstone Growth requires "EPS up YoY" as a value-
  trap filter.
- **Impact:** turns 3 methods live (already ranked by RS —
  the EPS gate is the only missing piece).
- **Relevance:** MEDIUM-HIGH
- **Duplication:** derived from DR-01's `eps` column
- **Priority:** P1
- **Owner action:** comes with DR-01
- **Effort:** 0 (if DR-01 delivered)

---

## P2 — Nice to have (niche / specialized methods)

### DR-08 · insider_trades (SEBI SAST feed)
- **Status:** OPEN
- **Field(s):** insider name, date, buy/sell, quantity, price
  — from SEBI SAST disclosures
- **Trader impact:**
  - Gray-Carlisle: 1 method (insider_buying_opportunistic)
- **Why:** the book's strongest "smart money" signal — outsiders
  acting on private info.
- **Impact:** turns 1 method live. Niche.
- **Relevance:** LOW for individual stock screening; HIGH as
  a confirmation overlay on other signals.
- **Duplication:** none
- **Priority:** P2
- **Owner action:** NSE publishes insider trades. Would require
  a scraper or CSV feed.
- **Effort:** L

### DR-09 · short_interest (NSE feed)
- **Status:** OPEN
- **Field(s):** `short_interest` + `shares_outstanding` →
  short interest ratio (SIR)
- **Trader impact:**
  - Gray-Carlisle: 1 method (low_short_interest)
- **Why:** low short interest = absence of smart-money bearishness
  = bullish signal.
- **Impact:** turns 1 method live. Niche.
- **Relevance:** LOW
- **Duplication:** shares_outstanding already needed for DR-04
- **Priority:** P2
- **Owner action:** NSE publishes this; needs parser.
- **Effort:** M

### DR-10 · activist_13d_filings (SEBI SAST)
- **Status:** OPEN
- **Field(s):** filings with % acquired, activist identity,
  intent
- **Trader impact:**
  - Gray-Carlisle: 1 method (activist_13d_filing)
- **Why:** activist interventions precede above-market returns.
- **Impact:** turns 1 method live. Niche.
- **Relevance:** LOW
- **Duplication:** none
- **Priority:** P2
- **Owner action:** SEBI website / NSE disclosures
- **Effort:** L

### DR-11 · corporate_bond_feed (price, rating, coupon, face value)
- **Status:** OPEN
- **Field(s):** `bond_price`, `bond_rating`, `current_yield`,
  `yield_to_maturity`, `face_value`
- **Trader impact:**
  - Lowe: 2 methods (junk_bond_value, bankruptcy_arbitrage)
- **Why:** distressed debt at deep discount to face = high
  yield with asset coverage.
- **Impact:** turns 2 methods live.
- **Relevance:** LOW — Indian corporate bond market is thin
  for individual investors.
- **Duplication:** none
- **Priority:** P2
- **Owner action:** requires a bond-market data vendor.
- **Effort:** L

### DR-12 · convertible_and_preferred_feed
- **Status:** OPEN
- **Field(s):** `conversion_premium`, `preferred_dividend_yield`,
  conversion terms
- **Trader impact:**
  - Lowe: 2 methods (convertible_securities_value,
    preferred_stock_value)
- **Why:** hybrid securities — upside with downside floor.
- **Impact:** turns 2 methods live.
- **Relevance:** LOW — few listed convertibles on NSE.
- **Duplication:** none
- **Priority:** P2
- **Owner action:** requires data vendor.
- **Effort:** L

### DR-13 · IBC_NCLT_feed (bankruptcy + liquidation proceedings)
- **Status:** OPEN
- **Field(s):** companies in NCLT, liquidation value estimates,
  emergence probability
- **Trader impact:**
  - Lowe: 2 methods (liquidation_arbitrage, bankruptcy_arbitrage)
- **Why:** deep-distressed asset plays.
- **Impact:** turns 2 methods live.
- **Relevance:** LOW — very niche.
- **Duplication:** none
- **Priority:** P2
- **Owner action:** IBC website, NCLT filings.
- **Effort:** L

### DR-14 · open_offer_feed (merger / takeover)
- **Status:** OPEN
- **Field(s):** `offer_price`, `months_to_close`
- **Trader impact:**
  - Lowe: 1 method (merger_takeover_arbitrage)
- **Why:** merger arb — small spreads, high turnover.
- **Impact:** turns 1 method live. Niche.
- **Relevance:** LOW
- **Duplication:** none
- **Priority:** P2
- **Owner action:** SEBI open-offer filings.
- **Effort:** L

### DR-15 · ipo_feed (new listings + underwriter fees)
- **Status:** OPEN
- **Field(s):** IPO date, offer price, underwriter fee %
- **Trader impact:**
  - Lowe: 1 method (ipo_value_assessment)
- **Why:** IPO value assessment.
- **Impact:** turns 1 method live. Niche.
- **Relevance:** LOW
- **Duplication:** none
- **Priority:** P2
- **Owner action:** NSE IPO calendar.
- **Effort:** M

---

## Duplication map (one fetch, many unlocks)

| Fetch | Unlocks |
|---|---|
| **DR-01 fundamentals_history** | DR-02, DR-03 partial, DR-04 partial, DR-05 partial, DR-06, DR-07 → ~18 methods |
| **DR-04 shares_outstanding** | DR-09 partial (denominator for SIR) |
| **Fundamentals export (Screener.in)** | DR-01, DR-02, DR-04, DR-05, DR-06, DR-07, DR-08 partial |

**Practical reality:** a single premium Screener.in subscription
(~₹6,000/year) covers ~75% of the entire backlog. The remaining
25% (event feeds, bond data, IBC) needs specialized sources with
diminishing returns.

---

## Priority summary

| Priority | Requests | Methods unlocked | Est. effort |
|---|---|---|---|
| **P0** | DR-01, DR-02, DR-03 | ~21 methods | M + S |
| **P1** | DR-04, DR-05, DR-06, DR-07 | ~7 methods | S each |
| **P2** | DR-08 through DR-15 | ~11 methods | M–L each |

**Total backlog value:** ~39 methods currently flagged across
O'Shaughnessy, Gray-Carlisle, and Lowe.

**Single biggest win:** DR-01. One fetch, ~18 methods, biggest
signal lift.

---

## Update protocol

- When the owner delivers a data source → move request to
  DELIVERED, log in EXECUTION_LOG.md, activate the affected
  methods in the trader module.
- When a method no longer needs a feature (e.g., the module was
  refactored to use a proxy) → mark DEPRECATED with reason.
- When the priority changes → update here + log in EXECUTION_LOG.md.
- Review cadence: on every new trader book extraction (new
  requests get appended), and on every owner data delivery
  (status flips).