# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in `PORTAL_REDESIGN.md`.
- Survives chat migration.

---

## A. RULES  (always active)

- **R1**  Whole files only. No patches. Ever.
- **R2**  Plain English. Ask for screenshots when useful.
- **R3**  VS Code (Windows) + Oracle Cloud VM via SSH.
- **R4**  Every change = full file + 1 laptop block + 1 VM block.
- **R5**  Batch related commands into one block per machine.
- **R6**  Skip credential / HTTPS / ops tasks unless explicitly asked.
- **R7**  Every new idea / request / brainstorm → auto-add to BACKLOG.
- **R8**  Instructions tagged with `#` prefix.
- **R9**  Every execution logged in EXECUTION_LOG.md.
- **R10** No pausing; keep momentum.
- **R11** 3-4 file edits per response when possible.
- **R12** Execute new ideas only AFTER the machine is functionally complete.
- **R13** Fast feedback loops (~5s), not multi-minute waits.
- **R14** Verdicts are PF-driven.
- **R15** Parameter changes are swept, not picked.
- **R16** Non-monotonic sweeps = noise.
- **R17** Multi-window WF is ground truth.
- **R18** Equivalent results → simpler wins.
- **R19** **System identifies. Owner decides.** No prescribed exits,
          targets, sizing, or signals.
- **R20** Log every owner instruction in BACKLOG immediately.
- **R21** Every candidate presented with full picture.
- **R22** All tunable parameters in `strategy_config.py`.
- **R23** Optional integrations skip gracefully if creds/files missing.
- **R24** Research tables are sortable + colour-coded by sample size.
- **R25** **Portal is redesigned around the two-pillar model.**
- **R26** **Strategies are JSON, not code.** Every new strategy is a
          rule definition in `data/strategies.json`. No code changes.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
I1–I7 as logged.

### Session 2 — 2026-09-12 (midday → evening)
I8–I28 as logged. Additions this batch:
- **I29** Proceed with Phase 2 (rule engine + seed strategies).
- **I30** Seed: Multibagger, RCP, Episodic Pivot. Owner can edit rules
          in `data/strategies.json`.

---

## C. DEMANDS

- **D1** Ideas never lost.
- **D2** Durable execution log.
- **D3** Fast pace.
- **D4** Portal presents, never recommends.
- **D5** Every panel serves a decision the owner will actually make.

---

## D. IDEAS

All ID1–ID38 previously logged, plus:

### ID39 — Rule DSL engine · **DONE this batch**
Generic evaluator. Reads strategy JSON, computes features per symbol,
applies conditions, ranks by weighted score. Zero code for new
strategies.

### ID40 — Seed strategies (Multibagger / RCP / Episodic Pivot) · **DONE**
Initial definitions in `data/strategies.json`. Owner edits directly.

### ID41 — Strategy execution UI · **DONE**
Funda tab shows fundamental strategies. Swing tab shows swing strategies.
Each has a Run button. Results include per-condition pass/fail marks.

### ID42 — In-browser strategy editor · **NEXT**
JSON editor in the System tab. Save → immediate effect. No file editing.

### ID43 — Backtest sandbox per strategy · **PLANNED (Phase 2 cont.)**
Run any strategy over last N years in browser. Equity curve, hit rate.
Change a rule → re-run. Still in Phase 2.

---

## E. IMAGINATIONS
IM1–IM6 as logged.

---

## F. FEATURES COMPLETED

Prior list, plus:

### FRE — Rule Engine · **DONE this batch**
Generic JSON-driven strategy evaluator.

### FSE — Seed strategies · **DONE**
3 seed strategies. Owner-tunable.

### FSU — Strategy UI · **DONE**
Funda + Swing tabs show strategies with Run buttons.

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R26 | Rules                    | Active       |
| I1–I30 | Instructions             | Applied      |
| ID1–ID23c | As logged             | DONE         |
| ID24  | Candle behaviour          | PLANNED P3   |
| ID25  | Sector strength overlay   | FUTURE       |
| ID26  | Setup similarity          | PLANNED P3   |
| ID27  | Rule DSL engine           | **DONE**     |
| ID28  | Two-pillar portal         | **DONE**     |
| ID29  | Signature matching        | PLANNED P3   |
| ID30  | Pattern transparency      | PLANNED P3   |
| ID31  | Time-machine markers      | PLANNED P3   |
| ID32  | Data source plugins       | PLANNED P4   |
| ID33  | Unified stock card        | IN PROGRESS  |
| ID34  | Backtest sandbox          | PLANNED P2   |
| ID35  | Progressive disclosure    | **DONE**     |
| ID36  | Compare mode              | PLANNED P3   |
| ID37  | Strategy library page     | PARTIAL      |
| ID38  | Strategy seeds            | **DONE**     |
| ID39  | Rule DSL engine           | **DONE**     |
| ID40  | Seed strategies           | **DONE**     |
| ID41  | Strategy UI               | **DONE**     |
| ID42  | In-browser strategy editor| NEXT         |
| ID43  | Backtest sandbox (per strat)| PLANNED P2 |

---

## H. REMAINING / LEFT

### Phase 2 — IN PROGRESS
- ✅ Rule engine
- ✅ 3 seed strategies
- ✅ Strategy UI in Funda + Swing tabs
- ⬜ In-browser strategy editor (ID42)
- ⬜ Backtest sandbox per strategy (ID43)

### Phase 3
- ID24 Candle behaviour analytics
- ID29 Signature matching
- ID30 Pattern transparency
- ID31 Time-machine markers
- ID36 Compare mode

### Phase 4
- ID32 Data source plugins

### Deferred
As logged.

---

## I. HOW THIS FILE GROWS
As logged. PORTAL_REDESIGN.md captures vision. Strategies in
data/strategies.json.