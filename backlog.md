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
- **R20** Log every owner instruction in BACKLOG **immediately**.
- **R21** Every candidate presented with full picture.
- **R22** All tunable parameters in `strategy_config.py`.
- **R23** Optional integrations skip gracefully if creds/files missing.
- **R24** Research tables are sortable + colour-coded by sample size.
- **R25** **Portal is redesigned around the two-pillar model.**
- **R26** **Strategies are JSON, not code.**
- **R27** **Data source fixes are probed, not guessed.** Before rewriting
          a fetcher, first probe what the source actually returns.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
- **I1**–**I7** as previously logged.

### Session 2 — 2026-09-12 (midday → evening)
- **I8**–**I34** as previously logged.

### Session 2 (continued) — 2026-09-12 (evening)
- **I35** Proceed with ID44 (fundamentals fix). Step 1: probe TradingView
          to find working column names before rewriting fetcher.

---

## C. DEMANDS

- **D1**–**D6** as previously logged.

---

## D. IDEAS

### ID1–ID43 · All DONE or listed with status below.

### ID44 — Fundamentals data fix · **IN PROGRESS**
TradingView returns NULL for ROCE / growth / CFO on most India symbols.
Multibagger produces 0 picks. Fix:
1. Probe TV column names to find which return real values.
2. Rewrite `fundamentals_tv.py` with the working set.
3. Re-fetch fundamentals.
4. Verify Multibagger produces picks.

### ID45 — Signature matching · **PLANNED (Phase 3)**
### ID46 — Candle feature statistics · **PLANNED (Phase 3)**

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Everything previously listed, up to **FBT** (Strategy backtest sandbox).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R27 | Rules                    | Active       |
| I1–I35 | Instructions             | Applied      |
| ID1–ID43 | Various               | See prior logs |
| ID44  | Fundamentals data fix     | IN PROGRESS  |
| ID45  | Signature matching        | PLANNED P3   |
| ID46  | Candle feature stats      | PLANNED P3   |

---

## H. REMAINING / LEFT

### Immediate NEXT
- **ID44** Fundamentals data fix (this batch is step 1)

### Phase 3 (research upgrades)
- ID45 Signature matching
- ID46 Candle behaviour analytics
- ID30 Pattern transparency
- ID31 Time-machine chart markers
- ID36 Compare mode
- ID33 Finish unified stock card rollout

### Phase 4 (data plugins)
- ID32 Data source plugin system

### Deferred
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets (Telegram token, GCP key)
- Retire Streamlit app.py (nse.service)
- Google Sheets sync (missing GCP key)

---

## I. HOW THIS FILE GROWS
As previously documented.