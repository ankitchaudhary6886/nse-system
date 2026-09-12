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

---

## HOW NEW SESSIONS USE THIS
1. Read `backlog.md` — rules, instructions, current status.
2. Read `EXECUTION_LOG.md` — exactly what shipped.
3. Read `PORTAL_REDESIGN.md` — vision & roadmap.
4. Continue from the last entry's status.