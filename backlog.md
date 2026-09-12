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
- **R19** **System identifies. Owner decides.**
- **R20** Log every owner instruction in BACKLOG **immediately**.
- **R21** Every candidate presented with full picture.
- **R22** All tunable parameters in `strategy_config.py`.
- **R23** Optional integrations skip gracefully if creds/files missing.
- **R24** Research tables are sortable + colour-coded by sample size.
- **R25** Portal is redesigned around the two-pillar model.
- **R26** Strategies are JSON, not code.
- **R27** Data source fixes are probed, not guessed.
- **R28** No partial edits — every file is sent as a full replacement,
          including documentation files.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
I1–I7.

### Session 2 — 2026-09-12 (midday → evening)
I8–I34.

### Session 3 — 2026-09-13
- **I35**–**I42** as previously logged.
- **I43** Fix pattern_grader to handle BEARISH patterns (H&S top).
- **I44** No partial edits — always full file replacements.
- **I45** Proceed with ID50 (compare mode) + ID51 (unified stock card)
          to finish Phase 3.

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

### ID1–ID49 as previously logged (all DONE or listed).
### ID50 — Compare mode · **DONE this batch**
New `/api/compare` endpoint + `compare_tool.py`. Compare panel in
Research tab with text input (2-4 comma-separated symbols). Renders
a side-by-side table covering overview / fundamentals / signal /
history / signature match. Reads only from cached data and existing
tables — no on-demand compute.
### ID51 — Unified stock card · **DONE this batch**
`terminal/static/cards.js` defines `renderUnifiedCard(item)`. Now used
by Top Picks, Radar, Trend, Positional, and Value Radar — same visual
language everywhere.
### ID52 — Data source plugins · **PLANNED (Phase 4)**
### ID53 — Bearish pattern grading · **DONE** (previous batch)

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED

- **FC** Regime Spectrum (5 levels)
- **FP** Fundamentals Pipeline
- **FS** Sizing with quality multiplier
- **FA** Unified Alerts
- **FU** Canonical Universe
- **FT** Trend Scanner v3
- **FP2** Positional Scanner
- **FV** Value Radar v2
- **FM** Meta-Model v7
- **FML** Price-Model
- **FVAL** Fast Validation
- **FSP** Setup v3.5
- **FWF** Walk-forward v5
- **FSR** Strategy Runs ledger
- **FCONF** Central Config
- **FDEP** Deployment Verification
- **FRC** Research Cockpit v1
- **FRU** Research Universe
- **FRS** Sector Aggregation
- **FSRT** Sortable + Reliability UI
- **FP1** Portal Phase 1 (5-tab nav)
- **FRE** Rule Engine (JSON strategy DSL)
- **FSE** Seed strategies
- **FSU** Strategy UI
- **FED** In-browser strategy editor
- **FBT** Strategy backtest sandbox
- **FDF** Fundamentals v5
- **FPS** Percentile scoring
- **FCA** Candle behaviour analytics
- **FSM** Signature matching
- **FPB** Weekly pool rebuild scheduler job
- **FPT** Pattern transparency
- **FTM** Time-machine chart markers
- **FBPG** Bearish pattern grading
- **FCMP** Compare mode (ID50)
- **FUC** Unified stock card (ID51)

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R28 | Rules                    | Active       |
| I1–I45 | Instructions             | Applied      |
| ID44  | Fundamentals fix          | DONE         |
| ID45  | Score normalization       | DONE         |
| ID46  | Signature matching        | DONE         |
| ID47  | Candle behaviour          | DONE         |
| ID48  | Pattern transparency      | DONE         |
| ID49  | Time-machine markers      | DONE         |
| ID50  | Compare mode              | DONE         |
| ID51  | Unified stock card        | DONE         |
| ID52  | Data source plugins       | NEXT (P4)    |
| ID53  | Bearish pattern grading   | DONE         |

---

## H. REMAINING / LEFT

### Phase 3 — **COMPLETE**
All items shipped.

### Phase 4 (this or next session)
- **ID52** Data source plugin system — standard interface for
          TradingView / Yahoo / NSE / Chartink / ScanX / screener.in.
          Auto-discovery, fallback chain, health dashboard.
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