# DATA REQUESTS — Owner Action List

**Purpose:** live list of every data element the owner must provide
to unlock remaining methods across all traders.

**Last updated:** 2026-09-18 (trader #14 Singhal added — DR-23)
**Status legend:** OPEN · PARTIAL · DELIVERED · DEPRECATED

---

## ScanX snapshot enrichment (2026-09-26)

The 750-row export is retained in `scanx_fundamentals_snapshots` with the
original row JSON and normalized, structured research fields for multi-year
quality, quarterly growth, cash flow, balance-sheet context, peer valuation,
and ownership changes. These fields are **research-only**: importing a ScanX
file does not write to `fundamentals`, change the trading universe, or affect
scores, vetoes, signals, or backtests.

The export date is not the underlying financial period-end or public filing
date. Those dates remain unknown, so this snapshot must not be used as
point-in-time historical fundamentals in backtests. DR-01 and DR-21 remain
open until period- and filing-dated histories are available.

The importer preserves every source value in `raw_json`, but withholds
system-wide all-zero sentinel fields (currently payout ratio and promoter
holding change) and out-of-range structured metrics from analysis, recording
quality flags on each snapshot row. The raw values remain available for
auditing. These guards are conservative data-quality checks, not claims that
every unusual source value is wrong.

Run `python scanx_snapshot_report.py --db data/app.db` to inspect per-field
coverage and quality-flag counts for the latest imported export.

---

## Traders with zero data requests

John Crane, Larry Spears, Way of the Turtle, 7 Simple Strategies,
Ishaan Agnihotri, Steve Nison, Tushar Chande, Fred McAllen.

Total: ~70 methods running on existing data today.

---

## P0 — Critical

### DR-01 · fundamentals_history (multi-year snapshots)
- **Status:** OPEN
- **Trader impact:** O'Sh, QV, Lowe, Parikh → ~20 methods
- **Priority:** P0 · **Effort:** M + S
- **Owner action:** Screener.in premium export.

### DR-02 · balance_sheet_line_items (latest)
- **Status:** OPEN — subsumed by DR-01

### DR-03 · aaa_bond_yield (live value)
- **Status:** PARTIAL — hardcoded 7.5%
- **Priority:** P0 · **Effort:** S

---

## P1 — High value

- **DR-04** shares_outstanding · O'Sh (2), QV (1)
- **DR-05** dividend_history · Lowe (2)
- **DR-06** price_to_sales_ttm · O'Sh (4)
- **DR-07** eps_growth_1y · O'Sh (3)
- **DR-16** promoter_holding + pledged_pct · Parikh (1)
- **DR-17** nifty_pe (live) · Parikh (1)
- **DR-20** nifty500_index_daily · O'Neil (~6 methods)
- **DR-21** quarterly_fundamentals · O'Neil (1)
- **DR-22** rs_rating + sponsorship · O'Neil (1)
- **DR-23** RBI repo rate · Singhal (1) — NEW

---

## P2 — Nice to have

- DR-08 through DR-19 as previously logged.

---

## Priority summary

| Priority | Requests | Methods | Effort |
|---|---|---|---|
| P0 | DR-01, DR-02, DR-03 | ~21 | M + S |
| P1 | DR-04–DR-07, DR-16, DR-17, DR-20–DR-23 | ~15 | S–M |
| P2 | DR-08–DR-15, DR-18, DR-19 | ~11 | M–L |

**Single biggest win:** DR-01 (~20 methods).

**Second-biggest:** DR-20 (~6 methods for O'Neil).