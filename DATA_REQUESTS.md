# DATA REQUESTS — Owner Action List

**Purpose:** live list of every data element the owner must provide
to unlock remaining methods across all traders.

**Last updated:** 2026-09-17 (trader #10 Nison added — no new requests)
**Status legend:** OPEN · PARTIAL · DELIVERED · DEPRECATED

---

## Traders with zero data requests

The following traders are fully implemented with price-only or
current-snapshot data. No owner action needed for them:

- **John Crane** (Swing, 13 methods)
- **Larry Spears** (Swing, 7 methods)
- **Curtis Faith — Way of the Turtle** (Multi, 9 methods)
- **Patel & Kiri — 7 Simple Strategies** (Swing, 11 methods)
- **Ishaan Agnihotri — A Technical Trader's Handbook** (Swing, 5 methods)
- **Steve Nison — Beyond Candlesticks** (Multi, 6 methods)

Total: 51 methods running on existing data today.

---

## P0 — Critical

### DR-01 · fundamentals_history (multi-year snapshots)
- **Status:** OPEN
- **Field(s):** yearly row per symbol: `revenue`, `gross_profit`,
  `ebit`, `net_income`, `eps`, `total_assets`, `current_assets`,
  `current_liabilities`, `cash_and_equivalents`, `total_debt`,
  `shareholders_equity`, `book_value_per_share`, `cfo`, `capex`,
  `fcf`, `shares_outstanding`, `dividend_per_share`,
  `depreciation_amortization`
- **Years needed:** 10 minimum, 20 ideal
- **Trader impact:**
  - O'Shaughnessy: 4 methods (PSR, EPS-growth-1y, buyback-yield via
    shares delta, P/CF)
  - Gray-Carlisle: 8 methods (F_SCORE, FS_SCORE, Franchise Power,
    PROBM, PFD, STA, SNOA, buyback_yield)
  - Lowe: 6 methods (NCAV, Graham 10-attribute full, Defensive
    Investor, Enterprising Investor, Earnings Stability, Babson
    Pricing)
  - Parikh: 2 methods (Secrets 3, 4 — sales/profit growth 10y)
  - **Total: ~20 methods**
- **Why:** every "change over time" and "average over N years"
  signal needs historical snapshots. The current `fundamentals`
  table stores only the latest snapshot.
- **Impact:** turns ~20 flagged funda methods live. Estimated
  +60–120 additional signals per scan.
- **Relevance:** CRITICAL — the single largest unblocker.
- **Duplication:** subsumes DR-02, DR-04 (partial), DR-05 (partial),
  DR-06, DR-07, DR-18
- **Priority:** P0 · **Effort:** M (one-time setup) + S (quarterly refresh)
- **Owner action:** Screener.in premium export (~₹6k/yr) or equivalent
  CSV. One export for the top ~200 band symbols. Loader to be written
  after the first CSV arrives.

### DR-02 · balance_sheet_line_items (latest snapshot)
- **Status:** OPEN — subsumed by DR-01
- **Field(s):** `total_assets`, `current_assets`,
  `current_liabilities`, `cash_and_equivalents`, `total_debt`,
  `gross_profit`, `ebit`, `tangible_book_value`
- **Trader impact:**
  - Gray-Carlisle: 3 methods (EBIT/TEV, magic_formula full,
    quality_and_price full)
  - Lowe: 3 methods (balance_sheet_safety full, NCAV, quick_ratio)
- **Why:** TEV denominator, NCAV numerator, quick-ratio math.
- **Impact:** turns ~6 methods live once DR-01's latest row is parsed.
- **Priority:** P0 (solved by DR-01)

### DR-03 · aaa_bond_yield (live value)
- **Status:** PARTIAL — currently hardcoded at 7.5% in
  `traders/value_investing_made_easy.py`
- **Field(s):** Indian AAA corporate bond yield (%) — equivalent to
  10-year G-sec + ~100 bps
- **Trader impact:** Lowe (3 methods — graham_earnings_yield,
  graham_dividend_yield, intrinsic_value_formula)
- **Why:** Graham's thresholds are all expressed relative to the AAA
  yield. Rate regime changes shift every threshold.
- **Impact:** improves signal *accuracy*, not count.
- **Priority:** P0 · **Effort:** S
- **Owner action:** update `AAA_BOND_YIELD_PCT` constant quarterly,
  or leave hardcoded and accept approximation.

---

## P1 — High value

### DR-04 · shares_outstanding (current + 5-year history)
- **Status:** OPEN — partially covered by DR-01
- **Field(s):** `shares_outstanding` (diluted) + 5-year history
- **Trader impact:** O'Shaughnessy (2 methods), Gray-Carlisle (1)
- **Why:** Market Leaders filter + shareholder-yield calculation
  needs shares delta over time.
- **Priority:** P1 · **Effort:** S (if DR-01 covers most)

### DR-05 · dividend_history (10–20 years)
- **Status:** OPEN — partially covered by DR-01
- **Field(s):** `dividend_per_share` per FY + count of dividend cuts
- **Trader impact:** Lowe (2 methods + sharpens 2)
- **Priority:** P1 · **Effort:** S (if DR-01 covers)

### DR-06 · price_to_sales_ttm
- **Status:** OPEN — needs `revenue` from DR-01
- **Field(s):** `sales_ttm` = trailing 12-month revenue
- **Trader impact:** O'Shaughnessy (4 methods)
- **Priority:** P1 · **Effort:** 0 (if DR-01 delivered)

### DR-07 · eps_growth_1y (YoY EPS change)
- **Status:** OPEN — needs EPS history from DR-01
- **Field(s):** `eps_growth_1y` = (EPS_t − EPS_t−1) / |EPS_t−1|
- **Trader impact:** O'Shaughnessy (3 methods)
- **Priority:** P1 · **Effort:** 0 (if DR-01 delivered)

### DR-16 · promoter_holding + pledged_pct
- **Status:** OPEN
- **Field(s):** `promoter_holding` (% held by promoters),
  `pledged_percentage` (% of promoter shares pledged)
- **Trader impact:**
  - Parikh: 1 secret (Secret 2 — Promoter ≥ 51%, Pledge ≤ 20%)
  - Also useful for `fund_veto` gate
- **Why:** promoter holding is a "skin in the game" filter; pledge
  is a danger signal. Not available on TV India scanner.
- **Impact:** turns Secret 2 live. Adds ~10-30% filter strength.
- **Priority:** P1 · **Effort:** S (comes with Screener.in export)

### DR-17 · nifty_pe (live gate)
- **Status:** PARTIAL — proxy constant set to 22.0 in
  `traders/apurva_parikh.py`
- **Field(s):** Nifty 50 trailing P/E
- **Trader impact:** Parikh (Secret 10 partial — market gate)
- **Why:** book warns against buying when Nifty PE > 25–40; best
  entry zone ≤ 15.
- **Priority:** P1 · **Effort:** S
- **Owner action:** update `NIFTY_PE_PROXY` constant weekly/quarterly,
  or leave as proxy.

---

## P2 — Nice to have

### DR-08 · insider_trades (SEBI SAST feed)
- **Trader impact:** Gray-Carlisle (1)
- **Priority:** P2 · **Effort:** L

### DR-09 · short_interest (NSE feed)
- **Trader impact:** Gray-Carlisle (1)
- **Priority:** P2 · **Effort:** M

### DR-10 · activist_13d_filings (SEBI SAST)
- **Trader impact:** Gray-Carlisle (1)
- **Priority:** P2 · **Effort:** L

### DR-11 · corporate_bond_feed
- **Field(s):** price, rating, coupon, face value, current yield, YTM
- **Trader impact:** Lowe (2 methods — junk_bond_value,
  bankruptcy_arbitrage)
- **Priority:** P2 · **Effort:** L

### DR-12 · convertible_and_preferred_feed
- **Field(s):** conversion premium, preferred dividend yield,
  conversion terms
- **Trader impact:** Lowe (2 methods)
- **Priority:** P2 · **Effort:** L

### DR-13 · IBC_NCLT_feed
- **Field(s):** companies in NCLT, liquidation values, emergence
  probability
- **Trader impact:** Lowe (2 methods — liquidation_arbitrage,
  bankruptcy_arbitrage)
- **Priority:** P2 · **Effort:** L

### DR-14 · open_offer_feed (merger / takeover)
- **Field(s):** offer_price, months_to_close
- **Trader impact:** Lowe (1 method)
- **Priority:** P2 · **Effort:** L

### DR-15 · ipo_feed
- **Field(s):** IPO date, offer price, underwriter fee %
- **Trader impact:** Lowe (1 method)
- **Priority:** P2 · **Effort:** M

### DR-18 · business_age (years_since_incorporation / listing_years)
- **Status:** OPEN — partially covered by DR-01 if Screener export
  includes incorporation date
- **Trader impact:** Parikh (Secret 1 — ≥10 years of history)
- **Priority:** P2 · **Effort:** S

### DR-19 · qualitative_leadership_data (NOTE only)
- **Field(s):** ceo_tenure, auditor_reputation,
  related_party_transactions, management_remuneration
- **Trader impact:** Parikh (Secret 5 — NOTE only, not gating)
- **Priority:** P2 (informational only)

---

## Priority summary

| Priority | Requests | Methods unlocked | Effort |
|---|---|---|---|
| P0 | DR-01, DR-02, DR-03 | ~21 methods | M + S |
| P1 | DR-04, DR-05, DR-06, DR-07, DR-16, DR-17 | ~9 methods | S each |
| P2 | DR-08 through DR-15, DR-18, DR-19 | ~11 methods | M–L each |

**Total backlog value:** ~41 methods currently flagged across
O'Shaughnessy, Gray-Carlisle, Lowe, and Parikh.

**Single biggest win:** DR-01 (+ DR-16, DR-18 via same Screener.in
export). One subscription, ~21 methods unlocked.

---

## Duplication map

| Fetch | Unlocks |
|---|---|
| **DR-01 fundamentals_history** | DR-02, DR-04 partial, DR-05 partial, DR-06, DR-07, DR-18 → ~20 methods |
| **Screener.in premium export** | DR-01, DR-02, DR-04, DR-05, DR-06, DR-07, DR-16, DR-18 → ~21 methods |

**Practical reality:** one Screener.in premium subscription covers
~80% of the entire backlog.

---

## Update protocol

- Owner delivers data → move request to DELIVERED, log in
  `EXECUTION_LOG.md`, activate methods in the affected trader modules.
- Method refactored to use a proxy → mark DEPRECATED with reason.
- Priority changes → update here + log in `EXECUTION_LOG.md`.
- Review cadence: on every new trader book extraction, and on every
  owner data delivery.
- **This file updates independently.** Do not bundle it with other
  file changes unless a batch genuinely touches both.