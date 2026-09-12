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
- **R18** When two approaches give statistically equivalent PF/expectancy
          but one is more complex, keep the simpler one.
- **R19** **System identifies. Owner decides.** No prescribed exits,
          targets, sizing, or signals. The tool presents data.
- **R20** Log every owner expectation/instruction in BACKLOG immediately,
          even mid-conversation.
- **R21** Every candidate presented with the full picture — predictability,
          potential, historical hit rate at multiple R levels, candle
          behaviour, sector context.
- **R22** All tunable parameters live in `strategy_config.py`. Edit one
          file to change behavior.

---

## B. INSTRUCTIONS
### 2026-09-12
I1–I18 (see EXECUTION_LOG)
I19 Central config migration (this batch).
I20 After ID19 → do ID21 (production deployment).
I21 For every setup shown, present everything the owner needs to judge:
     predictability, potential, historical hit rate at multiple R levels,
     candle behaviour, sector context.

---

## C. DEMANDS
D1 Ideas never lost · D2 Durable log · D3 Fast pace.

---

## D. IDEAS

### ID1–ID10 · DONE
### ID11 — Signal sparsity fix · **DONE** (0.4% → 8.0%)
### ID12 — Alt setup patterns · **FUTURE**
### ID13 — Fast validation · **DONE**
### ID14 — Meta-model plateau · **OPEN** (AUC 0.629 stable)
### ID15 — Target sweep · **DONE** (3R as default reference)
### ID16 — Sizing quality multiplier · **DONE**
### ID17 — Robustness check · **DONE** (PF 1.73 / 1.43 / 1.16 across windows)
### ID18 — Hybrid tranche exits · **REJECTED** (per R16/R18)
### ID19 — Central strategy config · **DONE this batch**
All tunable parameters in `strategy_config.py`. Migrated modules:
setup, backtest, scanner, sizing, all_weather.

### ID20 — Strategy runs dashboard · **DONE**
### ID21 — Production deployment · **NEXT**
Final consolidated sweep across windows, lock reference params,
fresh full scan, verify first real signals land.

### ID22 — Research cockpit: full presentation · **PLANNED**
For every setup shown, present the full picture:
- Historical hit rate at +1R / +2R / +3R / +4R (from similar past setups)
- Median time-to-target at each R level
- Max favorable / adverse excursion distribution
- Candle behaviour at signal (mother bar, tightness, volume profile)
- Sector context (sector RS, similar sectors in same state)
- Predictability score (from meta-model, decomposed)
- Potential score (distance to 52w high, momentum alignment)
Owner decides which to look at; system does not rank or recommend.

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
### FSP Setup v3.5 · DONE (config-driven)
### FWF Walk-forward v5 · DONE (config-driven)
### FSR Strategy Runs ledger + UI · DONE
### FCONF Central Config · DONE this batch

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
| ID21 | Production deployment     | NEXT         |
| ID22 | Research cockpit          | PLANNED      |

---

## DEFERRED
- Settings `.env` / admin creds
- HTTPS via nginx + certbot
- Rotate secrets
- Retire Streamlit app.py