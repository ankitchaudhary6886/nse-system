# DATA REQUESTS — Owner Action List

**Purpose:** live list of every data element the owner must provide
to unlock remaining methods across all traders.

**Last updated:** 2026-09-17 (trader #12 O'Neil added — DR-20/21/22)
**Status legend:** OPEN · PARTIAL · DELIVERED · DEPRECATED

---

## Traders with zero data requests

Fully implemented with price-only or current-snapshot data:

- **John Crane** (Swing, 13 methods)
- **Larry Spears** (Swing, 7 methods)
- **Curtis Faith — Way of the Turtle** (Multi, 9 methods)
- **Patel & Kiri — 7 Simple Strategies** (Swing, 11 methods)
- **Ishaan Agnihotri — A Technical Trader's Handbook** (Swing, 5 methods)
- **Steve Nison — Beyond Candlesticks** (Multi, 6 methods)
- **Tushar Chande — Beyond Technical Analysis** (Multi, 5 methods)

Total: 56 methods running on existing data today.

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
- **Years needed:** 10 min, 20 ideal
- **Trader impact:**
  - O'Shaughnessy: 4 methods
  - Gray-Carlisle: 8 methods
  - Lowe: 6 methods
  - Parikh: 2 methods
  - **Total: ~20 methods**
- **Priority:** P0 · **Effort:** M + S quarterly
- **Owner action:** Screener.in premium (~₹6k/yr). One export
  covers DR-01, DR-02, DR-04, DR-05, DR-06, DR-07, DR-16, DR-18.

### DR-02 · balance_sheet_line_items (latest)
- **Status:** OPEN — subsumed by DR-01
- **Trader impact:** Gray-Carlisle (3), Lowe (3)
- **Priority:** P0

### DR-03 · aaa_bond_yield (live value)
- **Status:** PARTIAL — hardcoded 7.5% in
  `traders/value_investing_made_easy.py`
- **Trader impact:** Lowe (3 methods)
- **Priority:** P0 · **Effort:** S

---

## P1 — High value

- **DR-04** shares_outstanding · O'Sh (2), QV (1) · P1
- **DR-05** dividend_history · Lowe (2) · P1
- **DR-06** price_to_sales_ttm · O'Sh (4) · P1
- **DR-07** eps_growth_1y · O'Sh (3) · P1
- **DR-16** promoter_holding + pledged_pct · Parikh (1) · P1
- **DR-17** nifty_pe (live) · Parikh (1) · P1

---

## P1 · NEW from O'Neil (trader #12)

### DR-20 · nifty500_index_daily (OHLCV)
- **Status:** OPEN
- **Field(s):** daily OHLCV for Nifty 500 index (or Nifty 50
  proxy). Symbol name configurable — `oneil.INDEX_TICKER_CANDIDATES`.
- **Trader impact:** O'Neil (gates methods 1–6)
- **Why:** O'Neil's market-direction filter is the single most
  important gate in the book. Without it, all six of his
  breakout methods return zero signals.
- **Impact:** unlocks ~6 O'Neil methods.
- **Relevance:** CRITICAL for O'Neil specifically.
- **Duplication:** could also feed `regime.py` as a broader proxy
  alongside ^NSEI (which we already fetch).
- **Priority:** P1 · **Effort:** S (yfinance has `^CRSLDX` for
  Nifty 500; or scrape NSE)
- **Owner action:** add a symbol row in `prices_daily` for
  `NIFTY500` — either yfinance backfill or NSE CSV.

### DR-21 · quarterly_fundamentals
- **Status:** OPEN
- **Field(s):** quarterly EPS (YoY growth), quarterly sales
  (YoY growth), EPS 3-year growth rate, EPS acceleration (2+
  consecutive quarters of increasing growth rate)
- **Trader impact:** O'Neil (CAN SLIM — methods 1)
- **Why:** CAN SLIM requires quarterly EPS/sales growth of 18%/25%
  YoY. Currently we only have annual snapshots (and even those are
  just the latest).
- **Impact:** unlocks ~1 method (CAN SLIM composite).
- **Duplication:** partially covered by DR-01 but on a quarterly
  cadence.
- **Priority:** P1 · **Effort:** M

### DR-22 · rs_rating_and_sponsorship
- **Status:** OPEN
- **Field(s):** `rs_rating_52w` — O'Neil-style Relative Price
  Strength Rating (1-99 percentile of 52w price performance
  across Nifty 500); `sponsorship_change` — change in FII+DII
  holdings QoQ; `industry_rank` — stock's rank within its
  industry by earnings growth
- **Trader impact:** O'Neil (CAN SLIM — method 1)
- **Why:** L and I of CAN SLIM. The RS Rating is O'Neil's single
  most-used relative strength metric.
- **Impact:** unlocks ~1 method.
- **Duplication:** sponsorship overlaps with `promoter_holding`
  need in Lowe/Parikh.
- **Priority:** P1 · **Effort:** M

---

## P2 — Nice to have (existing)

- **DR-08** insider_trades · QV (1)
- **DR-09** short_interest · QV (1)
- **DR-10** activist_13d · QV (1)
- **DR-11** corporate_bond_feed · Lowe (2)
- **DR-12** convertible/preferred · Lowe (2)
- **DR-13** IBC/NCLT · Lowe (2)
- **DR-14** open_offer · Lowe (1)
- **DR-15** ipo_feed · Lowe (1)
- **DR-18** business_age · Parikh (1)
- **DR-19** qualitative_leadership · Parikh (NOTE)

---

## Priority summary

| Priority | Requests | Methods | Effort |
|---|---|---|---|
| P0 | DR-01, DR-02, DR-03 | ~21 | M + S |
| P1 (existing) | DR-04–DR-07, DR-16, DR-17 | ~9 | S each |
| P1 (new O'Neil) | DR-20, DR-21, DR-22 | ~8 | S / M / M |
| P2 | DR-08–DR-15, DR-18, DR-19 | ~11 | M–L |

**Single biggest win:** DR-01 (~20 methods). One Screener.in
subscription covers DR-01, DR-02, DR-04, DR-05, DR-06, DR-07,
DR-16, DR-18.

**New critical add:** DR-20 (Nifty 500 index) — unlocks all of
O'Neil's methods with one small fetch.

---

## Update protocol

- Owner delivers data → move request to DELIVERED, log in
  EXECUTION_LOG.md, methods activate automatically.
- Method refactored → mark DEPRECATED with reason.
- **This file updates independently.** Do not bundle with other
  file changes unless a batch genuinely touches both (R39).