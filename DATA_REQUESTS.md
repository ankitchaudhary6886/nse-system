# DATA REQUESTS — Owner Action List

**Purpose:** live list of every data element the owner must provide
to unlock remaining methods across all traders.

**Last updated:** 2026-09-17 (added note for trader #9 — no new requests)
**Status legend:** OPEN · PARTIAL · DELIVERED · DEPRECATED

---

## Trader #9 (Ishaan Agnihotri) — no new requests

Every indicator (EMA9/21, MACD, RSI, DMA180, pivots, support levels,
candlestick patterns, chart patterns) computes inline from
`prices_daily`. Fully implementable today. **Zero backlog
additions.**

---

## P0 — Critical

### DR-01 · fundamentals_history (multi-year snapshots)
- **Status:** OPEN
- **Field(s):** yearly row per symbol — revenue, gross_profit, ebit,
  net_income, eps, total_assets, current_assets, current_liabilities,
  cash_and_equivalents, total_debt, shareholders_equity,
  book_value_per_share, cfo, capex, fcf, shares_outstanding,
  dividend_per_share, depreciation_amortization
- **Years:** 10 min, 20 ideal
- **Trader impact:** O'Shaughnessy (4), Gray-Carlisle (8),
  Lowe (6), Apurva Parikh (2) → **~20 methods**
- **Priority:** P0 · **Effort:** M + S quarterly

### DR-02 · balance_sheet_line_items (latest)
- **Status:** OPEN — subsumed by DR-01
- **Trader impact:** Gray-Carlisle (3), Lowe (3)
- **Priority:** P0

### DR-03 · aaa_bond_yield
- **Status:** PARTIAL — hardcoded 7.5%
- **Trader impact:** Lowe (3)
- **Priority:** P0 · **Effort:** S

---

## P1 — High value

### DR-04 · shares_outstanding (current + 5y history)
- **Status:** OPEN — partially covered by DR-01
- **Trader impact:** O'Shaughnessy (2), Gray-Carlisle (1)
- **Priority:** P1

### DR-05 · dividend_history (10–20y)
- **Status:** OPEN — partially covered by DR-01
- **Trader impact:** Lowe (2 + sharpens 2)
- **Priority:** P1

### DR-06 · price_to_sales_ttm
- **Status:** OPEN — needs revenue from DR-01
- **Trader impact:** O'Shaughnessy (4)
- **Priority:** P1

### DR-07 · eps_growth_1y
- **Status:** OPEN — needs EPS history
- **Trader impact:** O'Shaughnessy (3)
- **Priority:** P1

### DR-16 · promoter_holding + pledged_pct
- **Status:** OPEN
- **Trader impact:** Apurva Parikh (1 secret)
- **Priority:** P1 · **Effort:** S (comes with Screener.in export)

### DR-17 · nifty_pe (live)
- **Status:** PARTIAL — proxy constant 22.0 in apurva_parikh.py
- **Trader impact:** Apurva Parikh (Secret 10 partial)
- **Priority:** P1 · **Effort:** S

---

## P2 — Nice to have

- **DR-08** insider_trades · Gray-Carlisle (1)
- **DR-09** short_interest · Gray-Carlisle (1)
- **DR-10** activist_13d · Gray-Carlisle (1)
- **DR-11** corporate_bond_feed · Lowe (2)
- **DR-12** convertible/preferred · Lowe (2)
- **DR-13** IBC/NCLT · Lowe (2)
- **DR-14** open_offer · Lowe (1)
- **DR-15** ipo_feed · Lowe (1)
- **DR-18** business_age · Parikh (1)
- **DR-19** qualitative_leadership · Parikh (NOTE only)

---

## Priority summary

| Priority | Requests | Methods | Effort |
|---|---|---|---|
| P0 | DR-01, DR-02, DR-03 | ~22 | M + S |
| P1 | DR-04, DR-05, DR-06, DR-07, DR-16, DR-17 | ~9 | S each |
| P2 | DR-08–DR-15, DR-18, DR-19 | ~11 | M–L each |

**Single biggest win:** DR-01 (+ DR-16 via same Screener.in export).
One Screener.in premium subscription covers ~75% of the backlog.