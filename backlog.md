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

- **R1**–**R42** as previously logged.
- **R43** **Scanner emits both entry and top-warning signals.**
          `LONG_ENTRY` signals are actionable long setups.
          `TOP_WARNING` signals are informational — they flag a
          stock that now shows a top-formation pattern, for the
          owner to review existing positions. They are NOT short
          entries. Short entries remain out of scope across all
          traders.

---

## B. INSTRUCTIONS  (chronological)

### Session 1–6 as previously logged.

### Session 7 — 2026-09-14 → 2026-09-18 (this chat — traders & books)
- **I52**–**I72** as previously logged (traders #3–#12, rules
  R32–R42).
- **I73** Trader #13 — Fred McAllen, *Charting and Technical
          Analysis*. Classified Multi. **Option B — net-new
          patterns only** (11 methods). **No shorting** — bearish
          patterns ship as TOP_WARNING signals (not short entries).
          Exit strategy per R40. → R43.

---

## C. DEMANDS

- **D1**–**D15** as previously logged.
- **D16** Scanner distinguishes entry signals from informational
         top-warnings. (reinforces R43)

---

## D. IDEAS

### ID54–ID70 as previously logged.

### ID71 — Strip existing proxies from shipped traders · BACKLOG

### ID72 — Charting and Technical Analysis (McAllen) · DONE
Trader #13. **11 methods (4 entries + 7 top-warnings).** Multi,
long-only. Fully price-only. **Option B — net-new patterns only**
(skips the ~15 patterns already covered by patterns.py, Nison,
Ishaan, Patel & Kiri, Turtle, O'Neil).
**Long entries:** saucer bottom, island bottom, three white
soldiers, bullish harami.
**Top warnings:** three black crows, bearish harami, hanging man,
shooting star, exhaustion gap, spike top, descending triangle.
**Overlap marking (R41):** every signal carries cross-links.
**R43** logged — scanner emits both entries and top-warnings.

### ID52 — Data source plugins · DEFERRED (post-traders)

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR + F11S + FATT + FNIS + FCH + FONL + FMCA
(McAllen).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R43 | Rules                    | Active       |
| I1–I73 | Instructions             | Applied      |
| ID59–ID63 | Traders #3–#7         | DONE · VERIFIED |
| ID64  | DATA_REQUESTS.md          | DONE         |
| ID65  | Apurva Parikh             | DONE · VERIFIED |
| ID66  | Ishaan Agnihotri          | DONE · VERIFIED |
| ID67  | Greenwald                 | REJECTED     |
| ID68  | Steve Nison               | DONE · VERIFIED |
| ID69  | Tushar Chande             | DONE · VERIFIED |
| ID70  | William O'Neil            | DONE · VERIFIED |
| ID71  | Strip existing proxies    | BACKLOG      |
| ID72  | Fred McAllen              | DONE         |
| Traders 14+ | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration
- **Traders #1–#12 all shipped and verified.**
- **Trader #13 (McAllen) shipped — awaiting VM verification.**
- **135 methods across 13 traders.**

### Backlog TODOs
- Reverse-mark overlaps in existing traders.
- Strip existing proxies once real data arrives (ID71).

### Owner data delivery (see DATA_REQUESTS.md)
- P0: DR-01 (~20 methods), DR-02, DR-03
- P1: DR-04–DR-07, DR-16, DR-17, DR-20, DR-21, DR-22
- P2: DR-08–DR-15, DR-18, DR-19

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync