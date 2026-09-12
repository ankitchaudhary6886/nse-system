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
- **R13** Fast feedback loops (funnels/diags ~5s), not multi-minute waits.
- **R14** Verdicts are PF-driven. A 2R system with 40% WR and PF >=1.2 is
          tradeable. Do not dismiss on win rate alone.
- **R15** Parameter changes are swept, not picked. One variable at a time,
          measure PF / expectancy / DD.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I14 (see EXECUTION_LOG)
I15 Adopt 3R target after sweep.
I16 Sweep wider target still (3.5R, 4R) as follow-up.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE
### ID11 — Signal sparsity fix · **DONE**
Final: 8.0% setup pass rate (was 0.4%).

### ID12 — Alt setup patterns · **FUTURE**
If 3.5R/4R sweep doesn't improve PF above 1.5, add second setup family.

### ID13 — Fast validation · **DONE**
`fast_wf.py`, `quick_funnel.py`, `quick_setup_diag.py`.

### ID14 — Meta-model plateau · **OPEN**
AUC 0.629 stable. Deferred.

### ID15 — Target sweep · **DONE 2026-09-12**
| R    | Trades | WR   | PF   | Total  | DD    | Expectancy |
|------|--------|------|------|--------|-------|------------|
| 2.0R | 215    | 39.1%| 1.21 | +85.8% | 13.7% | +0.126R    |
| 2.5R | 194    | 36.1%| 1.30 | +150.6%| 15.7% | +0.193R    |
| 3.0R | 185    | 35.1%| 1.43 | +273.5%| 17.5% | +0.276R    |
Decision: adopt 3R as default (setup.py v3.4, backtest.py).

### ID16 — Position sizing integration · **PENDING**
Wire confidence into sizing.py. Regime multiplier already works.

### ID17 — 3.5R / 4R sweep · **NEXT**
Test if PF keeps climbing past 3R or plateaus.
Command: `python fast_wf.py 3.5` / `python fast_wf.py 4`.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · DONE
### FP Fundamentals Pipeline · DONE (863 symbols)
### FS Sizing with fallback · DONE
### FA Unified Alerts · DONE
### FU Canonical Universe · DONE
### FT Trend Scanner v3 · DONE
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (AUC 0.629)
### FVAL Fast Validation · DONE
### FSP Setup v3.4 · DONE (3R target, WF-validated)
### FWF Walk-forward v2 · DONE (PF 1.43 at 3R, +273.5%, DD 17.5%)

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R15 | Rules                   | Active       |
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
| ID15 | Target sweep              | DONE         |
| ID16 | Sizing integration        | PENDING      |
| ID17 | 3.5R / 4R sweep           | NEXT         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py