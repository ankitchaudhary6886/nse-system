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
- **R13** Fast feedback loops: use funnels/diags (~5s), not multi-minute
          walk-forwards, when hunting for bottlenecks.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I13 (see EXECUTION_LOG)

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE (see EXECUTION_LOG)

### ID11 — Signal sparsity fix · **DONE (v3.2 + v3.3)**
Timeline:
- Initial: 0.4% setup pass rate (4 setups in 100×2y sample).
- v3.2: widened impulse 25-50%→18-75%, EMA10 tol 0.25→0.35,
  PB depth 12-20%→8-25%.  Result: 3.2% pass (36 setups).
- v3.3: EMA10 tol 0.35→0.45, PB floor 0.08→0.06, PB days cap 15→20.
  Target: 5-8% pass rate.
Diag showed 1c_ema10_breaks was still the #1 killer at 50% post-v3.2.

### ID12 — Alt setup patterns · **FUTURE**
If v3.3 doesn't produce an edge, add second setup family
(breakout-pullback, consolidation-tight-close). Independent strategy,
same swing_signals table with different mode.

### ID13 — Fast validation · **DONE**
- `validate.py` v3 delegates to Backtester (100x faster)
- `fast_wf.py` — inline walk-forward, ~60s
- `quick_funnel.py` — 5s funnel diagnostic
- `quick_setup_diag.py` — 3s per-check breakdown

### ID14 — Meta-model plateau · **OPEN**
3 consecutive retrains: AUC 0.629 (v6), 0.629 (v7 33-feat).
Features have hit diminishing returns. Options:
- Accept 0.629 (top-decile win 62-63% is tradeable)
- Add fundamentally different features (e.g. sector rotation,
  FII/DII flow interaction)
- Pivot to shorter-horizon labels
Deferred until swing signal base is validated.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · DONE (5 levels)
### FP Fundamentals Pipeline · DONE (863 symbols weekly)
### FS Sizing with fallback · DONE
### FA Unified Alerts · DONE
### FU Canonical Universe · DONE
### FT Trend Scanner v3 · DONE (unbounded score)
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (33 features, AUC 0.629)
### FVAL Fast Validation · DONE (`fast_wf.py`, `quick_funnel.py`)
### FSP Setup v3.3 · DONE (widened thresholds)

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R13 | Rules                   | Active       |
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

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py