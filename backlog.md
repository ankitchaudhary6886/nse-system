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

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I15 (see EXECUTION_LOG)
I16 Add quality multiplier to sizing (this batch).
I17 Keep 3R — reject 4R (non-monotonic curve, see ID15).

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE
### ID11 — Signal sparsity fix · **DONE** (0.4% → 8.0% setup pass rate)
### ID12 — Alt setup patterns · **FUTURE**
### ID13 — Fast validation · **DONE**
### ID14 — Meta-model plateau · **OPEN** (AUC 0.629 stable)
### ID15 — Target sweep · **DONE 2026-09-12**
| R    | Trades | WR    | PF   | Total   | DD    | Exp/trade |
|------|--------|-------|------|---------|-------|-----------|
| 2.0R | 215    | 39.1% | 1.21 | +85.8%  | 13.7% | +0.126R   |
| 2.5R | 194    | 36.1% | 1.30 | +150.6% | 15.7% | +0.193R   |
| **3.0R** | 185 | 35.1% | **1.43** | **+273.5%** | **17.5%** | **+0.276R** |
| 3.5R | 180    | 30.6% | 1.25 | +100.1% | 19.3% | +0.176R   |
| 4.0R | 179    | 30.7% | 1.46 | +322.7% | 20.9% | +0.319R   |
Decision: **adopt 3R**. 4R marginal (PF +0.03, DD +3.4pp) — noise.

### ID16 — Sizing quality multiplier · **DONE this batch**
shape_score → capital multiplier (0.60x - 1.20x). Applied on top of
regime multiplier. Absolute cap raised 20% → 25%.

### ID17 — Robustness check (different window) · **NEXT**
Run fast_wf on alternate 2-year and 4-year windows:
`python fast_wf.py --years 2` and `--years 4`.
If PF stays in 1.3-1.5 range, the edge is stable.

### ID18 — Hybrid tranche exits · **FUTURE**
Current model: full exit at target. Alternative: exit 1/3 at 2R,
1/3 at 3R, trail remaining 1/3 with 10-EMA. Requires partial-exit
support in backtest.py. Test against current 3R.

### ID19 — Central strategy config module · **FUTURE**
Move all SetupDetector thresholds + TARGET_R + regime thresholds into
a single `strategy_config.py`. Enables one-file sweeps. (ID7 concern.)

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
### FWF Walk-forward v3 · DONE (PF 1.43 at 3R, +273.5%, DD 17.5%)

---

## G. STATUS SUMMARY

| ID   | Item                      | Status       |
|------|---------------------------|--------------|
| R1–R16 | Rules                   | Active       |
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
| ID17 | Robustness check          | NEXT         |
| ID18 | Hybrid tranche exits      | FUTURE       |
| ID19 | Central strategy config   | FUTURE       |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py