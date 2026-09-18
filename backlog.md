# BACKLOG — Ankit's Instructions, Rules, Ideas & Future Work

## HOW TO USE THIS FILE
- Every message from Ankit prefixed with `#` is captured here.
- Categories: RULES · INSTRUCTIONS · DEMANDS · IDEAS · IMAGINATIONS
- DONE items stay. Execution details live in EXECUTION_LOG.md.
- Portal redesign vision lives in PORTAL_REDESIGN.md.
- Book-extraction standard lives in docs/BOOK_EXTRACTION_PROMPT.md.
- Feature registry lives in NEW_FEATURES_BACKLOG.md.
- Owner data request list lives in DATA_REQUESTS.md.
- McAllen's theses live in MCALLEN_THESES.md + `traders/mcallen_theses.py`.
- Market wisdom lives in MARKET_WISDOM.md + `traders/wisdom.py` + `/static/wisdom.html`.
- Survives chat migration.

---

## A. RULES  (always active)

- **R1**–**R43** as previously logged.

---

## B. INSTRUCTIONS  (chronological)

### Session 1–6 as previously logged.

### Session 7 — 2026-09-14 → 2026-09-18 (traders & books chat)
- **I52**–**I74** as previously logged (traders #3–#13, rules R32–R43).
- **I75** Trader #14 — Aseem Singhal, *51 Trading Strategies*.
          Classified Multi. **18 methods implemented:**
          7 Ch 1 swing + 4 Ch 4 positional + 7 Ch 7 more.
          Skipped: Ch 2 (intraday), Ch 3 (SMC/Elliott/etc),
          Ch 5 (scalping), Ch 6 (options). All indicators inline.

---

## C. DEMANDS

- **D1**–**D17** as previously logged.

---

## D. IDEAS

### ID54–ID73 as previously logged.

### ID74 — 51 Trading Strategies (Aseem Singhal) · DONE
Trader #14. **18 methods.** Multi, long-only, daily-bar.
7 swing (BB+9EMA, Williams+MACD+SMA, MACD+Fib, Triangle BO,
Gap Retracement, BB Width, Ichimoku Cloud) +
4 positional (Macro Pivot, Supertrend+RSI, Sector RS, M&W RSI) +
7 more (9/21 EMA, Positional BO, Pin Bar, Pullback-Retest,
Repo, VCP, Two-Leg).
**Indicators inline (R42):** Bollinger, Williams %R, MACD,
Fibonacci, Ichimoku, Supertrend, Pivot Points, Pin Bar, VCP,
Two-leg.
**New DR-23:** RBI repo rate (Method 49 silent until supplied).
**Overlaps marked (R41).**
**Exits per R40.**

### ID52 — Data source plugins · DEFERRED (post-traders)

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR + F11S + FATT + FNIS + FCH + FONL + FMCA +
FMT + FWIS + FSIN (Singhal).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R43 | Rules                    | Active       |
| I1–I75 | Instructions             | Applied      |
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
| ID69  | Tushar Chande             | DONE · VERIFIED |
| ID70  | William O'Neil            | DONE · VERIFIED |
| ID71  | Strip existing proxies    | BACKLOG      |
| ID72  | Fred McAllen              | DONE · VERIFIED |
| ID73  | McAllen theses capture    | DONE         |
| ID74  | Aseem Singhal             | DONE         |
| Traders 15+ | Pending owner input | PENDING      |
| ID52  | Data source plugins       | DEFERRED     |

---

## H. REMAINING / LEFT

### Traders integration
- **Traders #1–#14 shipped and verified (#14 awaiting VM).**

### Backlog TODOs
- Reverse-mark overlaps in existing traders.
- Strip existing proxies once real data arrives (ID71).

### Owner data delivery (see DATA_REQUESTS.md)
- P0: DR-01, DR-02, DR-03
- P1: DR-04–DR-07, DR-16, DR-17, DR-20, DR-21, DR-22
- **P1 (new): DR-23 RBI repo rate**
- P2: DR-08–DR-15, DR-18, DR-19

### Phase 4 (deferred until traders done)
- ID52 Data source plugin system

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync