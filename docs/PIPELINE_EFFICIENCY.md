# PIPELINE EFFICIENCY — is the nightly chain efficient? (18 Oct 2026)

Scope: the daily signal chain as it actually runs on the live VM and on the
laptop copy (`technicals → scan → ML → PWin → patterns → templates → Top
Picks`), with measured timings on the synced 823,386-row database.

**Short answer: the order had two real defects (fixed today), and the chain is
~3× slower than it needs to be because every stage re-reads and re-computes the
same price-derived features. The single biggest win is a shared feature pass,
not more hardware.**

## 1. What was wrong (and is now fixed)

| # | Defect | Effect | Fix (applied) |
|---|---|---|---|
| 1 | **Scan ran BEFORE ML** in `daily_update.py` | `scan.py` reads `MAX(prediction_date)` from `ml_predictions`, so it silently used *yesterday's* ML scores while today's were computed minutes later | order is now `prices → technicals → breadth → ML → scan → PWin → Top Picks` |
| 2 | **Breadth was never computed nightly** | `breadth_daily` stayed empty; `breadth.breadth_ok()` only happened lazily inside swing, so every other consumer saw stale/absent breadth | new `breadth` step right after technicals (`breadth.compute(force=True)`) |
| 3 | **Fundamentals refreshed weekly but derived/provenance fields were not** | `eps_ttm`/`book_value`/`shares_outstanding` and the veto-only ownership fields could lag the refresh indefinitely | the Saturday fundamentals job now runs `fundamentals_derive` + `fundamentals_enrich` immediately after the refresh |
| 4 | **Fundamentals were in the score but not in the scan gate** | a name vetoed by `fund_veto` could still appear as a scan "pass", disagreeing with patterns/Top Picks/swing | `scan.py` now loads the veto once and excludes vetoed names from eligibility/pass (reason row + `fund veto:` flag written) |
| 5 | **Price ingest walked `stocks.active` only (825)** while the tradable universe is band ∪ core (865) | 40 band-only symbols were never fetched — the hidden half of the VM's 75.2% coverage number | ingest now walks `universe_helper.combined_universe`, with a punctuation-normalised retry (`BOSCH_HCIL` → `BOSCH-HCIL`) |
| 6 | **`price_meta` insert used positional columns** after the new `basis` column was added | any legacy price writer would fail with "table has 5 columns but 4 values" | named-column upsert |
| 7 | **A crash in institutional left an open write transaction** | the next writer (Top Picks) could not even write its gate audit row and hard-blocked itself ("cannot determine freshness") | institutional now always closes its connection (and tolerates NULL closes) |
| 8 | **Price-coverage gaps had no diagnosis** | "75.2%" hid which symbols were missing and why | new `coverage_report.py`: 24 no-price + 16 behind-max on the VM; 28 are SME/InvIT/REIT (should be excluded), 7 cash-equity ingest gaps, 2 alias, 2 other series, 1 unresolved (SSFLPP.E1) |

## 2. Measured cost of each stage (laptop, synced VM database, Sun 18 Oct)

| Stage | Time | Writes | Notes |
|---|---|---|---|
| technicals | **1.9 s** | 736 rows | per-symbol SQL loop (≤260 rows each) |
| ML predict | **0.4 s** | 727 rows | batch model |
| scan | **1.3 s** | 823 scans + reasons | per-symbol scoring + veto loop |
| PWin (meta-model) | **1.4 s** | 714 rows | second model scoring the same universe |
| **patterns** | **104.0 s** | 873 tags (840 symbols scanned, 554 hits, 263 veto-filtered) | **91% of the whole chain** |
| templates (DTW) | **13.6 s** | 72 scores | shape-matched symbols |
| institutional | ~2 s | 294 rows | accumulation proxy |
| Top Picks | 5.8 s | 50 picks (241 veto-skipped) | composite ranking |
| breadth | <1 s | 1 row | 400 symbols, EWMA |
| **Total** | **≈130 s** | | dominated by patterns |

## 3. Why it is still inefficient

