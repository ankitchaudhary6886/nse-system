# NSE INTELLIGENCE TERMINAL — COMPLETE PROJECT HANDOFF
Doc date: 2026-09-12 · System version: 3.x · READ EVERYTHING BEFORE TOUCHING CODE

## 0. HOW TO USE THIS DOCUMENT
- This file lives at the project root: PROJECT_HANDOFF.md
- New chat first message: "Read PROJECT_HANDOFF.md fully and continue from Current Tasks."
- Append a line to the CHANGELOG (§16) at the end of every working session.

## 1. OWNER AND WORKING STYLE (rules for the AI)
- Owner: Ankit. Beginner coder. Windows 11 laptop. Uses phone as main screen.
- MUST send WHOLE files for any change. NEVER partial find/replace fragments (a fragment once caused a full outage).
- Minimize back-and-forth: give complete copy-paste-ready code + exact commands + expected output.
- Verify every deploy with command output (status/journal/grep) before declaring success.
- Plain English, lists, no jargon without explanation.

## 2. WHAT THE SYSTEM IS
A self-running quant terminal for NSE small/mid-cap momentum swing trading, implementing the
Hiren Gabani "Stage-2 / VCP master pullback" method plus institutional, breadth, sector and
machine-learning layers. Runs 24/7 on a FREE Oracle Cloud VM; viewed from phone/laptop browser;
sends Telegram alerts. No paid services anywhere.

Daily automation (IST): 15:30 data-quality → 15:45 EOD update → 16:00 delivery fetch →
16:15 swing scan+grading+drift → 16:45 institutional accumulation → 17:30 FII/DII macro →
18:05 patterns → 18:35 templates. Saturdays: 08:00 fundamentals refresh, 09:00 meta-model
retrain. Mondays: 08:00 Monte-Carlo. 1st of month: 10:00 walk-forward.

## 3. ACCESS MAP
- Laptop project folder: C:\Users\Ankit\Desktop\nse_system
- VM: Oracle Always Free Ubuntu, public IP 140.238.226.249, user ubuntu
- SSH: ssh -i C:\Users\Ankit\.ssh\nse.pem ubuntu@140.238.226.249
- Git repo (PRIVATE): https://github.com/ankitchaudhary6886/nse-system ; VM clone: ~/nse-system
- Modern terminal: http://140.238.226.249:8000 (FastAPI, HTTP Basic login)
- Legacy Streamlit backup: http://140.238.226.249:8501 (service nse; cosmetic @import glitch; can disable)
- Login: ADMIN_USER=ankit, ADMIN_PASS=ankitc21 (stored in ~/nse-system/.env on VM; change anytime)
- Telegram: token read from data/tg_secret.txt line 1 or env TELEGRAM_TOKEN; chat id line 2
  (or env TELEGRAM_CHAT_ID). Repo is private; rotate bot via @BotFather if leaked.
- Open ports (Oracle security list + iptables): TCP 8501, 8000 from 0.0.0.0/0
- Services: nse-terminal.service (uvicorn terminal_api:app --host 0.0.0.0 --port 8000,
  Environment=PYTHONUNBUFFERED=1); nse.service (streamlit, optional)
- VM python: always source venv/bin/activate first (venv at ~/nse-system/venv)

## 4. GOLDEN RULES (deploy & edit)
1. Laptop: edit → git add . → git commit -m "..." → git push. VM: cd ~/nse-system && git pull.
2. Backend .py change → sudo systemctl restart nse-terminal.
3. terminal/static/* change → NO restart; hard-refresh browser (phone: incognito or ?v=2).
4. WHOLE files only. No fragments. Ever.
5. Verify: sudo systemctl status nse-terminal --no-pager | head -5 ;
   sudo journalctl -u nse-terminal -n 300 --no-pager
6. Journal timestamps are UTC. IST = UTC + 5:30.
7. Every optional integration (telegram, yahoo, nse, meta) wrapped in try/except — UI must never blank.
8. DB changes: CREATE TABLE IF NOT EXISTS; upsert via INSERT OR REPLACE or DELETE+INSERT; never DROP.
9. data/*.db and data/*.pkl are gitignored (each machine has its own data).
10. Rollback safety: git checkout -- <file> ; git revert <commit>.

## 5. FILE INVENTORY (root unless noted)
- terminal_api.py — FastAPI backend: all /api/* endpoints + lifespan that starts the scheduler.
- terminal/static/index.html, app.js, style.css — modern terminal UI (views: Top Picks, Overview, Swing Desk, Screener, Patterns, Ledger, Radar).
- scheduler_bg.py — APScheduler cron jobs (§9). Uses log_utils.get_logger("scheduler").
- daily_update.py — crash-proof EOD pipeline (prices→technicals→scan→ml→pwin→toppicks→events→swing→telegram→sheets). Uses log_utils.get_logger("daily_update").
- log_utils.py — rotating file + console logger (data/logs/*.log, 14-day retention).
- ingest_prices.py, ingest_smallcaps.py, ingest_missing.py, broad_scan.py — data ingestion.
- technicals.py, scan.py, ml_predict.py, ml_train.py, events.py, sentiment.py — 2.0 analytics.
- regime.py — MarketRegime (index close vs EMA10; fallback chain ^CNXSMALLCAP → ^CNXSC → NIFTY_SMALLCAP_100.NS → ^NSEI; start/end dates, not period strings).
- breadth.py — %above-50EMA + adv/dec, cached daily in breadth_daily.
- sector_gate.py — sector RS ranking + top-3 leadership gate.
- scanner.py — fundamental/quality gates (Screener.evaluate).
- setup.py — SetupDetector OFFICIAL v3 + shape_score (0-100 pullback orderliness).
- swing_live.py — signal scan / outcome grading / backfill / Telegram hook. Veto gate runs BEFORE insert; staleness guard (pattern must end on last bar).
- swing_alerts.py — Telegram sender (delegates to telegram_alerts, .env fallback).
- telegram_alerts.py — legacy bot sender + daily report.
- meta_model.py — LightGBM meta-model: train / score_symbol / SHAP why / rank_symbols. v6, 30 features (adds pattern flags + dtw_sim + delivery_sim). Model saved as bundle {model, features, version}. get_model() refuses incompatible feature counts.
- top_picks.py — daily composite shortlist (cached in top_picks table). Skips vetoed symbols.
- institutional.py — accumulation proxy (up-volume share) + optional NSE delivery%.
- macro.py — FII/DII fetch (NSE, often blocked) + manual mode: python macro.py set F D.
- fundamentals_refresh.py — csv / yahoo / auto fundamentals refresh.
- sectors_refresh.py — fills stocks.sector via Yahoo info.
- data_quality.py — 6-check monitor + Telegram alerts.
- delivery.py — NSE bhavcopy delivery% scanner; delivery_daily table.
- patterns.py — rule-based pattern scanner (HTF, Asc Triangle, Double Bottom, Inverse H&S, H&S Top warning). BULL_FLAG killed by evidence 2026-09-17.
- pattern_grader.py — grades historical tags; empirical hit-rate gate (>=30 graded & >=60% WR = ENABLED).
- template_match.py — DTW shape matching vs VCP/HTF/BULL_FLAG/DOUBLE_BOTTOM templates.
- fund_veto.py — fundamental veto gate (debt_eq>3 / ROCE<8 / promoter<20).
- chart_img.py — candlestick PNG for Telegram alerts (matplotlib).
- ledger.py — paper-trade ledger + system stats.
- sizing.py — half-Kelly position sizing with caps.
- pwin_cache.py — daily P(WIN) cache.
- validate.py — Monte-Carlo + walk-forward validation harness.
- model_report.py — model_runs ledger.
- db.py — sqlite helper + central SCHEMA (all tables; data/app.db per machine).
- app.py — legacy Streamlit dashboard (backup only; all optional panels guarded with try/except).
- check_stock.py, diag.py, diagnose.py, db_check.py — diagnostics.
- deploy.bat, daily_update.bat — Windows helper scripts.

## 6. DATABASE TABLES (sqlite: data/app.db)
Central schema defined in db.py SCHEMA (all CREATE TABLE IF NOT EXISTS; safe to re-run).

Core:
prices_daily(symbol,date,open,high,low,close,volume, UNIQUE(symbol,date)) ·
price_meta(symbol,last_date,rows,updated_at) ·
universe_broad(symbol,name,mcap_cr,close,pe,perf1m,perf3m,relvol,updated_at) ·
stocks(symbol,name,sector,active,updated_at)

Fundamentals + sentiment:
fundamentals(symbol,name,sector,current_price,market_cap_cr,pe,pb,roe,roce,
  debt_to_equity,interest_coverage,operating_margin,net_profit_margin,
  sales_growth_3y,profit_growth_3y,promoter_holding,pledge_pct,fii_holding,
  dividend_yield,cfo_positive,uploaded_at) ·
sentiment_results(symbol,created_at,headline_count,positive,neutral,negative,
  sentiment_score,major_negative) ·
sentiment_headlines(symbol,created_at,title,age_days,label,prob) ·
corp_calendar(symbol,event_date,kind,detail)

Scans + pipeline:
scan_results(scan_date,symbol,passed,fundamental_score,ml_score,risk_flags,status,
  PRIMARY KEY(scan_date,symbol)) ·
scan_reasons(scan_date,symbol,rule_name,passed,actual_value,expected_text,reason_text) ·
pipeline(symbol,status,added_date,updated_date,reason,notes,review_date) ·
settings(key,value)

ML:
ml_predictions(symbol,prediction_date,ml_score_6m,ml_score_12m,final_ml_score,
  ml_rank,model_version, PRIMARY KEY(symbol,prediction_date)) ·
model_runs(run_date,note,rows,winners,auc,base_win,top10_win,n_features,
  price_only_auc,delta_auc,delta_top10, PRIMARY KEY(run_date,note)) ·
pwin_daily(symbol,date,p_win,why, PRIMARY KEY(symbol,date))

Technicals + market context:
technicals_daily(symbol,date,close,dma20,dma50,dma200,rsi,vol_ratio,high52,low52,
  mom20,above200, PRIMARY KEY(symbol,date)) ·
breadth_daily(date,above50,adv,dec) ·
institutional(symbol,date,accum,delivery_pct, UNIQUE(symbol,date)) ·
macro_flow(date,fii_net_cr,dii_net_cr) ·
delivery_daily(date,symbol,traded_qty,deliverable_qty,delivery_pct,close,created_at,
  PRIMARY KEY(date,symbol))

Patterns + templates:
pattern_tags(date,symbol,pattern,direction,status,confidence,breakout_level,
  stop_level,target_level,notes,params,created_at, PRIMARY KEY(date,symbol,pattern)) ·
pattern_grades(tag_date,symbol,pattern,outcome,exit_date,r_multiple,graded_at,
  PRIMARY KEY(tag_date,symbol,pattern)) ·
template_scores(date,symbol,template,similarity,created_at,
  PRIMARY KEY(date,symbol,template))

Swing + top picks:
swing_signals(signal_date,symbol,entry_trigger,stop,target,risk_pct,pullback,
  impulse,ema_zone,outcome,updated_at) ·
top_picks(date,symbol,p_win,accum,sector_rs,sector,setup,composite,delivery)

Events + quality + validation:
events(date,symbol,kind,text) ·
data_quality_log(run_at,status,severity,check_name,message) ·
validation_log(run_date,mode,payload, PRIMARY KEY(run_date,mode)) ·
webhook_events(created_at,source,symbol,kind,price,payload)

## 7. STRATEGY SPEC (OFFICIAL v3 + gates)
Setup checklist (ALL must pass): impulse 25-50% within 90 bars, price mostly above EMA10 during impulse;
pullback 12-20% over 6-15 days, orderly, no >=15% crash in any 3-day window; price touching EMA10/EMA20 zone;
volume dry-up (avg3 < 0.8x vol20 OR last < 0.7x vol20); mother bar = inside bar OR tight cluster
(range <= 0.9x ATR14, run of 2-4); pattern completed within last 3 sessions (MAX_SHIFT=2).
Entry/exit: trigger = mother-bar high; stop = pattern-day low (PDL); risk <= 5%; target = 2R.
Tranche lifecycle: initial SL → +2R move SL to breakeven → +4R exit 1/3 → trail 10EMA → trail 20EMA / vertical climax.
Gates before ANY new signal: regime BULLISH (index close > EMA10) AND breadth ok (above50 >= 0.5 AND adv >= dec)
AND symbol sector in top-3 by RS AND symbol not vetoed by fund_veto.
Grading: PENDING → OPEN → WIN / LOSS / EXPIRED (no trigger in 3d) / TIMEOUT (30d).
Staleness guard: signal_date must equal the last bar's date (no stale patterns).

## 8. ML SPEC
meta_model.py v6, LightGBM classifier. Label: max high within next 20 sessions >= +10%.
Weekly sampling per symbol; time-based 80/20 split (no lookahead).
30 features: mom1,mom3,mom6,d52,above200,slope200,pb,d10,d20,atr,rv,vc,roce,pe,
  debt_eq,promoter,sector_rs,sentiment,vcr,ret_std20,below52,
  pat_htf,pat_tri,pat_db,pat_flag,pat_ihs,pat_bear,pat_any,dtw_sim,delivery_sim.
Context features (roce,pe,debt_eq,promoter,sector_rs,sentiment) coerced with pd.to_numeric
(LightGBM rejects object dtypes) and filled with median (0.0 if median missing).
Model file: data/meta_model.pkl (gitignored). Saved as bundle {model, features, version}.
get_model() refuses to load if feature list mismatch — retrain required.
SHAP "why" via booster_.predict(pred_contrib=True) top-5.
score_symbol(sym, use_yahoo=True): Yahoo fallback when local history < 300 rows.
Top Picks composite = 0.45*P(WIN) + 0.25*accum + 0.15*sectorRS + 0.15*delivery
  (+0.10 live-setup bonus). Top-50 cached daily. Vetoed symbols skipped.

## 9. SCHEDULER (times IST; started by terminal_api lifespan)
15:30 data_quality · 15:45 daily_update · 16:00 delivery fetch · 16:15 swing scan + drift check ·
16:45 institutional · 17:30 macro FII/DII · 18:05 patterns · 18:35 templates ·
Sat 08:00 fundamentals refresh · Sat 09:00 meta retrain · Mon 08:00 Monte-Carlo · 1st 10:00 walk-forward.
Verify: sudo journalctl -u nse-terminal -n 50 --no-pager | grep -i scheduler

## 10. CURRENT STATUS SNAPSHOT (2026-09-12)
- Services healthy; ~794,608 price rows; tracked universe ~863 symbols (mcap 1,000-8,000 cr + core).
- Data quality: all 6 checks green (7% "missing" = delisted/garbage symbols, expected).
- Regime currently DEFENSIVE (^NSEI below EMA10) → swing scan holds new entries; Top Picks still ranks.
- Sectors filled (sectors_refresh run once). Fundamentals sparse → C3 features mostly neutral until fresh CSV.
- Telegram verified end-to-end (test message delivered).
- PO fixes deployed: yfinance period bug fixed (regime.py, screener_engine.py); central DB schema
  (all tables in db.py); meta_model v6 retrained (30 features, AUC ~0.629, top-10% ~63%);
  events date fix; swing veto gate + staleness guard; deepdive try/except; backtest stale-signal guard;
  app.py optional-panel guards.
- Structured logging deployed: log_utils.py + daily_update.py + scheduler_bg.py write to data/logs/*.log.
- requirements.txt split: core (requirements.txt) + optional (requirements-optional.txt).

## 11. MASTER TO-DO LIST
DONE: modern FastAPI terminal + Top Picks UI · scheduler autonomy · B1 sector gate · B2 shape score ·
C1 meta-model · C2 SHAP · C4 drift+weekly retrain · C5 5-year training · D1 data-quality monitor ·
E1 Telegram alerts · A1 fundamentals refresh · A2 institutional footprint · A3 FII/DII macro · A4 breadth ·
N1 whole-band screener · N2 delivery % scanner + Top Picks reweight · N3 paper-trade ledger ·
Monte-Carlo + walk-forward validation · chart snapshots in Telegram · model_runs ledger.
REMAINING: A0 custom domain + HTTPS (outline §13).
OPTIONAL FUTURE: C3 lift re-test after fresh fundamentals · intraday entry timing ·
delivery%/bulk-block real NSE parsing if a stable source appears.

## 12. KNOWN QUIRKS & WORKAROUNDS
- yfinance "Cookie/crumb fetch failed" warnings: harmless for price history; info/fundamentals may fail.
- yfinance period strings must be start/end dates or valid values ("1mo","3mo","6mo","1y","2y","5y","max").
  Do NOT use "120d" or "18mo" — invalid.
- NSE blocks datacenter IPs: macro auto-fetch usually fails → manual: python macro.py set <fii> <dii>.
- ^CNXSMALLCAP dead → regime falls back to ^NSEI (logged, fine).
- Python stdout buffered → service sets PYTHONUNBUFFERED=1 (else scheduler prints appear late).
- Journal = UTC. Phone browsers cache hard → incognito or ?v=2 after frontend changes.
- Legacy Streamlit shows raw @import text line — cosmetic only; fixed by moving @import inside <style>.
- Universe contains garbage symbols ($-prefixed) → filtered with NOT LIKE '%$%'.
- Streamlit "missing ScriptRunContext" warnings when importing outside `streamlit run` — harmless.

## 13. A0 OUTLINE (the only remaining roadmap item)
Buy domain (or free DuckDNS subdomain) → A record → 140.238.226.249 → VM: sudo apt install nginx certbot
python3-certbot-nginx → nginx reverse proxy / → 127.0.0.1:8000 (keep Basic auth) → open TCP 80/443 in Oracle
security list + iptables → sudo certbot --nginx -d yourdomain → auto-renew. Keep :8000 as fallback.

## 14. OPERATIONS RUNBOOK (VM, after source venv/bin/activate)
sudo systemctl restart nse-terminal · sudo journalctl -u nse-terminal -n 300 --no-pager ·
python data_quality.py · python top_picks.py · python meta_model.py train · python meta_model.py SYM ·
python swing_live.py · python swing_live.py backfill · python institutional.py · python sector_gate.py ·
python macro.py [set F D] · python fundamentals_refresh.py csv|yahoo|auto · python ingest_missing.py ·
python sectors_refresh.py · python swing_alerts.py (test message) · python delivery.py backfill 30 ·
python patterns.py run · python template_match.py run · python validate.py all ·
python model_report.py lift · tail -20 data/logs/scheduler.log

## 15. RULES FOR THE NEXT AI CHAT
- Obey §4 golden rules absolutely (whole files; restart rules; verification).
- No paid services; respect Oracle free-tier (avoid heavy concurrent jobs).
- Keep every optional layer in try/except; UI must never blank.
- Prefer: new module → endpoint → view. Update this file + CHANGELOG after each session.
- If you edit requirements, keep core vs optional split.

## 16. CHANGELOG
2026-08: 2.0 Streamlit system → VM bootstrap → FastAPI modern terminal → meta-model (C1/C2/C5) →
gates (B1/B2/A4) → monitors (D1) → alerts (E1) → fetching (A1/A2/A3) → Top Picks UI → handoff doc.
(append new entries below this line)

2026-09-07c: N3 ledger live + half-Kelly position sizing (sizing.py, /api/sizing/*, Overview panel).
2026-09-08b: validate.py wf datetime-index fix; backfill seeds mc; deploys now command-only (no deploy.bat).
2026-09-08c: Validation panel (MC percentiles + WF verdict) in Ledger view via /api/validate/latest.
2026-09-09a: E1 chart snapshots — chart_img.py + telegram send_photo; setup alerts now attach candlestick PNG; data/charts/ gitignored.
2026-09-09b: model_runs ledger + meta_model.lift_test (C3 lift: full vs price-only, same split) + /api/model/runs; weekly retrain auto-records.
2026-09-09c: app.js v6 — Model Runs panel (AUC history + C3 lift verdict) in Ledger view; completes model_runs feature.
NEW MODULES since §5: ledger.py, sizing.py, pwin_cache.py, validate.py, model_report.py, chart_img.py.
NEW ENDPOINTS: /api/ledger/*, /api/sizing/*, /api/validate/latest, /api/model/runs, /api/screener/*, /api/pwin/refresh.
NEW TABLES: top_picks(ext), pwin_daily, validation_log, model_runs, ledger uses swing_signals.
2026-09-10a: Phase-1 secret sauce — vcr / ret_std20 / below52 added to meta-model (21 features); pattern-scanner roadmap agreed (patterns.py + pattern_tags + empirical 60% gate).
2026-09-10b: patterns.py v1 — rule-based pattern scanner with HTF, ascending triangle, double bottom, bull flag, inverse H&S and bearish H&S warning; stores pattern_tags; uses vcr/ret_std20/below52; scheduler patterns@18:05; API /api/patterns/*.
2026-09-10c: Patterns tab UI — pattern cards (direction/status/confidence/levels/secret-sauce) + Run Full Scan button wired to /api/patterns/scan.
2026-09-11b: template_match.py — DTW shape matching vs VCP/HTF/BULL_FLAG/DOUBLE_BOTTOM templates; template_scores table; nightly 18:35 IST job.
2026-09-11a: pattern->ML integration — 7 pattern flags (pat_*) as meta-model features (28 total); patterns.backfill_tags() stores historical tags; retrain records lift in model_runs.
2026-09-12a: pattern_grader.py — every historical tag graded as a 2R trade; per-pattern win-rate gate (>=30 graded & >=60% WR = ENABLED); patterns.run stores only enabled patterns and auto-grades nightly.
2026-09-12c: pattern_grader v3 — report KeyError fixed; gate saved from 86,422 graded tags (+1R stop-first 45-bar); nightly scan now stores only ENABLED patterns.
2026-09-12d: gate verdict — IHS 67.3% / AT 63.8% / DB 63.0% / HTF 60.1% ENABLED, BULL_FLAG 56.0% DISABLED; pattern_grader v4 keeps ungraded patterns provisional; gate re-saves nightly so statuses self-correct.
2026-09-13a: /api/webhook/ingest (token-authed, free-webhook-ready, Telegram mirror) + /api/templates/latest + DTW Shape Matches card in Patterns tab (terminal_api v10, app.js v9).
2026-09-11b: webhook token flow live; template_match v2 backfill; meta_model v5 (29 feats incl. dtw_sim); DTW doubles as UI card + ML feature.
2026-09-11c: WEBHOOK_TOKEN live in .env (webhook ingest verified); template backfill + meta_model v5 (29 feats, dtw_sim) deployed.
2026-09-13b: delivery.py — NSE bhavcopy delivery% scanner; delivery_daily table; /api/delivery/top, /api/delivery/accum, /api/delivery/{symbol}; nightly 16:00 IST fetch; backfill 30 days; accumulation signal = consistently high delivery% (institutional conviction).
2026-09-13c: Top Picks composite reweighted 45/25/15/15 with delivery conviction; top_picks.delivery column (safe ALTER); Overview Delivery card via /api/delivery/{symbol}.
2026-09-14a: meta_model v6 — delivery_sim (10-day delivery conviction, neutral 0.5) as feature #30; delivery backfill 400d; retrain recorded in model_runs.
2026-09-15a: IDENTITY LOCKED — daily-bar swing + partial fundamentals only; intraday entry-timing layer removed (entry_timing.py deleted, 16:20 job dropped).
2026-09-15b: fund_veto gate live (debt_eq>3 / ROCE<8 / promoter<20): suppresses swing alerts, purges vetoed same-day signals; patterns+Top Picks veto next batch.
2026-09-16b: veto complete — patterns.run drops BULLISH formations on vetoed symbols (bearish kept), top_picks skips vetoed symbols; veto now covers alerts + swing storage + patterns + picks.
2026-09-16c: bullflag_rescue.py experiment ran — verdict: KILL (see 2026-09-17a).
2026-09-17a: BULL_FLAG KILLED by evidence — rescue variants 53.0-55.9% WR (n=127-1572), all below 60% bar; detector removed (patterns v5); historical tags/grades retained for audit; live pattern library now HTF / AscTriangle / DoubleBottom / InvH&S (+H&S-top warning).
2026-09-12b: PO fixes — regime.py + screener_engine.py yfinance period (use start/end dates); db.py central schema (all tables); meta_model feature-count guard + bundle format + retrained v6 (30 features); events.py uses latest technicals date; swing_live.py veto-before-insert + staleness guard; deepdive.py try/except; backtest.py stale-signal guard + diagnostic counters; screener_engine.py index fallback list; app.py optional-panel guards (safe_rows/safe_call helpers) + CSS @import moved inside <style>.
2026-09-12c: Structured logging — log_utils.py (rotating TimedRotatingFileHandler → data/logs/<name>.log, 14-day retention); daily_update.py + scheduler_bg.py migrated to log_utils.get_logger(); requirements.txt split into core (requirements.txt) + requirements-optional.txt (streamlit, plotly, transformers, torch, feedparser, matplotlib, gspread).