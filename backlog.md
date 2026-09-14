# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.
- Book-extraction standard lives in docs/BOOK_EXTRACTION_PROMPT.md.
- Feature registry lives in NEW_FEATURES_BACKLOG.md.
- Survives chat migration.

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
- **R29** Famous-trader methods live under `traders/` — one module per
          trader, auto-registered, one page per trader.
- **R30** When a trader's method includes stop-loss / sizing /
          execution rules, extract **only** the setup-identification
          logic unless the owner explicitly asks otherwise.
- **R31** **Book extraction standard.** Every trading book fed to
          the system must be processed through
          `docs/BOOK_EXTRACTION_PROMPT.md`. Output must be
          method-centric (one complete block per setup, not scattered
          across categories). Extraction output → new
          `traders/<slug>.py` module + entries in
          NEW_FEATURES_BACKLOG.md + updates to backlog.md +
          EXECUTION_LOG.md.
- **R32** This chat is dedicated to **traders and book-strategy
          implementation & integration**. Every batch ships the
          standard 6-artifact set: module + registry + backlog +
          execution log + feature registry + laptop/VM blocks.
- **R33** **Full copy-paste blocks, not patchwork.** When a file is
          being updated, ship the WHOLE file, not "append this to
          Section X". Every file sent to the owner must be ready to
          paste into a fresh editor tab with no further assembly.
          This applies to backlog.md, EXECUTION_LOG.md, and
          NEW_FEATURES_BACKLOG.md too, not just code files.

---

## B. INSTRUCTIONS  (chronological)

### Session 1 — 2026-09-12 (morning)
I1–I7.

### Session 2 — 2026-09-12 (midday → evening)
I8–I34.

### Session 3 — 2026-09-13
I35–I45.

### Session 4 — 2026-09-14
I46–I47.

### Session 5 — 2026-09-15
- **I48** Trader #1 (John Crane) shipped. Framework verified.
- **I49** Trader #2 (Larry Spears). Extract only setup-identification
          logic. Classified Swing.

### Session 6 — 2026-09-16
- **I50** Evolve book-extraction prompt: method-centric output
          (one complete block per method), US→India translation
          rules, structural invalidation field, setup validity
          window, logical structure (AND/OR), variants.
- **I51** Ship: docs/BOOK_EXTRACTION_PROMPT.md +
          NEW_FEATURES_BACKLOG.md + R31 in backlog.

### Session 7 — 2026-09-14 (this chat — traders & books)
- **I52** Trader #3 — James O'Shaughnessy, *What Works on Wall
          Street* (3rd Edition). Classified Funda. 19 methods
          (16 scanned, 3 portfolio constructions). Ship module
          + registry + backlog + execution log + feature registry.
- **I53** This chat's scope = traders + book-strategy implementation
          & integration. Standard 6-artifact batch per trader.
          → captured as R32.
- **I54** Trader #4 — Wesley Gray & Tobias Carlisle,
          *Quantitative Value* (2012). Classified Funda (+ Multi
          for smart-money methods). 17 methods — 7 scanned with
          documented proxies, 10 flagged as BACKLOG (EBIT/TEV,
          balance-sheet changes, 8y history, insider/SI/13D feeds).
- **I55** `#rule` — always give full copy-paste blocks, not
          patchwork. → captured as R33.

---

## C. DEMANDS

- **D1** Ideas never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace.
- **D4** Portal presents, never recommends (R19).
- **D5** Every panel serves a decision the owner will actually make.
- **D6** Backlog and execution log stay current — no drift.
- **D7** No patchwork. Full files. Always. (reinforces R1, R28, R33)

---

## D. IDEAS

### ID1–ID53 as previously logged.

### ID54 — Famous Traders framework · **DONE**
### ID55 — John Crane (Advanced Swing Trading) · **DONE**
14 methods classified under Swing.

### ID56 — Larry Spears · **DONE**
7 setup-identification methods, classified Swing.

### ID57 — Book extraction standard · **DONE**
Method-centric output format, US→India translation, structural
invalidation, setup validity window. Lives in
`docs/BOOK_EXTRACTION_PROMPT.md`. All future book feeds use this
format.

### ID58 — Feature registry · **DONE**
`NEW_FEATURES_BACKLOG.md` — single source of truth for features the
system supports. New book requests check here first.

### ID59 — James O'Shaughnessy (What Works on Wall Street, 3rd ed.) · **DONE**
Trader #3. 19 methods extracted. Classified Funda. 16 implementable
as per-symbol scans; 3 portfolio constructions listed for reference.
Data-availability gaps documented (PSR, EPS growth, shareholder yield,
sales, cashflow per-share). Features flagged in feature registry for
ID52 resolution.

### ID60 — Quantitative Value (Gray & Carlisle) · **DONE**
Trader #4. 17 methods extracted from *Quantitative Value* (2012).
7 scanned immediately (Graham Simple Value, Earnings Yield proxy,
Book-to-Market, Magic Formula proxy, Quality & Price proxy,
Composite Price Ratios proxy, ROCE Quality Gate). 10 flagged —
need EBIT/TEV, balance-sheet changes, 8-year fundamentals history,
or non-price feeds (insider trades, short interest, 13D filings).
These auto-activate when ID52 (Phase 4 data-source plugins) lands.

### ID52 — Data source plugins · **DEFERRED (post-traders)**
Directly unblocks: O'Shaughnessy Methods 6/12/14/15 (PSR),
8 (EPS history), 17 (buyback history), 1 (sales/cashflow/shares);
Gray-Carlisle Methods 2/3/11/12 (EBIT/TEV), 4/5 (balance-sheet
changes), 6 (PROBM), 7 (PFD), 8/9 (F_SCORE/FS_SCORE),
10 (Franchise Power), 13 (buyback yield), 14/15/16 (insider /
13D / short interest).

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + **FTR** (Traders framework) + **FJC** (John Crane) +
**FLS** (Larry Spears) + **FBEP** (Book extraction prompt) +
**FNFR** (New features registry) + **FJO** (James O'Shaughnessy) +
**FQV** (Quantitative Value — Gray & Carlisle).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R33 | Rules                    | Active       |
| I1–I55 | Instructions             | Applied      |
| ID54  | Traders framework         | DONE         |
| ID55  | John Crane                | DONE         |
| ID56  | Larry Spears              | DONE         |
| ID57  | Book extraction standard  | DONE         |
| ID58  | Feature registry          | DONE         |
| ID59  | James O'Shaughnessy       | DONE         |
| ID60  | Quantitative Value        | DONE         |
| Traders 5–10 | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration (current focus)
- **Traders #1–#4 shipped**: John Crane (Swing), Larry Spears (Swing),
  James O'Shaughnessy (Funda), Gray & Carlisle (Funda).
- **Awaiting trader #5** from owner.

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system
- Growth data source integration
- **Direct impact on shipped traders:**
  - O'Shaughnessy: lights up 6 currently-empty methods (PSR, EPS
    history, shareholder yield, sales, cashflow, shares).
  - Gray-Carlisle: lights up 10 flagged methods (EBIT/TEV,
    balance-sheet changes, PROBM, PFD, F_SCORE, FS_SCORE,
    Franchise Power, buyback yield, insider/SI/13D feeds).

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync