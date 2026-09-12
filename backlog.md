# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in `EXECUTION_LOG.md`.
- Survives chat migration. A new session reads this + EXECUTION_LOG.

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
- **R16** Non-monotonic sweep results are NOISE, not signal. Prefer the
          simpler/earlier parameter when in doubt.
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
- **I8** 3-4 edits per response.
- **I9** Universe unification via shared module.
- **I10** Replace alert modules with unified `alerts`.
- **I11** Scale up validation to get a real edge verdict.
- **I12** Address signal sparsity.
- **I13** Keep validation fast (Backtester path or funnel diagnostics).
- **I14** Correct verdict logic — PF-driven, not WR-driven.
- **I15** Adopt 3R target after sweep.
- **I16** Add quality multiplier to sizing.
- **I17** Keep 3R — reject 4R (non-monotonic curve).
- **I18** Reject tranche exits (PF identical, DD worse).
- **I19** Central config migration.
- **I20** After ID19 → do ID21 (production deployment).
- **I21** For every setup shown, present everything the owner needs.
- **I22** Fix graceful skips for ml + sheets; fix fundamentals date check.
- **I23** ID22 (research cockpit v1) — shipped.
- **I24** ID22b shipped — research universe view.
- **I25** Proceed with A) sortable + reliability colouring AND
          B) ID23 sector aggregation.
- **I26** Insert all logs of demands/executions/to-do/left (this batch).

---

## C. DEMANDS  (hard requirements)

- **D1** Ideas never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace.

---

## D. IDEAS  (chronological)

### ID1 — All-weather swing mode · **DONE**
Defensive-regime swing entries. 115 candidates → 5 signals.

### ID2 — Long-term Value Radar · **DONE**
Quality + value composite, tiers A/B/C. Weekly Sunday 09:00.

### ID3 — Custom scanners: swing + positional · **PARTIAL**
- ID3a Positional scanner — DONE
- ID3b Swing scanner (custom) — PARTIAL (screener_engine covers)

### ID4 — Free data source expansion (ScanX etc.) · **FUTURE**

### ID5 — "Feeding of life into stocks" · **FUTURE** (scope TBD)

### ID6 — Universe split · **PARTIAL**
Fundamentals covers Nifty 500 ∪ band. Full Nifty 1000 target.

### ID7 — Trim / unify / simplify · **MOSTLY DONE**
- Alert modules — DONE (alerts.py canonical)
- Canonical universe source — DONE
- Pick one screener — pending
- Retire Streamlit app.py — deferred
- Single price ingester — pending

### ID8 — Trend-regime scanner · **DONE**
Price > EMA50 AND > EMA200. Unbounded score, no saturation.

### ID9 — Scanner UI panels · **DONE**

### ID10 — Meta-model v7 (33 features) · **DONE**
AUC 0.629 stable. Plateau open (ID14).

### ID11 — Signal sparsity fix · **DONE**
0.4% → 8.0% setup pass rate.

### ID12 — Alt setup patterns · **FUTURE**

### ID13 — Fast validation · **DONE**
fast_wf.py (80s), quick_funnel.py (5s), quick_setup_diag.py (3s).

### ID14 — Meta-model plateau · **OPEN**
3 retrains, same 0.629. Features at diminishing returns.

### ID15 — Target sweep · **DONE**
2R / 2.5R / 3R / 3.5R / 4R measured. 3R adopted (monotonic improvement
up to 3R; 3.5R blip is noise; 4R marginal).

### ID16 — Sizing quality multiplier · **DONE** (v4)
shape_score → 0.60x-1.20x on top of regime multiplier.

### ID17 — Robustness check · **DONE**
Multi-window WF: PF 1.72 (2y) / 1.43 (3y) / 1.16 (4y). All positive.
Conservative baseline: 20-25% CAGR / ~18% DD.

### ID18 — Hybrid tranche exits · **REJECTED**
PF identical, DD worse by 7.3pp, return worse by 65pp. Per R16/R18,
keep full-exit. Code retained behind `TRANCHES_ENABLED = False`.

### ID19 — Central strategy config · **DONE**
All thresholds in `strategy_config.py`. Migrated: setup, backtest,
scanner, sizing, all_weather.

### ID20 — Strategy runs dashboard · **DONE**

### ID21 — Production deployment · **DONE**
`verify_deployment.py` (checks first, `--fast`, `--sweep`).
15/15 checks green. `ml_train.py` produced `data/ml_models.pkl`.

### ID22 — Research Cockpit v1 · **DONE**
Per-symbol 5y analysis: P(trigger), P(+1R/+2R/+3R/+4R), median bars,
MFE/MAE distributions, outcome mix, recent setups. Cached 7 days.

### ID22b — Research Universe · **DONE**
Today's setups joined with cached stats. Sortable. Reliability colour.

### ID22c — Warm cache nightly · **DONE**
Scheduler job at 16:20 IST computes stats for today's signals.

### ID23 — Sector aggregation · **DONE**
Pools raw setups across symbols by sector. Real pooling, not averages
of averages. Endpoint `/api/research-sector`. Sortable + reliability.

### ID23b — Reliability colour coding · **DONE**
`rel-strong` (≥10), `rel-mod` (5-9), `rel-thin` (1-4), `rel-none` (0).

### ID23c — Sortable columns · **DONE**
Click any header to sort ascending/descending.

### ID24 — Candle behaviour analytics · **FUTURE**
Classify each setup's mother bar (inside, hammer, tight cluster width
vs ATR). Compute hit rate conditioned on that feature.

### ID25 — Sector strength overlay · **FUTURE**
Join sector aggregation with `sector_gate.sector_perf` — see if hit
rates differ across sector regimes.

### ID26 — Setup similarity matching · **FUTURE**
For a live setup, find N closest historical setups across all symbols
by feature distance. Personalised context, not symbol-only.

---

## E. IMAGINATIONS

- **IM1** Personal multi-strategy quant terminal.
- **IM2** Bear-market accumulation engine.
- **IM3** Self-documenting, self-improving system.
- **IM4** Research cockpit (predictability, potential, candle behaviour).

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
| R1–R24 | Rules                    | Active       |
| I1–I26 | Instructions             | Applied      |
| ID1   | All-weather swing         | DONE         |
| ID2   | Value Radar v2            | DONE         |
| ID3a  | Positional scanner        | DONE         |
| ID3b  | Swing scanner (custom)    | PARTIAL      |
| ID4   | Free data sources         | FUTURE       |
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
| ID24  | Candle behaviour          | FUTURE       |
| ID25  | Sector strength overlay   | FUTURE       |
| ID26  | Setup similarity          | FUTURE       |

---

## H. REMAINING / LEFT

### Next (queued, not started)
- **ID24** Candle behaviour analytics
- **ID25** Sector strength overlay
- **ID26** Setup similarity matching
- **ID3b** Custom swing scanner consolidation
- **ID7** Trim pass completion (one screener, one price ingester)
- **ID12** Alt setup patterns if 3R plateaus
- **ID4** Free data source expansion (ScanX)
- **ID5** "Feed life into stocks" (scope TBD)
- **ID6** Full Nifty 1000 fundamentals coverage

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