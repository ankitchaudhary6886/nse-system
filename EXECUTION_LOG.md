# EXECUTION LOG — durable record of every code batch

Purpose: this file survives chat migrations. A new AI session reads
BACKLOG.md + EXECUTION_LOG.md and knows the full history.

Format: each batch gets a numbered entry.
- **Files** — what was touched
- **What** — one-line summary
- **Verify** — how it was validated (and by whom)
- **Status** — DEPLOYED · VERIFIED · REVERTED

---

## 2026-09-12

### #001 · regime.py — yfinance period fix
- Files: `regime.py`
- What: `period=f"{days}d"` invalid string → `start`/`end` dates. Fallback chain ^CNXSMALLCAP → ^CNXSC → NIFTY_SMALLCAP_100.NS → ^NSEI.
- Verify: VM test → `RegimeState(is_bullish=False, ...)` returned; benchmark = ^NSEI.
- Status: DEPLOYED · VERIFIED

### #002 · screener_engine.py — yfinance period fix + index fallback
- Files: `screener_engine.py`
- What: same yfinance bug fix + fallback list for index fetch.
- Verify: VM `python -c "import screener_engine"` OK; check_global_regime returns tuple.
- Status: DEPLOYED · VERIFIED

### #003 · db.py — central schema
- Files: `db.py`
- What: all tables moved into SCHEMA (single source). 27 → 29 tables on VM.
- Verify: VM `SELECT name FROM sqlite_master` shows 29 tables; sentiment_headlines + corp_calendar now present.
- Status: DEPLOYED · VERIFIED

### #004 · meta_model.py — feature guard + bundle format
- Files: `meta_model.py`
- What: `get_model()` refuses incompatible feature counts; train saves `{model, features, version}`; score_symbol reordered so `_attach_extra_feats` runs before dropna.
- Verify: laptop import OK; VM retrain → rows 120156, AUC 0.629, top-10% 63.0%, model saved.
- Status: DEPLOYED · VERIFIED

### #005 · events + swing_live + deepdive — three fixes
- Files: `events.py`, `swing_live.py`, `deepdive.py`
- What: events uses latest technicals date; swing veto runs before insert; deepdive wraps ML in try/except.
- Verify: laptop imports OK; VM events detect runs clean.
- Status: DEPLOYED · VERIFIED

### #006 · backtest + swing_live + screener_engine — staleness
- Files: `backtest.py`, `swing_live.py`, `screener_engine.py`
- What: only accept patterns completed on current bar; add fallback index list.
- Verify: laptop imports OK; VM same.
- Status: DEPLOYED · VERIFIED

### #007 · app.py — optional-panel guards
- Files: `app.py`
- What: `safe_rows` / `safe_read_sql` / `safe_call` helpers; all optional panels wrapped. CSS `@import` moved inside `<style>`.
- Verify: laptop `import app` OK.
- Status: DEPLOYED · VERIFIED

### #008 · log_utils + daily_update + scheduler_bg + requirements split
- Files: `log_utils.py` (new), `daily_update.py`, `scheduler_bg.py`, `requirements.txt`, `requirements-optional.txt` (new)
- What: rotating file logger; print → log.*; split heavy deps.
- Verify: laptop imports OK; VM `tail data/logs/scheduler.log` shows timestamps.
- Status: DEPLOYED · VERIFIED

### #009 · setup.py v3.1 — impulse indexing fix
- Files: `setup.py`
- What: impulse window used mixed negative/positive indices → inflated impulse by 10–30x → 0 setups. Now positive indices throughout.
- Verify: VM test — 433 tested, 220 pass screener, 2 setups, impulse range 35.1%–46.8%.
- Status: DEPLOYED · VERIFIED

### #010 · all_weather.py + swing_live + swing_alerts — all-weather mode
- Files: `all_weather.py` (new), `swing_live.py`, `swing_alerts.py`
- What: DEFENSIVE regime runs AW scan; quality tier soft; half size; Telegram alert. v2: near-low relaxed to 15%, quality soft tag.
- Verify: VM `python all_weather.py` → 5 setups (INDIASHLTR, ABFRL, ALOKINDS, AHLUCONT, HGINFRA); Telegram 200 OK ×2 each; stored with mode='ALL_WEATHER'.
- Status: DEPLOYED · VERIFIED

### #011 · value_radar.py
- Files: `value_radar.py` (new)
- What: quality + value scoring; tier A/B/C; weekly Sunday 09:00 IST; Telegram alert; independent of swing.
- Verify: VM standalone run produced ranked candidates.
- Status: DEPLOYED · VERIFIED

### #012 · value_radar wiring
- Files: `scheduler_bg.py`, `terminal_api.py`, `terminal/static/index.html`, `terminal/static/app.js`
- What: weekly job, `/api/value-radar` endpoint, Value Radar card in Radar view.
- Verify: laptop imports OK; VM restart OK.
- Status: DEPLOYED · VERIFIED

### #013 · fundamentals_tv.py + scheduler_bg.py — canonical fetcher
- Files: `fundamentals_tv.py` (replaced), `scheduler_bg.py`
- What: TradingView India scanner, batched + retries + logging. Fills `fundamentals` table. Weekly Sat 08:00 IST.
- Verify: pending — VM run pending.
- Status: DEPLOYED · AWAITING VERIFICATION

### #014 · BACKLOG + EXECUTION_LOG restructure
- Files: `BACKLOG.md`, `EXECUTION_LOG.md` (new)
- What: layered instruction capture (RULES / INSTRUCTIONS / DEMANDS / IDEAS / IMAGINATIONS); durable execution log; designed for chat migration.
- Verify: file presence + manual review.
- Status: DEPLOYED · VERIFIED

---

## HOW NEW SESSIONS USE THIS
1. Read `BACKLOG.md` — know the rules, ideas, current status.
2. Read `EXECUTION_LOG.md` — know exactly what shipped and when.
3. Continue from the last entry's status (`AWAITING VERIFICATION` or the next task in BACKLOG's status summary).