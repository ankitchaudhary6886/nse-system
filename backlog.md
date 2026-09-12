# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay (never delete) so history survives.
- Execution details live in `EXECUTION_LOG.md`.
- This file survives chat migration.

---

## A. RULES  (always active)

- **R1**  Whole files only. No partial find/replace patches. Ever.
- **R2**  Plain English. Novice-friendly. Ask for screenshots when useful.
- **R3**  Environment: VS Code (Windows) + Oracle Cloud VM via SSH.
- **R4**  Every change = full file + 1 laptop block + 1 VM block.
- **R5**  Batch related commands into one block per machine.
- **R6**  Skip credential / HTTPS / ops tasks unless explicitly asked.
- **R7**  Every new idea / request / brainstorm → auto-add to BACKLOG.
- **R8**  Instructions from Ankit are tagged with `#` prefix.
- **R9**  Every execution is logged in EXECUTION_LOG.md (durable).
- **R10** No pausing; keep momentum.
- **R11** 3-4 file edits per response when possible.

---

## B. INSTRUCTIONS  (dated)

### 2026-09-12
- I1 Fix every PO issue + requirements + handoff.
- I2 Sequence: Option 1 (all-weather) first; then 2, 3 sequentially.
- I3 Update PROJECT_HANDOFF.
- I4 Fix impulse bug in setup.py.
- I5 Fix sparse fundamentals.
- I6 Restructure BACKLOG by category.
- I7 Create EXECUTION_LOG.md.
- I8 3-4 edits per response.

---

## C. DEMANDS  (hard requirements)

- D1 Ideas auto-captured, never lost.
- D2 Durable execution log across chat sessions.
- D3 Fast pace — no pausing.

---

## D. IDEAS

### ID1 — All-weather swing mode · **DONE**
Defensive-regime swing entries. Verified: 115 candidates → 5 signals.

### ID2 — Long-term Value Radar · **DONE (v2 tuned)**
Quality names in downturns. Tiers A/B/C. Weekly Sun 09:00. Telegram.
v2: softer quality bands, promoter + CFO pulled from TV.

### ID3 — Custom scanners: swing + positional · **IN PROGRESS**
Swing partially covered by screener_engine.py. Positional scanner new.

### ID4 — Free data source expansion (ScanX etc.) · **FUTURE**

### ID5 — "Feeding of life into stocks" · **FUTURE**

### ID6 — Universe split · **PARTIAL DONE**
Fundamentals now covers union of Nifty 500 + band (~860-1500 symbols).
Full Nifty 1000 target.

### ID7 — Trim / unify / simplify · **FUTURE**
- Merge alert modules
- Pick one screener
- Retire Streamlit
- Consolidate fundamental fetchers
- Single universe source
- Single price ingester

---

## E. IMAGINATIONS

### IM1 — Personal multi-strategy quant terminal
### IM2 — Bear-market accumulation engine
### IM3 — Self-documenting, self-improving

---

## F. FEATURE C — Regime Spectrum · **DONE**
5 levels: STRONG_BULL / BULL / NEUTRAL / WEAK / CAPITULATION.
Sizing scales 1.00 / 1.00 / 0.75 / 0.50 / 0.25.
`allows_swing` only in first three levels.
Verified on VM: `level=CAPITULATION size_mult=0.25 allows_swing=False`.

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R11 | Rules                   | Active       |
| I1–I8 | Instructions             | Applied      |
| ID1  | All-weather swing         | DONE         |
| ID2  | Value Radar v2            | DONE         |
| ID3  | Custom scanners           | IN PROGRESS  |
| ID4  | Free data sources         | FUTURE       |
| ID5  | Feed life into stocks     | FUTURE       |
| ID6  | Universe split            | PARTIAL      |
| ID7  | Trim / unify / simplify   | FUTURE       |
| FC   | Regime spectrum           | DONE         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets