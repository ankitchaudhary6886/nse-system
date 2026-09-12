# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in `EXECUTION_LOG.md`.

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
- **R13** Fast feedback loops (funels/diags ~5s), not multi-minute waits.
- **R14** Verdicts are PF-driven. A 2R system with 40% WR and PF >=1.2 is
          tradeable — do not dismiss on win rate alone.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I13 (see EXECUTION_LOG)
I14 Correct verdict logic — PF-driven, not WR-driven.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE
### ID11 — Signal sparsity fix · **DONE**
- Initial: 0.4% setup pass rate
- v3.2: 3.2%
- v3.3: **8.0% (89 setups in sample)** — 20x the original

### ID12 — Alt setup patterns · **FUTURE**
Add second setup family (breakout-pullback, consolidation-tight-close)
if 2R/2.5R/3R sweep doesn't improve PF above 1.3.

### ID13 — Fast validation · **DONE**
`fast_wf.py` (80s), `quick_funnel.py` (5s), `quick_setup_diag.py` (3s).

### ID14 — Meta-model plateau · **OPEN**
AUC 0.629 stable across 3 retrains. Top-decile 62-63% is tradeable.
Deferred.

### ID15 — Target sweep (2R vs 2.5R vs 3R) · **IN PROGRESS**
First WF result: PF 1.21, +85.82% over 3y, DD 13.72%.
Sweep targets to see if PF breaks 1.3.

### ID16 — Position sizing integration · **PENDING**
Wire swing signal confidence into sizing.py alloc multiplier (already
supports regime mult). Add quality tier multiplier.

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
### FT Trend Scanner v3 · DONE
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (33 features)
### FVAL Fast Validation · DONE
### FSP Setup v3.3 · DONE (widened)
### FWF Walk-forward v1 · DONE (PF 1.21, +85.82%, DD 13.72%)

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R14 | Rules                   | Active       |
| ID1  | All-weather swing         | DONE         |
| ID2  | Value Radar v2            | DONE         |
| ID3a | Positional scanner        | DONE         |
| ID3b | Swing scanner (custom)    | PARTIAL      |
| ID4  | Free data sources         | FUTURE       |
| ID5  | Feed life into stocks     | FUTURE       |
| ID6  | Universe split            | PARTIAL      |
| ID7  | Trim / unify / simplify   | MOSTLY DONE  |
| ID8  | Trend scanner             | DONE         |
| ID9  | Scanner UI panels         | DONE         |
| ID10 | Meta-model v7             | DONE         |
| ID11 | Signal sparsity fix       | DONE         |
| ID12 | Alt setup patterns        | FUTURE       |
| ID13 | Fast validation           | DONE         |
| ID14 | Meta-model plateau        | OPEN         |
| ID15 | Target sweep              | IN PROGRESS  |
| ID16 | Sizing integration        | PENDING      |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py