# BACKLOG — Ideas & Feature Requests

Auto-updated as new ideas come in. Not a commitment, not a schedule.
Format: `## [YYYY-MM-DD] Title` then bullet points.

Legend:
- IN PROGRESS = being built now
- DONE        = shipped, verified
- IDEA        = captured, not started
- DEFERRED    = owner chose to skip for now
- FUTURE      = executable after skeleton runs purposefully

---

## [2026-09-12] Trim / unify / simplify redundant code  · FUTURE
The system has grown organically. Consolidation pass needed:
- Two screeners exist: `scanner.py` (Screener) and `screener_engine.py`. Pick one.
- Two alert senders: `telegram_alerts.py` + `swing_alerts.py`. Merge into one.
- Two UIs: `app.py` (legacy Streamlit) + `terminal_api.py` + `terminal/static/*`. Retire Streamlit.
- Multiple fundamental fetchers: `fundamentals_compute`, `fundamentals_refresh`, `fundamentals_tv`, `ingest_fundamentals`. Consolidate to one canonical path.
- Multiple universe sources: `broad_scan`, `universe`, `main.smallcap_universe`. Single source.
- Multiple price ingesters: `ingest_prices`, `ingest_smallcaps`, `ingest_missing`, `deepdive.download_prices`. One writer.
- Config: one file, no drift.
- Logger: already unified via `log_utils.py`.
Goal: fewer files, clearer ownership, easier to reason about. Do AFTER skeleton runs.

## [2026-09-12] Custom scanners — swing + positional  · FUTURE
Build dedicated screeners for two horizons:
- Swing scanner (days–weeks) — partially covered by screener_engine.py
- Positional scanner (months) — new
Each with its own filter set.

## [2026-09-12] Free data source expansion — ScanX / others  · FUTURE
Explore ScanX and other free sources to download historical data, charts, bulk exports.
Goal: supplement / backup yfinance. Zero paid services.

## [2026-09-12] "Feeding of life into stocks"  · FUTURE (needs clarification)
Interpretation TBD. Likely: enrich each tracked stock with narrative/context
(news, filings, promoter activity) so the system sees the stock's story.
Confirm scope when we pick it up.

## [2026-09-12] Universe split  · FUTURE
- Fundamentals pipeline covers **Nifty 1000** (broad quality/value coverage).
- Active swing hunting focuses on **midcap + smallcap band** (mcap 1,000–8,000 cr).
- Different layers use different universes.

---

## [2026-09-12] All-weather swing mode  · DONE
Defensive-regime swing entries. >= 25% below 52w high, within 15% of 52w low,
hammer/bullish-engulfing reversal, risk <= 5%, half size. Quality tier is soft.
Deployed; verified with 115 candidates, 5 signals, Telegram fired.

## [2026-09-12] Long-term Value Radar  · IN PROGRESS
Quality names in downturns. Composite = 0.6*value + 0.4*quality.
Tiers A/B/C. Weekly job. Telegram alert. Independent of swing.
`value_radar.py` shipped. Scheduler + API + UI wiring in this batch.

## [2026-09-12] Regime spectrum (5 levels, not binary)  · IDEA
Replace BULLISH/DEFENSIVE with:
STRONG_BULL, BULL, NEUTRAL, WEAK, CAPITULATION.
Position size and filter strictness scale with level.

## [2026-09-12] Fix impulse calculation bug in setup.py  · DONE
setup.py v3.1 — negative/positive index mix inflated impulse 10–30x.
Verified: 433 tested, 220 pass screener, impulse range 35.1–46.8%.

## [2026-09-12] Backlog file naming fix  · DONE
Windows case-sensitivity prevented BACKLOG.md from committing. Now use `git add -A`.

## [2026-09-12] Settings env / admin creds  · DEFERRED
## [2026-09-12] HTTPS via nginx + certbot  · DEFERRED
## [2026-09-12] Rotate secrets  · DEFERRED