# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.

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
- **R22** All tunable parameters in strategy_config.py.
- **R23** Optional integrations skip gracefully if creds/files missing.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I22 (see EXECUTION_LOG)
I23 ID22 (research cockpit v1) — shipped this batch.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID21 · DONE / partial (see EXECUTION_LOG)

### ID22 — Research Cockpit · **v1 DONE this batch**
For any symbol:
- Historical setups on that symbol (5y, step=5 bars)
- P(trigger), P(+1R / +2R / +3R / +4R | triggered)
- Median bars to each R level
- MFE/MAE distributions (p5 / median / p95)
- Outcome mix (WIN/LOSS/TIMEOUT/EXPIRED)
- Today's setup (if any) side by side
- Recent 5 historical setups tabulated
Files: research_cockpit.py, /api/research/{symbol}, research.js, Overview panel.

### ID22b — Cross-symbol similarity · **NEXT**
Extend cockpit: when analysing a symbol, compare its setup to *other
symbols' historical setups* with similar dimensions (impulse %, pullback %,
shape score, sector). Batch table + cached. Not real-time.

### ID23 — Sector-level research · **FUTURE**
Same view but at sector level — how have setups in Energy / IT / etc
behaved historically? Adds sector-relative context.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system · IM4 Research cockpit.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · DONE
### FP Fundamentals Pipeline · DONE (961 symbols)
### FS Sizing with quality multiplier · DONE
### FA Unified Alerts · DONE
### FU Canonical Universe · DONE
### FT Trend Scanner v3 · DONE
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (AUC 0.629)
### FML Price-Model · DONE (AUC 0.584 / 0.589)
### FVAL Fast Validation · DONE
### FSP Setup v3.5 · DONE
### FWF Walk-forward v5 · DONE
### FSR Strategy Runs ledger + UI · DONE
### FCONF Central Config · DONE
### FDEP Deployment Verification · DONE (15/15 green)
### FRC Research Cockpit v1 · **DONE this batch**

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R23 | Rules                   | Active       |
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
| ID21 | Production deployment     | DONE         |
| ID22 | Research cockpit v1       | DONE         |
| ID22b | Cross-symbol similarity  | NEXT         |
| ID23 | Sector-level research     | FUTURE       |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync (missing GCP key)