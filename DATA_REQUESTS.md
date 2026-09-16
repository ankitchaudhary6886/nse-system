# DATA REQUESTS — Owner Action List

**Purpose:** single, live list of every data element the owner must
provide to unlock the remaining methods across all traders.

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
- **Duplication** — overlaps with other requests
- **Priority** — P0 / P1 / P2
- **Owner action** — how to obtain
- **Effort** — S / M / L

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
  - O'Shaughnessy: unlocks 4 methods
  - Gray-Carlisle: unlocks 8 methods
  - Lowe: unlocks 6 methods
  - **Apurva Parikh: unlocks 2 methods (Secrets 3, 4)**
  - **Total: ~20 methods**
- **Why:** every "change over time" and "average over N years"
  signal needs historical snapshots. `fundamentals` table only
  stores the latest snapshot today.
- **Impact:** turns ~20 flagged funda methods live.
  Estimated +60–120 additional signals per scan.
- **Relevance:** CRITICAL
- **Duplication:** subsumes DR-02, DR-04 (partial), DR-05 (partial),
  DR-06, DR-07, DR-18, DR-19
- **Priority:** P0
- **Owner action:** Screener.in premium (~₹6k/yr) or equivalent CSV
  export for top ~200 band symbols. Loader to be written on arrival.
- **Effort:** M + S quarterly refresh

### DR-02 · balance_sheet_line_items (latest snapshot)
- **Status:** OPEN — subsumed by DR-01
- **Field(s):** `total_assets`, `current_assets`,
  `current_liabilities`, `cash_and_equivalents`, `total_debt`,
  `gross_profit`, `ebit`, `tangible_book_value`
- **Trader impact:** Gray-Carlisle (3), Lowe (3)
- **Priority:** P0 (solved by DR-01)

### DR-03 · aaa_bond_yield (live value)
- **Status:** PARTIAL — hardcoded 7.5% in value_investing_made_easy.py
- **Field(s):** Indian AAA corp yield (10yr G-sec + ~100 bps)
- **Trader impact:** Lowe (3 methods)
- **Priority:** P0 (trivial)
- **Owner action:** update constant quarterly, or leave hardcoded.
- **Effort:** S

---

## P1 — High value

### DR-04 · shares_outstanding (current + 5-year history)
- **Status:** OPEN — partially covered by DR-01
- **Trader impact:** O'Shaughnessy (2), Gray-Carlisle (1)
- **Priority:** P1
- **Effort:** S (if DR-01 covers most) / M (standalone)

### DR-05 · dividend_history (10–20 years)
- **Status:** OPEN — partially covered by DR-01
- **Trader impact:** Lowe (2 methods + sharpens 2)
- **Priority:** P1
- **Effort:** S (if DR-01 covers)

### DR-06 · price_to_sales_ttm
- **Status:** OPEN — needs `revenue` from DR-01
- **Trader impact:** O'Shaughnessy (4 methods)
- **Priority:** P1
- **Effort:** 0 (if DR-01 delivered)

### DR-07 · eps_growth_1y
- **Status:** OPEN — needs EPS history from DR-01
- **Trader impact:** O'Shaughnessy (3 methods)
- **Priority:** P1
- **Effort:** 0 (if DR-01 delivered)

### DR-16 · promoter_holding_and_pledged_pct
- **Status:** OPEN
- **Field(s):** `promoter_holding` (% of shares held by promoters),
  `pledged_percentage` (% of promoter shares pledged)
- **Trader impact:**
  - Apurva Parikh: unlocks 1 secret (Secret 2)
  - Sharpe: also useful for fund_veto (already a gate elsewhere)
- **Why:** book requires Promoter ≥ 51% + Pledge ≤ 20%. Promoter
  holding is a "skin in the game" filter; pledge is a danger signal.
  Not available on TV India scanner — null across the board today.
- **Impact:** turns Secret 2 live (adds ~10-30% filter strength to
  the composite).
- **Relevance:** HIGH — Parikh's #2 filter is one of the strongest
  in the book.
- **Duplication:** none
- **Priority:** P1
- **Owner action:** Screener.in provides both columns in their
  standard CSV export. If DR-01 delivers Screener.in data, this
  comes for free.
- **Effort:** S (if Screener.in export covers it)

### DR-17 · nifty_pe (live gate)
- **Status:** PARTIAL — proxy constant set to 22.0 in
  `apurva_parikh.py`. Owner updates when rate regime changes.
- **Field(s):** Nifty 50 trailing P/E
- **Trader impact:** Apurva Parikh (Secret 10 partial — market gate)
- **Why:** book explicitly warns against buying when Nifty PE > 25-40;
  best entry zone is ≤ 15.
- **Impact:** improves signal timing, not count.
- **Relevance:** MEDIUM — current 22.0 is a fair live approximation.
- **Duplication:** none
- **Priority:** P1
- **Owner action:** update `NIFTY_PE_PROXY` constant in
  `traders/apurva_parikh.py` weekly/quarterly; OR we build a daily
  fetch from NSE in a future batch.
- **Effort:** S

---

## P2 — Nice to have

### DR-08 · insider_trades (SEBI SAST)
- **Trader impact:** Gray-Carlisle (1)
- **Priority:** P2 · **Effort:** L

### DR-09 · short_interest (NSE)
- **Trader impact:** Gray-Carlisle (1)
- **Priority:** P2 · **Effort:** M

### DR-10 · activist_13d_filings (SEBI SAST)
- **Trader impact:** Gray-Carlisle (1)
- **Priority:** P2 · **Effort:** L

### DR-11 · corporate_bond_feed
- **Trader impact:** Lowe (2)
- **Priority:** P2 · **Effort:** L

### DR-12 · convertible_and_preferred_feed
- **Trader impact:** Lowe (2)
- **Priority:** P2 · **Effort:** L

### DR-13 · IBC_NCLT_feed
- **Trader impact:** Lowe (2)
- **Priority:** P2 · **Effort:** L

### DR-14 · open_offer_feed
- **Trader impact:** Lowe (1)
- **Priority:** P2 · **Effort:** L

### DR-15 · ipo_feed
- **Trader impact:** Lowe (1)
- **Priority:** P2 · **Effort:** M

### DR-18 · business_age (years_since_incorporation / listing_years)
- **Status:** OPEN — partially covered by DR-01 if Screener export
  includes incorporation date.
- **Field(s):** `listing_date`, `incorporation_date`
- **Trader impact:** Apurva Parikh (Secret 1)
- **Why:** book requires ≥ 10 years of history.
- **Impact:** turns Secret 1 live.
- **Relevance:** MEDIUM
- **Priority:** P2
- **Owner action:** NSE bhavcopy history, or a curated list.
- **Effort:** S

### DR-19 · qualitative_leadership_data (NOTE only)
- **Status:** OPEN — informational
- **Field(s):** `ceo_tenure`, `auditor_reputation`,
  `related_party_transactions`, `management_remuneration`
- **Trader impact:** Apurva Parikh (Secret 5 — NOTE)
- **Why:** book flags leadership quality, but the extraction
  classified it as NOTE (subjective, not scanner-testable).
- **Impact:** none (recorded, not gating).
- **Priority:** P2
- **Owner action:** not required.

---

## Duplication map

| Fetch | Unlocks |
|---|---|
| **DR-01 fundamentals_history** | DR-02, DR-04, DR-05, DR-06, DR-07, DR-18 partial → ~20 methods |
| **Screener.in premium export** | DR-01, DR-02, DR-04, DR-05, DR-06, DR-07, DR-16, DR-18 → ~21 methods |

**Practical reality:** one Screener.in premium subscription covers
~75% of the entire backlog.

---

## Priority summary

| Priority | Requests | Methods unlocked | Effort |
|---|---|---|---|
| P0 | DR-01, DR-02, DR-03 | ~22 methods | M + S |
| P1 | DR-04, DR-05, DR-06, DR-07, DR-16, DR-17 | ~9 methods | S each |
| P2 | DR-08–DR-15, DR-18, DR-19 | ~11 methods | M–L each |

**Total backlog value:** ~42 methods currently flagged across
O'Shaughnessy, Gray-Carlisle, Lowe, and Parikh.

**Single biggest win:** DR-01 (+ DR-16 via same Screener export).

---

## Update protocol

- Owner delivers data → move request to DELIVERED, log in
  EXECUTION_LOG.md, activate methods.
- Method refactored to use a proxy → mark DEPRECATED with reason.
- Priority changes → update + log.
- Review cadence: on every new trader book extraction, and on every
  owner data delivery.