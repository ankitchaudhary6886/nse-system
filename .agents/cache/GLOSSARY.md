# GLOSSARY — domain and system vocabulary

Disambiguation matters here: several words mean different things in the code
than they do in trading books. Read this before acting on a term.

---

## A. Trading terminology used by this system

| Term | Meaning in this codebase |
|---|---|
| **Stage-2** | O'Neil/Weinstein uptrend definition: price above a rising 200-DMA. Gate in `scanner.Screener.evaluate`. |
| **VCP** | Volatility Contraction Pattern (Minervini). Successive pullbacks each smaller and quieter. Encoded as `setup.shape_score` (0-100) and as a DTW template in `template_match.py`. |
| **Master pullback / Gabani setup** | The system's official entry: impulse up 18-75 % within 90 bars, then an orderly 6-25 % / 6-20 day pullback into the EMA10-EMA20 zone, on drying volume, ending in a tight "mother bar". `setup.py` + `strategy_config.SETUP`. |
| **Mother bar** | The tight consolidation bar(s) whose high becomes the entry trigger. |
| **Impulse** | The advance preceding the pullback. Must be ≥ 0.18 and ≤ 0.75 of the pre-impulse low. |
| **PDL** | Pattern-day low — the stop reference for the official setup. |
| **R / R-multiple** | Risk unit = entry − stop. +2R = 2 × risk in profit. Used for targets, grading (`ledger.py`) and League exits. |
| **MR / tranche** | Position-scaling stage. Lifecycle documented in PROJECT_HANDOFF §7: SL → breakeven at +2R → exit ⅓ at +4R → trail 10-EMA → trail 20-EMA / vertical climax. |
| **HTF** | High Tight Flag. ENABLED pattern (60.1 % graded WR). |
| **AscTriangle / DB / IHS** | Ascending Triangle / Double Bottom / Inverse Head & Shoulders. ENABLED patterns (63.8 / 63.0 / 67.3 %). |
| **H&S Top warning** | Bearish informational signal (`TOP_WARNING`, rule R43). Not a short. |
| **BULL_FLAG** | **Killed** 2026-09-17 after rescue variants scored 53.0-55.9 % WR against a 60 % bar. Historical tags retained. See `FINDINGS.md` F-14. |
| **Delivery %** | Share of traded quantity actually delivered (taken for custody) — an institutional-conviction proxy. `delivery.py` → `delivery_daily`. |
| **Accumulation** | Up-volume share over 20 days. `institutional.accumulation_score`. |
| **FII / DII** | Foreign / Domestic Institutional Investors' net cash flow, in ₹ crore. `macro.py` → `macro_flow`. |
| **Breadth** | % of the sample universe above its 50-EMA, plus advancers vs decliners. `breadth.py` → `breadth_daily`. |
| **Sector RS** | Sector relative strength = `0.6 × perf1m + 0.4 × perf3m`. Top-3 sectors are allowed. `sector_gate.py`. |
| **Regime** | 5-level spectrum from index close vs EMA10: `STRONG_BULL / BULL / NEUTRAL / WEAK / CAPITULATION`. `regime.py` + `regime_spectrum.py`. |
| **All-weather** | A counter-trend path that runs when regime forbids normal swing: deep-pullback hammer/engulfing near 52-week lows. `all_weather.py`. |
| **P(WIN)** | Model probability that the max high in the next 20 sessions reaches +10 %. `pwin_cache.py` / `meta_model.py`. |
| **DTW** | Dynamic Time Warping — shape similarity of the last 90 bars against templates. `template_match.py`. Similarity = `100 × exp(−dist/10)`. |
| **Top Picks** | Daily composite shortlist = `0.45·p_win + 0.25·accum + 0.15·sector_rs + 0.15·delivery` (+0.10 live-setup bonus). `top_picks.py`. |
| **Veto** | Fundamental disqualification: `debt_to_equity > 3` OR `roce < 8` OR `promoter_holding < 20`. A **missing** row passes. `fund_veto.py`. |
| **Drift check** | Alerts when live win rate over the last 40 graded signals drops below 35 %. `scheduler_bg._drift_check`. |
| **Staleness guard** | A setup is only valid if its `signal_date` equals the last price bar's date. `swing_live.py`. |
| **Point-in-time (PIT)** | A value known as of that historical date. A snapshot without a financial-period-end **and** a publication date is **not** PIT and must not enter replay. See DATA_REQUESTS DR-01/DR-21. |
| **Book / player** | In the League, one of 14 trading books (or `home`, our own system) trading ₹10 lakh each. |
| **Home** | The League player representing this system's own Swing Desk pipeline. |

---

## B. System-internal terms

| Term | Meaning |
|---|---|
| **The three repos** | This working tree (`C:\Users\Ankit\Desktop\nse_system`), the private GitHub repo `ankitchaudhary6886/nse-system`, and the VM clone `~/nse-system`. `trading-agents-swarm/` is a nested **separate** git repo, not imported by the system. |
| **Laptop vs VM** | Laptop = edit + stale DB. VM (`140.238.226.249`, user `ubuntu`) = production. `data/*.db` and `data/*.pkl` are gitignored, so each machine has its own data. |
| **VM service** | `nse-terminal.service` → `uvicorn terminal_api:app --host 0.0.0.0 --port 8000`, `PYTHONUNBUFFERED=1`. Optional legacy `nse.service` → Streamlit :8501. |
| **Golden rules** | PROJECT_HANDOFF §4 — ten non-negotiable edit/deploy rules. Summarised in `JOIN_HERE.md` §4. |
| **R-rules** | Owner rules IDs (R1…R47). Trader-relevant ones: R30 setup-only, R35 bug-safety, R38/R40 structured exits, R41 overlap marking, R42 no indicator proxies, R43 LONG_ENTRY vs TOP_WARNING, R44 EXIT_LOGIC entry, R45 wisdom entry, R47 whole copy-paste blocks. |
| **Provider / adapter** | `data_sources/core.py` — `SourceAdapter` protocol, `SourceRegistry` with ordered explicit fallback, `RateWindow`, `SourceHealth`, `ProviderFetchError`, `FetchResult`. Dataset names are dotted strings (`prices.daily_history`, `fundamentals.tv_batch`, `universe.nse_constituents`, `universe.chartink_symbols`). |
| **Promotion** | Moving a value from an isolated research snapshot into a live table, only via an explicit per-field rule with before/after evidence. `kite_reconcile.py` is the reference implementation. |
| **Snapshot (research-only)** | `scanx_fundamentals_snapshots`, `kite_market_snapshots`. Importing them must never affect scores, vetoes, signals or backtests. |
| **Attestation** | `market_data_attestations` — the ledger of what a snapshot claimed, whether it was applied, and if not why (e.g. `attested_stale_snapshot_not_applied`). |
| **Code hash** | `trader_league._code_hash(slug)` — `sha1[:12]` of the trader file (or of `SETUP`+`SCREENER`+`setup.py`+`scanner.py` for `home`). Drives `replay --changed`. |
| **`--changed` replay** | Re-runs only players whose code or settings changed since the last replay. |
| **INTRABAR "path"** | League simulator convention: a green bar is walked open→low→high→close (stop-first), a red bar open→high→low→close (target-first). `"worst"` always stops first. |
| **Worst-case fill** | Re-simulation with `INTRABAR="worst"`; must keep PF ≥ 1.0 to pass readiness. |
| **Gate (pattern)** | Empirical switch in `settings['pattern_gate']`: ≥30 graded tags and ≥60 % WR to ENABLE; 15-29 and ≥55 % provisional; unknown ⇒ enabled. Currently vacuously open (F-04). |
| **`?v=`** | Cache-buster suffix on `/static/*.js|css` in `index.html`. Editing a static file without bumping it serves a stale bundle from phone browsers. |
| **ctx-gate / TokenSculpt / caveman** | Third-party VS Code extensions that inject rules into the workspace (`CLAUDE.md`, `.github/hooks/ctx-gate.json`, `.cavemanrc`, `.context-ops/`). Their mandated tools (`rtk`, `codegraph_explore`, `skeleton_view`, `cache_lookup`, `redcon_rank`) are **not available in this environment** — see `FINDINGS.md` and `.agents/AGENT_SETUP.md`. |
| **MCP servers configured** | `.agents/mcp_config.json`: `token-cache` (TokenSculpt cache server) and `headroom`. `.vscode/mcp.json`: `codebase-memory`. Availability is reported in `.agents/AGENT_SETUP.md`. |

---

## C. Abbreviations

`EOD` end of day · `EMA/DMA/SMA` exponential/simple moving average (D = daily)
· `ATR` average true range · `RSI` relative strength index · `VCP` see above
· `RS` relative strength · `PF` profit factor · `DD` drawdown · `MC` Monte
Carlo · `WF` walk-forward · `PIT` point-in-time · `DQ` data quality · `DR-n`
a numbered owner data request (DATA_REQUESTS.md) · `ID-n` an idea/feature id
(backlog.md) · `R-n` an owner rule.
