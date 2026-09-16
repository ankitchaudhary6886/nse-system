# EXECUTION LOG — durable record of every code batch

Purpose: survives chat migrations. New session reads `backlog.md` +
`EXECUTION_LOG.md` + `PORTAL_REDESIGN.md` and knows the full history.

Format: numbered batches. Session boundaries marked.
Status legend: DEPLOYED · VERIFIED · PARTIAL · REJECTED · AWAITING

---

## SESSION 1 — 2026-09-12 (morning)

### #001 · regime.py — yfinance period fix
- Files: `regime.py`
- Status: DEPLOYED · VERIFIED

### #002 · screener_engine.py — yfinance period + index fallback
- Files: `screener_engine.py`
- Status: DEPLOYED · VERIFIED

### #003 · db.py — central schema (29 tables)
- Status: DEPLOYED · VERIFIED

### #004 · meta_model.py — feature guard + bundle format
- Status: DEPLOYED · VERIFIED

### #005 · events + swing_live + deepdive — three fixes
- Status: DEPLOYED · VERIFIED

### #006 · backtest + swing_live + screener_engine — staleness
- Status: DEPLOYED · VERIFIED

### #007 · app.py — optional-panel guards
- Status: DEPLOYED · VERIFIED

### #008 · log_utils + daily_update + scheduler_bg + requirements split
- Status: DEPLOYED · VERIFIED

### #009 · setup.py v3.1 — impulse indexing bug fix
- Result: impulse range 35.1–46.8% (was 10–3000%).
- Status: DEPLOYED · VERIFIED

### #010 · all_weather.py — all-weather swing mode
- Result: 115 candidates → 5 signals → Telegram fired.
- Status: DEPLOYED · VERIFIED

### #011 · value_radar.py
- Status: DEPLOYED · VERIFIED

### #012 · value_radar wiring
- Status: DEPLOYED · VERIFIED

### #013 · fundamentals_tv.py — canonical fetcher
- Result: 863 symbols.
- Status: DEPLOYED · VERIFIED

### #014 · BACKLOG + EXECUTION_LOG restructure
- Status: DEPLOYED · VERIFIED

---

## SESSION 2 — 2026-09-12 (midday → evening)

### #015 · Feature C — regime spectrum
- Files: `regime_spectrum.py` (new), `regime.py`, `sizing.py`
- Result: 5 levels; size_mult 1.00/1.00/0.75/0.50/0.25.
- Status: DEPLOYED · VERIFIED

### #016 · Value Radar v2 — tiers + promoter/CFO enrichment
- Result: tier A appeared (RSYSTEMS, MADRASFERT, SANOFI, TANLA).
- Status: DEPLOYED · VERIFIED

### #017 · Sizing — fallback win-rate 0.35
- Status: DEPLOYED · VERIFIED

### #018 · positional_scanner.py (ID3a)
- Result: 50 picks saved.
- Status: DEPLOYED · VERIFIED

### #019 · alerts.py — unified alerts (ID7)
- Files: `alerts.py` (new), `telegram_alerts.py`, `swing_alerts.py` (shims)
- Status: DEPLOYED · VERIFIED

### #020 · universe_helper.py (ID7)
- Files: `universe_helper.py` (new), `swing_live.py` migrated
- Status: DEPLOYED · VERIFIED

### #021 · trend_scanner.py (ID8)
- Status: DEPLOYED · VERIFIED

### #022 · universe_helper migration (ID7 cont.)
- Files: `value_radar.py`, `positional_scanner.py`
- Status: DEPLOYED · VERIFIED

### #023 · Scanners UI (ID9)
- Files: `terminal/static/scanners.js` (new), `index.html`
- Status: DEPLOYED · VERIFIED

### #024 · Trend v2 + meta_model v7 (33 features)
- Result: trend still saturated at 100; meta AUC unchanged 0.629.
- Status: DEPLOYED · PARTIAL

### #025 · Trend v3 — unbounded score
- Result: scores differentiate (100.0 / 99.8 / 99.3 / ...).
- Status: DEPLOYED · VERIFIED

### #026 · validate.py v3 — fast walk-forward
- What: delegates to Backtester (100x faster). Dual OOS windows.
- Status: DEPLOYED · VERIFIED

### #027 · Setup v3.2 — widen impulse
- Files: `setup.py`, `quick_setup_diag.py`, `quick_funnel.py` (new)
- Result: setup pass 0.4% → 3.2%.
- Status: DEPLOYED · VERIFIED

### #028 · Setup v3.3 — widen 1c / PB
- Result: setup pass 3.2% → 8.0%.
- Status: DEPLOYED · VERIFIED

### #029 · fast_wf.py — target sweep
- Result: 2R PF 1.21 / 2.5R PF 1.30 / 3R PF 1.43.
- Decision: adopt 3R.
- Status: DEPLOYED · VERIFIED

### #030 · Sizing v4 — quality multiplier
- Status: DEPLOYED · VERIFIED

### #031 · strategy_runs.py — durable ledger
- Status: DEPLOYED · VERIFIED

### #032 · Tranche exits tested (ID18)
- Result: PF identical (1.45 vs 1.43), DD worse, return worse.
- Status: REJECTED · Code retained behind `TRANCHES_ENABLED = False`

### #033 · Strategy runs dashboard
- Files: `terminal_api.py`, `terminal/static/strategy_runs.js` (new)
- Status: DEPLOYED · VERIFIED

### #034 · strategy_config.py — central config (ID19)
- Files: `strategy_config.py` (new), `setup.py`, `backtest.py`,
  `scanner.py`, `sizing.py`, `all_weather.py`
- Verify: WF numbers unchanged (185 trades / PF 1.43).
- Status: DEPLOYED · VERIFIED

### #035 · Deployment verification (ID21)
- Files: `verify_deployment.py` (new), `terminal_api.py`,
  `terminal/static/deployment.js` (new)
- Status: DEPLOYED · VERIFIED

### #036 · Graceful skips — ml_predict + sheets_sync
- Result: 15/15 checks green. `ml_train.py` produced `data/ml_models.pkl`
  (AUC 0.584 6M / 0.589 12M).
- Status: DEPLOYED · VERIFIED

### #037 · research_cockpit.py (ID22 v1)
- Files: `research_cockpit.py` (new), `terminal_api.py`,
  `terminal/static/research.js` (new)
- Status: DEPLOYED · VERIFIED

### #038 · Research Universe (ID22b)
- Files: `research_cockpit.py`, `terminal_api.py`,
  `terminal/static/research_universe.js` (new)
- Status: DEPLOYED · VERIFIED

### #039 · Warm cache scheduler (ID22c)
- Files: `research_cockpit.py`, `scheduler_bg.py`
- Status: DEPLOYED · VERIFIED

### #040 · Sector aggregation + sortable UI (ID23 / R24)
- Files: `research_cockpit.py`, `terminal_api.py`,
  `terminal/static/research_sector.js` (new), `research_universe.js`
- Status: DEPLOYED · VERIFIED

### #041 · Fix warm_cache --force + CACHE_VERSION
- Files: `research_cockpit.py`
- Result: sector aggregation shows real pooled numbers.
- Status: DEPLOYED · VERIFIED

---

## SESSION 2 (continued) — 2026-09-12 (evening)

### #042 · Portal Phase 1 redesign
- Files: `terminal/static/app.js`, `terminal/static/index.html`,
  `backlog.md`
- What: 5-tab nav (Funda/Swing/Research/Ledger/System). Overview retired.
  Progressive disclosure on sizing/SHAP/delivery.
- Status: DEPLOYED · VERIFIED

### #043 · Rule engine + seed strategies (Phase 2 start)
- Files: `rule_engine.py` (new), `terminal_api.py`,
  `terminal/static/strategies.js` (new), `terminal/static/index.html`
- What: JSON-driven strategy evaluator. Seeds: Multibagger, RCP,
  EpisodicPivot. Funda/Swing panels with Run buttons.
- API: `/api/strategies`, `/api/strategies/{name}/run`,
  `/api/strategies/{name}`, `/api/strategies/seed`.
- Storage: `data/strategies.json`.
- Status: DEPLOYED · PARTIAL (numpy bug in _sma/_ema)

### #044 · Fix rule_engine numpy truth-value bug
- Files: `rule_engine.py`
- What: `not vals` on numpy arrays raises ambiguous truth value.
  Replaced with `_seq_len(v) == 0` guard in `_sma` / `_ema` / `_rsi`.
- Status: DEPLOYED · VERIFIED

### #045 · Rule engine: failure breakdown diagnostic
- Files: `rule_engine.py`
- What: `run_strategy` now returns per-condition fail counts and
  "missing" (NULL value) counts. CLI shows the block after picks.
- Verify: diagnosed that RCP failed mostly on `days_since_impulse_peak`.
- Status: DEPLOYED · VERIFIED

### #046 · Gap-up + impulse/pullback features; RCP/EP rewrite
- Files: `rule_engine.py`
- What: Added 10 new features to the feature extractor:
  `had_gapup_15d`, `days_since_gapup`, `gapup_size`,
  `pre_gap_above50`, `pre_gap_above200`, `pre_gap_drawdown`,
  `impulse_pct_60d`, `days_since_impulse_peak`,
  `pullback_from_peak_pct`, `consolidation_range_pct`.
  Rewrote RCP and EpisodicPivot seeds per owner's specific rules.
- Verify: RCP 15 picks, EpisodicPivot 7 picks.
- Status: DEPLOYED · VERIFIED

### #047 · Route ordering fix for /api/strategies/seed
- Files: `terminal_api.py`
- What: `{name}` route was swallowing `/seed`. Static prefix routes
  now registered before parametrised ones.
- Status: DEPLOYED · VERIFIED

### #048 · strategies.js — use JSON key for API calls
- Files: `terminal/static/strategies.js`
- What: UI was sending display name (`"RCP — Range Contraction Pattern"`)
  instead of JSON key (`"RCP"`) → 404. Switched to `Object.entries()`
  and pass the key.
- Status: DEPLOYED · VERIFIED

### #049 · ID42: in-browser strategy editor
- Files: `terminal/static/strategy_editor.js` (new),
  `terminal/static/strategies.js`, `terminal/static/index.html`
- What: Modal editor for any strategy — add/remove conditions,
  edit thresholds, weights, universe, type. Save via API.
- Status: DEPLOYED · AWAITING VERIFICATION

### #050 · ID43: strategy backtest sandbox
- Files: `strategy_backtest.py` (new), `terminal_api.py`,
  `terminal/static/strategies.js`
- What: Historical walk of any strategy (2y default). Entry = next
  bar open, stop = entry × (1 - stop_pct), target = entry + r × risk,
  hold up to `hold_bars`. Aggregates: n_signals, W/L/T, win rate,
  avg return, total return, max DD, equity curve, recent signals.
  Cached 7 days in `data/backtest_cache.json`. Backtest button in
  each strategy card.
- API: `/api/strategies/{name}/backtest`
- Status: DEPLOYED · AWAITING VERIFICATION

---

## HOW NEW SESSIONS USE THIS
1. Read `backlog.md` — rules, instructions, current status.
2. Read `EXECUTION_LOG.md` — exactly what shipped.
3. Read `PORTAL_REDESIGN.md` — vision & roadmap.
4. Continue from the last entry's status.



# EXECUTION LOG — durable record of every code batch

Purpose: survives chat migrations. New session reads `backlog.md` +
`EXECUTION_LOG.md` + `PORTAL_REDESIGN.md` and knows the full history.

Status legend: DEPLOYED · VERIFIED · PARTIAL · REJECTED · AWAITING

---

## SESSION 1 — 2026-09-12 (morning)
#001–#014 — as logged in prior versions. PO fixes, setup bug fix,
all-weather, value radar, logging, handoff.

## SESSION 2 — 2026-09-12 (midday → evening)
#015–#041 — as logged. Feature C, value radar v2, sizing, positional,
alerts, universe helper, trend scanner, target sweep, strategy config,
deployment, research cockpit, sector aggregation.

## SESSION 2 (continued) — 2026-09-12 (evening)
#042–#050 — as logged. Portal Phase 1, rule engine, gap-up features,
route fix, editor, backtest sandbox.

### #051 · TV column probe (ID44 step 1)
- Files: `tv_column_probe.py` (new)
- What: probes ~100 candidate TradingView column names against 30 NSE
  symbols. Reports which return real values, which are accepted but
  null, which are rejected. Data-driven basis for rewriting
  `fundamentals_tv.py`.
- Status: DEPLOYED · AWAITING VERIFICATION

---

## HOW NEW SESSIONS USE THIS
1. Read `backlog.md` — rules, instructions, current status.
2. Read `EXECUTION_LOG.md` — exactly what shipped.
3. Read `PORTAL_REDESIGN.md` — vision & roadmap.
4. Continue from the last entry's status.

### #051 · TV column probe (ID44 step 1)
- Files: `tv_column_probe.py` (new)
- Result: 48 of 104 columns return real values. Growth, shareholding,
  price_to_book, operating_cash_flow are all null or rejected.
- Status: DEPLOYED · VERIFIED

### #052 · Fundamentals v5 + schema migration (ID44 step 2)
- Files: `db.py` (added `_migrate`), `fundamentals_tv.py` (v5),
  `rule_engine.py` (Multibagger seed → quality-only)
- What:
  - 6 new columns on `fundamentals`: beta_1y, eps_fy, book_value,
    ev_ebitda, fcf_fy, net_debt_fy. Plus `data_source` marker.
  - `db.get_conn()` runs idempotent column migration on every connection.
  - `fundamentals_tv.py` uses only probe-verified columns; derives
    `pb` from close/book_value and `cfo_positive` from FCF sign.
  - Multibagger seed rewritten as quality-only strategy.
- Status: DEPLOYED · AWAITING VERIFICATION

### #051 · TV column probe (ID44 step 1)
- Files: `tv_column_probe.py`
- Result: 48 of 104 columns return real values.
- Status: DEPLOYED · VERIFIED

### #052 · Fundamentals v5 + schema migration (ID44 step 2)
- Files: `db.py`, `fundamentals_tv.py`, `rule_engine.py`
- Result: 863 rows; roce 875, roe 850, pe 846, debt_eq 853, cfo_flag 860.
  Multibagger 98 picks (was 0).
- Status: DEPLOYED · VERIFIED

### #053 · Percentile scoring (ID45)
- Files: `rule_engine.py`
- What: score = Σ(percentile × weight) instead of Σ(raw × weight).
  Negative weights invert percentile. Fallback to raw only if pct
  map missing. Fixes outlier-dominated scores (JPOLYINVST at 1850).
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #051 · TV column probe (ID44 step 1)
- Status: DEPLOYED · VERIFIED

### #052 · Fundamentals v5 + schema migration (ID44 step 2)
- Result: 863 rows, all core fields populated; Multibagger 98 picks.
- Status: DEPLOYED · VERIFIED

### #053 · Percentile scoring (ID45)
- Result: scores in 0-100 range (was 20-1850).
- Status: DEPLOYED · VERIFIED

### #054 · Candle behaviour analytics (ID47)
- Files: `research_cockpit.py`, `terminal/static/research.js`
- What:
  - `_classify_mother_bar()` — classifies each historical setup's
    mother bar (inside / hammer / inv_hammer / doji / wide / normal)
    with shape metrics (body_ratio, wick ratios, close_position,
    range_atr, is_bull).
  - `_candle_stats()` — groups setups by mtype, computes per-category
    hit rates and median MFE/MAE.
  - Current setup also gets its mother bar classified.
  - Cache version bumped to 3 (auto-invalidates).
  - UI: new "Candle behaviour" table in the Research Cockpit, with
    the current setup's category highlighted.
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #054 · Candle behaviour analytics (ID47) — VERIFIED
- Result: TANLA shows inv_hammer setups hitting +1R/+2R/+3R 100% (n=1
  triggered, caveat small sample). Grouping works.

### #055 · Signature matching (ID46)
- Files: `build_setup_pool.py` (new), `research_cockpit.py`,
  `terminal/static/research.js`
- What:
  - `setup_pool` table stores every historical setup across the whole
    universe with 8-dimensional feature vector + forward outcome.
  - `build_setup_pool.py` populates it (top 200 symbols, 5y, step=5).
  - `signature_match(live_features, k=30)` computes L1 distance in
    z-scored feature space, returns k nearest + pooled stats.
  - Live setups in the Research Cockpit now include a "Signature match"
    block above the symbol-only history — global context.
  - Cache version bumped to 4 (auto-invalidate).
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #054 · Candle behaviour analytics (ID47) — VERIFIED
- Result: TANLA shows inv_hammer setups 100% hit on 1 triggered sample.

### #055 · Signature matching (ID46) — VERIFIED
- Result: setup_pool built with 200 symbols → 1,300 setups across
  166 symbols, hit_1R total 445.
- Note: initial 200-symbol build was a scoping choice; full universe
  (~800 symbols) yields ~5,000+ setups.

### #056 · Weekly setup_pool rebuild scheduler job
- Files: `scheduler_bg.py`
- What: `_pool_rebuild_job` at Sunday 06:00 IST. Calls
  `build_setup_pool.build(limit=800, step=5, clear=True)`.
  Full rebuild weekly — ~8-10 minutes. Runs before value_radar
  (Sun 09:00) and does not overlap with weekday pipeline.
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #055 · Signature matching (ID46) — VERIFIED
- Result: initial 1,300 setups across 166 symbols. Pool scales with
  symbol count — 200 was a scoping choice.
### #056 · Weekly setup_pool rebuild scheduler job — VERIFIED
- Job: `poolRebuild@Sun06:00` with 800 symbols.

### #057 · Pattern transparency + chart markers (ID48 + ID49)
- Files: `patterns.py`, `terminal_api.py`, `terminal/static/app.js`
- What:
  - **ID48** — every detector in `patterns.py` now builds a `checks`
    list. `_save()` stores it in `pattern_tags.params` JSON. UI
    renders an expandable "Show conditions (N)" toggle on each
    pattern card in the Research tab.
  - **ID49** — new endpoint `/api/patterns/history/{symbol}` returns
    compact signal+outcome rows (joins pattern_tags with
    pattern_grades). Research cockpit chart now overlays markers
    at every historical signal: green up arrow (WIN), red down
    arrow (LOSS), yellow circle (TIMEOUT/EXPIRED), blue square
    (OPEN/undefined). Bearish patterns use downward arrow shape.
  - Route ordering: `/api/patterns/latest`, `/api/patterns/stats`,
    `/api/patterns/history/{symbol}` all registered before the
    generic `/api/patterns/{symbol}`.
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #051 · TV column probe (ID44 step 1) — VERIFIED
- Result: 48 of 104 columns return real values.

### #052 · Fundamentals v5 + schema migration (ID44 step 2) — VERIFIED
- Result: 863 rows; roce 875, roe 850, pe 846, debt_eq 853, cfo_flag 860.
  Multibagger 98 picks.

### #053 · Percentile scoring (ID45) — VERIFIED
- Result: scores in 0-100 range.

### #054 · Candle behaviour analytics (ID47) — VERIFIED
- Result: TANLA shows inv_hammer setups hitting +1R/+2R/+3R 100%.

### #055 · Signature matching (ID46) — VERIFIED
- Result: setup_pool built with 200 symbols → 1,300 setups across
  166 symbols.

### #056 · Weekly setup_pool rebuild scheduler job — VERIFIED
- Job: `poolRebuild@Sun06:00` with 800 symbols.

### #057 · Pattern transparency + chart markers (ID48 + ID49) — VERIFIED
- Result: new tags carry checks; history endpoint returns signals for
  chart markers.

### #058 · Bearish pattern grading fix (ID53)
- Files: `pattern_grader.py`
- What: `_grade_one` now accepts `direction`. Bearish patterns
  (H&S top warning) are graded on the short side: trigger = LOW breaks
  below breakout, stop above, target below at -1R. Long logic unchanged.
  `grade_all` now reads direction from pattern_tags. `regrade` command
  re-runs the full history with the new logic.
- Impact: previously all HEAD_SHOULDERS_TOP_WARNING tags were ungraded
  (breakout <= stop sanity check failed). Fixes chart markers on the
  Research cockpit for bearish signals.
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #058 · Bearish pattern grading fix (ID53) — VERIFIED
- Result: `pattern_grader.py` handles bearish H&S top warning;
  regrade produced full gate table:
  HTF 60.1%, AT 63.8%, DB 62.9%, InvHS 67.3%, H&S Top 76.8%
  (ENABLED). Bull Flag 56.1% (DISABLED).

### #059 · Compare mode + unified stock card (ID50 + ID51)
- Files: `compare_tool.py` (new), `terminal_api.py`,
  `terminal/static/cards.js` (new), `terminal/static/app.js`,
  `terminal/static/scanners.js`, `terminal/static/index.html`
- What:
  - **ID50** — `/api/compare?symbols=A,B,C` reads only cached data.
    Compare panel in Research tab with text input. Renders side-by-side
    table (overview / fundamentals / signal / history / signature).
  - **ID51** — `cards.js` defines `renderUnifiedCard(item)`.
    Top Picks, Radar, Trend, Positional, and Value Radar now use the
    same card. Same visual language everywhere.
  - Phase 3 complete.
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #051 · TV column probe (ID44 step 1) — VERIFIED
- Result: 48 of 104 columns return real values.
- TV India does NOT return: growth (revenue/net_income/eps), insider
  or institutional holding, price_to_book, operating cash flow.

### #052 · Fundamentals v5 + schema migration (ID44 step 2) — VERIFIED
- Files: `db.py`, `fundamentals_tv.py`, `rule_engine.py`
- Result: 863 rows; roce 875, roe 850, pe 846, debt_eq 853, cfo_flag 860.
  Multibagger 98 picks.

### #053 · Percentile scoring (ID45) — VERIFIED
- Files: `rule_engine.py`
- Result: scores in 0-100 range (was 20-1850).

### #054 · Candle behaviour analytics (ID47) — VERIFIED
- Files: `research_cockpit.py`, `terminal/static/research.js`
- Result: TANLA shows inv_hammer setups hitting +1R/+2R/+3R 100%.

### #055 · Signature matching (ID46) — VERIFIED
- Files: `build_setup_pool.py` (new), `research_cockpit.py`,
  `terminal/static/research.js`
- Result: initial pool 1,300 setups across 166 symbols (200-symbol
  build).

### #056 · Weekly setup_pool rebuild scheduler job — VERIFIED
- Files: `scheduler_bg.py`
- Job: `poolRebuild@Sun06:00` with 800 symbols, step=5, full clear+rebuild.

### #057 · Pattern transparency + chart markers (ID48 + ID49) — VERIFIED
- Files: `patterns.py`, `terminal_api.py`, `terminal/static/app.js`
- What:
  - Every detector records a `checks` list stored in
    `pattern_tags.params` JSON.
  - New `/api/patterns/history/{symbol}` endpoint.
  - Chart overlays markers at every historical signal — green up
    arrow (WIN), red down arrow (LOSS), yellow circle
    (TIMEOUT/EXPIRED), blue square (OPEN).

### #058 · Bearish pattern grading fix (ID53) — VERIFIED
- Files: `pattern_grader.py`
- Result: `pattern_grader.py` handles bearish H&S top warning;
  regrade produced full gate table:
  HTF 60.1%, AT 63.8%, DB 62.9%, InvHS 67.3%, H&S Top 76.8%
  (all ENABLED). Bull Flag 56.1% (DISABLED).

### #059 · Compare mode + unified stock card (ID50 + ID51) — VERIFIED
- Files: `compare_tool.py` (new), `terminal_api.py`,
  `terminal/static/cards.js` (new), `terminal/static/app.js`,
  `terminal/static/scanners.js`, `terminal/static/index.html`,
  `backlog.md`, `EXECUTION_LOG.md`
- What:
  - **ID50** — `/api/compare?symbols=A,B,C` reads only cached data.
    Compare panel in Research tab with text input (2-4 symbols).
    Side-by-side table: overview / fundamentals / signal / history /
    signature match.
  - **ID51** — `cards.js` defines `renderUnifiedCard(item)`.
    Top Picks, Radar, Trend, Positional, and Value Radar now use
    the same card.
- Result: API `status: 200`, `rows: 3`. Phase 3 complete.

---
### #060 · Famous Traders framework + John Crane (ID54 + ID55)
- Files:
  - `traders/__init__.py` (new) — registry
  - `traders/base.py` (new) — shared utilities (pivots, trendlines,
    weekday-holiday counting, SSTO)
  - `traders/john_crane.py` (new) — 14 methods from Advanced Swing Trading
  - `terminal_api.py` — new endpoints `/api/traders`,
    `/api/traders/{slug}`, `/api/traders/{slug}/scan`
  - `terminal/static/traders.js` (new) — Traders view: sidebar of
    traders + method table + universe scan results
  - `terminal/static/index.html` — added **📚 Traders** nav item + view
  - `backlog.md` — logged R29, ID54, ID55
  - `EXECUTION_LOG.md` — this entry
- What:
  - Framework: each trader = one module with SLUG, NAME, PILLAR,
    SOURCE, METHODS, scan(conn, limit).
  - John Crane classified as **Swing**. Methods implemented:
    reaction swing, time forecast (Reverse→Forward count with weekday
    holiday law), action/reaction lines, retracement windows (60%/30%),
    two-day rule, peg-leg, gap and go, gap reversal, trail day,
    continuation gap, major reversal, SSTO 20-period divergence,
    and the master decision engine stub.
  - Trader page: sidebar of traders, method table, "Run Scan" button
    → signals across the band universe, grouped by method.
  - Signals carry symbol, direction, order type, entry, stop,
    confidence, notes.
- Status: DEPLOYED · AWAITING VERIFICATION

### #062 · Trader #2 — Larry Spears (ID56)
- Files:
  - `traders/larry_spears.py` (new) — 7 setup-identification methods
  - `traders/__init__.py` — registry now includes larry_spears
  - `backlog.md` — logged R30, ID56
  - `EXECUTION_LOG.md` — this entry
- What:
  - Classified as **Swing**.
  - Methods:
    1. Beta filter — symbol beta ≥1.30 vs ^NSEI (cov/var).
    2. Amplitude filter — 5-day high-low range ≥5% of price.
    3. Gap classification — open ≥0.5% from prior close.
    4. MA trend alignment — SMA10/20/50 stacking + slopes.
    5. Counter-trend retracement — 2-3 consecutive lower highs
       (in uptrend) / higher lows (in downtrend), invalidated
       beyond 5 days.
    6. Force Index filter (Elder) — FI13 ≥0 and FI3 ≤0 (long);
       FI13 ≤0 and FI3 ≥0 (short).
    7. Composite setup — all six aligned → full Larry Spears setup.
  - Execution, stop-loss, sizing, trailing intentionally excluded
    per owner's request (recorded as R30).
  - Benchmark returns for ^NSEI fetched once per scan and cached
    at module level.
- Status: DEPLOYED · AWAITING VERIFICATION

---
### #063 · Fix Larry Spears `_ma_trend` slope-check bug — VERIFIED
- Files: `traders/larry_spears.py`
- What: `_strictly_increasing` / `_strictly_decreasing` helpers
  replaced the buggy `all(v is not None and s10_hist[i] < s10_hist[i+1]
  ...)` inline checks that referenced an undefined `v`.
- Status: DEPLOYED · VERIFIED

### #064 · Book extraction standard + feature registry (ID57 + ID58)
- Files:
  - `BOOK_EXTRACTION_PROMPT.md` (new) — the standard prompt for
    extracting trading-book methods. Method-centric output, US→India
    translation rules, structural invalidation, setup validity
    window, logical structure, variants.
  - `NEW_FEATURES_BACKLOG.md` (new) — registry of every feature the
    system supports. Groups: price primitives, MAs, momentum,
    structure, volume, patterns, cross-sectional, fundamentals,
    trader-specific (John Crane, Larry Spears). Track requested /
    pending features separately.
  - `backlog.md` — added R31 (book extraction standard), ID57, ID58.
  - `EXECUTION_LOG.md` — this entry.
- Status: DEPLOYED · AWAITING VERIFICATION


### #065 · Trader #3 — James O'Shaughnessy
- Files:
  - `traders/oshaughnessy.py` (new) — 19 methods from
    *What Works on Wall Street* (3rd Edition)
  - `traders/__init__.py` — registry now includes oshaughnessy
  - `backlog.md` — added I52, I53, ID59, R32; status table updated
  - `NEW_FEATURES_BACKLOG.md` — 10 new BACKLOG feature entries
  - `EXECUTION_LOG.md` — this entry
- What:
  - Classified as **FUNDA** (annual-rebalance, long-only, fundamental).
  - Methods implemented as scanned (16):
    - Market Leaders Universe (top ~15% by mcap, non-utility)
    - Dogs of the Dow (top 10 by yield in large-cap proxy)
    - Low PE, Low P/B, Low PSR*, Low P/CF*, High Dividend Yield
    - Worst 1Y Earnings Gains*
    - 1-Year Relative Strength
    - Low PE + RS, Low P/B + RS, Low PSR* + RS
    - Cornerstone Growth original*, improved*
    - Cornerstone Value original, improved*
  - (*) = partial — awaits PSR / EPS history / cashflow standardization
    / shares-outstanding history. These methods currently emit zero
    hits and log a data-coverage report at scan start.
  - Portfolio constructions listed but not scanned (Methods 13, 18, 19).
  - Uses `universe_helper.band_universe` for the reference universe.
  - Cross-sectional percentiles and top-N rankings computed once per
    scan (single pass over ~800 symbols).
- Verification pending (owner to run: `python -c "import traders; print([t.SLUG for t in traders.REGISTRY])"`).
- Status: DEPLOYED · AWAITING VERIFICATION


### #065 · Trader #3 — James O'Shaughnessy — VERIFIED
- Result: 256 signals across 46 symbols (test scan, limit=50).
- Methods with hits (10): relative_price_strength_1y (46),
  market_leaders_universe (45), low_pb_value (44),
  high_dividend_yield (30), cornerstone_value_original (30),
  cornerstone_value_improved (30), low_pe_value (10),
  low_pe_plus_rs (10), dogs_of_the_dow (10), low_pb_plus_rs (1).
- Methods with zero hits — expected, awaiting ID52 features:
  low_psr_value, low_psr_plus_rs, cornerstone_growth_original,
  cornerstone_growth_improved, worst_earnings_gains, low_pcf_value.
