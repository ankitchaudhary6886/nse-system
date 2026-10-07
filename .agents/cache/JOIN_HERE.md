# JOIN HERE — NSE Intelligence Terminal, condensed system state

> Companion to `PROJECT_HANDOFF.md` (authoritative, owner-maintained).
> This file is the **agent-facing summary**: what the system is, the component
> map, what is verified broken right now, and where the traps are.
> Regenerate the `.json` facts with `.agents\build_cache.py`; edit this file by hand.

Last verified: **2026-10-05**, against `data/app.db` on the laptop and a full
read of the repo. Numbers cited as "live" come from `db_index.json` /
`FINDINGS.md` evidence blocks.

---

## 1. What it is, in one paragraph

A solo-owner, no-paid-services quant terminal for **NSE small/mid-cap momentum
swing trading** on daily bars. Strategy core is the Hiren Gabani
Stage-2 / VCP "master pullback" method (`setup.py` + `scanner.py` +
`strategy_config.py`). Around that sit institutional-flow, breadth, sector-RS,
delivery-%, pattern, DTW-template and LightGBM meta-model layers. It runs 24/7
on a free Oracle Cloud VM, is viewed from a phone browser via a FastAPI +
vanilla-JS terminal (`terminal_api.py` + `terminal/static/`), and pushes
Telegram alerts. A separate `trader_league.py` replay harness runs 14 trading
books at Rs 10 lakh each to sanity-check the home system against real NSE data.

The laptop (`C:\Users\Ankit\Desktop\nse_system`) is the **edit** machine and its
`data/app.db` is a **stale copy** (~40 days behind at the time of writing). The
VM at `140.238.226.249` is **production** and holds the fresh data.

---

## 2. Data flow (the whole system on one line)

```
sources ──► adapters/ingest ──► data/app.db ──► analytics ──► gates ──► signals
                                                              │
                            terminal_api.py ──► terminal/static/*.js ──► phone
                                                              │
                                             scheduler_bg.py (19 IST jobs)
                                                              │
                                          alerts.py ──► Telegram
```

### 2.1 Sources → DB

| Source | Via | Lands in | Notes |
|---|---|---|---|
| Yahoo Finance | `data_sources/adapters/yahoo.py` (registry) **and ~14 direct `yfinance` call sites** | `prices_daily`, `price_meta` | Direct callers are an open migration item (DR/ID52) |
| TradingView India scanner | `adapters/tradingview.py` (registry) + `broad_scan.py` (direct) | `fundamentals`, `universe_broad` | `fundamentals_tv.py` is the canonical fundamentals fetcher |
| NSE website | `universe.py` (3-way fallback), `delivery.py`, `macro.py`, `institutional.py` | `stocks`, `delivery_daily`, `macro_flow`, `institutional` | NSE blocks datacenter IPs → these fail on the VM by design; `macro.py set F D` is the manual path |
| Google News RSS + FinBERT | `sentiment.py` | `sentiment_headlines`, `sentiment_results` | 14-day age cut |
| KITE / ScanX CSV exports | `kite_import.py`, `scanx_import.py`, `kite_reconcile.py` | `kite_market_snapshots`, `scanx_fundamentals_snapshots`, `market_data_attestations` | Research-only; **not** point-in-time. Dry-run by default |

### 2.2 DB → analytics (the daily chain)

`daily_update.py` runs 10 stages in this exact order, each isolated in `_safe()`
so one failure never stops the rest (`jobs_index.json.daily_update_trace`):

| # | Stage | Module | Entry |
|---|---|---|---|
| 1 | prices | `ingest_prices` | `run` |
| 2 | technicals | `technicals` | `compute_all` |
| 3 | scan | `scan` | `run` |
| 4 | ml | `ml_predict` | `predict_all` |
| 5 | pwin | `pwin_cache` | `refresh_all` |
| 6 | toppicks | `top_picks` | `compute(force=True)` |
| 7 | events | `events` | `detect` |
| 8 | swing | `swing_live` | `update_outcomes` + `scan` |
| 9 | telegram | `telegram_alerts` | `report` |
| 10 | sheets | `sheets_sync` | `sync` |

**Ordering defect (F-09):** `scan` (3) reads `ml_predictions` but `ml_predict`
(4) writes it — today's ML score is invisible to today's scan.

### 2.3 Gates a new swing signal must survive

`swing_live.scan()`, in order — re-read before touching any of them:

1. `regime.MarketRegime.compute()` — index close vs EMA10 (raises if no benchmark)
2. `regime_spectrum` allows normal swing? if not → all-weather path (own breadth gate ≥ 0.35)
3. `breadth.breadth_ok()` — `above50 ≥ 0.50` **and** `adv ≥ dec`
4. `sector_gate` — symbol's sector in the **top-3** by `0.6*perf1m + 0.4*perf3m`
5. ≥ 280 price bars
6. `scanner.Screener.evaluate().passed` — Stage-2 + liquidity + momentum
7. `setup.SetupDetector.detect().triggered` — the official v3 pattern
8. **staleness guard** — `signal_date == last bar date` (no pattern more than `MAX_SHIFT=2` sessions old)
9. `fund_veto.vetoed()` — `debt_eq > 3` OR `roce < 8` OR `promoter < 20`
10. INSERT `swing_signals` (PENDING)
11. `alerts.notify_setup()` — **re-runs the veto** (F-13)

`top_picks` and `patterns` apply the veto too, with their own orderings.

### 2.4 Outputs

| Output | Producer | Consumed by |
|---|---|---|
| Telegram alerts + candlestick PNG | `alerts.py`, `chart_img.py` | phone |
| 7-tab web terminal | `terminal_api.py` (62 routes) | `terminal/static/*.js` |
| Trader League scoreboards | `trader_league.py` | `/api/league/*`, Telegram Sat 11:00 |
| Forward validation | `ledger.py`, `validate.py` | Ledger tab |

---

## 3. Component map (12 components)

Each component below is a candidate **subagent boundary** — see
`.agents/SUBAGENTS.md` for the roster that maps 1:1 onto these.

| # | Component | Owns (primary files) | Key tables | Entrypoints |
|---|---|---|---|---|
| C1 | **Data acquisition & providers** | `data_sources/*`, `ingest_*.py`, `universe*.py`, `broad_scan.py` | `prices_daily`, `price_meta`, `universe_broad`, `stocks` | `ingest_prices.run`, `universe.main` |
| C2 | **Data quality, provenance & promotion** | `data_quality.py`, `data_sources/provenance.py`, `fundamentals_store.py`, `kite_import.py`, `scanx_import.py`, `kite_reconcile.py`, `*_snapshot_report.py` | `data_quality_log`, `*_snapshots`, `market_data_attestations` | CLI per module |
| C3 | **Strategy core (setup + screen)** | `strategy_config.py`, `setup.py`, `scanner.py`, `screener_engine.py`, `scoring.py`, `rule_engine.py` | `scan_results`, `scan_reasons`, `pipeline`, `data/strategies.json` | `scan.run` |
| C4 | **Market context & gates** | `regime.py`, `regime_spectrum.py`, `breadth.py`, `sector_gate.py`, `macro.py`, `fund_veto.py` | `breadth_daily`, `macro_flow`, `fundamentals` | `swing_live.scan` |
| C5 | **Flow & accumulation** | `institutional.py`, `delivery.py`, `events.py`, `corporate.py` | `institutional`, `delivery_daily`, `events`, `corp_calendar` | `institutional.refresh`, `delivery.fetch` |
| C6 | **Patterns & shape matching** | `patterns.py`, `pattern_grader.py`, `template_match.py`, `build_setup_pool.py` | `pattern_tags`, `pattern_grades`, `template_scores`, `setup_pool` | `patterns.run`, `template_match.run` |
| C7 | **ML meta-model & P(WIN)** | `meta_model.py`, `ml_features.py`, `ml_train.py`, `ml_predict.py`, `pwin_cache.py`, `model_report.py` | `ml_predictions`, `pwin_daily`, `model_runs`; `data/*.pkl` | `meta_model.py train\|SYM` |
| C8 | **Signals, ranking & exit discipline** | `swing_live.py`, `top_picks.py`, `all_weather.py`, `sizing.py`, `ledger.py`, `validate.py` | `swing_signals`, `top_picks`, `validation_log`, `settings` | `swing_live.py`, `top_picks.py` |
| C9 | **Traders & book library** | `traders/*.py` (15 files, ~70 methods), `EXIT_LOGIC.md`, `MARKET_WISDOM.md` | — | `traders.list_traders`, `/api/traders/*` |
| C10 | **Trader League & backtesting** | `trader_league.py`, `strategy_backtest.py`, `strategy_runs.py`, `backtest.py`, `fast_wf.py` | `league_*`, `strategy_runs` | `trader_league.py <cmd>` |
| C11 | **API & terminal presentation** | `terminal_api.py`, `terminal/static/*` | reads all | uvicorn `terminal_api:app` |
| C12 | **Orchestration, deploy & ops** | `scheduler_bg.py`, `daily_update.py`, `log_utils.py`, `verify_deployment.py`, `db.py`, `config.py`, `alerts.py` | `settings`, `data_quality_log` | `scheduler_bg.start` |

Explicitly **out of the live system** (safe to ignore unless asked):
`app.py` (legacy Streamlit, referenced by nothing), `swing.py` (legacy third
scorer), `broad_scan`/`quick_*`/`tv_probe*` diagnostics, `bullflag_rescue.py`
(closed experiment), `trading-agents-swarm/` (separate git repo, not imported).

---

## 4. Where the traps are (read before editing)

1. **Whole files only.** Owner rule R1/§4.4 — a partial edit once caused a full
   outage. Never hand back a fragment.
2. **Copy-paste blocks for git/VM.** Rule R47 — one complete block per place
   (Laptop PowerShell · SSH · VM), each self-contained, with expected output.
3. **Verify before claiming success.** `systemctl status` + `journalctl`
   (§4.5). A command exiting 0 is not evidence the deploy worked.
4. **Restart rules.** Backend `.py` → `sudo systemctl restart nse-terminal`.
   `terminal/static/*` → no restart, but **bump the `?v=`** in `index.html`
   (authoritative list: `api_index.json.asset_versions`).
5. **Never `DROP`.** `CREATE TABLE IF NOT EXISTS` + `INSERT OR REPLACE`
   / `DELETE`+`INSERT`. New columns go through `db.py:MIGRATIONS`.
6. **Every optional integration stays in `try/except`.** The UI must never blank.
7. **Scheduler times are IST; journal timestamps are UTC** (IST = UTC + 5:30).
   This is the single most common mis-read during incident triage.
8. **Auth is opt-in per route.** `terminal_api.py` has no global dependency; a
   new route without `Depends(verify_user)` is silently public (`F-05`).
9. **Route order matters.** Literal paths must be registered *before* the
   `{symbol}`/`{name}` catch-all on the same prefix (`F-06`).
10. **`/static` and `/docs` are unauthenticated** (`F-05`). No secrets there.
11. **NSE is blocked from datacenter IPs** — delivery/macro/universe fetches
    failing on the VM is expected, not a bug.
12. **yfinance period strings** must be valid (`"5y"`, `"max"`) or explicit
    start/end dates. `"120d"` / `"18mo"` raise.
13. **No paid services.** Oracle free tier: avoid heavy concurrent jobs.
14. **Two DBs exist.** Laptop = stale edit copy; VM = production. Never quote
    local row counts as production facts.

---

## 5. Current state

**Working end-to-end:** the terminal, the scheduler, the 19 cron jobs, the
traders library and its registry, the League harness, the source-adapter
registry + `/api/sources` health, `db.py`'s central schema + migrations.

**Verified broken / inert (details + evidence in `FINDINGS.md`):**

| ID | Sev | One-line |
|---|---|---|
| F-01 | HIGH | Laptop `data/app.db` is ~40 days stale (prices end 2026-08-26) |
| F-02 | CRITICAL | `data/meta_model.pkl` is a bare estimator → `get_model()` returns None → P(WIN), Top Picks, meta features all dead |
| F-03 | CRITICAL | `data/ml_models.pkl` is `v0.1` but `ml_predict` demands `v0.2-pit-safe` → `ml_predictions` empty → `scan.py` rejects every symbol |
| F-04 | HIGH | `pattern_grades` = 0 rows and `settings.pattern_gate` is `{}` → the empirical 60 % pattern gate is vacuously open (all 6 patterns enabled) |
| F-05 | HIGH | `/static/*`, `/docs`, `/redoc`, `/openapi.json` unauthenticated; auth is opt-in per route |
| F-06 | MED | `{symbol}` catch-all route shadowing risk on 7 prefixes |
| F-07 | MED | `window.loadResearchSectors` is never exported → Research Sectors never refreshes on global Refresh |
| F-08 | MED | `deployment.js` is not loaded; wiring it as-is double-binds `#refreshBtn` |
| F-09 | MED | `daily_update` runs `ml_predict` *after* `scan` → today's ML never used today |
| F-10 | MED | `fundamentals_tv.run(N)` truncates an alphabetically-sorted list → not top-N by market cap |
| F-11 | MED | `data_quality.py` does `DELETE FROM data_quality_log` each run → no history |
| F-12 | LOW | `sizing.py` has no Kelly maths despite the "half-Kelly" name; `SIZING.B_PAYOFF`/`FALLBACK_WINRATE` are referenced nowhere |
| F-13 | LOW | A swing symbol is veto-checked twice and can emit a "suppressed" Telegram *after* the row was inserted |
| F-14 | LOW | `BULL_FLAG` is a zombie: killed as a detector but still in `pattern_grader.ALL_PATTERNS`, `template_match.TEMPLATES`, `PAT_MAP`, meta features (+161 orphan tags) |
| F-15 | LOW | Duplicated universe SQL in 12+ modules; duplicated Stage-2 logic in `screener_engine.py`; duplicated forward simulation in `build_setup_pool` vs `research_cockpit` |
| F-16 | FIXED | `verify_deployment.py` hardcoded a credential (scrubbed; login gate removed) |

**Gated, do NOT act on without explicit owner approval:**
ID71 legacy proxy cleanup (blocked on DR-01 v2), real-money trading (verdict
NOT READY — PF 0.93 vs 1.3 bar, 0/30 live paper trades), Streamlit retirement,
credential rotation, HTTPS/domain.
