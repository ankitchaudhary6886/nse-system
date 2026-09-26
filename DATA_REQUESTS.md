# DATA REQUESTS — Owner Action List

**Purpose:** live list of every data element the owner must provide
to unlock remaining methods across all traders.

**Last updated:** 2026-09-26 (official exchange filings selected for
point-in-time fundamentals)
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

## KITE market snapshot (2026-09-26)

The KITE export was imported into `kite_market_snapshots`, a separate
research-only table. Its file modification date is retained as the
snapshot date; the file contains no financial period-end or public
filing timestamp. The export had 600 rows representing 500 distinct
instrument labels: 100 exact duplicate rows were collapsed; 366
instruments mapped by normalized official name, curated alias, or exact
symbol; 134 were retained without a symbol because mapping was not
unambiguous. The source's Average Price, Buy/Sell Quantity, Trade Value,
and Volume columns were zero for every row and are withheld from
structured analysis while remaining in the raw JSON.

This import does not modify live fundamentals, daily prices, universe
membership, signals, or backtests. Review coverage with
`python kite_snapshot_report.py --db data/app.db`; manually resolve
unmapped names before using symbol-level metrics. It does not satisfy
DR-01 or DR-21.

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
- **Source decision (2026-09-26):** use official NSE/BSE company
  financial-result filings as the source of truth; do not require a
  premium data subscription.
- **Data required:** annual and quarterly statements mapped to exchange
  symbol and, where available, ISIN; retain financial period-end,
  first public filing timestamp, units, source URL/artifact, and any
  restatement or supersession relationship.
- **Acceptance rule:** an observation is eligible for historical replay
  only when both the financial period and public-availability time are
  known. DR-01 remains OPEN until a filing adapter/import path is
  implemented and coverage and date quality are verified.

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

### Point-in-time fundamentals decision (2026-09-26)
Official NSE/BSE filings are the authority for dated fundamentals. The
plugin framework does not yet ingest those filings; DR-01 and DR-21
remain open. The ScanX export is still research-only because it has no
underlying period-end or public filing date.