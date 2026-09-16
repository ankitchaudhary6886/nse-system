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
- **R31** **Book extraction standard.**
- **R32** Chat scope = traders + book-strategy implementation.
- **R33** **Full copy-paste blocks, not patchwork.**
- **R34** **Always end with git + VM blocks.**
- **R35** **Null-safe formatting + `_try_emit` in every trader module.**
- **R36** **Maintain a live owner-data request list in
          `DATA_REQUESTS.md`.**
- **R37** **Wait for explicit `trader N` instruction before
          implementing a book.** A book file sent without an
          explicit implement-this instruction is informational, not
          a build request.
- **R38** **Exit strategies ship when the owner asks for them.**
          For technical traders (Multi/Swing), ship a structured
          `raw.exits` block per signal with: `stop_out` (price +
          condition), `target` (price + condition), `offset`
          (opposite-pattern exit trigger), `invalidation` (setup-
          death condition), `exhaustion` (record-session rule where
          applicable), `time_exit` (N sessions or None).
          Nison (#10) is the first trader under this rule.
- **R39** **One file, one block. No bundling.** Each file gets its
          own dedicated section with its own full-file code block.
          Do NOT mix DATA_REQUESTS.md with EXECUTION_LOG.md, or any
          file with any other file. Only ship a file in a response
          if that file actually changed in that response. If a file
          is unchanged, note it in one line ("X — unchanged this
          batch") rather than shipping its full content. This
          applies to all .md docs and all .py files alike.

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
- **I50** Evolve book-extraction prompt.
- **I51** Ship BOOK_EXTRACTION_PROMPT.md + NEW_FEATURES_BACKLOG.md
          + R31.

### Session 7 — 2026-09-14 → 2026-09-17 (traders & books chat)
- **I52**–**I61** as previously logged (traders #3–#7).
- **I62** `#rule` → R36 live owner-data request list.
- **I63** Trader #8 — Apurva Parikh.
- **I64** Trader #9 — Ishaan Agnihotri.
- **I65** `#no` — do NOT add the Greenwald book as trader #10.
          Revert.
- **I66** `#rule` — wait for explicit `trader N` instruction
          → R37.
- **I67** Trader #10 — Steve Nison, *Beyond Candlesticks* (1994).
          Classified Multi. 6 methods, all scanned. Structured
          exits per signal. Overlap with Ishaan marked on Nison's
          side.
- **I68** `#rule` — exit strategies ship when owner asks for them
          → R38.
- **I69** `#rule` — one file, one block, no bundling. Ship
          DATA_REQUESTS.md only when it changes. → R39.

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
- **D9** Null-safe emission.
- **D10** The owner always knows what data to fetch next.
- **D11** Wait for explicit go on a book before shipping it.
- **D12** One file per block, no bundling. Ship only changed files.

---

## D. IDEAS

### ID54–ID58 as previously logged.
Traders framework · Book extraction standard · Feature registry.

### ID59 — James O'Shaughnessy · DONE · VERIFIED
19 methods. Funda. 256 signals / 46 symbols.

### ID60 — Quantitative Value (Gray & Carlisle) · DONE · VERIFIED
20 methods. Funda (+ Multi). 147 signals / 30 symbols.

### ID61 — Value Investing Made Easy (Lowe) · DONE · VERIFIED
21 methods. Funda (+ Multi). 25 signals / 20 symbols.

### ID62 — Way of the Turtle (Faith) · DONE · VERIFIED
9 methods, 8 scanned. Multi. 16 signals / 8 symbols.

### ID63 — 7 Simple Strategies (Patel & Kiri) · DONE · VERIFIED
11 methods, all scanned. Swing. 13 signals / 11 symbols.

### ID64 — DATA_REQUESTS.md · DONE

### ID65 — 11 Secrets (Apurva Parikh) · DONE · VERIFIED
1 composite strategy. Funda. 5 of 11 secrets testable today.
0 signals on limit=50 test (strict composite — expected).

### ID66 — A Technical Trader's Handbook (Ishaan Agnihotri) · DONE · VERIFIED
5 methods, all scanned. Swing. 3 signals / 3 symbols on test.

### ID67 — Greenwald book · **REJECTED by owner (I65)**

### ID68 — Beyond Candlesticks (Steve Nison) · DONE · VERIFIED
Trader #10. **6 methods, all scanned.** Multi (Swing + Positional,
long-only). Fully price-only. No data blocks.
**Structured exits per signal** (R38 — first trader under the rule).
**Overlap marking:** Nison's candle-reversal signals carry
`overlaps_with: ["ishaan_agnihotri.candlestick_reversal_at_support"]`.
Result: 13 signals / 12 symbols on limit=50 test.

### ID52 — Data source plugins · DEFERRED (post-traders)

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior list + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR + F11S + FATT + FNIS (Nison).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R39 | Rules                    | Active       |
| I1–I69 | Instructions             | Applied      |
| ID54–ID58 | Framework docs        | DONE         |
| ID59  | James O'Shaughnessy       | DONE · VERIFIED |
| ID60  | Quantitative Value        | DONE · VERIFIED |
| ID61  | Value Investing Made Easy | DONE · VERIFIED |
| ID62  | Way of the Turtle         | DONE · VERIFIED |
| ID63  | 7 Simple Strategies       | DONE · VERIFIED |
| ID64  | DATA_REQUESTS.md          | DONE         |
| ID65  | Apurva Parikh             | DONE · VERIFIED |
| ID66  | Ishaan Agnihotri          | DONE · VERIFIED |
| ID67  | Greenwald                 | REJECTED     |
| ID68  | Steve Nison               | DONE · VERIFIED |
| Traders 11+ | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration
- **Traders #1–#10 shipped. All verified.**
- **10 traders · 112 methods · 81 scanned.**

### Backlog TODOs
- **Reverse-mark the Ishaan↔Nison candle overlap** in
  `traders/ishaan_agnihotri.py`. Currently only marked on Nison's
  side. Defer to a batch that naturally touches Ishaan's module
  (respects R28 whole-file discipline + R11 batch size).

### Owner data delivery (see DATA_REQUESTS.md)
- P0: DR-01 (~20 methods), DR-02, DR-03
- P1: DR-04–DR-07, DR-16, DR-17
- P2: DR-08–DR-15, DR-18, DR-19

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync