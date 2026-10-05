# EXECUTION LOG — durable record of every code batch

Purpose: survives chat migrations. New session reads `backlog.md` +
`EXECUTION_LOG.md` + `PORTAL_REDESIGN.md` and knows the full history.

Format: numbered batches. Session boundaries marked.
Status legend: DEPLOYED · VERIFIED · PARTIAL · REJECTED · AWAITING

---

## RECENT - last 6 entries (full text)

### #102 - B2: consolidate band-universe SQL into universe_helper - VERIFIED
- **Owner-approved batch B2** — the codebase's largest single-point-of-failure.
  The band SQL (`mcap_cr BETWEEN 1000 AND 8000 …`) existed as **17 inline
  copies**; a threshold change previously needed 17 edits with silent
  divergence risk. All now route through `universe_helper.band_universe(conn, limit)`.
- Helper hardened first: `limit=None` added for the whole band, and documented
  that it truncates by `mcap_cr DESC` **before** returning A-Z, so the selected
  SET is faithful for any limit while output order changed mcap-desc -> alpha.
- 16 files changed: `universe_helper.py`, `all_weather.py`, `breadth.py`,
  `data_quality.py`, `fundamentals_tv.py`, `fund_veto.py`, `institutional.py`,
  `meta_model.py`, `patterns.py`, `pwin_cache.py`, `rule_engine.py`,
  `screener_engine.py`, `sectors_refresh.py`, `template_match.py`,
  `top_picks.py`, `trader_league.py`.
- Two consumers previously selected **all** band rows with no LIMIT
  (`data_quality`, `fundamentals_tv`); they now pass `None` / an explicit 1500 —
  equivalent today (855 band rows) and no longer silently capped at 1000.
- Verification, completed before any claim of success: 16/16 `py_compile` clean;
  16/16 imports clean (no circular-import regression); old-vs-new symbol SET
  equal at every site for its own limit (60/300/400/500/600/800/855/900/1500 and
  unbounded) — all `set-equal True`.
- Not yet deployed. Backend `.py` changed, so the VM needs `git pull` +
  `sudo systemctl restart nse-terminal` + the `journalctl` check.
- No trader / setup / scanner / strategy_config file touched, so no League
  `--changed` replay is required (`home` `code_hash` unchanged).

### #096 - Audit remediation: sizing, ML, and backtest safeguards - VERIFIED
- Sizing uses fixed-risk calculations, rejects invalid inputs, caps position
  allocation and planned risk, and does not infer sizing from `p_win`.
- ML uses canonical price-derived features, model-version checks, and global-date
  splits purged by label availability. Imputation values are learned from the
  training fold and reused for inference.
- Backtests fingerprint strategy/data for cache separation, reject unsupported
  current-context fields, handle entry gaps and stop/target ties conservatively,
  and mark incomplete windows as right-censored rather than closed trades.
- Validation: `python -m unittest discover -p 'test_*.py' -v` passed 30 tests;
  Python compilation checks passed. The complete suite ran after installing
  already-declared dependencies missing from the local environment.
- No live database import, training run, or VM deployment occurred during
  validation. The unverified NIFTY 50 CSV remains uncommitted and unpromoted.
- Legacy ambiguous values remain unchanged pending the owner's policy choice.

### #097 - Publish and deploy audit remediation - VERIFIED
- Main merged and published to GitHub at `33ee8fc`; VM fast-forwarded to the
  same commit. No source/data import or ML training was run.
- Created online SQLite backup
  `data/app.db.pre-audit-20261002-183658.bak`; `PRAGMA integrity_check`
  returned `ok` for both backup and live DB.
- Confirmed migration columns `fundamentals.source_metadata` and
  `pwin_daily.model_version` are present. Fundamentals (1,268), daily prices
  (815,135), and broad-universe rows (1,535) match the pre-deployment backup.
- `nse-terminal.service` is active; authenticated `/api/health` returned HTTP
  200 with `ok=true`. The 30-test suite passed locally and on the VM.
- `/api/deployment-check` returned HTTP 200 with one failed freshness check:
  `universe_broad` last updated 34 days ago (1,535 rows). This is a visible
  data freshness issue, not a code-deployment failure; no refresh was triggered.
- The provenance-unknown NIFTY CSV remains uncommitted, unapplied, and absent
  from the VM.

### #098 - Preserve and deprecate ambiguous fundamentals values - IMPLEMENTED
- Owner decision: keep potentially legacy `cfo_positive` and `roce` values
  temporarily for production compatibility and tag affected rows
  `legacy_deprecated`. After DR-01 v2 dated-fundamentals backfill satisfies
  its period/public-availability acceptance criteria, clear only the flagged
  legacy values; keep physical columns until separately reviewed.
- Added `flag_legacy_deprecated(conn, apply=False)` with preview by default,
  exact per-field provenance checks, idempotent apply behavior, and no numeric
  value mutation. Known non-TradingView per-field values are not tagged merely
  because another field on the row came from TradingView.
- Validation: focused tests verify preview-only behavior, preservation of
  current values and existing flags, source-specific targeting, and idempotence.
  Full local suite is now 31 tests; production tagging and its checks are in #099.

### #099 - Apply legacy deprecation flags on VM - VERIFIED
- Preview identified 887 rows with ambiguous legacy values: 860
  `cfo_positive` fields and 878 `roce` fields (some rows have both). The
  selection requires missing field-level provenance or explicit TradingView
  provenance; known non-TradingView field sources were not tagged.
- Created `/home/ubuntu/nse-system/data/app.db.pre-legacy-deprecated-20261002-191739.bak`;
  backup `PRAGMA integrity_check` returned `ok`.
- Applied only the row quality flag `legacy_deprecated` to 887 rows.
  Existing numeric values were compared against the backup and unchanged;
  existing flags were preserved. A second preview found all 887 rows already
  flagged and proposed zero further changes.
- Fundamentals (1,268), prices (815,135), and broad-universe rows (1,535)
  remain unchanged. The 31-test suite passes on both laptop and VM;
  authenticated `/api/health` returns HTTP 200 and the service is active.
- Removal gate: clear only the flagged legacy values immediately after DR-01
  v2 dated-fundamentals backfill is verified against period-end and
  public-availability requirements. Keep schema columns until compatibility
  is reviewed separately.

### #100 - Publish and deploy terminal UX and operating skills - VERIFIED
- Published commit `782c401` to `origin/main` and fast-forwarded the VM to the
  same commit. The terminal service remained active; no restart was needed for
  static assets and project skills.
- Deployed UI updates clarify navigation, market snapshot metrics, event-score
  meaning, and fixed-risk sizing. Added project skills for recurring/one-time
  operations and terminal UX principles.
- Deployed `/static/index.html`, `/static/app.js`, and `/static/style.css`
  returned HTTP 200. SHA-256 hashes for all four changed web assets matched
  between the canonical main worktree and VM.
- Targeted sizing, ML, backtest, and fundamentals tests passed (16 total);
  `node --check` passed for `app.js` and `cards.js`. Browser checks confirmed
  mobile-width overflow is absent, accessible navigation works, and sizing
  does not present win probability or Kelly as sizing inputs.
- An unauthenticated `/api/health` request returned HTTP 401; this probe does
  not verify the authenticated API health response. The application service
  was active. API behavior was not changed by this static UI release.
- Existing untracked user configuration, data, and VM backup files were
  preserved and not included in the release.

### #101 · Repair refresh, research, and trader-method flows — VERIFIED
- Research uses the newest stored swing/trend scan dates instead of requiring
  a scan dated today; it exposes source dates and warns when scans lag prices.
  Per-symbol research preserves the latest market state with short history,
  while withholding historical setup statistics until the 280-bar minimum.
  Research cache entries now invalidate when that symbol's latest price date
  advances.
- The company view launches current-state research and trader-method matching
  for the selected stock. Implemented scanners can target a single symbol
  within the established universe; cross-sectional rankers remain full-universe
  to preserve their ranking logic. Trader-method rows and matches open a
  plain-language guide instead of raw method JSON.
- Wired scan/screener controls to their APIs, added scan status/error feedback,
  made refresh behavior explicit (reload saved data versus run a scan), and
  removed duplicate refresh listeners. Added coverage for latest scan dates,
  price staleness, short histories, cache freshness, and the target-universe
  gate.
- Performance review was diagnostic only: production ledger shows 2 wins /
  44 graded signals (4.5%). The three-year common-book replay's highest listed
  win rate was 39.6% (PF 0.82, negative expectancy); no tested method supports
  a >60% claim. No signal thresholds or outcome labels were altered to improve
  the displayed rate.
- Validation: 36 unit tests passed locally and on the VM; changed Python
  modules compiled, browser scripts passed `node --check`, and diff hygiene
  passed.
- Published and deployed to main/VM at `7f0243e`. The terminal service is
  active, `/static/app.js?v=19` returns HTTP 200, and unauthenticated root/API
  probes correctly return HTTP 401. Static JS checksums match local files.
  No production database rows or trading settings were changed.
- Status: DEPLOYED · VERIFIED on main and VM at `7f0243e`.

---

## HOW NEW SESSIONS USE THIS
1. Read `backlog.md` — rules, instructions, current status.
2. Read `EXECUTION_LOG.md` — exactly what shipped.
3. Read `DATA_REQUESTS.md` — what the owner provides next.
4. Read `PORTAL_REDESIGN.md` — vision & roadmap.
5. Continue from the last entry's status.

---

## INDEX - #001..#093, one line each (85 entries)

Full text for these lives in `EXECUTION_LOG_FULL.md`.

| # | what changed |
|---|---|
| #001 | regime.py — yfinance period fix |
| #002 | screener_engine.py — yfinance period + index fallback |
| #003 | db.py — central schema (29 tables) |
| #004 | meta_model.py — feature guard + bundle format |
| #005 | events + swing_live + deepdive — three fixes |
| #006 | backtest + swing_live + screener_engine — staleness |
| #007 | app.py — optional-panel guards |
| #008 | log_utils + daily_update + scheduler_bg + requirements split |
| #009 | setup.py v3.1 — impulse indexing bug fix |
| #010 | all_weather.py — all-weather swing mode |
| #011 | value_radar.py |
| #012 | value_radar wiring |
| #013 | fundamentals_tv.py — canonical fetcher |
| #014 | BACKLOG + EXECUTION_LOG restructure |
| #015 | Feature C — regime spectrum |
| #016 | Value Radar v2 — tiers + promoter/CFO enrichment |
| #017 | Sizing — fallback win-rate 0.35 |
| #018 | positional_scanner.py (ID3a) |
| #019 | alerts.py — unified alerts (ID7) |
| #020 | universe_helper.py (ID7) |
| #021 | trend_scanner.py (ID8) |
| #022 | universe_helper migration (ID7 cont.) |
| #023 | Scanners UI (ID9) |
| #024 | Trend v2 + meta_model v7 (33 features) |
| #025 | Trend v3 — unbounded score |
| #026 | validate.py v3 — fast walk-forward |
| #027 | Setup v3.2 — widen impulse |
| #028 | Setup v3.3 — widen 1c / PB |
| #029 | fast_wf.py — target sweep |
| #030 | Sizing v4 — quality multiplier |
| #031 | strategy_runs.py — durable ledger |
| #032 | Tranche exits tested (ID18) |
| #033 | Strategy runs dashboard |
| #034 | strategy_config.py — central config (ID19) |
| #035 | Deployment verification (ID21) |
| #036 | Graceful skips — ml_predict + sheets_sync |
| #037 | research_cockpit.py (ID22 v1) |
| #038 | Research Universe (ID22b) |
| #039 | Warm cache scheduler (ID22c) |
| #040 | Sector aggregation + sortable UI (ID23 / R24) |
| #041 | Fix warm_cache --force + CACHE_VERSION |
| #042 | Portal Phase 1 redesign |
| #043 | Rule engine + seed strategies (Phase 2 start) |
| #044 | Fix rule_engine numpy truth-value bug |
| #045 | Rule engine: failure breakdown diagnostic |
| #046 | Gap-up + impulse/pullback features; RCP/EP rewrite |
| #047 | Route ordering fix for /api/strategies/seed |
| #048 | strategies.js — use JSON key for API calls |
| #049 | ID42: in-browser strategy editor |
| #050 | ID43: strategy backtest sandbox |
| #051 | TV column probe (ID44 step 1) |
| #052 | Fundamentals v5 + schema migration (ID44 step 2) |
| #053 | Percentile scoring (ID45) |
| #054 | Candle behaviour analytics (ID47) |
| #055 | Signature matching (ID46) |
| #056 | Weekly setup_pool rebuild scheduler job |
| #057 | Pattern transparency + chart markers (ID48 + ID49) |
| #058 | Bearish pattern grading fix (ID53) |
| #059 | Compare mode + unified stock card (ID50 + ID51) |
| #060 | Famous Traders framework + John Crane (ID54 + ID55) |
| #062 | Trader #2 — Larry Spears (ID56) |
| #063 | Fix Larry Spears `_ma_trend` slope-check bug |
| #064 | Book extraction standard + feature registry (ID57 + ID58) |
| #065 | Trader #3 — James O'Shaughnessy |
| #066 | Trader #4 — Wesley Gray & Tobias Carlisle |
| #069 | Trader #5 — Janet Lowe |
| #070 | Trader #6 — Curtis Faith (Way of the Turtle) |
| #073 | Trader #7 — Alpesh Patel & Paresh Kiri |
| #075 | Trader #8 — Apurva Parikh |
| #076 | Trader #9 — Ishaan Agnihotri |
| #078 | Trader #10 — Steve Nison (Beyond Candlesticks) |
| #079 | Rule R39 + D12 logged |
| #080 | Trader #11 — Tushar Chande |
| #081 | Trader #12 — William O'Neil |
| #085 | Trader #14 — Aseem Singhal |
| #086 | R44 + R45 — Exit logic + wisdom extraction mandatory |
| #087 | Trader League + pre-deployment backtest (D20, ID77) |
| #088 | Copy-paste blocks rule (R47) + league replay hardening |
| #089 | Terminal data-clickability and navigation |
| #090 | Verify VM pre-season replay and real-money readiness |
| #091 | Source adapter framework and first migrations |
| #092 | Import KITE export as a quarantined research snapshot |
| #093 | Cross-attest KITE against ScanX and refresh confirmed fields |
| #094 | Apply source-aware NSE research audit |
| #095 | Audit remediation: fundamentals integrity |
