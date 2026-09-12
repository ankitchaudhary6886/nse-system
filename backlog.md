# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in `PORTAL_REDESIGN.md`.
- Survives chat migration. A new session reads this + EXECUTION_LOG
  + PORTAL_REDESIGN.

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
- **R13** Fast feedback loops (funnels/diags ~5s), not multi-minute waits.
- **R14** Verdicts are PF-driven. Do not dismiss on win rate alone.
- **R15** Parameter changes are swept, not picked.
- **R16** Non-monotonic sweep results are NOISE, not signal.
- **R17** Multi-window walk-forward is the ground truth.
- **R18** Equivalent results → simpler wins.
- **R19** **System identifies. Owner decides.** No prescribed exits,
          targets, sizing, or signals.
- **R20** Log every owner instruction in BACKLOG immediately.
- **R21** Every candidate presented with full picture — predictability,
          potential, historical hit rate at multiple R levels, candle
          behaviour, sector context.
- **R22** All tunable parameters live in `strategy_config.py`.
- **R23** Optional integrations skip gracefully if creds/files missing.
- **R24** Research tables are sortable + colour-coded by sample size:
          green ≥10, amber 5-9, grey <5, dash for none.
- **R25** **Portal is redesigned around the two-pillar model** — Funda
          (positional) and Swing (midcap/smallcap momentum). See
          `PORTAL_REDESIGN.md`. No new features land before Phase 1 of
          that roadmap.

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
- **I14** Correct verdict logic — PF-driven, not WR-driven.
- **I15** Adopt 3R target after sweep.
- **I16** Add quality multiplier to sizing.
- **I17** Keep 3R — reject 4R (non-monotonic).
- **I18** Reject tranche exits (PF identical, DD worse).
- **I19** Central config migration.
- **I20** After ID19 → do ID21 (production deployment).
- **I21** For every setup shown, present everything the owner needs.
- **I22** Fix graceful skips for ml + sheets; fix fundamentals date check.
- **I23** ID22 (research cockpit v1) — shipped.
- **I24** ID22b shipped — research universe view.
- **I25** Proceed with A) sortable + reliability colouring AND
          B) ID23 sector aggregation.
- **I26** Insert all logs of demands/executions/to-do/left.
- **I27** **Portal redesign vision** — 9-point purpose, 10 innovative
          ideas, 4-phase roadmap. Logged in `PORTAL_REDESIGN.md`.
          Next: Phase 1 (portal redesign + noise reduction).

---

## C. DEMANDS  (hard requirements)

- **D1** Ideas never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace.
- **D4** Portal must present, never recommend (R19).
- **D5** Every panel serves a decision the owner will actually make.

---

## D. IDEAS  (chronological)

### ID1 — All-weather swing mode · **DONE**
### ID2 — Long-term Value Radar · **DONE**
### ID3 — Custom scanners: swing + positional · **PARTIAL**
### ID4 — Free data source expansion (ScanX etc.) · **PLANNED (Phase 4)**
### ID5 — "Feeding of life into stocks" · **FUTURE**
### ID6 — Universe split · **PARTIAL**
### ID7 — Trim / unify / simplify · **MOSTLY DONE**
### ID8 — Trend-regime scanner · **DONE**
### ID9 — Scanner UI panels · **DONE**
### ID10 — Meta-model v7 · **DONE**
### ID11 — Signal sparsity fix · **DONE**
### ID12 — Alt setup patterns · **FUTURE**
### ID13 — Fast validation · **DONE**
### ID14 — Meta-model plateau · **OPEN**
### ID15 — Target sweep · **DONE**
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
### ID24 — Candle behaviour analytics · **PLANNED (Phase 3)**
### ID25 — Sector strength overlay · **FUTURE**
### ID26 — Setup similarity matching · **PLANNED (Phase 3)**

### New (from portal redesign vision, 2026-09-12)

### ID27 — Rule DSL engine · **PLANNED (Phase 2)**
JSON strategy rules stored in DB, edited in UI. Zero code for new
strategies. See PORTAL_REDESIGN §Idea 1.

### ID28 — Two-pillar portal redesign · **PLANNED (Phase 1)**
Funda / Swing / Research / Ledger / System nav. Overview retired.
See PORTAL_REDESIGN §2, §4.

### ID29 — Signature matching across symbols · **PLANNED (Phase 3)**
Beyond per-symbol: find N closest historical setups across ALL symbols
by feature distance. Pooled stats. See PORTAL_REDESIGN §Idea 2.

### ID30 — Pattern condition transparency · **PLANNED (Phase 3)**
Per-condition pass/fail UI. See PORTAL_REDESIGN §Idea 3.

### ID31 — Time-machine chart markers · **PLANNED (Phase 3)**
Historical pattern signals overlaid on charts, outcome-coloured.
See PORTAL_REDESIGN §Idea 4.

### ID32 — Data source plugin system · **PLANNED (Phase 4)**
Standard interface, auto-discovery, fallback chain, health dashboard.
See PORTAL_REDESIGN §Idea 5.

### ID33 — Unified stock card · **PLANNED (Phase 1)**
One card component used everywhere. See PORTAL_REDESIGN §Idea 6.

### ID34 — Backtest sandbox per strategy · **PLANNED (Phase 2)**
In-browser "Run on history" for any strategy rule. See §Idea 7.

### ID35 — Progressive disclosure everywhere · **PLANNED (Phase 1)**
Default answer, derivation on click. See §Idea 8.

### ID36 — Compare mode · **PLANNED (Phase 3)**
Multi-select 2-4 stocks side-by-side. See §Idea 9.

### ID37 — Strategy library page · **PLANNED (Phase 2)**
List all strategies, rules preview, backtest PF, enable/disable.
See §Idea 10.

### ID38 — Strategy seeds (Multibagger, RCP, Episodic Pivot) · **PLANNED (Phase 2)**
Rule design session needed with owner. See PORTAL_REDESIGN §6.

---

## E. IMAGINATIONS

- **IM1** Personal multi-strategy quant terminal.
- **IM2** Bear-market accumulation engine.
- **IM3** Self-documenting, self-improving system.
- **IM4** Research cockpit (predictability, potential, candle behaviour).
- **IM5** **Two-pillar portal** — Funda and Swing as distinct product
          lines, each with its own strategies, each respecting market
          regime. Custom scanners live inside each pillar.
- **IM6** **Owner-authored strategies** — the tool becomes a platform
          where owner writes rules in JSON, sees results in-browser.

---

## F. FEATURES COMPLETED

- FC Regime Spectrum (5 levels)
- FP Fundamentals Pipeline (863 symbols weekly)
- FS Sizing with quality multiplier
- FA Unified Alerts
- FU Canonical Universe
- FT Trend Scanner v3
- FP2 Positional Scanner
- FV Value Radar v2
- FM Meta-Model v7 (AUC 0.629)
- FML Price-Model (AUC 0.584 / 0.589)
- FVAL Fast Validation
- FSP Setup v3.5 (config-driven)
- FWF Walk-forward v5 (config-driven)
- FSR Strategy Runs ledger + UI
- FCONF Central Config
- FDEP Deployment Verification (15/15)
- FRC Research Cockpit v1
- FRU Research Universe
- FRS Sector Aggregation
- FSRT Sortable + Reliability UI

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R25 | Rules                    | Active       |
| I1–I27 | Instructions             | Applied      |
| ID1   | All-weather swing         | DONE         |
| ID2   | Value Radar v2            | DONE         |
| ID3   | Custom scanners           | PARTIAL      |
| ID4   | Free data sources         | PLANNED P4   |
| ID5   | Feed life into stocks     | FUTURE       |
| ID6   | Universe split            | PARTIAL      |
| ID7   | Trim / unify / simplify   | MOSTLY DONE  |
| ID8   | Trend scanner             | DONE         |
| ID9   | Scanner UI panels         | DONE         |
| ID10  | Meta-model v7             | DONE         |
| ID11  | Signal sparsity fix       | DONE         |
| ID12  | Alt setup patterns        | FUTURE       |
| ID13  | Fast validation           | DONE         |
| ID14  | Meta-model plateau        | OPEN         |
| ID15  | Target sweep              | DONE         |
| ID16  | Sizing quality multiplier | DONE         |
| ID17  | Robustness check          | DONE         |
| ID18  | Hybrid tranche exits      | REJECTED     |
| ID19  | Central strategy config   | DONE         |
| ID20  | Strategy runs dashboard   | DONE         |
| ID21  | Production deployment     | DONE         |
| ID22  | Research Cockpit v1       | DONE         |
| ID22b | Research Universe         | DONE         |
| ID22c | Warm cache nightly        | DONE         |
| ID23  | Sector aggregation        | DONE         |
| ID23b | Reliability colours       | DONE         |
| ID23c | Sortable columns          | DONE         |
| ID24  | Candle behaviour          | PLANNED P3   |
| ID25  | Sector strength overlay   | FUTURE       |
| ID26  | Setup similarity          | PLANNED P3   |
| ID27  | Rule DSL engine           | PLANNED P2   |
| ID28  | Two-pillar portal         | PLANNED P1   |
| ID29  | Signature matching        | PLANNED P3   |
| ID30  | Pattern transparency      | PLANNED P3   |
| ID31  | Time-machine markers      | PLANNED P3   |
| ID32  | Data source plugins       | PLANNED P4   |
| ID33  | Unified stock card        | PLANNED P1   |
| ID34  | Backtest sandbox          | PLANNED P2   |
| ID35  | Progressive disclosure    | PLANNED P1   |
| ID36  | Compare mode              | PLANNED P3   |
| ID37  | Strategy library page     | PLANNED P2   |
| ID38  | Strategy seeds (M/RCP/EP) | PLANNED P2   |

---

## H. REMAINING / LEFT

### Next (Phase 1 — portal redesign)
- ID28 Two-pillar portal nav
- ID33 Unified stock card
- ID35 Progressive disclosure
- Remove noise from Overview
- Retire Overview tab

### Phase 2 (rule engine + strategies)
- ID27 Rule DSL engine
- ID34 Backtest sandbox
- ID37 Strategy library
- ID38 Multibagger + RCP + Episodic Pivot rule design

### Phase 3 (research upgrades)
- ID24 Candle behaviour analytics
- ID29 Signature matching across symbols
- ID30 Pattern transparency
- ID31 Time-machine chart markers
- ID36 Compare mode

### Phase 4 (data plugins)
- ID32 Data source plugin system
- Migrate TradingView, Yahoo, NSE
- Add Chartink, ScanX
- Health dashboard

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets (Telegram token, GCP key)
- Retire Streamlit app.py (nse.service)
- Google Sheets sync (missing GCP key)

---

## I. HOW THIS FILE GROWS
Every new idea / instruction / demand gets a numbered entry in the
appropriate section. DONE items stay for history. REMAINING section
tracks what's left. Deferred section tracks explicit skips.
PORTAL_REDESIGN.md captures the vision and roadmap in detail.