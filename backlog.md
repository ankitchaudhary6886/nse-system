# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.
- Book-extraction standard lives in docs/BOOK_EXTRACTION_PROMPT.md.
- Feature registry lives in NEW_FEATURES_BACKLOG.md.
- Owner data request list lives in DATA_REQUESTS.md.
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
          method-centric. Extraction output → new
          `traders/<slug>.py` module + entries in
          NEW_FEATURES_BACKLOG.md + updates to backlog.md +
          EXECUTION_LOG.md.
- **R32** This chat is dedicated to **traders and book-strategy
          implementation & integration**. Standard 6-artifact set
          per trader.
- **R33** **Full copy-paste blocks, not patchwork.**
- **R34** **Always end with git + VM blocks.**
- **R35** **Null-safe formatting + `_try_emit` in every trader
          module.** One method's failure must never kill the whole
          symbol's signal set.
- **R36** **Maintain a live owner-data request list in
          `DATA_REQUESTS.md`.** Update on every new book extraction
          and on every owner delivery. Log status flips in
          EXECUTION_LOG.md.

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
- **I48** Trader #1 (John Crane). Swing. Verified.
- **I49** Trader #2 (Larry Spears). Swing. Setup-ID only.

### Session 6 — 2026-09-16
- **I50** Evolve book-extraction prompt (method-centric).
- **I51** Ship BOOK_EXTRACTION_PROMPT.md + NEW_FEATURES_BACKLOG.md
          + R31.

### Session 7 — 2026-09-14 → 2026-09-17 (this chat — traders & books)
- **I52** Trader #3 — James O'Shaughnessy. 19 methods. Funda.
- **I53** Chat scope → R32.
- **I54** Trader #4 — Gray & Carlisle. 20 methods. Funda (+ Multi).
- **I55** `#rule` full copy-paste blocks → R33.
- **I56** `#rule` always send git + VM → R34.
- **I57** Trader #5 — Janet Lowe. 21 methods. Funda (+ Multi).
- **I58** Trader #6 — Curtis Faith (Way of the Turtle). 9 methods.
- **I59** Doc count corrections.
- **I60** QV null-format bug fix → R35.
- **I61** Trader #7 — Patel & Kiri. 11 methods. Swing, long-only.
- **I62** `#rule` — live owner-data request list → R36.
- **I63** Trader #8 — Apurva Parikh, *11 Secrets to find Value
          Stocks*. 1 composite strategy (all 11 secrets merged
          per owner's extraction). Funda, long-only. 5 of 11
          secrets testable today; 6 flagged pending DR-01/DR-16/
          DR-17/DR-18. Exit rules shipped as informational metadata.

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

---

## D. IDEAS

### ID54–ID58 as previously logged.
- Traders framework · Book extraction standard · Feature registry

### ID59 — James O'Shaughnessy · DONE · VERIFIED
19 methods. Funda. 256 signals / 46 symbols.

### ID60 — Quantitative Value (Gray & Carlisle) · DONE · VERIFIED
20 methods. Funda (+ Multi). 7 scanned, 13 flagged.
147 signals / 30 symbols.

### ID61 — Value Investing Made Easy (Janet Lowe) · DONE · VERIFIED
21 methods. Funda (+ Multi). 7 scanned, 14 flagged.
25 signals / 20 symbols.

### ID62 — Way of the Turtle (Curtis Faith) · DONE · VERIFIED
9 methods, 8 scanned. Multi. 16 signals / 8 symbols.

### ID63 — 7 Simple Strategies (Patel & Kiri) · DONE · VERIFIED
11 methods, all scanned. Swing. 13 signals / 11 symbols.

### ID64 — DATA_REQUESTS.md · DONE
Owner-facing live list (R36).

### ID65 — 11 Secrets to find Value Stocks (Apurva Parikh) · DONE
Trader #8. **1 composite strategy** (all 11 secrets merged).
Funda, long-only. **5 of 11 secrets testable today**
(6: D/E≤0.30, 7: CFO+, 8: ROE≥15%, 9: ROCE≥20%, 10 partial:
PE≤sector-median, 11: RSI≥60 + uptrend). **6 flagged** —
Secrets 1, 2, 3, 4, 5 and the Nifty PE gate (DR-01/DR-16/DR-17/
DR-18). Exit rules shipped as informational metadata per R30.

### ID52 — Data source plugins · DEFERRED (post-traders)

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR + F11S (11 Secrets Parikh).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R36 | Rules                    | Active       |
| I1–I63 | Instructions             | Applied      |
| ID54–ID58 | Framework docs        | DONE         |
| ID59  | James O'Shaughnessy       | DONE · VERIFIED |
| ID60  | Quantitative Value        | DONE · VERIFIED |
| ID61  | Value Investing Made Easy | DONE · VERIFIED |
| ID62  | Way of the Turtle         | DONE · VERIFIED |
| ID63  | 7 Simple Strategies       | DONE · VERIFIED |
| ID64  | DATA_REQUESTS.md          | DONE         |
| ID65  | 11 Secrets (Apurva Parikh)| DONE         |
| Traders 9–10 | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration (current focus)
- **Traders #1–#8 shipped** (#1–#7 verified).
- **Awaiting trader #9** from owner.

### Owner data delivery (see DATA_REQUESTS.md)
- **P0:** DR-01 fundamentals_history (~20 methods), DR-02, DR-03
- **P1:** DR-04, DR-05, DR-06, DR-07, DR-16 promoter/pledge,
  DR-17 Nifty PE
- **P2:** DR-08 through DR-15, DR-18 business age, DR-19 NOTE

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync