# JOIN HERE — NSE Intelligence Terminal, condensed system state

> Companion to `PROJECT_HANDOFF.md` (authoritative, owner-maintained).
> This file is the **agent-facing summary**: what the system is, the component
> map, what is verified broken right now, and where the traps are.
> Regenerate the `.json` facts with `.agents\build_cache.py`; edit this file by hand.

Last verified: **2026-10-19**, against `data/app.db` on the laptop, against
**production** (`fe0f09d`, SSH probe), and against on-disk code. Numbers cited
as "live" come from `db_index.json` / `FINDINGS.md` evidence blocks — note
`MANIFEST.json.generated_at` may be older than the code (see F-26).

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

`daily_update.py` runs **12** stages in this exact order (was 10 on
2026-10-05 — `fyers` and `breadth` were added), each isolated in `_safe()` so
one failure never stops the rest (`jobs_index.json.daily_update_trace`):

| # | Stage | Module | Entry |
|---|---|---|---|
| 1 | fyers | `ingest_fyers` | `sync_recent(days=15)` — authenticated feed **first**, missing token is not an outage |
| 2 | prices | `ingest_prices` | `run` |
| 3 | technicals | `technicals` | `compute_all` |
| 4 | breadth | `breadth` | `compute(force=True)` — second half of the regime gate |
| 5 | ml | `ml_predict` | `predict_all` |
| 6 | scan | `scan` | `run` |
| 7 | pwin | `pwin_cache` | `refresh_all` |
| 8 | toppicks | `top_picks` | `compute(force=True)` |
| 9 | events | `events` | `detect` |
| 10 | swing | `swing_live` | `update_outcomes` + `scan` |
| 11 | telegram | `telegram_alerts` | `report` |
| 12 | sheets | `sheets_sync` | `sync` |

**Ordering defect (F-09) — FIXED.** `ml` (5) now runs **before** `scan` (6),
with a comment at the call site saying why. `refresh_pipeline.py` (the one-click
⚡ Data button) uses the same ML → scan order. Verified 2026-10-19.

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
11. `alerts.notify_setup()` — **uses the verdict from step 9** (F-13 fixed
    2026-10-19: `veto=(bad, why)` is passed in, so the veto runs once and the
    alert can never contradict the committed row)

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
8. **There is no auth at all.** The gate was removed wholesale on 2026-10-07
   (owner decision, `.agents/auth-verify-report.md`); `verify_user` no longer
   exists. Every route — and `/static`, `/docs`, `/redoc` — is public by
   design. Never put a secret in `terminal/static/`, and never re-add a
   per-route gate without an explicit owner decision (`F-05`).
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
| F-01 | ~~HIGH~~ **FIXED** | laptop DB was stale — synced by the 2026-10-18 rebuild (`prices_daily` → 2026-10-16) |
| F-02 | ~~CRITICAL~~ **RETRACTED** | P(WIN) chain was healthy in production all along (`pwin_daily` 28,310 rows thru 2026-10-18) |
| F-03 | ~~CRITICAL~~ **FIXED** | `ml_models.pkl` is `v0.2-pit-safe`; `ml_predictions` 25,173 rows on both machines |
| F-04 | ~~HIGH~~ **FIXED** | `pattern_gate` populated 2026-10-18 with real win rates; `pattern_grades` = 59,697 |
| F-05 | HIGH | **No auth on any route** (gate removed 2026-10-07, owner decision). Password + Telegram token still live in *git history* → rotation is owner-gated |
| F-06 | MED | `{symbol}` catch-all route shadowing risk — advisory; spot-checked OK as of 2026-10-19 |
| F-07 | ~~MED~~ **RETRACTED** | false positive — classic script, `window.loadResearchSectors` proved `"function"` live |
| F-08 | ~~MED~~ **FIXED** | `deployment.js` no longer exists; `app.js:961` owns `loadDeployment` |
| F-09 | ~~MED~~ **FIXED** | `ml` now runs before `scan`; chain is 12 stages |
| F-10 | ~~MED~~ **FIXED** | `run N` now ranks by `mcap_cr DESC` before truncating (CLI-only impact) |
| F-11 | ~~MED~~ **FIXED** | log is append + prune to `HISTORY_RUNS = 60`; no longer wiped each run |
| F-12 | ~~LOW~~ **RESOLVED** | owner call made 2026-10-19: no Kelly and no machine-chosen quantity — `suggest()` returns caps only |
| F-13 | ~~LOW~~ **FIXED** | veto computed once in `swing_live` and passed into the alert; gate order unchanged |
| F-14 | LOW | `BULL_FLAG` still in `pattern_grader`/`template_match`/`PAT_MAP` (historical tags kept on purpose) |
| F-15 | LOW | **3 of 4 duplication items fixed 2026-10-23** (Yahoo call sites, forward-sim, sector PE — all equivalence-proven). **1 remains and needs the owner**: Stage-2/VCP is *not* equivalent (old 13 pass vs canonical 41 over 745 symbols), so consolidating would change what the screener flags |
| F-16 | FIXED | `verify_deployment.py` credential scrubbed |
| **F-26** | **MED** | **the registers themselves were 14 days stale and contradicted the code — always check `MANIFEST.json.generated_at` vs `git log -1`** |

**Gated, do NOT act on without explicit owner approval:**
ID71 legacy proxy cleanup (blocked on DR-01 v2), real-money trading (verdict
NOT READY — PF 0.93 vs 1.3 bar, 0/30 live paper trades), Streamlit retirement,
**credential rotation** (password + Telegram token in git history), HTTPS/domain.
