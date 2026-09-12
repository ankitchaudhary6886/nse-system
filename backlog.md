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
- **R16** Non-monotonic sweeps = noise. Prefer simpler parameter.
- **R17** Multi-window WF is ground truth.
- **R18** Equivalent results → simpler wins.
- **R19** **System identifies. Owner decides.** No prescribed exits,
          targets, sizing, or signals.
- **R20** Log every owner instruction in BACKLOG immediately.
- **R21** Every candidate presented with full picture.
- **R22** All tunable parameters in `strategy_config.py`.
- **R23** Optional integrations skip gracefully if creds/files missing.
- **R24** Research tables are sortable + colour-coded by sample size.
- **R25** **Portal is redesigned around the two-pillar model** — Funda
          (positional) and Swing (midcap/smallcap momentum). See
          `PORTAL_REDESIGN.md`.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
I1–I7 as previously logged.

### Session 2 — 2026-09-12 (midday → evening)
I8–I26 as previously logged.
- **I27** Portal redesign vision captured in `PORTAL_REDESIGN.md`.
- **I28** Proceed with Phase 1 (portal redesign).

---

## C. DEMANDS

- **D1** Ideas never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace.
- **D4** Portal must present, never recommend (R19).
- **D5** Every panel serves a decision the owner will actually make.

---

## D. IDEAS

All ID1–ID38 as previously logged. Status changes this batch:
- **ID28** Two-pillar portal redesign · **IN PROGRESS** — nav shipped,
  panels reorganized, progressive disclosure in place.
- **ID35** Progressive disclosure · **DONE this batch** — sizing,
  SHAP why, delivery counts all behind toggles.
- **ID33** Unified stock card · **IN PROGRESS** — helper function
  `renderUnifiedCard` added; will be applied to more places next.

---

## E. IMAGINATIONS

IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED

All previously listed, plus:

### FP1 — Portal Phase 1 · **DONE**
- 5-tab nav: Funda / Swing / Research / Ledger / System.
- Overview tab retired.
- Panels reorganized by product line.
- Progressive disclosure on sizing / SHAP / delivery.
- Legacy "overview" view name remapped to "research" for
  backwards compatibility.

---

## G. STATUS SUMMARY

(unchanged, plus ID28 / ID33 / ID35 statuses updated)

---

## H. REMAINING / LEFT

### Phase 1 · **IN PROGRESS**
- ✅ New nav
- ✅ Panels reorganized
- ✅ Progressive disclosure
- ✅ Overview retired
- ⬜ Apply unified card to scanner result lists (next)

### Phase 2
- ID27 Rule DSL engine
- ID34 Backtest sandbox
- ID37 Strategy library
- ID38 Multibagger + RCP + Episodic Pivot rule design

### Phase 3
- ID24 Candle behaviour analytics
- ID29 Signature matching
- ID30 Pattern transparency
- ID31 Time-machine markers
- ID36 Compare mode

### Phase 4
- ID32 Data source plugins

### Deferred
As previously logged.

---

## I. HOW THIS FILE GROWS
As previously logged. PORTAL_REDESIGN.md captures vision + roadmap.