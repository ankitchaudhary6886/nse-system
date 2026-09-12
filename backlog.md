# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories:
  - **RULES** — working-style rules, always active
  - **INSTRUCTIONS** — dated, specific directives
  - **DEMANDS** — hard requirements
  - **IDEAS** — feature / capability captures
  - **IMAGINATIONS** — visions / aspirations
- DONE items stay (never delete) so history survives.
- Execution details (what ran, when, output) live in `EXECUTION_LOG.md`.
- This file is designed to survive chat migration — a new AI session can
  read this + EXECUTION_LOG.md and continue without missing context.

---

## A. RULES  (always active)

- **R1**  Whole files only. No partial find/replace patches. Ever.
- **R2**  Plain English. Novice-friendly. Ask for screenshots when useful.
- **R3**  Environment: VS Code (Windows) + Oracle Cloud VM via SSH.
- **R4**  Every change = full file + 1 laptop block + 1 VM block. No line-by-line.
- **R5**  Batch related commands into one block per machine.
- **R6**  Skip credential / HTTPS / ops tasks unless explicitly asked.
- **R7**  Every new idea / request / brainstorm → auto-add to BACKLOG.
- **R8**  Instructions from Ankit are tagged with `#` prefix.
- **R9**  Every execution is logged in EXECUTION_LOG.md (durable).
- **R10** No pausing; keep momentum.

---

## B. INSTRUCTIONS  (dated)

### 2026-09-12
- **I1** Fix every PO issue identified + requirements.txt + PROJECT_HANDOFF.
- **I2** Sequence: Option 1 (all-weather) first; then 2, 3 sequentially.
- **I3** Update PROJECT_HANDOFF with all changes.
- **I4** Fix impulse calculation bug in setup.py.
- **I5** Fix sparse fundamentals data.
- **I6** Restructure BACKLOG by category (RULES / INSTRUCTIONS / DEMANDS / IDEAS / IMAGINATIONS).
- **I7** Create EXECUTION_LOG.md — durable, survives chat migration.

---

## C. DEMANDS  (hard requirements)

- **D1** Ideas auto-captured, never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace — do not pause for confirmation once a batch is agreed.

---

## D. IDEAS  (feature / capability capture)

### ID1 — All-weather swing mode  ·  **DONE**
Defensive-regime swing entries with stricter filters.
Final spec (v2):
- >= 25% below 52w high AND within 15% of 52w low
- Hammer OR bullish engulfing reversal candle
- Risk <= 5%
- Quality tier is a SOFT tag (HIGH / MED / UNK), not a hard gate
- Half position size (owner rule)
- Relaxed breadth: above50 >= 0.35 only
Files: `all_weather.py` · `swing_live.py` · `swing_alerts.py`
Verified: 115 candidates → 5 signals → Telegram fired.

### ID2 — Long-term Value Radar  ·  **IN PROGRESS**
Quality names in downturns for accumulation.
- Quality score: ROCE, D/E, promoter, CFO+, profit growth
- Value score: >= 25% below 52w high, PE < sector median
- Composite = 0.6*value + 0.4*quality; tiers A/B/C
- Weekly Sun 09:00 IST; Telegram alert
File: `value_radar.py` — shipped, wired to scheduler + API + UI.

### ID3 — Custom scanners: swing + positional  ·  **FUTURE**
- Swing scanner (days–weeks) — partially covered by `screener_engine.py`
- Positional scanner (months) — new
Separate filter sets, separate UI cards.

### ID4 — Free data source expansion (ScanX etc.)  ·  **FUTURE**
- Explore ScanX and other zero-cost sources
- Download historical data, charts, bulk exports
- Backup / supplement for yfinance
- Must run on the VM with no paid services

### ID5 — "Feeding of life into stocks"  ·  **FUTURE** (scope TBD)
- Enrich each tracked stock with narrative/context
- News, filings, promoter activity, social, sentiment
- System sees the *story*, not just numbers
- Confirm scope when we pick it up

### ID6 — Universe split  ·  **FUTURE**
- Fundamentals pipeline: **Nifty 1000** (broad quality/value coverage)
- Swing hunting: **midcap + smallcap band** (mcap 1,000–8,000 cr)
- Different layers → different universes

### ID7 — Trim / unify / simplify  ·  **FUTURE**
Consolidation pass — one canonical implementation per concern:
- Screeners: `scanner.py` vs `screener_engine.py` → pick one
- Alerts: `telegram_alerts.py` vs `swing_alerts.py` → merge
- UIs: `app.py` (legacy Streamlit) vs `terminal_api.py` → retire Streamlit
- Fundamentals fetchers: `fundamentals_compute`, `fundamentals_refresh`,
  `fundamentals_tv`, `ingest_fundamentals` → one
- Universe sources: `broad_scan`, `universe`, `main.smallcap_universe` → one
- Price ingesters: `ingest_prices`, `ingest_smallcaps`, `ingest_missing`,
  `deepdive.download_prices` → one writer
- Config: single source of truth
Goal: fewer files, clear ownership. Do AFTER skeleton runs.

---

## E. IMAGINATIONS  (visions)

### IM1 — Personal multi-strategy quant terminal
Free infra (Oracle VM), multi-horizon: swing, positional, value, all-weather.
Decision cockpit, not a trading bot. Runs 24/7. Delivers tiered opportunity lists.

### IM2 — Bear-market accumulation engine
Downturns are when quality goes on sale. The system must actively hunt
in WEAK / CAPITULATION regimes — not sit in cash.

### IM3 — Self-documenting, self-improving
Every action logged. Every metric recorded. Every iteration preserved
across chat migrations. The system improves because the trail is clear.

---

## F. STATUS SUMMARY

| ID  | Item                      | Status      |
|-----|---------------------------|-------------|
| R1–R10 | Rules                  | Active      |
| I1–I7 | Instructions            | Applied     |
| ID1 | All-weather swing         | DONE        |
| ID2 | Value Radar               | IN PROGRESS |
| ID3 | Custom scanners           | FUTURE      |
| ID4 | Free data sources         | FUTURE      |
| ID5 | Feed life into stocks     | FUTURE      |
| ID6 | Universe split            | FUTURE      |
| ID7 | Trim / unify / simplify   | FUTURE      |

---

## DEFERRED (owner chose to skip)
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets (Telegram token, GCP key)

---

## APPENDIX — historical DONE items (kept for audit)

- 2026-09-12: setup.py v3.1 — impulse indexing bug fixed (verified).
- 2026-09-12: db.py central schema — all tables (verified, 29 on VM).
- 2026-09-12: meta_model v6 — feature guard + bundle format + retrain.
- 2026-09-12: events.py — use latest technicals date.
- 2026-09-12: swing_live.py — veto before insert + staleness guard.
- 2026-09-12: deepdive.py — try/except around optional ML.
- 2026-09-12: backtest.py — stale-signal guard.
- 2026-09-12: app.py — optional-panel guards + CSS fix.
- 2026-09-12: regime.py + screener_engine.py — yfinance period fix.
- 2026-09-12: log_utils.py + daily_update + scheduler_bg — structured logging.
- 2026-09-12: requirements.txt split (core + optional).