1. **Seven passes over the same prices.** technicals, scan (via scoring), ML
   features, PWin (meta-model features), patterns (ATR/EMA/volume per symbol),
   templates (DTW on 600 series), institutional, breadth each query
   `prices_daily` themselves. That is roughly 4,000 per-symbol SQL round trips
   and 7 independent copies of the same indicators per night. A single
   vectorised feature pass (pandas pivot → indicator columns → `features_daily`
   table) would replace all of them and is the highest-leverage change.
2. **Two unrelated ML stacks score every symbol.** `ml_models.pkl` (727
   predictions) and `meta_model` (714 PWin scores) are different models with
   different feature sets, run back-to-back. Either unify them or derive PWin
   from the ML score so the funnel cannot disagree with itself.
3. **Full-universe detectors.** Patterns scans 840 symbols to save 873 tags;
   templates runs DTW on many series. Both should run on a *candidate* list
   (technical prefilter: above 200-DMA + volume dry-up + ATR contraction +
   liquidity), which is what the method already requires — expected patterns
   cost 104 s → ~20 s.
4. **No incrementality.** If prices did not change (holiday, re-run, weekend
   repair), every stage recomputes and overwrites identical rows. A price
   fingerprint (`MAX(date)` + row count + hash of the last day) would let the
   chain no-op in seconds, with `--force` for deliberate reruns.
5. **No lineage/dependency record.** If technicals change, the existing pattern
   tags are not invalidated. The freshness gate protects against stale *prices*
   but not against stale *derived* artifacts. A `pipeline_runs` table
   (run_at, price_fingerprint, stage, rows, version) would make recomputation
   decisions auditable.
6. **SQLite is single-writer.** Parallelising stages that write different
   tables still serialises on the write lock; parallelise the *read-only*
   feature computation into temp tables and keep one writer, or move to WAL
   mode with short transactions.
7. **Fundamentals cadence.** Weekly is right for reported data (they change
   quarterly), but the veto-only enrichment must never be treated as PIT data;
   dated sources (shareholding XBRL, announcements) are being ingested in
   Option B and *are* replay-safe.

## 4. Target architecture (proposed)

```
ingest prices + corporate actions + freshness gate
        │
        ▼
features_daily (ONE vectorised pass: OHLCV-derived indicators per symbol)
        │
        ├── market context: regime, breadth, sector RS   (one pass, cached)
        ├── model: ONE batch score (ML + PWin unified)
        ├── detectors: candidates → patterns / templates  (prefiltered)
        └── veto inputs: weekly fundamentals + dated announcements/pledge
        │
        ▼
ranking (Top Picks composite) → sizing → alerts/dashboard
```

Expected: nightly chain **≈130 s → <45 s**, patterns 104 s → ~20 s, and one
place to fix an indicator instead of seven.

## 5. What else can be done (prioritised)

| Priority | Change | Expected win | Effort |
|---|---|---|---|
| 1 | `features_daily` shared pass (vectorised indicators) | removes ~6 redundant price passes; simpler correctness | M |
| 2 | Candidate prefilter for patterns/templates | patterns −80% time | S |
| 3 | Unify ML/PWin into one scoring pass | −1 pass, removes score disagreements | M |
| 4 | Price fingerprint + no-op on unchanged bars (`--force` escape) | holiday/re-run runs in seconds | S |
| 5 | `pipeline_runs` lineage + derived-artifact versioning | prevents stale-derived signals | S |
| 6 | Batch-load `fund_veto` inputs once (instead of per symbol) | small, but patterns scanned 263 veto calls | S |
| 7 | WAL mode + short transactions for the nightly writer | fewer lock stalls | S |
| 8 | `coverage_report` into the nightly DQ summary | catches coverage regressions the freshness gate cannot see | S |

**"Insert funda as well if needed":** fundamentals already enter at three points
— score (ROCE/growth/valuation in `scoring`), veto (`fund_veto`, now also in
scan), and derived ratios (`eps_ttm`/`book_value`/shares). Weekly refresh plus
the new post-refresh derive/enrich step is the right cadence. The missing piece
is *dated* governance data (pledge/auditor/announcements, Option B), which can
be replayed safely — unlike the undated ScanX snapshot.
