# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.
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
- **R20** Log every owner instruction in BACKLOG **immediately**.
- **R21** Every candidate presented with full picture.
- **R22** All tunable parameters in `strategy_config.py`.
- **R23** Optional integrations skip gracefully if creds/files missing.
- **R24** Research tables are sortable + colour-coded by sample size.
- **R25** **Portal is redesigned around the two-pillar model.**
- **R26** **Strategies are JSON, not code.**
- **R27** **Data source fixes are probed, not guessed.**
- **R28** **No partial edits — every file is sent as a full replacement,
          including documentation files (backlog, execution log,
          handoff, portal redesign).**

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
- **I1** Fix every PO issue identified + requirements + PROJECT_HANDOFF.
- **I2** Sequence: Option 1 (all-weather) first; then 2, 3 sequentially.
- **I3** Update PROJECT_HANDOFF.
- **I4** Fix impulse calculation bug in setup.py.
- **I5** Fix sparse fundamentals data.
- **I6** Restructure BACKLOG by category.
- **I7** Create EXECUTION_LOG.md.

### Session 2 — 2026-09-12 (midday → evening)
- **I8**  3-4 edits per response.
- **I9**  Universe unification via shared module.
- **I10** Replace alert modules with unified `alerts`.
- **I11** Scale up validation to get a real edge verdict.
- **I12** Address signal sparsity.
- **I13** Keep validation fast (Backtester path).
- **I14** Correct verdict logic — PF-driven.
- **I15** Adopt 3R target after sweep.
- **I16** Add quality multiplier to sizing.
- **I17** Keep 3R — reject 4R.
- **I18** Reject tranche exits.
- **I19** Central config migration.
- **I20** After ID19 → do ID21.
- **I21** Present full picture per candidate.
- **I22** Graceful skips for ml + sheets.
- **I23** ID22 (research cockpit v1).
- **I24** ID22b (research universe view).
- **I25** Proceed with sortable + colouring AND sector aggregation.
- **I26** Insert all logs of demands/executions/to-do/left.
- **I27** Portal redesign vision captured in `PORTAL_REDESIGN.md`.
- **I28** Proceed with Phase 1 (portal redesign).
- **I29** Proceed with Phase 2 (rule engine + seed strategies).
- **I30** Seed Multibagger, RCP, Episodic Pivot.
- **I31** Correct RCP + Episodic Pivot per owner's specific rules.
- **I32** Proceed with ID42 (in-browser strategy editor).
- **I33** Proceed with ID43 (backtest sandbox).
- **I34** Update backlog.md and EXECUTION_LOG.md every batch.
- **I35** Proceed with ID44. Step 1: probe TV.
- **I36** Step 2: rewrite fetcher, quality-only Multibagger.
- **I37** Fix score outlier bug — percentile scoring.
- **I38** Proceed with Phase 3 + Phase 4. Start Phase 3 with ID47.
- **I39** ID47 verified. Proceed with ID46 (signature matching).
- **I40** Add weekly setup_pool rebuild job (Sunday 06:00 IST).
- **I41** (merged into I40)
- **I42** Proceed with ID48 + ID49.

### Session 3 — 2026-09-13
- **I43** Fix pattern_grader to handle BEARISH patterns (H&S top).
          Previously all bearish tags went ungraded.
- **I44** No partial edits — always full file replacements, including
          documentation files.

---

## C. DEMANDS

- **D1** Ideas never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace.
- **D4** Portal presents, never recommends (R19).
- **D5** Every panel serves a decision the owner will actually make.
- **D6** Backlog and execution log stay current — no drift.

---

## D. IDEAS

### ID1 — All-weather swing mode · **DONE**
### ID2 — Long-term Value Radar · **DONE**
### ID3 — Custom scanners: swing + positional · **PARTIAL**
### ID4 — Free data source expansion · **PLANNED (Phase 4)**
### ID5 — "Feeding of life into stocks" · **FUTURE**
### ID6 — Universe split · **PARTIAL**
### ID7 — Trim / unify / simplify · **MOSTLY DONE**
### ID8 — Trend-regime scanner · **DONE**
### ID9 — Scanner UI panels · **DONE**
### ID10 — Meta-model v7 · **DONE**
### ID11 — Signal sparsity fix · **DONE** (0.4% → 8.0%)
### ID12 — Alt setup patterns · **FUTURE**
### ID13 — Fast validation · **DONE**
### ID14 — Meta-model plateau · **OPEN**
### ID15 — Target sweep · **DONE** (3R adopted)
### ID16 — Sizing quality multiplier · **DONE**
### ID17 — Robustness check · **DONE**
### ID18 — Hybrid tranche exits · **REJECTED**
### ID19 — Central strategy config · **DONE**
### ID20 — Strategy runs dashboard · **DONE**
### ID21 — Production deployment · **DONE**
### ID22 — Research Cockpit v1 · **DONE**
### ID22b — Research Universe · **DONE**
### ID22c — Warm cache nightly · **DONE**
### ID23 — Sector aggregation · **DONE**
### ID23b — Reliability colour coding · **DONE**
### ID23c — Sortable columns · **DONE**
### ID24 — Candle behaviour analytics · **DONE** (as ID47)
### ID25 — Sector strength overlay · **FUTURE**
### ID26 — Setup similarity matching · **DONE** (as ID46)
### ID27 — Rule DSL engine · **DONE**
### ID28 — Two-pillar portal redesign · **DONE**
### ID29 — Signature matching across symbols · **DONE** (as ID46)
### ID30 — Pattern condition transparency · **DONE** (as ID48)
### ID31 — Time-machine chart markers · **DONE** (as ID49)
### ID32 — Data source plugin system · **PLANNED (Phase 4)**
### ID33 — Unified stock card · **PLANNED (Phase 3)**
### ID34 — Backtest sandbox per strategy · **DONE** (as ID43)
### ID35 — Progressive disclosure · **DONE**
### ID36 — Compare mode · **NEXT (Phase 3)**
### ID37 — Strategy library page · **PARTIAL**
### ID38 — Strategy seeds · **DONE**
### ID39 — Rule DSL engine · **DONE**
### ID40 — Seed strategies · **DONE**
### ID41 — Strategy UI · **DONE**
### ID42 — In-browser strategy editor · **DONE**
### ID43 — Backtest sandbox per strategy · **DONE**
### ID44 — Fundamentals data fix · **DONE**
### ID45 — Score normalization (percentile) · **DONE**
### ID46 — Signature matching · **DONE**
### ID47 — Candle behaviour analytics · **DONE**
### ID48 — Pattern condition transparency · **DONE**
### ID49 — Time-machine chart markers · **DONE**
### ID50 — Compare mode · **NEXT (Phase 3)**
### ID51 — Unified stock card · **PLANNED (Phase 3)**
### ID52 — Data source plugins · **PLANNED (Phase 4)**
### ID53 — Bearish pattern grading · **DONE this batch**
`pattern_grader._grade_one` now handles direction. Bearish patterns
(H&S top warning) are graded on the short side: trigger = LOW breaks
below breakout, stop above, target below at -1R.

---

## E. IMAGINATIONS

- **IM1** Personal multi-strategy quant terminal.
- **IM2** Bear-market accumulation engine.
- **IM3** Self-documenting, self-improving system.
- **IM4** Research cockpit (predictability, potential, candle behaviour).
- **IM5** Two-pillar portal — Funda and Swing as distinct product lines.
- **IM6** Owner-authored strategies — write rules, see results in-browser.

---

## F. FEATURES COMPLETED

- **FC** Regime Spectrum (5 levels)
- **FP** Fundamentals Pipeline (863 symbols weekly)
- **FS** Sizing with quality multiplier
- **FA** Unified Alerts
- **FU** Canonical Universe
- **FT** Trend Scanner v3
- **FP2** Positional Scanner
- **FV** Value Radar v2
- **FM** Meta-Model v7 (AUC 0.629)
- **FML** Price-Model (AUC 0.584 / 0.589)
- **FVAL** Fast Validation
- **FSP** Setup v3.5 (config-driven)
- **FWF** Walk-forward v5 (config-driven)
- **FSR** Strategy Runs ledger + UI
- **FCONF** Central Config
- **FDEP** Deployment Verification (15/15)
- **FRC** Research Cockpit v1
- **FRU** Research Universe
- **FRS** Sector Aggregation
- **FSRT** Sortable + Reliability UI
- **FP1** Portal Phase 1 (5-tab nav)
- **FRE** Rule Engine (JSON strategy DSL)
- **FSE** Seed strategies
- **FSU** Strategy UI (Run/Edit/Backtest buttons)
- **FED** In-browser strategy editor (ID42)
- **FBT** Strategy backtest sandbox (ID43)
- **FDF** Fundamentals v5 (probe-verified columns)
- **FPS** Percentile scoring
- **FCA** Candle behaviour analytics (ID47)
- **FSM** Signature matching (ID46)
- **FPB** Weekly pool rebuild scheduler job
- **FPT** Pattern transparency (ID48)
- **FTM** Time-machine chart markers (ID49)
- **FBPG** Bearish pattern grading (ID53)

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R28 | Rules                    | Active       |
| I1–I44 | Instructions             | Applied      |
| ID1–ID43 | Various               | DONE / listed |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Score normalization       | DONE         |
| ID46  | Signature matching        | DONE         |
| ID47  | Candle behaviour          | DONE         |
| ID48  | Pattern transparency      | DONE         |
| ID49  | Time-machine markers      | DONE         |
| ID50  | Compare mode              | NEXT         |
| ID51  | Unified stock card        | PLANNED P3   |
| ID52  | Data source plugins       | PLANNED P4   |
| ID53  | Bearish pattern grading   | DONE         |

---

## H. REMAINING / LEFT

### Phase 3
- ID50 Compare mode — NEXT
- ID51 Unified stock card

### Phase 4
- ID52 Data source plugin system
- Growth data source integration (needed for Multibagger growth filters)

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets (Telegram token, GCP key)
- Retire Streamlit app.py (nse.service)
- Google Sheets sync (missing GCP key)

---

## I. HOW THIS FILE GROWS
Every new idea / instruction / demand gets a numbered entry in the
appropriate section. DONE items stay for history. REMAINING tracks
what's left. PORTAL_REDESIGN.md captures vision. Strategies live in
data/strategies.json. EXECUTION_LOG.md captures every shipped batch.