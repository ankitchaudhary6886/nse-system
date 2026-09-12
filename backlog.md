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
I1–I11 (see EXECUTION_LOG for details)
I12 Address signal sparsity — done via v3.2 threshold widening.
I13 Keep validation fast (Backtester path or funnel diagnostics).

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE (see EXECUTION_LOG)
### ID11 — Signal sparsity fix · **DONE 2026-09-12**
Empirical finding: setup detector fired 0.2 signals per symbol over
4+ years. quick_setup_diag showed three impulse checks + pullback depth
killed 83% + 11% of candidates.
Fix (setup.py v3.2): widened impulse 25-50% → 18-75%, EMA10 break
tolerance 0.25 → 0.35, pullback depth 12-20% → 8-25%.
Expected: setup pass rate 0.4% → 3-5% of screener passes.

### ID12 — Fallback: alternative setup patterns · **FUTURE**
If v3.2 doesn't recover enough signals, add a second setup family
(breakout-pullback, consolidation-tight-close, etc). Two independent
strategies feed swing_signals.mode.

### ID13 — Validation via Backtester (fast path) · **DONE**
validate.py v3 delegates to Backtester which precomputes indicators
once per symbol. 100x faster than slice-and-eval.

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
### FT Trend Scanner v3 · DONE (unbounded score)
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (33 features)
### FVAL Validation v3 · DONE (fast via Backtester)
### FSP Setup v3.2 · DONE (widened thresholds)

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
| ID8  | Trend scanner             | DONE         |
| ID9  | Scanner UI panels         | DONE         |
| ID10 | Meta-model v7             | DONE         |
| ID11 | Signal sparsity fix       | DONE         |
| ID12 | Alt setup patterns        | FUTURE       |
| ID13 | Fast validation           | DONE         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py