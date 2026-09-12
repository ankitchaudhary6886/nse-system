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
- **R13** Fast feedback loops (~5s), not multi-minute waits.
- **R14** Verdicts are PF-driven.
- **R15** Parameters are swept, not picked.
- **R16** Non-monotonic sweeps = noise. Prefer simpler parameter.
- **R17** Multi-window WF is ground truth.
- **R18** Equivalent results → simpler wins.
- **R19** System identifies. Owner decides. No prescribed exits,
          targets, sizing, or signals.
- **R20** Log every owner instruction in BACKLOG immediately.
- **R21** Every candidate presented with full picture — predictability,
          potential, historical hit rate at multiple R levels, candle
          behaviour, sector context.
- **R22** All tunable parameters live in `strategy_config.py`.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I21 (see EXECUTION_LOG)
I22 ID21 deployment complete → verify → then ID22 (research cockpit).

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID20 · DONE / partial (see EXECUTION_LOG)

### ID19 — Central strategy config · **DONE**
All parameters in `strategy_config.py`. Behavior unchanged (verified:
same 185 trades / PF 1.43).

### ID21 — Production deployment · **IN PROGRESS**
- `verify_deployment.py` — CLI check + `--scan` + `--sweep`
- `/api/deployment-check` endpoint
- Deployment panel in Ledger view
- Next: run `--scan` on VM to populate fresh data, then verify all-green.

### ID22 — Research cockpit · **NEXT (after ID21)**
For every setup shown, present the full picture:
- Historical hit rate at +1R / +2R / +3R / +4R from similar past setups
- Median time-to-target at each R level
- Max favorable / adverse excursion distributions
- Candle behaviour at signal (mother bar, tightness, volume profile)
- Sector context (RS, similar sectors in same state)
- Predictability score (from meta-model, decomposed)
- Potential score (distance to 52w high, momentum alignment)
Owner decides which to examine. No recommendations from the AI.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system · IM4 Research cockpit (ID22).

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · DONE
### FP Fundamentals Pipeline · DONE (863 symbols)
### FS Sizing with quality multiplier · DONE
### FA Unified Alerts · DONE
### FU Canonical Universe · DONE
### FT Trend Scanner v3 · DONE
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (AUC 0.629)
### FVAL Fast Validation · DONE
### FSP Setup v3.5 · DONE
### FWF Walk-forward v5 · DONE
### FSR Strategy Runs ledger + UI · DONE
### FCONF Central Config · DONE
### FDEP Deployment Verification · **DONE this batch**

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R22 | Rules                   | Active       |
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
| ID16 | Sizing quality multiplier | DONE         |
| ID17 | Robustness check          | DONE         |
| ID18 | Hybrid tranche exits      | REJECTED     |
| ID19 | Central strategy config   | DONE         |
| ID20 | Strategy runs dashboard   | DONE         |
| ID21 | Production deployment     | IN PROGRESS  |
| ID22 | Research cockpit          | NEXT         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py