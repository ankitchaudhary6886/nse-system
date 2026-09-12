# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in `EXECUTION_LOG.md`.
- This file survives chat migration.

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
Tier A examples: RSYSTEMS, MADRASFERT, SANOFI, TANLA.

### ID3 — Custom scanners: swing + positional · **PARTIAL DONE**
- ID3a Positional scanner — DONE (`positional_scanner.py`, Sat 10:00 IST).
- ID3b Swing scanner — partially covered by screener_engine.py.

### ID4 — Free data source expansion (ScanX etc.) · **FUTURE**

### ID5 — "Feeding of life into stocks" · **FUTURE**

### ID6 — Universe split · **PARTIAL DONE**
Fundamentals now covers Nifty 500 + band union (~863 symbols).
Full Nifty 1000 target.

### ID7 — Trim / unify / simplify · **IN PROGRESS**
- Consolidate alert modules (telegram_alerts + swing_alerts)
- Pick one screener (scanner.py vs screener_engine.py)
- Retire Streamlit app.py
- Single universe source
- Single price ingester

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · **DONE**
5 levels: STRONG_BULL / BULL / NEUTRAL / WEAK / CAPITULATION.
Sizing 1.00 / 1.00 / 0.75 / 0.50 / 0.25.
`allows_swing` only in first three.

### FP Fundamentals Pipeline · **DONE**
Canonical `fundamentals_tv.py` fetches 863 symbols weekly (Sat 08:00).
Adds promoter via `held_percent_insiders` (returned null by TV),
CFO via `free_cash_flow_fq`. Universe = Nifty 500 ∪ band.

### FS Sizing with fallback · **DONE**
Conservative win-rate 0.35 when no cache/graded data. Regime multiplier applied.

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R11 | Rules                   | Active       |
| ID1  | All-weather swing         | DONE         |
| ID2  | Value Radar v2            | DONE         |
| ID3a | Positional scanner        | DONE         |
| ID3b | Swing scanner (custom)    | PARTIAL      |
| ID4  | Free data sources         | FUTURE       |
| ID5  | Feed life into stocks     | FUTURE       |
| ID6  | Universe split            | PARTIAL      |
| ID7  | Trim / unify / simplify   | IN PROGRESS  |
| FC   | Regime spectrum           | DONE         |
| FP   | Fundamentals pipeline     | DONE         |
| FS   | Sizing fallback           | DONE         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets