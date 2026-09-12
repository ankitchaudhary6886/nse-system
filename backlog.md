# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in `EXECUTION_LOG.md`.
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
I8 3-4 edits per response · I9 Universe unification via shared module ·
I10 Replace `telegram_alerts`/`swing_alerts` with unified `alerts` (shims).

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1 — All-weather swing mode · **DONE**
115 candidates → 5 signals. Verified.

### ID2 — Long-term Value Radar · **DONE (v2)**
Tier A visible. Examples: RSYSTEMS, MADRASFERT, SANOFI, TANLA.

### ID3 — Custom scanners: swing + positional · **PARTIAL DONE**
- ID3a Positional scanner — DONE (`positional_scanner.py`).
- ID3b Swing scanner — partially covered by screener_engine.py.

### ID4 — Free data source expansion (ScanX etc.) · **FUTURE**

### ID5 — "Feeding of life into stocks" · **FUTURE**

### ID6 — Universe split · **PARTIAL DONE**
Fundamentals covers Nifty 500 ∪ band (~863). Full Nifty 1000 target.

### ID7 — Trim / unify / simplify · **MOSTLY DONE**
- Merge alert modules — **DONE** (`alerts.py` canonical)
- Canonical universe source — **DONE** (`universe_helper.py`; swing_live,
  value_radar, positional migrated)
- Pick one screener (scanner.py vs screener_engine.py) — pending
- Retire Streamlit app.py — deferred
- Single price ingester — pending

### ID8 — Trend-regime scanner · **DONE**
Price > EMA50 AND > EMA200. Daily 15:50 IST. API `/api/trend`.
UI card in Scanners panel.

### ID9 — UI panels for new scanners · **DONE this batch**
Trend + Positional cards in Scanners view.
Value Radar card already in Radar view.

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
Conservative win-rate 0.35. Regime multiplier applied.

### FA Unified Alerts · **DONE**
`alerts.py` canonical. `telegram_alerts.py` + `swing_alerts.py` are shims.

### FU Canonical Universe · **DONE**
`universe_helper.py` — band / active / combined.

### FT Trend Scanner · **DONE**
`trend_scanner.py` + API + scheduler slot + UI card.

### FP2 Positional Scanner · **DONE**
`positional_scanner.py` + API + scheduler slot + UI card.

### FV Value Radar v2 · **DONE**
`value_radar.py` + API + scheduler slot + UI card.

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
| ID7  | Trim / unify / simplify   | MOSTLY DONE  |
| ID8  | Trend-regime scanner      | DONE         |
| ID9  | Scanner UI panels         | DONE         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py (nse.service)