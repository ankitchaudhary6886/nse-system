# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.
- Book-extraction standard lives in docs/BOOK_EXTRACTION_PROMPT.md.
- Feature registry lives in NEW_FEATURES_BACKLOG.md.
- **Owner data request list lives in DATA_REQUESTS.md.**
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
- **R34** **Always end with git + VM blocks.** Every response that
          ships files — code, docs, config, registry — ends with
          one git block (laptop) and one VM block.
- **R35** **Null-safe formatting in every signal note.** No
          `f"{value:.Nf}"` where `value` can be None. Use `_fmt_num`
          that returns "—" for None. Wrap each signal emission in
          `_try_emit` so one method's failure never kills the whole
          symbol's signal set.
- **R36** **Maintain a live owner-data request list.** Every
          feature requested by any book/trader goes into
          `DATA_REQUESTS.md` with: field+formula, trader impact
          (which methods need it), why, impact, relevance,
          duplication, priority, owner action, effort. This is the
          owner-facing counterpart to `NEW_FEATURES_BACKLOG.md`.
          Update on every new book extraction and on every owner
          delivery. Log status flips in EXECUTION_LOG.md.

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
- **I49** Trader #2 (Larry Spears). Swing. Setup-ID only.

### Session 6 — 2026-09-16
- **I50** Evolve book-extraction prompt (method-centric output).
- **I51** Ship BOOK_EXTRACTION_PROMPT.md + NEW_FEATURES_BACKLOG.md
          + R31.

### Session 7 — 2026-09-14 → 2026-09-17 (this chat — traders & books)
- **I52** Trader #3 — James O'Shaughnessy. 19 methods. Funda.
- **I53** Chat scope → R32.
- **I54** Trader #4 — Gray & Carlisle. 20 methods. Funda (+ Multi).
- **I55** `#rule` full copy-paste blocks → R33.
- **I56** `#rule` always send git + VM → R34.
- **I57** Trader #5 — Janet Lowe. 21 methods. Funda (+ Multi).
- **I58** Trader #6 — Curtis Faith (Way of the Turtle).
          9 methods, 8 scanned. Multi.
- **I59** Doc count corrections: QV actual = 20, Lowe actual = 21.
- **I60** QV null-format bug fix → R35.
- **I61** Trader #7 — Alpesh Patel & Paresh Kiri,
          *7 Simple Strategies of Highly Effective Traders* (2010).
          11 methods, all scanned. Swing, long-only, no intraday.
- **I62** `#rule` — maintain a live owner-data request list
          (`DATA_REQUESTS.md`) with field, formula, trader impact,
          why, impact, relevance, duplication, priority, owner
          action, effort. Update on every book + every delivery.
          → captured as R36.

---

## C. DEMANDS

- **D1** Ideas never lost.
- **D2** Durable execution log across chat sessions.
- **D3** Fast pace.
- **D4** Portal presents, never recommends (R19).
- **D5** Every panel serves a decision the owner will actually make.
- **D6** Backlog and execution log stay current — no drift.
- **D7** No patchwork. Full files. Always.
- **D8** Every response ends with actionable git + VM blocks.
- **D9** Null-safe emission — one signal's format error must never
        drop other signals for the same symbol.
- **D10** The owner always knows what data to fetch next.
         (`DATA_REQUESTS.md` is live and accurate.) (reinforces R36)

---

## D. IDEAS

### ID1–ID53 as previously logged.

### ID54–ID58 as previously logged.
- **ID54** Traders framework · DONE
- **ID55** John Crane · DONE
- **ID56** Larry Spears · DONE
- **ID57** Book extraction standard · DONE
- **ID58** Feature registry · DONE

### ID59 — James O'Shaughnessy · **DONE · VERIFIED**
Trader #3. 19 methods. Funda. 256 signals / 46 symbols.

### ID60 — Quantitative Value (Gray & Carlisle) · **DONE · VERIFIED**
Trader #4. 20 methods. Funda (+ Multi). 7 scanned, 13 flagged.
147 signals / 30 symbols.

### ID61 — Value Investing Made Easy (Janet Lowe) · **DONE · VERIFIED**
Trader #5. 21 methods. Funda (+ Multi). 7 scanned, 14 flagged.
25 signals / 20 symbols.

### ID62 — Way of the Turtle (Curtis Faith) · **DONE · VERIFIED**
Trader #6. 9 methods, 8 scanned. Multi. 16 signals / 8 symbols.

### ID63 — 7 Simple Strategies (Patel & Kiri) · **DONE · VERIFIED**
Trader #7. 11 methods, all scanned. Swing, long-only.
13 signals / 11 symbols (limit=50 sample).

### ID64 — DATA_REQUESTS.md · **DONE this batch**
Owner-facing live list of every data element needed to unlock
remaining methods. 15 requests (DR-01 through DR-15), grouped
by priority. Duplication map. Update protocol. One fetch
(DR-01 fundamentals_history) unlocks ~18 methods.

### ID52 — Data source plugins · **DEFERRED (post-traders)**

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR (DATA_REQUESTS).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R36 | Rules                    | Active       |
| I1–I62 | Instructions             | Applied      |
| ID54  | Traders framework         | DONE         |
| ID55  | John Crane                | DONE         |
| ID56  | Larry Spears              | DONE         |
| ID57  | Book extraction standard  | DONE         |
| ID58  | Feature registry          | DONE         |
| ID59  | James O'Shaughnessy       | DONE · VERIFIED |
| ID60  | Quantitative Value        | DONE · VERIFIED |
| ID61  | Value Investing Made Easy | DONE · VERIFIED |
| ID62  | Way of the Turtle         | DONE · VERIFIED |
| ID63  | 7 Simple Strategies       | DONE · VERIFIED |
| ID64  | DATA_REQUESTS.md          | DONE         |
| Traders 8–10 | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration (current focus)
- **Traders #1–#7 shipped & verified.**
- **Awaiting trader #8** from owner.

### Owner data delivery (see DATA_REQUESTS.md)
- **P0:** DR-01 fundamentals_history (unlocks ~18 methods),
  DR-02 (subsumed by DR-01), DR-03 aaa_bond_yield (trivial)
- **P1:** DR-04 shares_outstanding, DR-05 dividend_history,
  DR-06 sales_ttm, DR-07 eps_growth_1y (all subsumed by DR-01)
- **P2:** DR-08 insider, DR-09 short_interest, DR-10 activist,
  DR-11 corporate_bond, DR-12 convertible/preferred,
  DR-13 IBC/NCLT, DR-14 open_offer, DR-15 IPO

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system
- Growth data source integration
- **Direct impact on shipped traders:**
  - O'Shaughnessy: 6 methods
  - Gray-Carlisle: 13 methods
  - Lowe: 14 methods
  - Turtle / 7SS: no impact

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync