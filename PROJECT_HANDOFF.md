# NSE INTELLIGENCE TERMINAL — COMPLETE PROJECT HANDOFF
Doc date: 2026-09-07 · System version: 3.x · READ EVERYTHING BEFORE TOUCHING CODE

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

Daily automation (IST): 15:30 data-quality → 15:45 EOD update → 16:15 swing scan+grading+drift →
16:45 institutional accumulation → 17:30 FII/DII macro. Saturdays: 08:00 fundamentals refresh,
09:00 meta-model retrain.

## 3. ACCESS MAP
- Laptop project folder: C:\Users\Ankit\Desktop\nse_system
- VM: Oracle Always Free Ubuntu, public IP 140.238.226.249, user ubuntu
- SSH: ssh -i C:\Users\Ankit\.ssh\nse.pem ubuntu@140.238.226.249
- Git repo (PRIVATE): https://github.com/ankitchaudhary6886/nse-system ; VM clone: ~/nse-system
- Modern terminal: http://140.238.226.249:8000 (FastAPI, HTTP Basic login)
- Legacy Streamlit backup: http://140.238.226.249:8501 (service nse; cosmetic @import glitch; can disable)
- Login: ADMIN_USER=ankit, ADMIN_PASS=ankitc21 (stored in ~/nse-system/.env on VM; change anytime)
- Telegram: bot token hardcoded in telegram_alerts.py URL and in data/tg_secret.txt line 1;
  chat id 1107422528 (line 2). Repo is private so this is acceptable; rotate bot via @BotFather if leaked.
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
9. data/*.db and data/*.pkl are gitignored (each machine has its own data). data/tg_secret.txt IS tracked.
10. Rollback safety: git checkout -- <file> ; git revert <commit>.

## 5. FILE INVENTORY (root unless noted)
- terminal_api.py — FastAPI backend: all /api/* endpoints + lifespan that starts the scheduler.
- terminal/static/index.html, app.js, style.css — modern terminal UI (views: Top Picks, Overview, Swing Desk, Radar).
- scheduler_bg.py — APScheduler cron jobs (§9).
- daily_update.py — crash-proof EOD pipeline (prices→technicals→scan→ml→events→swing→telegram→sheets).
- ingest_prices.py, ingest_smallcaps.py, ingest_missing.py, broad_scan.py — data ingestion.
- technicals.py, scan.py, ml_predict.py, ml_train.py, events.py, sentiment.py — 2.0 analytics.
- regime.py — MarketRegime (index close vs EMA10; benchmark fallback ^NSEI).
- breadth.py — %above-50EMA + adv/dec, cached daily in breadth_daily.
- sector_gate.py — sector RS ranking + top-3 leadership gate.
- scanner.py — fundamental/quality gates (Screener.evaluate).
- setup.py — SetupDetector OFFICIAL v3 + shape_score (0-100 pullback orderliness).
- swing_live.py — signal scan / outcome grading / backfill / Telegram hook.
- swing_alerts.py — Telegram sender (delegates to telegram_alerts, .env fallback).
- telegram_alerts.py — legacy bot sender + daily report.
- meta_model.py — LightGBM meta-model: train / score_symbol / SHAP why / rank_symbols.
- top_picks.py — daily composite shortlist (cached in top_picks table).
- institutional.py — accumulation proxy (up-volume share) + optional NSE delivery%.
- macro.py — FII/DII fetch (NSE, often blocked) + manual mode: python macro.py set F D.
- fundamentals_refresh.py — csv / yahoo / auto fundamentals refresh.
- sectors_refresh.py — fills stocks.sector via Yahoo info.
- data_quality.py — 6-check monitor + Telegram alerts.
- db.py — sqlite helper (data/nse.db per machine).
- app.py — legacy Streamlit dashboard (backup only).

## 6. DATABASE TABLES (sqlite: data/nse.db)
prices_daily(symbol,date,open,high,low,close,volume, UNIQUE(symbol,date)) ·
universe_broad(symbol,perf1m,perf3m,relvol,mcap_cr,...) · stocks(symbol,sector,name,active) ·
fundamentals(symbol,roce,pe,...) · scan_results · pipeline · ml_predictions ·
sentiment_headlines(symbol,title,age_days,label) · events ·
swing_signals(signal_date,symbol,entry_trigger,stop,target,risk_pct,pullback,impulse,ema_zone,outcome,updated_at) ·
data_quality_log · breadth_daily(date,above50,adv,dec) ·
institutional(symbol,date,accum,delivery_pct) ·
top_picks(date,symbol,p_win,accum,sector_rs,sector,setup,composite) ·
macro_flow(date,fii_net_cr,dii_net_cr)

## 7. STRATEGY SPEC (OFFICIAL v3 + gates)
Setup checklist (ALL must pass): impulse 25-50% within 90 bars, price mostly above EMA10 during impulse;
pullback 12-20% over 6-15 days, orderly, no >=15% crash in any 3-day window; price touching EMA10/EMA20 zone;
volume dry-up (avg3 < 0.8x vol20 OR last < 0.7x vol20); mother bar = inside bar OR tight cluster
(range <= 0.9x ATR14, run of 2-4); pattern completed within last 3 sessions (MAX_SHIFT=2).
Entry/exit: trigger = mother-bar high; stop = pattern-day low (PDL); risk <= 5%; target = 2R.
Tranche lifecycle: initial SL → +2R move SL to breakeven → +4R exit 1/3 → trail 10EMA → trail 20EMA / vertical climax.
Gates before ANY new signal: regime BULLISH (index close > EMA10) AND breadth ok (above50 >= 0.5 AND adv >= dec)
AND symbol sector in top-3 by RS.
Grading: PENDING → OPEN → WIN / LOSS / EXPIRED (no trigger in 3d) / TIMEOUT (30d).

## 8. ML SPEC
meta_model.py, LightGBM classifier. Label: max high within next 20 sessions >= +10%.
Weekly sampling per symbol; time-based 80/20 split (no lookahead).
18 features: mom1,mom3,mom6,d52,above200,slope200,pb,d10,d20,atr,rv,vc,roce,pe,debt_eq,promoter,sector_rs,sentiment.
Context features coerced with pd.to_numeric (LightGBM rejects object dtypes).
Baseline (2026-08-30): rows 58,924 · test AUC 0.644 · base win 43.2% · top-decile win 66.0%.
Model file: data/meta_model.pkl (gitignored). SHAP "why" via booster_.predict(pred_contrib=True) top-5.
score_symbol(sym, use_yahoo=True): Yahoo fallback when local history < 300 rows.
Top Picks composite = 0.5*P(WIN) + 0.3*accum + 0.2*sectorRS + 0.1*live-setup bonus; top-50 cached daily.

## 9. SCHEDULER (times IST; started by terminal_api lifespan)
15:30 data_quality · 15:45 daily_update · 16:15 swing scan + drift check · 16:45 institutional ·
17:30 macro FII/DII · Sat 08:00 fundamentals refresh · Sat 09:00 meta retrain.
Verify: journalctl grep "SCHEDULER] started".

## 10. CURRENT STATUS SNAPSHOT (2026-09-07)
- Services healthy; ~794,608 price rows; tracked universe ~863 symbols (mcap 1,000-8,000 cr + core).
- Data quality: all 6 checks green (7% "missing" = delisted/garbage symbols, expected).
- Regime currently DEFENSIVE (^NSEI below EMA10) → swing scan holds new entries; Top Picks still ranks.
- Sectors filled (sectors_refresh run once). Fundamentals sparse → C3 features mostly neutral until fresh CSV.
- Telegram verified end-to-end (test message delivered).

## 11. MASTER TO-DO LIST
DONE: modern FastAPI terminal + Top Picks UI · scheduler autonomy · B1 sector gate · B2 shape score ·
C1 meta-model · C2 SHAP · C4 drift+weekly retrain · C5 5-year training · D1 data-quality monitor ·
E1 Telegram alerts · A1 fundamentals refresh · A2 institutional footprint · A3 FII/DII macro · A4 breadth.
REMAINING: A0 custom domain + HTTPS (outline §13).
OPTIONAL FUTURE: C3 lift re-test after fresh fundamentals · E1 chart-snapshot images in Telegram ·
walk-forward/Monte-Carlo validation harness · half-Kelly position sizing · intraday entry timing ·
delivery%/bulk-block real NSE parsing if a stable source appears.

## 12. KNOWN QUIRKS & WORKAROUNDS
- yfinance "Cookie/crumb fetch failed" warnings: harmless for price history; info/fundamentals may fail.
- NSE blocks datacenter IPs: macro auto-fetch usually fails → manual: python macro.py set <fii> <dii>.
- ^CNXSMALLCAP dead → regime falls back to ^NSEI (logged, fine).
- Python stdout buffered → service sets PYTHONUNBUFFERED=1 (else scheduler prints appear late).
- Journal = UTC. Phone browsers cache hard → incognito or ?v=2 after frontend changes.
- Legacy Streamlit shows raw @import text line — cosmetic only; optionally: sudo systemctl disable --now nse.
- Universe contains garbage symbols ($-prefixed) → filtered with NOT LIKE '%$%'.

## 13. A0 OUTLINE (the only remaining roadmap item)
Buy domain (or free DuckDNS subdomain) → A record → 140.238.226.249 → VM: sudo apt install nginx certbot
python3-certbot-nginx → nginx reverse proxy / → 127.0.0.1:8000 (keep Basic auth) → open TCP 80/443 in Oracle
security list + iptables → sudo certbot --nginx -d yourdomain → auto-renew. Keep :8000 as fallback.

## 14. OPERATIONS RUNBOOK (VM, after source venv/bin/activate)
sudo systemctl restart nse-terminal · sudo journalctl -u nse-terminal -n 300 --no-pager ·
python data_quality.py · python top_picks.py · python meta_model.py train · python meta_model.py SYM ·
python swing_live.py · python swing_live.py backfill · python institutional.py · python sector_gate.py ·
python macro.py [set F D] · python fundamentals_refresh.py csv|yahoo|auto · python ingest_missing.py ·
python sectors_refresh.py · python swing_alerts.py (test message)

## 15. RULES FOR THE NEXT AI CHAT
- Obey §4 golden rules absolutely (whole files; restart rules; verification).
- No paid services; respect Oracle free-tier (avoid heavy concurrent jobs).
- Keep every optional layer in try/except; UI must never blank.
- Prefer: new module → endpoint → view. Update this file + CHANGELOG after each session.

## 16. CHANGELOG
2026-08: 2.0 Streamlit system → VM bootstrap → FastAPI modern terminal → meta-model (C1/C2/C5) →
gates (B1/B2/A4) → monitors (D1) → alerts (E1) → fetching (A1/A2/A3) → Top Picks UI → handoff doc.
(append new entries below this line)

2026-09-07c: N3 ledger live + half-Kelly position sizing (sizing.py, /api/sizing/*, Overview panel).