- Registry check: traders.REGISTRY → 3 modules, 40 methods total
  (Crane 13 + Spears 7 + O'Shaughnessy 19... actually Crane=13,
  Spears=7, O'Shaughnessy=19 per METHODS list).
- Status: VERIFIED · 2026-09-14


### #066 · Trader #4 — Wesley Gray & Tobias Carlisle
- Files:
  - `traders/quantitative_value.py` (new) — 17 methods from
    *Quantitative Value* (2012)
  - `traders/__init__.py` — registry now includes quantitative_value
  - `backlog.md` — added I54, ID60, FQV; status table updated
  - `NEW_FEATURES_BACKLOG.md` — 9 new BACKLOG feature entries
  - `EXECUTION_LOG.md` — this entry
- What:
  - Classified **FUNDA** (annual-rebalance, long-only, fundamental).
    Some methods (buyback, insider, 13D, short interest) span
    Multi but primary use in the book is long-term value confirmation.
  - **7 scanned now** (with proxies where book's primary ratio
    unavailable — documented in signal notes):
    - Graham Simple Value (clean, no proxy)
    - Earnings Yield (EBIT/TEV proxy → 1/PE)
    - Book-to-Market (clean)
    - Magic Formula proxy (ROC + EBIT/TEV → ROCE + 1/PE)
    - Quality & Price proxy (GPA + BM → ROE + 1/PB)
    - Composite Price Ratios proxy (E/P + B/M + DY)
    - ROCE Quality Gate (clean)
  - **10 flagged** — emitted zero hits, log a data-coverage report
    each scan: STA, SNOA, PROBM, PFD, F_SCORE, FS_SCORE, Franchise
    Power, EBIT/TEV, Buyback Yield, Opportunistic Insider Buying,
    Activist 13D, Low Short Interest. Auto-activate when ID52 lands.
  - `quantitative_value_model` listed as portfolio construction,
    not scanned.
  - Uses `universe_helper.band_universe` for reference universe.
    Sector exclusion: financials, banks, NBFCs, insurance, utilities,
    power, gas distribution, water, electric, REITs.
- Verification pending (owner to run the two-line test below).
- Status: DEPLOYED · AWAITING VERIFICATION
5. NEW_FEATURES_BACKLOG.md — append to Section B
markdown
### ebit  ·  [Quantitative Value — Gray & Carlisle]
- **Status:** BACKLOG
- **Formula:** Earnings Before Interest and Taxes
- **Why it matters:** Primary field for EBIT/TEV — the book's best
  price ratio. Also feeds Magic Formula and franchise metrics.
- **Effort estimate:** M
- **Blocks:** QV methods ebit_enterprise_multiple, magic_formula,
  quantitative_value_model

### total_enterprise_value (tev)  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** market_cap + total_debt − excess_cash + preferred +
  minority_interests
- **Why it matters:** Denominator for EBIT/TEV.
- **Effort estimate:** M (derivable once components land)

### gross_profit  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** revenue − COGS
- **Why it matters:** GPA quality metric (Method 3).
- **Effort estimate:** M

### total_assets  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** balance-sheet total
- **Why it matters:** Denominator for GPA, SNOA, ROA, STA.
- **Effort estimate:** S (available via TV; not stored)

### current_assets / current_liabilities  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** balance-sheet current portions
- **Why it matters:** Net working capital, excess cash, STA.
- **Effort estimate:** S

### cash_and_equivalents  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** cash + ST investments
- **Why it matters:** Excess cash in TEV; SNOA.
- **Effort estimate:** S

### fundamentals_history  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** Yearly snapshot of all fundamentals fields
- **Why it matters:** Unlocks Piotroski F_SCORE, FS_SCORE, ΔROA,
  ΔLEVER, ΔMARGIN, 8-year geometric metrics (Franchise Power),
  PROBM, PFD, buyback yield.
- **Effort estimate:** L (schema + multi-year ingest)
- **Blocks:** the majority of Quantitative Value methods

### insider_trades  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** SEBI SAST disclosures — insider name, date, buy/sell,
  quantity, price
- **Why it matters:** Method 14 (Opportunistic Insider Buying).
- **Effort estimate:** L (external feed)

### short_interest  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** NSE short interest / shares outstanding
- **Why it matters:** Method 16 (Low Short Interest).
- **Effort estimate:** M (NSE publishes; parsing needed)

### activist_13d_filings  ·  [Quantitative Value]
- **Status:** BACKLOG
- **Formula:** SEBI SAST / substantial acquisition disclosures
- **Why it matters:** Method 15 (Activist 13D Filing).
- **Effort estimate:** L (external feed)


### #069 · Trader #5 — Janet Lowe
- Files:
  - `traders/value_investing_made_easy.py` (new) — 18 methods
  - `traders/__init__.py`
  - `backlog.md`, `NEW_FEATURES_BACKLOG.md`, `EXECUTION_LOG.md`
- Classified: Funda (+ Multi for special situations). 7 scanned
  with documented proxies, 11 flagged (balance-sheet line items,
  10/20yr history, event feeds, bond/convertible/preferred).
- Status: DEPLOYED · AWAITING VERIFICATION


### #070 · Trader #6 — Curtis Faith (Way of the Turtle)
- Files:
  - `traders/way_of_the_turtle.py` (new) — 9 methods
  - `traders/__init__.py` — registry now includes way_of_the_turtle
  - `backlog.md`, `NEW_FEATURES_BACKLOG.md`, `EXECUTION_LOG.md`
- Classified: **Multi** (daily-bar trend following).
- What:
  - **8 scanned** — all price-only, no data blocks:
    - Turtle System 1 (20-day breakout) — skip rule omitted
      (stateless scan; documented as aggressive variant)
    - Turtle System 2 (55-day breakout)
    - ATR Channel Breakout (350MA ± ATR)
    - Bollinger Breakout (350MA ± 2.5σ)
    - Donchian Trend (20d breakout + EMA25/EMA350 filter)
    - Dual Moving Average (100MA/350MA cross)
    - Triple Moving Average (150/250/350 MA stack)
    - Support/Resistance Breakdown (twice-tested levels)
  - 1 variant not scanned: `donchian_trend_time_exit` — same entry
    as Donchian Trend, different exit rule (exit is trade
    management, out of scope per R30).
  - MIN_BARS = 360 for 350-day MA/lookback support.
  - MIN_PRICE = ₹100 (penny-stock avoidance).
  - Short signals emitted for F&O-actionable contexts; notes flag
    "F&O only" for cash-equity limitation.
  - Breakout detection is fresh-breakout-only (checks today vs
    yesterday) to avoid re-firing on every day price stays above
    the level.
- Uses `universe_helper.band_universe` for the reference universe.
- Status: DEPLOYED · AWAITING VERIFICATION
---

### #073 · Trader #7 — Alpesh Patel & Paresh Kiri
- Files:
  - `traders/seven_simple_strategies.py` (new) — 11 methods
  - `traders/__init__.py` — registry now includes
    seven_simple_strategies
  - `backlog.md`, `NEW_FEATURES_BACKLOG.md`, `EXECUTION_LOG.md`
- Classified: **Swing** (long-only, no intraday, no shorting).
- What:
  - **11 methods, all scanned** — fully price-based, no data blocks:
    1. Breakout With Momentum (20d breakout OR gap-up, close near
       high, vol >= 1.5x)
    2. Mean Reversion (100-day mean, price >= 2% below, bullish
       reversal candle)
    3. MA Crossover 50/200 (fresh cross)
    4. MA Crossover 10 EMA / 24 SMA (fresh cross)
    5. MA Crossover 9 EMA / 16 SMA (fresh cross)
    6. Trend Line Trade (pivot-fit uptrend line touch + bullish candle)
    7. Trend Line Break (downtrend line break >= 2 ATR + volume)
    8. Channel Trade (lower-channel touch + bullish candle)
    9. Golden Entry (consolidation range <= 10% over 20 bars,
       breakout >= 2 ATR, vol >= 1.5x)
    10. Bullish Hammer (3 lower closes + hammer shape)
    11. Bullish Doji / Spinning Top (3 lower closes + small range
        bullish candle)### #074 · DATA_REQUESTS.md (I62, R36)
- Files:
  - `DATA_REQUESTS.md` (new) — owner-facing live list
  - `backlog.md` — added R36 + D10 + I62 + ID64; status updated
  - `EXECUTION_LOG.md` — this entry
- What:
  - Consolidated every flagged feature across O'Shaughnessy,
    Gray-Carlisle, and Lowe into 15 owner-actionable requests
    (DR-01 → DR-15).
  - Grouped by priority: P0 (3 requests, ~21 methods),
    P1 (4 requests, ~7 methods), P2 (8 requests, ~11 methods).
  - Duplication map: one fetch (fundamentals_history) unlocks
    ~18 methods across 3 traders.
  - Update protocol documented.
- Rule added: **R36** — maintain live owner-data request list.
- Demand added: **D10**.
- Status: DEPLOYED · VERIFIED
  - Bug-safety per R35: `_fmt_num` + `_try_emit` present from day one.
  - MIN_BARS = 260 (200-SMA headroom).
  - MIN_PRICE = ₹100 (penny avoidance).
  - All long-only, cash-equity actionable.
- Uses `universe_helper.band_universe` for reference universe.
- Status: DEPLOYED · AWAITING VERIFICATION



### #075 · Trader #8 — Apurva Parikh
- Files:
  - `traders/apurva_parikh.py` (new) — 1 composite strategy
  - `traders/__init__.py` — registry now includes apurva_parikh
  - `DATA_REQUESTS.md` — added DR-16 promoter/pledge,
    DR-17 Nifty PE, DR-18 business age, DR-19 NOTE only
  - `backlog.md`, `EXECUTION_LOG.md`
- Classified: **FUNDA** (long-only, no intraday, no short).
- **5 of 11 secrets testable today**:
  - Secret 6 — D/E ≤ 0.30 ✅
  - Secret 7 — CFO positive ✅
  - Secret 8 — ROE ≥ 15% ✅
  - Secret 9 — ROCE ≥ 20% ✅
  - Secret 10 partial — PE ≤ sector-median (industry-PE proxy) ✅
  - Secret 11 — RSI ≥ 60 + uptrend (close>SMA50>SMA200) ✅
- **6 secrets flagged** (pending DR):
  - Secret 1 business age → DR-18
  - Secret 2 promoter ≥ 51%, pledge ≤ 20% → DR-16
  - Secret 3 sales growth 10y → DR-01
  - Secret 4 profit growth 10y → DR-01
  - Secret 5 leadership quality → NOTE only (DR-19)
  - Secret 10 Nifty PE gate → DR-17 (proxy constant set to 22.0)
- **Exit rules shipped as informational metadata** on every signal
  (`raw.exit_rules`) — the book's "sell on fundamental deterioration"
  rules per R30/R19 (scanner identifies, owner decides).
- Bug-safety per R35: `_fmt_num` + `_try_emit` from day one.
- Uses `universe_helper.band_universe` for reference universe.
- Status: DEPLOYED · AWAITING VERIFICATION




## HOW NEW SESSIONS USE THIS
1. Read `backlog.md` — rules, instructions, current status.
2. Read `EXECUTION_LOG.md` — exactly what shipped.
3. Read `PORTAL_REDESIGN.md` — vision & roadmap.
4. Continue from the last entry's status.