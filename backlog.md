# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.

---

## A. RULES  (always active)

- **R1**  Whole files only. No patches. Ever.
- **R2**  Plain English.
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
- **R13** Fast feedback loops (~5s).
- **R14** Verdicts are PF-driven.
- **R15** Parameter changes are swept.
- **R16** Non-monotonic sweeps = noise.
- **R17** Multi-window WF is ground truth.
- **R18** Equivalent results → simpler wins.
- **R19** **System identifies. Owner decides.**
- **R20** Log every owner instruction in BACKLOG immediately.
- **R21** Every candidate presented with full picture.
- **R22** All tunable parameters in `strategy_config.py`.
- **R23** Optional integrations skip gracefully.
- **R24** Research tables are sortable + colour-coded.
- **R25** Portal is two-pillar (Funda / Swing).
- **R26** Strategies are JSON, not code.
- **R27** Data source fixes are probed, not guessed.
- **R28** No partial edits — every file is a full replacement.
- **R29** **Famous-trader methods live under `traders/`** — one module per
          trader, auto-registered, one page per trader in the Traders
          tab. Each page lists their methods + live universe signals.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
I1–I7.

### Session 2 — 2026-09-12 (midday → evening)
I8–I34.

### Session 3 — 2026-09-13
I35–I45.

### Session 4 — 2026-09-14
- **I46** Build a **Traders** section: one page per famous trader, one
          sub-section per method. Identify whether each trader belongs
          to Funda, Swing, or other. Owner will feed trader methods one
          at a time (started with John Crane / Advanced Swing Trading).
          Trader #1 (John Crane) classified as **Swing**.
- **I47** (Pending) Owner will feed traders 2–10. Integrate each as its
          own module + page.

---

## C. DEMANDS
D1–D6 as previously logged.

---

## D. IDEAS

### ID1–ID53 as previously logged (all DONE or listed).

### ID54 — Famous Traders framework · **DONE this batch**
New `traders/` package with registry. Each trader module exposes:
  SLUG, NAME, PILLAR, SOURCE, METHODS, scan(conn, limit).
Auto-registered via `traders/__init__.py`. New nav item **📚 Traders**
with one page per trader.

### ID55 — John Crane (Advanced Swing Trading) · **DONE this batch**
14 methods detected, classified under **Swing**:
  1. Reaction Swing detection
  2. Time Forecast (Reverse/Forward Count with holiday law)
  3. Action / Reaction Lines (Andrews/Babson geometry)
  4. Retracement Windows (60% / 30%)
  5. Two-Day Rule
  6. Peg-Leg
  7. Gap and Go
  8. Gap Reversal
  9. Continuation Gapping
  10. Trail Day Confirmation
  11. Major Reversal
  12. SSTO 20-Period Divergence
  13. Master Decision Engine (Time × Price × Pattern)

### ID52 — Data source plugins · **DEFERRED (Phase 4, post-traders)**
Phase 4 was scheduled before the Traders request. Now deferred until
all 10 trader pages are shipped, unless the owner says otherwise.

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + **FTR** (Traders framework) + **FJC** (John Crane methods).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R29 | Rules                    | Active       |
| I1–I47 | Instructions             | Applied      |
| ID1–ID53 | Various               | DONE / listed |
| ID54  | Traders framework         | DONE         |
| ID55  | John Crane                | DONE         |
| Traders 2–10 | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration (current focus)
- **Awaiting trader #2** from owner.
- Framework handles each new trader as one module + a registry entry.

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system
- Growth data source integration

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync