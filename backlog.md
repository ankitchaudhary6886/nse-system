# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in `EXECUTION_LOG.md`.
- This file survives chat migration.
- Filename is lowercase `backlog.md` (Windows case-safety).

---

## A. RULES  (always active)

- **R1**  Whole files only. No patches. Ever.
- **R2**  Plain English. Ask for screenshots when useful.
- **R3**  VS Code (Windows) + Oracle Cloud VM via SSH.
- **R4**  Every change = full file + 1 laptop block + 1 VM block.
- **R5**  Batch related commands into one block per machine.
- **R6**  Skip credential / HTTPS / ops tasks unless asked.
- **R7**  Every new idea → auto-add to BACKLOG.
- **R8**  Instructions tagged with `#` prefix.
- **R9**  Every execution logged in EXECUTION_LOG.md.
- **R10** No pausing; keep momentum.
- **R11** 3-4 file edits per response when possible.
- **R12** Execute new ideas only AFTER the machine is functionally complete.

---

## B. INSTRUCTIONS
### 2026-09-12
I1 PO issues · I2 Sequence 1→2→3 · I3 Handoff · I4 impulse fix ·
I5 fundamentals · I6 restructure BACKLOG · I7 EXECUTION_LOG ·
I8 3-4 edits per response.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1 — All-weather swing mode · **DONE**
115 candidates → 5 signals. Verified.

### ID2 — Long-term Value Radar · **DONE (v2)**
Tier A visible after promoter/CFO enrichment + band tuning.
Examples: RSYSTEMS, MADRASFERT, SANOFI, TANLA.

### ID3 — Custom scanners: swing + positional · **PARTIAL DONE**
- ID3a Positional scanner — DONE (`positional_scanner.py`, Sat 10:00 IST).
- ID3b Swing scanner — partially covered by screener_engine.py.

### ID4 — Free data source expansion (ScanX etc.) · **FUTURE**

### ID5 — "Feeding of life into stocks" · **FUTURE**

### ID6 — Universe split · **PARTIAL DONE**
Fundamentals now covers Nifty 500 + band union (~863 symbols).
Full Nifty 1000 target.

### ID7 — Trim / unify / simplify · **IN PROGRESS**
- Merge alert modules (telegram_alerts + swing_alerts) — **DONE this batch**
- Pick one screener (scanner.py vs screener_engine.py)
- Retire Streamlit app.py
- Single universe source
- Single price ingester

### ID8 — Trend-regime scanner  · **FUTURE**
Stocks whose current price is above BOTH EMA50 and EMA200.
Simple filter, useful for cutting bear-market noise.
- Daily list of "confirmed uptrend" symbols
- Feeds other scanners as a pre-filter
- Complements regime spectrum (market-level) with stock-level trend
Do after ID7.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · **DONE**
5 levels, sizing scale, allows_swing only in first three.

### FP Fundamentals Pipeline · **DONE**
Canonical `fundamentals_tv.py`, 863 symbols weekly (Sat 08:00).

### FS Sizing with fallback · **DONE**
Conservative win-rate 0.35 when no cache. Regime multiplier applied.

### FA Unified Alerts · **DONE this batch**
`alerts.py` is canonical. `telegram_alerts.py` + `swing_alerts.py` are shims.

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R12 | Rules                   | Active       |
| ID1  | All-weather swing         | DONE         |
| ID2  | Value Radar v2            | DONE         |
| ID3a | Positional scanner        | DONE         |
| ID3b | Swing scanner (custom)    | PARTIAL      |
| ID4  | Free data sources         | FUTURE       |
| ID5  | Feed life into stocks     | FUTURE       |
| ID6  | Universe split            | PARTIAL      |
| ID7  | Trim / unify / simplify   | IN PROGRESS  |
| ID8  | Trend-regime scanner      | FUTURE       |
| FC   | Regime spectrum           | DONE         |
| FP   | Fundamentals pipeline     | DONE         |
| FS   | Sizing fallback           | DONE         |
| FA   | Unified alerts            | DONE         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets