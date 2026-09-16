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
          implementing a book.**
- **R38** **Exit strategies ship when the owner asks for them.**
          Superseded by R40 (format evolved).
- **R39** **One file, one block. No bundling.** Each file gets its
          own dedicated section. Ship only files that changed.
- **R40** **Exit strategy — suggestive, explained, with hard numbers.**
          Every exit rule ships with:
            (a) `thesis` — plain-English explainer citing the book;
            (b) `hard_number` — a computed price where the rule
                permits (stop at ₹X, target at ₹Y, trailing at ₹Z);
                `None` when the rule is inherently trail-only;
            (c) `condition` — textual trigger for when the rule fires.
          Blocks: `stop_out`, `target`, `offset`, `invalidation`,
          `exhaustion`, `time_exit`. Exits are **suggestive, not
          directive** — owner decides. Evolves R38.
- **R41** **Overlap policy — mark, don't prune.** When a new
          trader's method conceptually overlaps an existing
          method, mark it via `overlaps_with: [<trader>.<method>]`
          on every signal from that method. Do NOT consolidate or
          remove either method. Owner decides later whether to
          prune after using the system. Reverse marking
          (existing module pointing back at the new one) is a
          backlog TODO, deferred to a batch that naturally
          touches the existing module.

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

### Session 7 — 2026-09-14 → 2026-09-17 (this chat — traders & books)
- **I52**–**I61** as previously logged (traders #3–#7).
- **I62** `#rule` → R36 live owner-data request list.
- **I63** Trader #8 — Apurva Parikh.
- **I64** Trader #9 — Ishaan Agnihotri.
- **I65** `#no` — do NOT add the Greenwald book as trader #10.
- **I66** `#rule` → R37.
- **I67** Trader #10 — Steve Nison. Multi. 6 methods.
- **I68** `#rule` → R38 (exits ship when owner asks).
- **I69** `#rule` → R39 (one file, one block).
- **I70** Trader #11 — Tushar Chande, *Beyond Technical Analysis*.
          Classified Multi. 5 methods. Overlap policy: mark,
          don't prune. Exit strategy: suggestive, explained, hard
          numbers where computable. → R40 + R41.

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
- **D12** One file per block, no bundling.
- **D13** Exit strategy is suggestive, explained, with hard numbers.
- **D14** Overlap policy — mark, don't prune.

---

## D. IDEAS

### ID54–ID58 as previously logged.

### ID59 — James O'Shaughnessy · DONE · VERIFIED
19 methods. Funda. 256 signals / 46 symbols.

### ID60 — Quantitative Value · DONE · VERIFIED
20 methods. Funda (+ Multi). 147 signals / 30 symbols.

### ID61 — Value Investing Made Easy · DONE · VERIFIED
21 methods. Funda (+ Multi). 25 signals / 20 symbols.

### ID62 — Way of the Turtle · DONE · VERIFIED
9 methods, 8 scanned. Multi. 16 signals / 8 symbols.

### ID63 — 7 Simple Strategies · DONE · VERIFIED
11 methods. Swing. 13 signals / 11 symbols.

### ID64 — DATA_REQUESTS.md · DONE

### ID65 — 11 Secrets (Parikh) · DONE · VERIFIED
1 composite. Funda. 0 signals on test (strict).

### ID66 — Technical Trader's Handbook (Ishaan) · DONE · VERIFIED
5 methods. Swing. 3 signals / 3 symbols on test.

### ID67 — Greenwald book · REJECTED by owner.

### ID68 — Beyond Candlesticks (Nison) · DONE · VERIFIED
6 methods. Multi. 13 signals / 12 symbols on test.
Structured exits (R38). Overlap marked.

### ID69 — Beyond Technical Analysis (Chande) · DONE
Trader #11. **5 methods, all scanned.** Multi (Swing + Positional,
long-only). Fully price-only. No data blocks.
**Exit strategy**: R40 format — suggestive, explained, hard
numbers where computable.
**Overlap marking**: R41 — five methods, all overlaps marked.

### ID52 — Data source plugins · DEFERRED (post-traders)

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR + F11S + FATT + FNIS + FCH (Chande).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R41 | Rules                    | Active       |
| I1–I70 | Instructions             | Applied      |
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
| ID69  | Tushar Chande             | DONE         |
| Traders 12+ | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration
- **Traders #1–#10 shipped & verified.**
- **Trader #11 (Chande) shipped — awaiting VM verification.**

### Backlog TODOs
- **Reverse-mark the Ishaan↔Nison candle overlap** in
  `traders/ishaan_agnihotri.py`.
- **Reverse-mark the new overlaps in existing trader modules**
  introduced by Nison and Chande (Turtle, Patel & Kiri,
  Larry Spears, Seven Simple Strategies).

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