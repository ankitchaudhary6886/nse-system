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
I10 Replace alert modules with unified `alerts`.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1 — All-weather swing mode · **DONE**
### ID2 — Long-term Value Radar · **DONE (v2)**
### ID3 — Custom scanners: swing + positional · **PARTIAL DONE**
### ID4 — Free data source expansion (ScanX etc.) · **FUTURE**
### ID5 — "Feeding of life into stocks" · **FUTURE**
### ID6 — Universe split · **PARTIAL DONE**
### ID7 — Trim / unify / simplify · **MOSTLY DONE**
### ID8 — Trend-regime scanner · **DONE**
### ID9 — UI panels for new scanners · **DONE**
### ID10 — Meta-model v7 features · **DONE this batch**
3 trend-persistence features added (days_above_200_30,
days_above_50_30, ema200_dist_z). Targets breaking the 0.629 plateau.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · DONE
### FP Fundamentals Pipeline · DONE
### FS Sizing with fallback · DONE
### FA Unified Alerts · DONE
### FU Canonical Universe · DONE
### FT Trend Scanner v2 · DONE (score no longer saturates at 100)
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (33 features, targets plateau break)

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
| ID10 | Meta-model v7             | DONE         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py