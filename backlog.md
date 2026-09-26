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
- **R47** Git + VM steps → ALWAYS whole copy-paste blocks, every time
          (2026-09-26). One block per place (Laptop PowerShell · SSH ·
          VM); each block complete on its own (cd, venv), one command
          per line, no placeholders, expected output after each block.

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

### Session 8 — 2026-09-25 (Arena agent chat)
- **I78** Build the Trader League: each of the 14 books gets
          Rs 10 lakh of play money and trades its own signals on real
          NSE data every evening (chosen from the "something unique"
          ideas list).
- **I79** "give me copy paste whole blocks always for git and vm
          sections everytime needed" → rule **R47** (also in
          PROJECT_HANDOFF.md §1). TRADER_LEAGUE.md rewritten as
          copy-paste Blocks A–K.

---

## C. DEMANDS

- **D1**–**D17** as previously logged (D18, D19 see #086).
- **D20** "We have to make something to backtest our system before
  deploying real money." → `trader_league.py` backtest + real-money
  checklist (TRADER_LEAGUE.md). DONE · real-data replay and readiness
  check verified on the VM (2026-09-26); current verdict NOT READY.

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

### ID77 — Trader League (Rs 10 lakh paper league) · DONE
14 books + our system, Rs 10 lakh each. Point-in-time replay of the
10 chart books + our Swing Desk pipeline (fundamentals books live
only, DR-01). Realistic simulator (next-day fills, gap-through stops,
Indian delivery costs, slippage, 1% risk sizing). Book exits vs same
exits scoreboards, results by regime, real-money verdict. Nightly live
league 19:00, Sat scorecard, 🏆 League tab. See #087.

### ID52 — Data source plugins · IN PROGRESS
Owner decisions (2026-09-26): implement the full adapter framework;
use official NSE/BSE filings as the authority for dated fundamentals;
keep broad quality-eligible Funda and liquid mid/small-cap Swing
universes separate; make Multibagger quality-led with multi-year growth
confirmation once dated data exists. Current work adds discovery,
health, local rate-limit status and explicit fallback routing, and
migrates TradingView fundamentals, Yahoo price history, NSE constituents
and Chartink screener inputs. Remaining direct Yahoo call sites and
official dated-filing ingestion are not yet migrated.

---

## E. IMAGINATIONS
IM1–IM6 as previously logged.

---

## F. FEATURES COMPLETED
Prior + FTR + FJC + FLS + FBEP + FNFR + FJO + FQV + FVIME +
FWOT + F7SS + FDR + F11S + FATT + FNIS + FCH + FONL + FMCA +
FMT + FWIS + FSIN (Singhal) + FTL (Trader League).

---

## G. STATUS SUMMARY

| ID    | Item                      | Status       |
|-------|---------------------------|--------------|
| R1–R43 | Rules                    | Active       |
| R47   | Whole copy-paste blocks (git/VM) | Active |
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
| ID71  | Strip existing proxies    | BLOCKED · real replacement data required |
| ID72  | Fred McAllen              | DONE · VERIFIED |
| ID73  | McAllen theses capture    | DONE         |
| ID74  | Aseem Singhal             | DONE         |
| ID77  | Trader League             | DONE · replay verified; NOT READY; live sample pending |
| D20   | Backtest before real money | DONE · real-data replay verified; NOT READY |
| Traders 15+ | Pending owner input | PENDING      |
| ID52  | Data source plugins       | IN PROGRESS · framework and first adapters implemented |

---

## H. REMAINING / LEFT

### Traders integration
- **Traders #1–#14 shipped; replay coverage is present on the VM.**
  Fundamentals books remain live-only until point-in-time data arrives
  (DR-01). Re-run changed-player replay after trader/config edits.

### Backlog TODOs
- Reverse-mark overlaps in existing traders (R41); newer traders already
  mark several links, but the older counterparts still need an audit.
- Strip existing proxies once suitable real replacement data arrives
  (ID71 / DR-01 and related requests).

### Trader League (ID77)
- Pre-season replay: **complete on VM**, through 2026-09-25.
- Latest readiness check (2026-09-26): **NOT READY**. PF 0.93 vs 1.3
  bar; return -6.2% vs Nifty +5.5%; worst-case-fill PF 0.72; live paper
  evidence 0/30 trades. Re-check `python trader_league.py ready` after
  at least 30 live paper trades; do not deploy real capital meanwhile.
- Not started (proposed in the same chat): Council score (vote
  weighted by each method's regime track record), Wisdom Court
  (test MARKET_WISDOM principles), Quiet Accumulation (pullback +
  falling volume + rising delivery%), Discipline Coach.

### Owner data delivery (see DATA_REQUESTS.md)
- P0: DR-01, DR-02, DR-03
- P1: DR-04–DR-07, DR-16, DR-17, DR-20, DR-21, DR-22
- **P1 (new): DR-23 RBI repo rate**
- P2: DR-08–DR-15, DR-18, DR-19

### Deferred roadmap work
- ID52 source-plugin migration: complete the remaining direct Yahoo
  call sites and add validated, period- and filing-dated official
  NSE/BSE fundamentals ingestion. Keep DR-01/DR-21 OPEN until data
  coverage, provenance and point-in-time safety are verified.
- Owner choices recorded 2026-09-26: separate broad quality-eligible
  Funda and liquid mid/small-cap Swing universes (exact thresholds still
  open); quality-led Multibagger with multi-year growth confirmation
  (scanner remains quality-only until dated data exists); official
  exchange filings for dated fundamentals; L1 signature distance is
  already implemented; RCP/Episodic Pivot seeds already have explicit
  conditions. Retiring legacy Streamlit remains a separate decision.
- Proposed League additions (Council score, Wisdom Court, Quiet
  Accumulation, Discipline Coach) are unstarted and need prioritization.

### Deferred (owner chose to skip)
- Settings `.env` / admin creds rotation
- HTTPS via nginx + certbot (A0)
- Rotate secrets
- Retire Streamlit app.py
- Google Sheets sync