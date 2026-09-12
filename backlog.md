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
- **R16** Non-monotonic sweep results are NOISE, not signal. Prefer the
          simpler/earlier parameter when in doubt.
- **R17** Multi-window walk-forward is the ground truth. A parameter set
          that only works on one window is overfit.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I16 (see EXECUTION_LOG)
I17 Adopt multi-window robustness as the validation standard.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE
### ID11 — Signal sparsity fix · **DONE** (0.4% → 8.0%)
### ID12 — Alt setup patterns · **FUTURE**
### ID13 — Fast validation · **DONE**
### ID14 — Meta-model plateau · **OPEN**
### ID15 — Target sweep · **DONE** (3R adopted)
### ID16 — Sizing quality multiplier · **DONE** (v4)
### ID17 — Robustness check · **DONE 2026-09-12**
Multi-window walk-forward results (3R default):
| Window | Trades | WR    | PF   | Total   | DD    | Exp/trade |
|--------|--------|-------|------|---------|-------|-----------|
| 2y     | 102    | 40.2% | 1.73 | +237.5% | 17.5% | +0.435R   |
| 3y     | 185    | 35.1% | 1.43 | +273.5% | 17.5% | +0.276R   |
| 4y     | 418    | 31.8% | 1.16 | +132.6% | 17.8% | +0.110R   |
**Finding: edge is regime-dependent. Monotonic decline with window
length is REAL signal (not noise). Positive expectancy in ALL windows.
Conservative baseline: expect 20-25% CAGR / 18% DD, not 2y's 90%.**

### ID18 — Hybrid tranche exits · **NEXT**
Exit 1/3 at 2R, 1/3 at 3R, trail remaining 1/3 with 10-EMA. Test
against current 3R full-exit. Requires partial-exit support in
backtest.py. Could improve 4y window PF.

### ID19 — Central strategy config · **FUTURE**
Move SetupDetector thresholds + TARGET_R + regime thresholds into one
`strategy_config.py`. Enables single-file sweeps. (ID7 concern.)

### ID20 — Strategy runs dashboard · **NEXT**
Surface strategy_runs history in terminal UI. See every walk-forward
result at a glance. Small API + card.

---

## E. IMAGINATIONS
IM1 Multi-strategy quant terminal · IM2 Bear-market accumulation ·
IM3 Self-documenting system.

---

## F. FEATURES COMPLETED

### FC Regime Spectrum · DONE
### FP Fundamentals Pipeline · DONE (863 symbols)
### FS Sizing with quality multiplier · DONE (v4)
### FA Unified Alerts · DONE
### FU Canonical Universe · DONE
### FT Trend Scanner v3 · DONE
### FP2 Positional Scanner · DONE
### FV Value Radar v2 · DONE
### FM Meta-Model v7 · DONE (AUC 0.629)
### FVAL Fast Validation · DONE
### FSP Setup v3.4 · DONE (3R target)
### FWF Walk-forward v4 · DONE (PF 1.43 / 1.73 / 1.16 across windows)
### FSR Strategy Runs ledger · DONE this batch

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R17 | Rules                   | Active       |
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
| ID18 | Hybrid tranche exits      | NEXT         |
| ID19 | Central strategy config   | FUTURE       |
| ID20 | Strategy runs dashboard   | NEXT         |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py