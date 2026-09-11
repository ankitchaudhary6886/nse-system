# BACKLOG — Ideas & Feature Requests

Auto-updated as new ideas come in. Not a commitment, not a schedule.
Format: `## [YYYY-MM-DD] Title` then bullet points.

Legend:
- IN PROGRESS = being built now
- DONE        = shipped, verified
- IDEA        = captured, not started
- DEFERRED    = owner chose to skip for now
- FUTURE      = executable idea, to be done AFTER skeleton runs purposefully

---

## [2026-09-12] Custom scanners — swing + positional  · FUTURE
Build dedicated screeners for two horizons:
- Swing scanner (days–weeks) — already partially covered by screener_engine.py
- Positional scanner (months) — new
Each with its own filter set. Separate from the current combined scanner.

## [2026-09-12] Free data source expansion — ScanX / others  · FUTURE
Explore ScanX and other free sources to download:
- Historical data files (OHLCV, fundamentals)
- Charts / images
- Bulk exports
Goal: supplement / backup yfinance. Zero paid services. Must be usable from the VM.

## [2026-09-12] "Feeding of life into stocks"  · FUTURE (needs clarification)
Interpretation TBD. Likely: enrich each tracked stock with narrative and context
(news, filings, promoter activity, sentiment, social) so the system sees the
stock's *story*, not just numbers.
Alternative reading: keep per-stock data freshness / "aliveness" (staleness tracking).
Confirm scope when we pick this up.

## [2026-09-12] Universe split — Nifty 1000 fundamentals, midcaps+smallcaps swing  · FUTURE
- Fundamentals pipeline covers **Nifty 1000** (broad quality/value coverage).
- Active swing hunting focuses on **midcap + smallcap band** (mcap 1,000–8,000 cr).
- Different layers use different universes. Fundamentals feed quality/tiers;
  swing stays on the aggressive small/midcap band.

---

## [2026-09-12] All-weather swing mode  · DONE
Allow swing entries when regime is DEFENSIVE, guarded by stricter conditions.
Final spec (v2):
- >= 25% below 52w high AND within 15% of 52w low
- Hammer OR bullish engulfing reversal candle
- Risk <= 5%
- Quality tier is a SOFT tag (HIGH/MED/UNK), not a hard gate
- Half position size (owner rule, alert says so)
- Relaxed breadth: above50 >= 0.35 only
Status: `all_weather.py` + `swing_live.py` + `swing_alerts.py` deployed.
Verified: 115 candidates, 5 signals, Telegram alerts fired.

## [2026-09-12] Long-term Value Radar  · IN PROGRESS (Feature B)
Separate scanner for quality names in downturns, for accumulation.
- Quality score: ROCE, D/E, promoter holding, CFO+, profit growth
- Value score: >= 25% below 52w high, PE < sector median
- Composite = 0.6*value + 0.4*quality; tiers A/B/C
- Weekly job, Telegram alert
- Independent of swing system
Status: `value_radar.py` shipped, standalone tested on VM. Scheduler wiring pending.

## [2026-09-12] Regime spectrum (5 levels, not binary)  · IDEA
Replace BULLISH/DEFENSIVE with:
STRONG_BULL, BULL, NEUTRAL, WEAK, CAPITULATION.
Position size and filter strictness scale with level.

## [2026-09-12] Fix impulse calculation bug in setup.py  · DONE
setup.py v3.1 — was mixing negative/positive indexing, inflating impulse_pct
by 10–30x, causing 0 setups for years. Now uses positive indices throughout.
Verified on VM: 433 tested, 220 pass screener, impulse range 35.1–46.8%.

## [2026-09-12] Backlog file naming fix
Windows case-sensitivity caused `BACKLOG.md` to never commit. Switched to
`git add -A` in commit blocks.

## [2026-09-12] Settings env / admin creds  · DEFERRED
## [2026-09-12] HTTPS via nginx + certbot  · DEFERRED
## [2026-09-12] Rotate secrets (Telegram token, GCP key)  · DEFERRED

---

## How this file grows
Every new idea / request / possibility automatically gets a new
`## [date] Title` block added above. No deletions without a DONE marker.
Ideas with `FUTURE` tag are parked until the skeleton is running purposefully.