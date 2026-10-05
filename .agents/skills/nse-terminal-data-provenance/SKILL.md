---
name: nse-terminal-data-provenance
description: Use when importing, reconciling, or promoting any market or fundamental data into the NSE terminal — enforces point-in-time correctness, per-field promotion with evidence, dry-run/backup/verify, and the rule that an undated snapshot must never enter replay.
---

# NSE Terminal — Data Provenance & Promotion

This skill is the operational companion to
`.github/skills/nse-data-research/SKILL.md` (the authoritative checklist).
Follow that document; this one adds the repo-specific wiring, exact commands, and
the failure modes already proven here. **Do not create a parallel checklist.**

## 1. The one rule that matters most

> A value is eligible for historical replay or a backtest **only** when both its
> financial **period end** and its **first public availability time** are known.

No date pair → the value may be displayed as research, but must never influence
scores, vetoes, signals, backtests, or replay. `DR-01` and `DR-21` remain OPEN
for exactly this reason. The ScanX and KITE exports are **research-only**.

Corollaries already learned in this repo:
- A **file modification timestamp is host metadata**, not publication evidence.
  Both importers record filename + content SHA-256 + file mtime + import time +
  the security-master SHA-256 — and label the dates as unknown.
- An **export date is not a period end**. The 2026-09-26 ScanX/KITE snapshots
  have no underlying period date.
- A source-agreed historical snapshot must **not** overwrite a newer daily bar.
  `kite_reconcile` records `attested_stale_snapshot_not_applied` instead.

## 2. Where data lives

| Layer | Tables | Rules |
|---|---|---|
| Live | `prices_daily`, `price_meta`, `technicals_daily`, `fundamentals`, `universe_broad`, `stocks`, `delivery_daily`, `institutional`, `macro_flow`, `breadth_daily` | Promotion only via an explicit per-field rule with before/after evidence |
| Research snapshots | `scanx_fundamentals_snapshots`, `kite_market_snapshots` | Keep the raw row (`raw_json`) forever; withhold suspect values with a visible flag; **never** touch live tables |
| Attestation | `market_data_attestations` | The ledger of what a snapshot claimed, whether it was applied, and why not |
| Quality | `data_quality_log` | Note F-11: the script deletes it each run — only the latest survives |

## 3. The importer workflow (dry-run is the default)

```bash
source venv/bin/activate

# 1. PREVIEW — no --apply means nothing is written
python scanx_import.py csv --as-of 2026-09-26 --master data/incoming/nse_equity_master.csv
python kite_import.py  --as-of 2026-09-26 --master data/incoming/nse_equity_master.csv

# 2. INSPECT coverage and quality flags
python scanx_snapshot_report.py --db data/app.db
python kite_snapshot_report.py  --db data/app.db

# 3. PREVIEW the cross-source promotion
python kite_reconcile.py --db data/app.db

# 4. APPLY only after review — each creates a data/app.db.pre-*.bak backup
python scanx_import.py csv --as-of 2026-09-26 --master data/incoming/nse_equity_master.csv --apply
python kite_import.py  --as-of 2026-09-26 --master data/incoming/nse_equity_master.csv --apply
python kite_reconcile.py --db data/app.db --apply

# 5. VERIFY after applying
python data_quality.py
```

**Known gotcha:** `data/incoming/` does not exist in the repo. Both importers
default `--master data/incoming/nse_equity_master.csv` and fail with
`FileNotFoundError` out of the box. Create the folder and place the master
before running.

## 4. Promotion rules (do not generalise these without validation)

`kite_reconcile` is the reference implementation:
- `current_price` — **exact** match required (tolerance 0.0).
- `market_cap_cr`, `pe`, `debt_to_equity`, `dividend_yield`, `roe` — relative
  difference **≤ 1 %**.
- Disagreements are **logged and withheld**, never resolved by picking a source.
- Fields are accepted **individually**, never as a whole row or whole source.
- A confirmed current price is **not applied** when a newer `prices_daily` bar
  exists; the comparison and newer bar date are stored in
  `market_data_attestations` without rolling live prices backward.
- Symbol mapping is by normalised exact name / curated alias / exact symbol —
  **ambiguity means the row is left out**, never fuzzy-matched. Unmapped rows
  stay visible (134 of 500 KITE instruments remain unmapped).
- `kite_reconcile.SNAPSHOT_DATE` is **hardcoded to `2026-09-26`** and its
  `--as-of` defaults to it. Change the date deliberately, and note that with the
  laptop's `prices_daily` frozen at 2026-08-26 the `stale_price` guard would not
  fire — an `--apply` there would promote a Sep-26 snapshot over an Aug-26 base.

**Never** reuse the 1 % tolerance for a different field or source without
validating that tolerance for that field.

## 5. Adding a new source or migrating a call site

1. Check `data_sources/` first — there is an auto-discovered registry:
   `SourceAdapter` (name, datasets, `fetch`, `health`, `rate_limit_ok`),
   `BaseSourceAdapter`, `RateWindow`, `SourceRegistry.fetch(dataset, providers,
   accept=...)` with **explicit ordered** fallback and `ProviderFetchError`.
   Existing datasets: `prices.daily_history`, `fundamentals.tv_batch`,
   `universe.nse_constituents` (3 NSE adapters), `universe.chartink_symbols`.
2. Report health via `/api/sources`; a new adapter must provide health and rate
   limits, not just a fetch.
3. ~14 modules still call `yfinance` directly (ID52 open work). Migrate **one
   call site at a time**, with a before/after value comparison.
4. Preferred order: official exchange filings / exchange-published data →
   documented aggregator → crawler (only with permission and terms checked).
   Never bypass auth, rate limits, or anti-bot protection. Never add a paid
   dependency or expose credentials without explicit owner approval.

## 6. Failure modes proven in this repo

| Failure | Symptom | Guard |
|---|---|---|
| Missing period/publication date | A "historical" value with no provenance | Refuse replay eligibility; keep it research-only |
| All-zero sentinel columns | A metric reads 0 for every row | The importer withholds them structurally while keeping the raw JSON |
| Out-of-range values | Impossible PE / negative market cap | Quarantined with an `out_of_range:<col>` flag, not clipped |
| File mtime mistaken for publication time | Undated data treated as dated | Recorded as host metadata and flagged `publication_time_unknown` |
| Snapshot overwriting live data | Prices roll backward | `stale_price` guard + attestation record |
| Silent success | A bad import looks like a good one | Preview counts, coverage, and flags **before** `--apply`; never turn "missing" into a success-shaped default |

## 7. Checklist

- [ ] Decision stated: is this for display, research, live screening, or replay?
- [ ] Authority, terms, schema, coverage, date semantics, and failure modes documented.
- [ ] Preview run; row/duplicate/mapping/field coverage and quality flags reviewed.
- [ ] Raw values preserved; suspect values withheld with a visible reason.
- [ ] Per-field promotion rule written down and testable; tolerance validated.
- [ ] Backup taken; uniqueness/PK behaviour proven idempotent.
- [ ] Post-apply verification: counts, attestations, out-of-scope tables unchanged, service health.
- [ ] Tests added for malformed input, duplicates, ambiguous identifiers, disagreement, and the "unapproved data cannot affect live decisions" rule.
- [ ] Anything unverified is reported as unverified — never as a success.
