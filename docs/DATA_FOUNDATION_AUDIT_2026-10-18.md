# DATA FOUNDATION AUDIT & ANALYST VERDICT — 18 Oct 2026

Owner: Ankit · System: NSE Intelligence Terminal (Stage-2/VCP swing, daily bars)
Audit scope: this laptop's database (`data/app.db`, 117 MB) + the code that reads it.
Reproduce: `python data_audit.py --json docs/data_audit_2026-10-18.json`

> **Read this first (updated 18 Oct, after probing the VM).** There are two
> databases. **The live VM (140.238.226.249) is current:** prices 823,386 rows /
> 843 symbols / last bar **2026-10-16**, 51 tables (31 active, 7 empty, 4 stale),
> 0 invalid OHLC, fundamentals 1,268 rows, 97 automated tests green, and the new
> hard freshness gate is live and passing. **The laptop copy is a stale snapshot**
> frozen at 2026-08-27 (52 days) — Sections 3 and 7 numbers describe that stale
> copy and are kept as the audit trail that motivated Option A. The structural
> findings (adjusted-vs-raw price basis, no corporate-action book, PIT-invalid
> snapshots, empty features, no freshness gate before today) applied to *both*.
> The laptop's impossible artifacts have been quarantined (3,422 rows).

---

## 1. Verdict in one page

1. **The system's edge is not blocked by missing data. It is blocked by data
   integrity and freshness.** A 1.13-million-row price history, a functioning
   strategy spec, a trained meta-model (AUC 0.68) and a 14-book league all exist —
   and then the price feed stopped on 27 Aug. Anything the system computed after
   that date from stale bars (patterns on 7 Oct, templates on 7 Oct, institutional
   on 7 Oct) is fiction and must be treated as such.
2. **40% of the database is empty shells** (17 of the 42 tables that existed before
   today; 18 of 44 after the two new Fyers tables) while another 31% is
   stale. The bottleneck is maintenance and point-in-time discipline, not
   acquisition. Adding a sixth data vendor before fixing the first one repeats a
   mistake the system already made with the ScanX/KITE snapshots.
3. **Fundamentals are a veto and sizing layer for a 5–30 day swing system, not an
   alpha source.** The repository has never recorded the price-only vs
   fundamentals lift it claims (`model_runs.price_only_auc` is NULL), yet DR-01
   (dated multi-year fundamentals) is planned as the single biggest investment.
   Measure before you pay.
4. **Fyers can fix the spine and only the spine.** It is a free, authenticated,
   exchange-native OHLCV/quote feed — exactly what is stale today — with no
   fundamentals, no delivery %, no FII/DII and no corporate-action calendar.
   The integration is built, reviewed and hardened (40 offline tests); the daily login is the
   only recurring chore (Section 4.2).
5. **Recommended order: fix the spine (Option A) → elimination engine (Option B) →
   dated fundamentals (Option C) only if A is green and a live sample exists.**
   Skip ESG, analyst targets, long-horizon DCF inputs, intraday data and news
   sentiment (Section 2.5) — for *this* system they are non-important.

---

## 2. The analyst's debate: what data actually earns money

### 2.1 The central argument

A trading system earns money from **the decision it changes**, not from the data
it stores. Every dataset must answer: *which trade does this make me take, avoid,
or size differently — and how do I know?*

- A 10-year ROE history does not change a 15-day VCP entry. It changes **whether
  you are allowed to own the stock at all** (veto) and **how big the position is**
  (sizing). That is real value, but it is second-order value.
- Daily OHLCV, corporate-action-clean, does change every single decision. It is
  first-order. It is also the dataset that is broken today.
- Point-in-time (PIT) index/constituent data does not produce signals, but it
  decides whether your backtest is a lie. In this repo the trader league already
  showed what honest simulation looks like: **178 home trades, −6.2% vs Nifty
  +5.5%, profit factor 0.93, worst-case-fill PF 0.72, 0 live paper trades → NOT
  READY.** More fundamental data would not have changed that verdict; better data
  integrity and a live sample would.
- Data that cannot be dated cannot be backtested. The ScanX snapshot has 750
  symbols × 72 rich fields (ROE 3y/10y averages, cash-flow lines, balance-sheet
  lines, industry comparables, shareholding changes) — and **zero**
  `financial_period_end` and `published_at` values. It is a research photograph,
  not history. Using it in a backtest is using tomorrow's newspaper.

### 2.2 Essentiality scorecard (for this system: daily bars, 5–30 day holds)

| # | Data | Essentiality | Why (the actual mechanism) | What it changes | Current state |
|---|---|---|---|---|---|
| 1 | Daily OHLCV, 5y+, split/dividend-clean | **ESSENTIAL** | Every signal, stop, target, ATR, regime, breadth, RS is a function of it | All entries/exits | 1.13M rows, clean, **52 days stale** |
| 2 | Liquidity / turnover (₹ value traded, 20d median) | **ESSENTIAL** | Small/mid-cap backtests assume fills that do not exist; impact cost is the silent killer | Sizing, universe filter, slippage model | Volume stored, never converted to ₹ turnover |
| 3 | Market regime series (NIFTY50 / NIFTY500 daily) | **ESSENTIAL** | Gate for new entries; benchmark for alpha and RS | Entry gate, performance truth | **No index series in DB** (regime falls back to Yahoo live) |
| 4 | Breadth (% above 50/200 DMA, adv/dec) | **ESSENTIAL** | Distinguishes a stock breakout from a tape-wide bounce | Entry gate, risk-on/off | Table exists, **0 rows** |
| 5 | Sector relative strength | **NECESSARY** | Leadership persistence is the documented edge of the method | Sector gate (top-3) | Computable from prices; not stored |
| 6 | Corporate actions (splits, bonuses, dividends) | **NECESSARY** | Without it, adjusted vs raw price series create fake 10–50% gaps (Fyers seam check exists precisely because of this) | Data correctness, pattern validity | **Absent**; yfinance adjustment is implicit and undocumented |
| 7 | Fundamental veto set: debt/equity, interest cover, promoter holding + pledge, CFO/PAT, auditor going-concern | **NECESSARY (veto only)** | Removes the stocks that can go to zero while looking like a VCP; tail-risk control | Universe exclusion, sizing | 3 of 6 fields exist; promoter/pledge **0% filled** |
| 8 | Point-in-time constituents + delisting data | **NECESSARY** | Survivorship bias inflates every backtest; league verdict depends on it | Honesty of validation | Not stored |
| 9 | Trading calendar / holidays | **NECESSARY** | Freshness checks, "stale 5 days" logic is wrong across holiday clusters | Data-quality gates | Derived implicitly from bars |
| 10 | Delivery % (NSE bhavcopy) | NICE | Institutional conviction proxy; already designed into Top Picks (15% weight) | Ranking, conviction | Table empty, feature dark |
| 11 | FII/DII net flows (NSE) | NICE | Macro context, not stock-level timing | Regime commentary | Table empty |
| 12 | Earnings / board-meeting calendar | NICE | Avoid entering 2 days before results; gap risk | Entry timing | 66 rows, 1996–2026, incomplete |
| 13 | Analyst estimates / targets | **NON-IMPORTANT** | Consensus is lagging and crowded; no defined use in the method | — | Absent (good) |
| 14 | News sentiment | **NON-IMPORTANT at daily horizon** | 8 headlines stored; feature is median-filled to a constant, so it contributes nothing while costing a pipeline | — | Dark, 9 rows |
| 15 | ESG, mutual-fund holdings by stock, macro forecasts | **NON-IMPORTANT** | No mechanism to change a 15-day trade | — | Absent (good) |
| 16 | Intraday ticks / order-book depth | **NON-IMPORTANT** (identity locked to daily bars on 2026-09-15; entry-timing layer deleted by design) | Re-introduces the scope that was deliberately removed | — | Absent (good) |
| 17 | Option chain / OI / IV | LATER (not now) | Positioning and event-vol signals, but a different strategy identity and a real maintenance load | — | Fyers can supply; not used |

### 2.3 "Necessary but not sufficient"

- **Fundamentals without price integrity is astrology with spreadsheets.** A
  beautiful 10-year ROE series attached to a price series that is stale by 52 days
  and adjusted by an unknown factor cannot produce a valid signal.
- **A veto is not a ranking.** Bad fundamentals remove names; good fundamentals do
  not create entries. The repo already half-knows this: `fund_veto.py` uses three
  thresholds (D/E > 3, ROCE < 8, promoter < 20) and nothing else consumes
  fundamentals at decision time.
- **PIT is a property of the dataset, not a checkbox.** A row is eligible for
  backtests only when both `financial_period_end` and first public availability
  are known (the repo's own DR-01 acceptance rule). ScanX fails this by design.

### 2.4 The overrated list

| Claim | Reality check |
|---|---|
| "We need 10 years of fundamentals to be serious" | 20 methods are waiting on DR-01, but the system cannot currently prove fundamentals add value (`model_runs.price_only_auc` is NULL; the one recorded run has 21 features, AUC 0.6785, base win 35.5%, top-10 60.5% — no price-only comparison). Pay for the experiment only after measuring the cheap version. |
| "More sources = more robust" | 5 price providers and 4 snapshot sources already exist. The result is 3 conflicting price fields per symbol (below) and no single source of truth. |
| "News sentiment is a differentiator" | 8 headlines, no backtest, feature imputed to a constant. It is currently decorative. |
| "Delivery % will unlock edge" | Plausible, cheap, already designed into Top Picks — but the table has 0 rows, so the 15% weight has been dead weight. Fix or remove the weight; do not add a sixth flow source. |
| "Fyers solves the data problem" | It solves daily prices/quotes/index/symbol master. It does not solve fundamentals, delivery %, FII/DII, corporate actions, or the daily token chore. |

### 2.5 The non-important list (explicitly refuse to collect)

For a **daily-bar swing system on NSE small/mid-caps**, these are non-important.
They cost maintenance (daily logins, mapping, drift, storage) and change no trade:

1. Intraday tick/minute data (identity was deliberately locked to daily bars;
   the entry-timing layer was deleted on 2026-09-15).
2. Full market-depth/order-book history (only useful for execution impact; we buy
   ~₹5,000 positions — impact is noise).
3. ESG scores, controversy scores.
4. Mutual-fund / ETF holdings by stock.
5. Analyst consensus, price targets, rating changes.
6. Macro forecasts (CPI/GDP projections); hardcoded AAA yield 7.5% is adequate for
   the one place it is used.
7. 10-year fundamentals for stocks outside the tradeable universe.
8. Company news sentiment at daily frequency (see above).
9. Options Greeks history (until a second strategy identity is approved).
10. Any dataset that cannot be dated and therefore cannot be backtested — the
    ScanX/KITE snapshots are the cautionary example, not the model.

### 2.6 SWOT — the data foundation as it stands

| | |
|---|---|
| **Strengths** | 1.13M rows of OHLCV with **0 invalid OHLC rows**; 925 symbols with ≥500 bars; per-field provenance plumbing (`field_sources`, `field_updated_at`) and a merge helper that never nulls an existing value; auto-discovered source adapters with health/fallback; a real data-quality monitor; a league simulator that exposed the truth instead of hiding it. |
| **Weaknesses** | 52-day price freeze; 17 empty tables; 15/33 fundamentals columns empty (45%); 3 conflicting prices per symbol (379/501 differ >1% vs universe, 407/501 vs prices); no corporate-action store; no PIT fundamentals; no index series in DB; no freshness gate on derived artifacts; laptop vs VM drift; secrets/token chores are manual. |
| **Opportunities** | Fyers authenticated feed (prices, index, quotes, depth, market status, symbol master/ISIN); algebraic derivation of EPS/book value/shares from data already owned (done today, 482/499/503 rows); index history unlocks beta, RS rating, breadth, NIFTY500 benchmark (DR-20/DR-22); a freshness gate can stop the "signals on stale bars" failure permanently. |
| **Threats** | Silent staleness (already happened: 7 Oct artifacts on 27 Aug bars); adjusted-vs-raw price seams corrupting patterns after any dividend/split; PIT violations making backtests look better than reality; vendor/token dependency (Fyers daily login, entitlement changes); survivorship bias in the 1,522-row universe; overfitting once new features arrive. |

### 2.7 Four propositions, challenged

**P1 — "Fundamentals are essential."**
*Antithesis:* for 5–30 day holds, fundamentals are a veto and a sizing input. The
system's own evidence is that the 20-method fundamental layer is *unmeasured*: the
model ledger has no price-only comparison. The correct next step is a 2-hour
experiment (train the meta-model with and without the 6 fundamental features on the
existing 503-row snapshot, record `price_only_auc` and `delta_auc`), not a 6-week
filing ingestion project. *Synthesis:* fund the experiment first; if delta is real,
Option B/C earn their cost. If delta is noise, stop at the veto layer.

**P2 — "More data makes better decisions."**
*Antithesis:* 17 empty tables and 13 stale tables prove acquisition is not the
bottleneck. The marginal value of a sixth source is negative until the first five
agree. *Synthesis:* one source of truth per dataset, cross-attested, with a
freshness contract — then add sources.

**P3 — "Sentiment/news adds edge."**
*Antithesis:* no mechanism, no backtest, constant-imputed feature, 8 stored
headlines. It is a cost centre. *Synthesis:* delete it from the model (it is
neutral today) or replace it with an event flag ("results in 2 days") that has a
clear mechanism.

**P4 — "The system is close; just needs more inputs."**
*Antithesis:* the honest league replay says otherwise: **−6.2% vs +5.5% Nifty,
PF 0.93, 0 live paper trades.** The bottleneck is validation and execution
realism, not inputs. *Synthesis:* fix the spine, run the live sample, and let the
league decide what to build next. Data builds should be justified by a measured
failure, not by a plausible story.

---

## 3. Existing data: what is actually there

### 3.1 Table inventory (44 tables; 42 before today's Fyers tables)

| Status | Count | Meaning |
|---|---|---|
| ACTIVE | 6 | populated and fresh-ish (`fundamentals`, `pipeline`, `scanx_fundamentals_snapshots`, `stocks`, `trend_candidates`, `fyers_symbol_master`) |
| STALE | 13 | populated but past its freshness threshold (`prices_daily` 52d, `universe_broad` 53d, `scan_results` 53d, `ml_predictions` 53d, `pattern_tags` 11d, …) |
| THIN | 8 | <100 rows (`sentiment_results` 9, `swing_signals` 9, `corp_calendar` 66, `fyers_sync_log` 1, …) |
| EMPTY | 18 | **zero rows** — see 3.7 (`fyers_quotes` is empty until the first authenticated sync) |

Usefulness proxy — how many modules read each table (from `data_audit.py`):
`prices_daily` 62 · `stocks` 40 · `fundamentals` 31 · `universe_broad` 17 ·
`swing_signals` 17 · `scan_results` 9 · `scan_reasons` 3 · `delivery_daily` 3 ·
`top_picks` 2 · `pwin_daily` 2 · `pattern_grades` 2 · `breadth_daily` 1 ·
`macro_flow` 1 · `value_radar` 1 · `positional_picks` 1 · `strategy_runs` 3.
**21 module references point at tables that are empty in this DB** — features are
coded and wired, but dark.

### 3.1b Live VM vs this laptop (18 Oct)
| | VM (live) | Laptop (audited above) |
|---|---|---|
| Last price bar | **2026-10-16** (2 days = weekend) | 2026-08-27 (52 days) |
| Price rows / symbols | 823,386 / 843 | 1,131,371 / 1,086 |
| History buckets (≥500 / 210–499 / 60–209 / <60) | 659 / 80 / 38 / 54 | 925 / 89 / 37 / 28 |
| Last-60-session bar coverage | **75.2%** (watch this) | 97.0% (before freeze) |
| Invalid OHLC rows | 0 | 0 |
| Tables (active / empty / stale / thin) | 51 (31 / 7 / 4 / 9) | 51 (after today; 17 empty before) |
| Fundamentals rows / dead columns | 1,268 / 4 (promoter, pledge, FII, net-debt) | 503 / 10 |
| Pattern tags rows | 149,923 (dated 18 Oct) | 0 (quarantined) |
| Freshness gate | **live, passes** (0 missing sessions) | correctly **blocks** (36 missing) |

The VM's 75.2% recent-bar coverage and 54 symbols with <60 bars are the next
data-coverage problem to fix (likely delisted/renamed tickers plus stale
universe rows), not a freshness problem.

### 3.2 Prices — the spine

| Metric | Value |
|---|---|
| Rows | 1,131,371 |
| Symbols | 1,086 |
| Date range | 2021-08-17 → **2026-08-27** |
| Freshness | **52 days stale**; ~36 weekdays (~34 exchange sessions net of holidays) missing |
| History buckets | ≥500 bars: 925 · 210–499: 89 · 60–209: 37 · <60: 28 |
| Usable for 200-DMA (≥210 bars) | **1,014 / 1,086 = 93.4%** |
| Last-60-session bar coverage (before freeze) | 97.0% (1,079 symbols printed on the last day) |
| Zero-volume rows | 9,666 (0.85%) — normal for illiquid names, must be excluded from liquidity math |
| Invalid OHLC rows | **0** |

Verdict: **raw quality is good; freshness is catastrophic.** Also note the hidden
gap: yfinance `auto_adjust=True` means stored history is split/dividend-adjusted,
while Fyers (and the exchange) are raw. Mixing them creates fake gaps — this is
why the new ingestion refuses to append across a >2% seam (Section 4.2).

### 3.3 Fundamentals — the veto layer

503 rows × 33 columns. **15 columns are 100% empty (45.5%)** before today's
derivation: `promoter_holding`, `pledge_pct`, `fii_holding`, `beta_1y`, `eps_fy`,
`book_value`, `ev_ebitda`, `fcf_fy`, `net_debt_fy`, `roic`, plus 5 provenance
columns never backfilled on legacy rows.

Fill rates of the columns that exist: price/mcap/pb/net-margin 503 · sales growth
3y 502 · sector 500 · ROE 499 · D/E 495 · CFO sign 493 · PE 482 · profit growth
445 · interest cover 442 · operating margin 442 · dividend yield 421 · ROCE 439.
**Ownership data (promoter/pledge/FII) is 0% — the veto gate is running blind on
exactly the fields that predict governance blow-ups.**

Anomalies found: 11 rows with P/E > 200, 4 with negative book value, 2 with D/E >
10, 0 negative P/E (possible only if loss-making names were dropped), 0 bad
prices. These are plausible but unaudited; they need a defined outlier policy.

**Cross-table inconsistency (important):** three price fields disagree —

| Comparison | Symbols >1% apart |
|---|---|
| `fundamentals.current_price` vs `universe_broad.close` | **379 / 501 (75.7%)** |
| `fundamentals.current_price` vs last `prices_daily.close` | **407 / 501 (81.2%)** |
| `universe_broad.close` vs last `prices_daily.close` | **296 / 501 (59.1%)** |
| `fundamentals.market_cap_cr` vs `universe_broad.mcap_cr` | median 2.3% diff; **18.4% differ >5%** |

They are snapshots from different days (16–27 Aug) and sources, so small gaps are
expected — but three "current prices" is exactly how a system ends up buying at a
price it never saw. **Rule needed: `prices_daily` is the only price truth; every
other price is metadata.**

**Derivation executed today** (`fundamentals_derive.py`, provenance-tagged with
`field_sources="derived:price_pe_pb"` and flags `derived_not_reported`,
`derived_from_valuation_snapshot_without_filing_date`):

| Derived field | Formula | Rows filled |
|---|---|---|
| `eps_ttm` | price ÷ trailing P/E | 482 / 503 |
| `book_value` | price ÷ P/B | 499 / 503 |
| `shares_outstanding` | market cap (cr) × 1e7 ÷ price | 503 / 503 |

That brings the table to 35 columns (33 + 2 new), with **10 still 100% empty** —
the 3 ownership fields, `beta_1y`, `eps_fy`, `ev_ebitda`, `fcf_fy`, `net_debt_fy`,
`roic` and `source_metadata` — and unlocks DR-04 (shares), DR-06/DR-07 partials
without any purchase. `eps_fy` (reported fiscal year) was deliberately **not**
touched.

### 3.4 Universe and symbol master

- `universe_broad`: 1,522 rows, all updated 2026-08-26; 855 in the 1,000–8,000 cr
  band; 1,084 have price history; PE present for 1,363; **`relvol` 0% filled**.
- `stocks`: 500 active Nifty-500 core, sector 100% filled.
- Combined tradeable universe: 1,349 symbols.
- New: Fyers NSE cash symbol master **10,116 rows** imported 2026-10-18
  (broker file dated 2026-10-16), giving ISIN, lot size, tick size and series.

### 3.5 Snapshots (research-only)

- ScanX: 750 rows × 72 columns, heavily populated (multi-year ROE/ROA/OPM averages,
  quarterly growth, cash-flow and balance-sheet lines, industry comparables,
  promoter/FII/DII holdings and changes).
- **`financial_period_end`: 0 rows. `published_at`: 0 rows.** `as_of_date` is the
  single export date 2026-09-26.
- KITE table absent in this DB.
- Verdict: useful as a **cross-sectional snapshot today**, invalid for backtests
  and invalid as "history". The repo already says this; it must stay quarantined.

### 3.6 Signals and research outputs

| Table | Rows | Dates | Assessment |
|---|---|---|---|
| `pattern_tags` | 2,542 | 2 dates (2026-09-09, 2026-10-07) | **7 Oct run used 27 Aug bars → invalid** |
| `template_scores` | 120 | 2026-10-07 | same staleness problem |
| `institutional` | 290 | 2026-10-07 | same staleness problem |
| `scan_results` / `scan_reasons` | 2,000 / 14,000 | 4 dates in Aug | consistent with price freeze |
| `ml_predictions` | 1,456 | 4 dates in Aug | consistent with price freeze |
| `swing_signals` | 9 | last 2026-06-09 | dead since June |
| `top_picks`, `pwin_daily`, `pattern_grades`, `delivery_daily`, `breadth_daily`, `macro_flow`, `value_radar`, `positional_picks`, league tables | **0** | — | features exist, data does not |

`model_runs` (1 row): AUC 0.6785, base win 35.45%, top-10 win 60.5%, 21 features,
**`price_only_auc` NULL** → the fundamental-feature lift claim is unverified.

### 3.7 Verdict per dataset: keep / revise / remove

**KEEP (core, repair freshness):**
`prices_daily`, `price_meta`, `stocks`, `universe_broad`, `settings`, `pipeline`,
`scan_results`/`scan_reasons` (recompute), `technicals_daily` (recompute — only
2 dates), `pattern_tags`/`template_scores` (discard 7 Oct rows, recompute after
backfill).

**REVISE (schema or content):**
- `fundamentals`: fill ownership fields or stop advertising the veto (3 of 6 veto
  inputs are empty); backfill provenance on legacy rows; define an outlier policy
  (P/E>200, PB<0, D/E>10).
- `universe_broad.relvol`: 0% filled → either compute from `prices_daily` or drop.
- `swing_signals`: only 9 rows and stale — the swing desk has effectively not run
  since June.
- `sentiment_*`: 8–9 rows, constant-imputed feature → either delete from the model
  or rebuild with a dated source; do not keep a decorative feature.
- `corp_calendar`: 66 rows spanning 1996–2026 (nonsense range) → rebuild from a
  dated source or drop.
- `trend_candidates`: 467 rows, one date; `research_cache`: 54 rows — keep, but
  document that they are single-run caches.

**REMOVE (data/hygiene, not schema):**
- 326 MB of `data/app.db.pre-*` backups (26 Sep) — verify VM copy, then archive.
- 10 empty `nse_cache_over_*` directories at repo root (0 files).
- The 7 Oct pattern/template/institutional rows computed on stale bars (mark or
  delete, do not silently keep them as history).
- Empty-table features that the owner does not intend to fund (e.g. `value_radar`,
  `positional_picks`) — keep the tables (schema is cheap, `CREATE IF NOT EXISTS`)
  but stop advertising them as live features until they have data.

Do **not** drop tables or columns in production; the repo rule is additive schema.
"Remove" above means remove *data claims*, not schema.

### 3.8 The staleness event (why 7 Oct artifacts are invalid)

- Price maximum: **2026-08-27**.
- `pattern_tags`: a run dated **2026-10-07** (1,388 rows).
- `template_scores`: 2026-10-07; `institutional`: 2026-10-07; `settings.pattern_gate`
  dated 2026-10-07 with an empty `{}` gate.

A pattern scanner with a staleness guard (the repo has one in `swing_live.py`)
should have refused to emit these. This is the single most dangerous failure mode
in the system: **derived artifacts newer than the data they were derived from.**
Foolproofing item G6 (Section 5) is the direct fix.

---

## 4. New data: calculable, derivable, or must-buy

### 4.1 Derivation matrix

| Required item (DATA_REQUESTS) | Derivable from what we own today? | From Fyers? | Needs new source | Status after today |
|---|---|---|---|---|
| Daily OHLCV | already owned (stale) | **yes** | — | integration built, awaiting daily login |
| NIFTY500 / NIFTY50 index daily (DR-20) | no | **yes** (`NSE:NIFTY50-INDEX`, `NSE:NIFTY500-INDEX`) | — | one `history` command after token |
| Beta 1y | no (no index) | **yes** (stock ÷ index) | — | computable day 1 |
| RS rating / sponsorship (DR-22) | needs benchmark index | **yes** | — | computable |
| Breadth daily | needs full universe bars | **yes** (full universe sync) | — | computable |
| Shares outstanding (DR-04) | **yes — done** (mcap ÷ price) | — | — | 503 rows filled |
| EPS TTM (feeds DR-07) | **yes — done** (price ÷ P/E) | — | — | 482 rows filled |
| Book value | **yes — done** (price ÷ P/B) | — | — | 499 rows filled |
| P/S TTM (DR-06) | no (no revenue level; only growth %) | no | filings/vendor | blocked |
| EV/EBITDA | no (no debt/cash levels) | no | filings/vendor | blocked |
| ROIC | no (needs NOPAT + invested capital) | no | filings | blocked |
| FCF / net debt levels | no | no | filings | blocked |
| Dividend history (DR-05) | partial (current yield only) | no | filings/exchange feed | blocked |
| Promoter holding + pledge (DR-16) | no | no | filings/ScanX (undated) | blocked |
| FII holding | no | no | filings/ScanX (undated) | blocked |
| Delivery % / FII-DII flows | no | **no** | NSE bhavcopy | blocked |
| Quarterly fundamentals (DR-21) | no | no | filings | blocked |
| AAA bond yield (DR-03) | no | no | FBIL/RBI | blocked |
| RBI repo (DR-23) | no | no | RB I | blocked |
| Nifty P/E live (DR-17) | no | partial (index level, not P/E) | NSE | blocked |
| Corporate actions | no | **no** (Fyers gives raw prices only) | exchange/filings | blocked |
| Earnings calendar | partial (`corp_calendar` 66 rows) | no | NSE announcements | partial |
| Liquidity/turnover | **yes** (volume × close today) | yes (better) | — | computable now |

**Bottom line:** today's system can produce **~8 of the ~23 open data requests**
without buying anything (price spine, index, beta, RS, breadth, shares, EPS TTM,
book value, turnover). The other ~15 require filing/market-announcement ingestion
and are genuinely new work. Fyers supplies none of them.

Across the wider "essential + necessary" list in Section 2.2, the split is roughly:
**price/market/technical layer ≈ 100% solvable with owned data + Fyers;
fundamental-veto layer ≈ 40% owned, 60% requires filings; flow layer ≈ 0% owned,
requires NSE.**

### 4.2 What Fyers changed today (built, tested, not yet authenticated)

| Item | Status |
|---|---|
| Client (`fyers_client.py`) — OAuth URL, code exchange, token store, history/quotes/depth/screeners, symbol mapping, rate limiting, retries | ✅ built |
| Ingestion (`ingest_fyers.py`) — symbol master, append/rebuild history into `prices_daily`, quote snapshots, verify, sync log | ✅ built |
| Single guarded writer (no adapter path into `prices_daily`) | ✅ hardened after review |
| Daily pipeline step before the generic price ingest | ✅ built |
| Symbol master imported from the live broker file | ✅ **10,116 rows, broker-dated 2026-10-16** |
| Universe → broker ticker resolution | ✅ **1,347 / 1,349 resolved** (1,293 exact, 54 normalized via `_`→`-` and NSE series suffixes `-SM/-BE/-RR/-IV`); only `HEG` (renamed to `HEGAM`) and `SSFLPP.E1` unresolved |
| Offline test suite | ✅ **40 tests pass** |
| Live price download | ❌ blocked on the one-time broker login (owner action) |

Safety properties that matter more than the happy path:
- **One guarded writer.** Only `ingest_fyers.py` writes broker bars. A
  `data_sources/adapters/fyers.py` provider was built first and then **removed**:
  it would have written raw bars through the generic `ingest_prices` path, which
  has no seam/validation gate. Two writers into one price series is how silent
  corruption happens; one is the fix.
- **Append-only by default.** Existing history is never rewritten; `--mode rebuild`
  requires an explicit flag, writes a CSV backup first, keeps rows outside the
  fetched window, and **refuses a shrunken fetch** (<60% of stored bars in that
  window, status `rebuild_shrunk`).
- **Seam detection.** Every sync re-fetches a 10-day overlap, measures
  `broker_close / stored_close`, and **refuses to append** if the ratio deviates
  >2% (a split/dividend happened between the adjusted store and the raw broker
  feed). No shared dates at all is also a refusal (`no_overlap`).
- **Post-seam corporate action.** A split/bonus after the last stored bar is
  invisible to the overlap ratio; the guard compares the *last stored close* to
  the *first new broker close* and blocks a >15% gap (`seam_gap_suspect`). Small
  dividend adjustments remain undetectable without a corporate-action calendar —
  the honest reason to do a full raw rebuild rather than append forever.
- **Bar validation.** Positive OHLC, high ≥ low, close inside the day's range,
  |move| ≤ 60% vs the last accepted close (seeded from the stored series so even
  the first appended bar is checked), no future dates, today's bar excluded
  until after the close (decided once per batch).
- **Price-basis provenance.** `price_meta.basis` records `fyers_raw`,
  `mixed_adjusted_then_raw`, or NULL (legacy adjusted) per symbol, so nobody has
  to guess which series a chart or backtest used.
- **Provenance.** `fyers_sync_log` records batch operations and anomalies; quote
  raw JSON is kept; timestamps are second-precision.
- **No order endpoint exists in the codebase.** The app is non-trading; this is a
  data client only.
- Rate limits: client-side 8 req/s / 180 req/min (broker allows 10 / 200 / 100k/day).
- Token: stored in `data/fyers_token.json` (gitignored), expires ~06:00 IST, so
  **it must be renewed once per trading day** (one command + browser login).

### 4.3 What remains genuinely unavailable (and should stay unavailable until chosen)

- **Dated fundamentals** — requires NSE/BSE filing ingestion (DR-01/DR-21). This is
  the only path to honest fundamental history. ScanX cannot substitute.
- **Delivery %, FII/DII** — NSE bhavcopy/API; datacenter IPs are often blocked
  (VM already knows this); manual mode exists for FII/DII.
- **Corporate-action calendar** — exchange announcements; required once the price
  history is rebuilt raw, otherwise the seam problem simply moves.
- **PIT constituents / delistings** — NSE index archives (DR-20); mandatory before
  any backtest claim is trusted.

---

## 5. Foolproofing: eight gates, current state, fix

| Gate | Purpose | Current state | Fix |
|---|---|---|---|
| G1 Ingestion validation | no bad bar enters | partial (`data_quality.py` checks; new Fyers bar rules) | make validation part of every writer, not a nightly report |
| G2 Adjustment/seam integrity | no fake gaps | **absent** before today | Fyers seam + first-bar gap checks, single guarded writer, `price_meta.basis`, **corporate_actions book + module deployed** ✅ (book populating from free yfinance/CSV); explicit adjustment policy still a decision |
| G3 Cross-source attestation | prove a bar outside the store | partial (KITE/ScanX field promotion pattern) | `ingest_fyers.py verify` ✅; record verdicts in a table |
| G4 Point-in-time discipline | no future data in backtests | documented policy, no enforcement | reject undated rows at import (ScanX already quarantine-only); add `published_at` requirement to fundamentals history |
| G5 Field provenance | know who said what | `fundamentals_store` supports it; legacy rows empty | backfill provenance; keep `field_sources` for every new writer (derivation does ✅) |
| G6 Freshness gate | **no derived artifact newer than its input** | **LIVE since 18 Oct**: `freshness_gate.py` + `signal_guard.py` hard-block 8 writers (patterns, templates, top_picks, swing, scan, ML, PWin, institutional); verified blocking on the stale laptop and passing on the fresh VM; decision logged in `freshness_gate_log` |  |
| G7 Monitoring + audit | detect drift weekly | `data_quality.py` (6 checks, Telegram) + new `data_audit.py` | run both daily/weekly; audit report to Telegram; add table-count/column-fill trend |
| G8 Ops/secrets | token and keys don't leak or silently expire | token file gitignored; expiry known | pre-market check: token valid? warn at 15:00 if not; never print secrets in logs |

A useful mental model: **data is a contract** — units (₹ vs crore), identifier
(ISIN as truth, not name), time (period-end + publication), tolerance (what
disagreement is acceptable), and lineage (who wrote it). The repo already has the
lineage plumbing; G1/G4/G6 are the missing enforcement.

---

## 6. Options to choose from

### 6.1 The menu (pick any combination; A is the prerequisite for the rest)

| Option | What it is | Data/source | Effort | What it unlocks | Risk | Verdict |
|---|---|---|---|---|---|---|
| **A — Fix the spine** | Fyers daily bars + index; rebuild price history raw (with backup + corporate actions); one price truth; freshness gate G6; repair stale pipeline; delete invalid 7 Oct artifacts | Fyers (free) + owned data | 2–4 days + one 10-min login | Correct signals; beta/RS/breadth; honest backtests; ends silent staleness | rebuild changes adjusted→raw prices, so downstream must be re-run | **DO FIRST** |
| **B — Elimination engine** | Dated/veto fundamentals: promoter holding + pledge, auditor/going-concern flags, debt, CFO/PAT, pledging events; wire into `fund_veto` and sizing | filings + ScanX (for cross-check only) | 1–2 weeks | Fewer blow-ups; DR-16; real quality filter for 14 books | without dates it repeats the PIT mistake; needs filing parser | **NEXT** |
| **C — Dated fundamentals (DR-01)** | Annual+quarterly statements with period-end and first-public timestamp; 5y history; restatement handling | NSE/BSE filings | 3–6 weeks | ~20 fundamental methods; honest multi-year backtests | biggest effort; value unproven (see P1) | after A is green; run the 2-hour lift test first |
| **D — Flow layer** | Delivery %, advance/decline, FII/DII, block/bulk deals | NSE bhavcopy (IP blocks) | 3–5 days | Delivery conviction (already in Top Picks weight), regime context | NSE blocking; low measured edge | optional, low priority; fix the dead 15% weight first |
| **E — Derivatives/positioning** | Index option chain, OI, IV, PCR | Fyers (after token) | 1–2 weeks | Positioning regime, event-vol filter | different strategy identity; scope creep | defer until live sample exists |

**Recommendation: A now. B next. C only after A is green *and* the fundamentals
lift experiment is positive. D opportunistically (delivery only, or delete its
weight). E defer.**

### 6.2 What I would refuse to build (for now)

1. A 10-year fundamental history before the price spine is clean and raw.
2. ESG, analyst estimates, mutual-fund holdings, macro forecasts — no mechanism.
3. Intraday/tick infrastructure — the system's identity was deliberately locked to
   daily bars; re-opening it would rebuild everything for an unproven edge.
4. A sixth free price provider instead of cross-attesting the existing five.
5. A "sentiment score" rebuild without a dated source and a measured mechanism.

### 6.3 Decisions I need from you (reply with the numbers/letters)

1. **Options to fund, and in what order** (e.g. "A now, B next; D skip; C later").
2. **Price basis for the rebuild:** (a) rebuild all history from Fyers **raw** and
   store corporate actions (cleanest, changes backtest inputs), or (b) keep the
   current adjusted yfinance history and only append Fyers bars when the seam
   factor is ≈1 (safest, but leaves the adjustment documentation unknowable)?
3. **Freshness gate G6:** should stale data **hard-block** all signal writers
   (recommended) or only warn?
4. **Fyers token chore:** accept a once-per-day login (simplest), or invest in
   refresh-token automation (longer gaps, more moving parts)?
5. **Derived fundamentals:** I already applied the three algebraic fields (503
   rows, provenance-tagged). Keep, or revert to empty?
6. **Run on VM first?** Should I apply the same audit + Fyers setup on the VM
   (the live machine) before touching this laptop DB further?
7. **Confirm the secret:** the screenshot can be read as `HDITOO853C` (letter O) or
   `HDITO0853C` (zero). I used the first. If the token exchange fails with an
   app-hash error, this is the first thing to check.

---

## 6.4 Option A delivery status (18 Oct, deployed to VM)

| A item | Status |
|---|---|
| Hard freshness gate + writer wiring | **LIVE on VM**; blocks on stale data (laptop proof: 36 missing sessions refused), passes on fresh VM (0 missing). Decisions audited in `freshness_gate_log` |
| Stale-artifact quarantine | **APPLIED on laptop** (3,422 rows moved: pattern_tags 2,542, trend_candidates 467, institutional 290, templates 120, validation 3); VM dry-run clean (5-day lag rule prevents false positives on weekend-run artifacts) |
| Corporate-action book | **DEPLOYED**: `corporate_actions.py` (CSV import, free yfinance splits/dividends, gap candidate detection); full harvest running on VM; pilot: 30 symbols -> 361 events |
| Raw-price rebuild from Fyers | **TOOLING READY**: `rebuild_raw_history.py` plan = 864 symbols, ~6,912 API calls, ~38 min at 180 req/min, dry-run by default, reuses guarded per-symbol rebuild. **Execution blocked on the one-time Fyers login** |
| One price truth | `price_meta.basis` recorded per symbol (all 864 VM symbols currently `legacy_adjusted`; will become `fyers_raw` after rebuild) |
| Recompute downstream after rebuild | Planned: after rebuild, run technicals -> scan -> ML -> PWin -> patterns -> templates -> top picks; the gate prevents recompute on stale data |

## 6.5 Option B started (18 Oct): veto layer no longer blind

| B increment | Status |
|---|---|
| Ownership enrichment from the free ScanX snapshot | **LIVE on VM**: `fundamentals_enrich.py` filled promoter_holding and fii_holding for **750 symbols** (coverage 750/1,268 = 59%), every field provenance-tagged `scanx_snapshot:2026-09-26` with flags `undated_snapshot`, `live_veto_only`, `not_point_in_time` |
| Veto rules expanded | `fund_veto.py` now also vetoes on **promoter pledge > 25%** (column exists; data still missing) and **interest cover < 1.5x**; measured effect on VM: **331 -> 335 of 800 band symbols vetoed** (promoter values are mostly healthy, so the increment is small — the honest result, not a headline) |
| PIT safety | Snapshot data is explicitly live-veto-only; `trader_league` already sets `HOME_USE_FUND_VETO=False` in replay, so no backtest lookahead is introduced |
| Still missing for a real elimination engine | pledge %, auditor/going-concern flags, promoter pledging events, quarterly cash conversion — all need filing/announcement ingestion (free NSE/BSE sources), not another snapshot |

## 7. Appendix

### A. Reproduce everything

```powershell
# this laptop
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\python.exe data_audit.py --json docs/data_audit_2026-10-18.json
.\env\Scripts\python.exe data_quality.py
.\env\Scripts\python.exe fundamentals_derive.py            # dry run
.\env\Scripts\python.exe -m unittest test_fyers_integration -v
.\env\Scripts\python.exe ingest_fyers.py status

# after the Fyers login (one time per day)
.\env\Scripts\python.exe fyers_client.py login-url
.\env\Scripts\python.exe fyers_client.py exchange --code <AUTH_CODE>
.\env\Scripts\python.exe ingest_fyers.py master
.\env\Scripts\python.exe ingest_fyers.py verify --limit 20
.\env\Scripts\python.exe ingest_fyers.py history --days 30
.\env\Scripts\python.exe ingest_fyers.py sync --dry-run
```

### B. Files added/changed in this batch

| File | Purpose |
|---|---|
| `data_audit.py` | **new** — inventory/usefulness/freshness/derivability audit (JSON + report) |
| `fyers_client.py` | **new** — Fyers v3 data client (OAuth, token store, history/quotes/depth, rate limit) |
| `ingest_fyers.py` | **new** — symbol master, append/rebuild ingestion, seam check, verify, sync log, daily entry point |
| `data_sources/adapters/fyers.py` | **removed after review** — created an unguarded second write path; Fyers writes only through `ingest_fyers.py` |
| `test_fyers_integration.py` | **new** — 40 offline tests (fake HTTP, in-memory DB) |
| `fundamentals_derive.py` | **new** — derives EPS TTM / book value / shares with provenance |
| `db.py` | +3 Fyers tables; +`fundamentals.eps_ttm`/`shares_outstanding`; +`price_meta.basis` (price-basis provenance) |
| `ingest_prices.py` | unchanged — Fyers deliberately **not** in the generic price chain |
| `daily_update.py` | Fyers sync step before generic price ingest |
| `docs/data_audit_2026-10-18.json` | machine-readable audit output |
| `.env` | **untracked/ignored** — Fyers app id/secret/redirect |

### C. Numbers at a glance

| | |
|---|---|
| Tables / empty / stale / thin / active | 44 / 18 / 13 / 8 / 6 (42 / 17 / 13 / 7 / 5 before today's Fyers tables) |
| Price rows / symbols / range | 1,131,371 / 1,086 / 2021-08-17 → 2026-08-27 |
| Price freshness / missing sessions | 52 days / ~34–36 |
| Symbols usable for 200-DMA | 1,014 (93.4%) |
| Invalid OHLC rows | 0 |
| Fundamentals rows / columns / empty columns | 503 / 35 / 10 (15 of 33 were empty this morning) |
| Fundamentals ownership fields filled | 0% |
| Price fields disagreeing >1% | 379–407 of 501 |
| ScanX rows × cols / dated period-ends | 750 × 72 / **0** |
| Fyers symbol master rows / broker date | 10,116 / 2026-10-16 |
| Universe resolved to broker tickers | 1,347 / 1,349 |
| Offline tests | **120 / 120 pass** (freshness 18, signal guard 5, Fyers 40, corporate actions 20, rebuild 14, enrichment 18, veto 5) |
| Reclaimable backups | 326 MB |
| League verdict (from handoff) | NOT READY — −6.2% vs Nifty +5.5%, PF 0.93, 0 live trades |
