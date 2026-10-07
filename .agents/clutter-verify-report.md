# Clutter verification — measured on the live NSE terminal

**Independent verification of `.agents/clutter-audit.md`, for the owner.**
Owner's request: *"i feel there is too much clutter in my portal, kindly suggest what could be thrown, what to trim, what to hide, what's repeating."*

This report **replaces guesswork with measurement**. The previous audit stated up front that it could never start a
server, so it read DOM order out of `index.html` and took row counts from code caps. Everything below was measured in
the real app: real Chrome, real layout, real API data, real rendered text.

## How it was measured (so you can trust or repeat it)

| | |
|---|---|
| Server | `.\env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8024` (login gate already removed) |
| Renderer | Chrome 154 headless over CDP — `tools/ui-audit/eval.mjs` (arbitrary JS in the live page), `tools/ui-audit/shot.mjs` (viewport screenshots) |
| Viewports | **1440×900** and **390×844** |
| Views | research, funda, swing, ledger, system, traders, league |
| Symbol loaded | `KEI` (and `VADILALIND`, which has a *live setup today*, for the trigger/stop/target test) |
| Offsets | `getBoundingClientRect().top + scrollY`, per top-level panel, all views, both viewports |
| Row/panel/card counts | counted in the DOM (not from code caps) |
| Dead markup | static grep **plus** a `MutationObserver` injected at document-start that records every id any script mutates, across all 7 views |
| Repetition | literal value tokens (dates, %, ₹, decimals) extracted per panel and intersected |
| Disclaimers | counted twice: in **rendered** text (`innerText`) and in full source text |
| Screenshots | `%TEMP%\clutter-shots\research-1440-KEI.png`, `research-390-KEI.png` (viewed) |

**Audited revision** — several files are byte-identical to the revision the previous audit read, so its structural
claims are testable against exactly the same code:

| file | sha256 (first 10) |
|---|---|
| `terminal/static/index.html` | `B1B7043862` |
| `terminal/static/app.js` | `693D8C17F7` |
| `terminal/static/cards.js` | `F221215D19` |
| `terminal/static/research.js` | `E3D2A51F8A` |
| `terminal/static/research_universe.js` | `70575DE345` |
| `terminal/static/research_sector.js` | `FFC8DCB94F` |
| `terminal/static/traders.js` | `514F49A4F0` |
| `terminal/static/league.js` | `A8A2025652` |
| `terminal/static/scanners.js` | `5E488E2B8D` |

`terminal/static/deployment.js` **no longer exists** (verified: file absent, no `<script src>`, no reference anywhere).
The frontend overhaul added `fintech.css`, `tailwind.css`, `icons.js`, `vendor/`.

---

## 1. The answer in one paragraph

The portal is not cluttered because it has too many *panels* — it is cluttered because **two panels are enormous list
dumps that swallow their whole view**. Measured: the 7 views total **53,188 px of vertical scroll at 1440×900 (59
screens)**, and **two panels alone are 33,424 px of that — 63%**. "Chart Patterns Found Today" in research is
**17,366 px tall (19.3 screens, 78% of the research page)** and pushes the panel after it **21,007 px — 23 screens —
below the fold**. "Trading Methods" in traders is **16,058 px (17.8 screens, 99% of its view)**. Every other view is
1–2 screens. Fix those two and the portal stops feeling bottomless. Everything else in this report is secondary.

---

## 2. Which viewport, and what is actually on the first screen

**1440×900, research view, symbol KEI** (`research-1440-KEI.png`): sidebar (232 px) + "Company research" title and
subtitle + search box with *Open symbol* / *Refresh* + "Latest saved data reloaded…" note + the **8-tab pill rail
(which repeats the sidebar item-for-item)** + a full-width amber **"Regime unavailable — no benchmark data found for
any candidate"** banner + **4 metric tiles** + then the chart panel (starts at 417 px, i.e. 46% down the screen) with
its toggle row and 6 SMA/EMA pills. **Exactly 1 of the 10 research panels is on the first screen**; the chart gets
about 320 px of visible height before the fold.

**390×844, research view** (`research-390-KEI.png`): hamburger → title → 2-line subtitle → search row + a **status
sentence wrapped over 4 lines** ("Latest saved data reloaded. Use scan buttons to compute new results.") → pill rail
(only 4 of 8 items fit; the rest need horizontal scroll) → regime banner → **4 metric tiles stacked 2×2 (254 px)** →
the chart panel only begins at **648 px of an 844 px screen (77% down)**. **There is no chart on the first mobile
screen at all** — you see pills, banners, tiles and status text.

So the first screen is dominated by *chrome*: a duplicated navigation, a status sentence, an empty-state banner and
four tiles. The data the portal exists for starts below the fold on mobile.

---

## 3. Verdict on the previous audit's executive-summary claims

| # | Claim (as written) | Verdict | The measurement that settles it |
|---|---|---|---|
| **1** | "The single biggest clutter source is the research view: **10 stacked panels**, of which 6 restate data already on screen — same bar date twice, same scan date twice, same close/1d/20d/60d/EMA-trend block twice, same trigger/stop/target twice." | **CONFIRMED** (one number needs correcting: *two* panels, not one, are the biggest clutter source) | **10 panels exactly** — measured `#view-research .panel` = 10 (6 direct children + 4 inside two `.terminal-grid` wrappers). Page = **22,169 px = 24.6 screens**; panel offsets: 417 / 1091 / 1323 / 1323 / 1534 / 1724 / 1915 / 3928 / 4522 / 21907. Only panel #1 is above the fold; **#9 "Chart Patterns Found Today" is 17,366 px = 78.3% of the page**, and #10 starts **21,007 px (23.3 screens) below the fold**. Value repetition confirmed in 5 separate panels (§5). *Correction to the claim:* the single biggest source is not "10 panels", it is panel #9 alone; and the traders view's single panel (16,058 px) is an equally large second source. |
| **2** | "Cut 1 — merge the two live-setup/state renderers. 'This Company at a Glance' and 'One Company, In Detail → Latest market state' print **4 identical numbers**; 'The Pattern and How Much to Risk' and the detail panel print the **same trigger/stop/target**." | **CONFIRMED** (both halves, with exact strings) | KEI, 1440: `#stockPulse` = *"Latest stored close 2026-08-21 ₹5527.60 1-session change -2.6% 20-session change +13.5% 60-session change +4.9% Trend context above EMA 20 / above EMA 50 / above EMA 200"* vs `#researchBox` = *"…as of 2026-08-21 · close 5527.60009765625 … Latest market state · 2026-08-21 Close / daily change 5527.60 · -2.6% 20 / 60 session move +13.6% · +4.9% Trend context above 20 · above 50 · above 200…"* → same **date, close, daily change, 60-session change and trend context** (the 20-session figure differs: 13.5% vs 13.6%). Trigger/stop/target: for **VADILALIND** (live setup today) `#setupSummary` = *"Trigger 7505 PDL Stop 7400 Target (3R) 7820"* and `#researchBox` = *"LIVE SETUP TODAY — signal 2026-08-25 entry 7505 · stop 7400 · 3R 7820"* — the **same three numbers in two panels**. Note the duplication *disappears* for symbols with no live setup (KEI shows "none triggered today"), so it is state-dependent but real. |
| **3** | "Cut 2 — collapse the ledger's third table. `ledgerCompanies` is a pure filtered re-render of the same `/api/ledger/trades` array that `ledgerTable` already shows, minus trigger/stop/target." | **CONFIRMED** | Ledger view measured: **4 panels / 3 tables / 16 rendered rows for 9 ideas**. "Every Idea We Recorded" = 1 table, 9 rows (*"2026-06-09 ATGL 761.73 737.74 809.72 LOSS"*). "Which companies worked, and which did not" = **2 more tables, 7 rows**, same 9 ideas regrouped (*"GEOJITFSL 2023-09-28 reached the goal WIN +2R"*). API confirms 9 rows (`/api/ledger/trades`: 6 LOSS, 1 WIN, 2 EXPIRED). So 9 ideas are rendered as 16 rows in 3 tables. |
| **4** | "Cut 3 — one home for the disclaimers. The uncalibrated-score sentence exists in **7** places, the 'not advice / not a forecast' family in **8** more (**15 total**); one copy is always-visible prose in a panel subtitle." | **PARTLY WRONG** | The 15 copies exist in *source*, but the volume of **rendered** text is **3, not 15**: measured across all 7 views, rendered text contains **1 × "uncalibrated"** (the swing subtitle at `index.html:448` — that part of the claim is **CONFIRMED**) and **2 × the not-advice family** (swing + `#researchBox`'s *"This is observed end-of-day price behaviour, not a forecast."*). **Research view: 0 "uncalibrated" rendered.** The other ~12 copies are invisible by design: `data-tip` tooltips (6), the collapsed **Methodology & Disclaimers** block (2), `MODEL_EVENT_SCORE_HELP` (1), default/empty-state strings (`cards.js`, `app.js`). So "delete 15 repeated sentences" would remove **nothing visible** and would delete tooltips that currently serve P7/P9. The correct verdict on this cut is **do nothing**. |
| **5** | "Plus one correctness win hiding as clutter: the tile 'Graded win rate' and the ledger row 'Win Rate' are **two different numbers under the same words**, one click apart." | **REFUTED** | Measured on one screen: tile = **"Graded win rate 14.3%"**; ledger panel "How The System Has Done" = **"Ideas Recorded 7 · Wins / Losses 1 / 6 · Win Rate 14.3%"**. Independently recomputed from `/api/ledger/trades` (1 WIN, 6 LOSS, 2 EXPIRED): 1 ÷ (1+6) = **14.3%** — the same number from the same underlying ideas. There is no two-numbers hazard. (A *real* smaller wrinkle: the ledger shows "Ideas Recorded 7" while the API returns 9 rows; the 2 EXPIRED are excluded from the graded set. The tile says "Only ideas whose outcome is already known", which is consistent.) |

---

## 4. Measured inventory — every top-level panel, both viewports

`belowBy` = how far the panel's top sits past the fold (blank = starts above the fold).
`screens` = panel height ÷ viewport height. Counts are live DOM counts.

### 1440×900 (fold 900 px) — all 7 views total **53,188 px of scroll = 59.1 screens**

| view | page height | panels | panel, in DOM order (top px, height px) | below-fold | interactive / buttons / `[data-explain]` / rows / cards |
|---|---|---|---|---|---|
| **research** | **22,169 px** (24.6 scr) | **10** | 1 Chart Inspector (417, 656) · 2 The Pattern and How Much to Risk (1091, 214) · 3 This Company at a Glance (1323, 193) · 4 Which Book Ideas Fit This Stock (1323, 193) · 5 Compare Companies (1534, 172) · 6 One Company, In Detail (1724, 173) · 7 Companies You Can Research (1915, 1995) · 8 Industry Groups (3928, 577) · **9 Chart Patterns Found Today (4522, 17366 = 78.3% of page)** · 10 Find Companies By Numbers (21907, 185) | #2 +191 · #3 +423 · #4 +423 · #5 +634 · #6 +824 · #7 +1015 · #8 +3028 · #9 +3622 · **#10 +21007** | 78 / 68 / 9 / 61 rows / 73 cards |
| **funda** | 1,026 px (1.1 scr) | 4 | 1 Rules You Have Written (158, 271) · 2 Cheap But Solid Companies (447, 172) · 3 Longer-Hold Ideas (637, 172) · 4 Today's Shortlist (827, 122) | #4 partially (ends 949) | 7 / 3 / 4 / 0 / 3 |
| **swing** | 9,166 px (10.2 scr) | 4 | 1 Custom Strategies (158, 437) · 2 Short-Term Ideas (614, 576) · **3 Steady Uptrends (1207, 5038 = 55%)** · **4 What Is Moving Today (6263, 2826 = 31%)** | #3 +307 · #4 +5363 | 55 / 7 / 48 / 9 rows / 70 cards |
| **ledger** | 1,688 px (1.9 scr) | 4 | 1 How The System Has Done (158, 752) · 2 Every Idea We Recorded (158, 752, side-by-side) · 3 Which companies worked… (928, 492) · 4 Rule Testing History (1438, 172) | #3 +28 · #4 +538 | 26 / 0 / 26 / 16 rows / 0 |
| **system** | 1,628 px (1.8 scr) | 3 | 1 Is everything working (158, 699) · 2 Where the numbers come from (876, 348) · 3 For Developers (1241, 310) | #3 +341 | 8 / 1 / 2 / 0 / 0 |
| **traders** | **16,294 px** (18.1 scr) | **1** | **1 Trading Methods (158, 16058 = 98.6% of page, 17.8 screens)** | extends 16,058 px | **171 / 167 / 1** / 0 / 0 (153 method rows, 3 `<details>`) |
| **league** | 1,217 px (1.4 scr) | 1 | 1 Practice League (Pretend Money) (205, 934) | — | 13 / 6 / 1 / 11 rows / 0 |

### 390×844 (fold 844 px) — all 7 views total **62,779 px of scroll = 74.4 screens**

| view | page height | panels | notable offsets | below-fold | interactive / buttons / rows |
|---|---|---|---|---|---|
| **research** | **22,920 px** (27.2 scr) | 10 | 1 Chart Inspector (648, 530) · **9 Chart Patterns (4787, 17791 = 77.6%)** · 10 Find Companies By Numbers (22596) | #2 +352 · #3 +553 · #4 +694 · #5 +878 · #6 +1075 · #7 +1277 · #8 +3307 · #9 +3943 · **#10 +21752** | 78 / 68 / 61 rows |
| **funda** | 1,357 px (1.6 scr) | 4 | 1 (245, 543) · 2 (806, 187) | #3 +167 · #4 +353 | 7 / 3 / 0 |
| **swing** | 13,614 px (16.1 scr) | 4 | 1 Custom Strategies (245, 1116) · **3 Steady Uptrends (1899, 6103)** · **4 What Is Moving Today (8020, 5522)** | #2 +535 · #3 +1055 · #4 +7176 | 55 / 7 / 9 rows |
| **ledger** | 2,272 px (2.7 scr) | 4 | 1 (245, 351) · 2 Every Idea We Recorded (613, 635) | #3 +422 · #4 +1188 | 26 / 0 / 16 rows |
| **system** | 1,747 px (2.1 scr) | 3 | 1 (245, 747) | #2 +166 · #3 +557 | 8 / 1 / 0 |
| **traders** | **19,365 px** (22.9 scr) | 1 | **1 Trading Methods (245, 19049 = 98.4%)** | extends 19,049 px | 171 / 167 / — |
| **league** | 1,504 px (1.8 scr) | 1 | 1 Practice League (245, 1188) | — | 13 / 6 / 11 rows |

**Real rendered counts vs the code caps** the previous audit had to assume:

| thing | code cap / assumption | actually rendered (measured) |
|---|---|---|
| research #7 Companies You Can Research | `max_symbols=200` | **51 rows × 12 columns** (page height 1,995 px) |
| research #9 Chart Patterns | `limit=60` + 12 DTW matches | **73 cards**, 61 toggle buttons, 14,225 chars |
| swing #2 Short-Term Ideas | server `limit: 80` | **9 rows** |
| swing #3 Steady Uptrends | `n=30` | **31 cards** |
| swing #4 What Is Moving Today | 3 groups × ≤18 | **39 cards** |
| traders | "14 books", every method expanded | **153 method rows**, 167 `?` buttons, 3 `<details>` |
| league | ~10 sub-blocks | 11 rows, 3 `<details>`, 1 table |
| `.level` rows | expected as a row class | **0 elements in all 7 views** (class is used by live code paths in `app.js:551,565` and `traders.js:265`, just never hit here) |

---

## 5. What is repeating — by value, from rendered text

Literal tokens (dates, percentages, ₹ amounts, decimals) extracted per research panel at 1440, KEI loaded, and
intersected across panels:

| repeated value | panels it appears in |
|---|---|
| `0%` | **5 panels** (#2, #6, #7, #8, #9) |
| `50%` | **4 panels** (#2, #6, #7, #8) |
| `2026-08-21` (the stored bar date) | **3 panels** (#1 KEI Inspector, #3 This Company at a Glance, #6 One Company In Detail) |
| `2026-10-07` (the scan date) | **3 panels** (#7 Companies, #8 Industry Groups, #9 Chart Patterns) |
| `₹52408.25` (market cap) | 2 panels (#1 Inspector, #2 Pattern & Risk) |
| `5527.60` (close) | 2 panels (#3 Glance, #6 In Detail) |
| 0.22, 0.70, 0.85, 100%, 2.6%, 22%, 60%, 63%, 69%, 80%, 86% … | 3 panels each (#7/#8/#9 mostly) |

The **scan date is repeated in 3 panels, not 2** — confirmed independently at the API: `/api/research-universe.date`
= `/api/research-sector.date` = `2026-10-07`. The **bar date and close are printed in 3 and 2 places** respectively.

Also visible in the data: `#researchBox` renders the close as an unformatted float — *"close 5527.60009765625"* —
while the same value is printed as `₹5527.60` two panels up. That is a small cosmetic bug the duplication hides.

---

## 6. Navigation duplication — measured live, both viewports

The nav system has **8 destinations** (7 views + Glossary) reached by **21 destination affordances**
(19 × `[data-view]` + 2 × `a[href="/glossary"]`), plus 2 more `[data-detail-url]` openers = **23 nav-ish affordances**
in the DOM.

| destination | 1440×900 total / on-screen | 390×844 total / on-screen |
|---|---|---|
| research | 4 / 4 — sidebar brand, sidebar item, rail item, metric tile | 4 / **2** — rail item + tile (sidebar brand & item off-canvas) |
| ledger | 4 / 4 — sidebar, rail, **2 metric tiles** | 4 / **3** |
| swing | 3 / 3 — sidebar, rail, tile | 3 / **2** |
| funda | 2 / 2 — sidebar, rail | 2 / **1** |
| traders | 2 / 2 — sidebar, rail | 2 / **1** |
| league | 2 / 2 — sidebar, rail | 2 / **0** (rail item at x=462 is past the 390 px edge) |
| system | 2 / 2 — sidebar, rail | 2 / **0** (rail item at x=534) |
| glossary | 2 / 2 — sidebar, rail | 2 / **0** (rail item at x=607) |
| **total** | **23 / 23 on-screen** | **23 / 10 on-screen** |

So the previous audit's **"21 affordances for 8 destinations" is CONFIRMED at 1440** — and it is viewport-dependent
exactly as you suspected: **at 390 only 10 of the 23 are reachable** without opening the hamburger drawer (the whole
sidebar is parked off-canvas at x = −286/−300) or scrolling the pill rail sideways (League, System and Glossary sit
beyond the right edge). At 1440 the pill rail repeats the sidebar **item for item** — same 8 destinations, their
labels repeated verbatim, so **16 of the 23 affordances are two copies of the same 8-item menu**.

---

## 7. Dead markup — measured two ways

| question | answer |
|---|---|
| ids defined in `index.html` | **93** |
| of those, present in the live DOM | **93 / 93** |
| of those, **touched by some script** (MutationObserver at document-start, all 7 views visited) | **93 / 93** |
| **ids nothing touches → dead markup** | **0** |
| ids created at runtime (not in `index.html`) | 84 (e.g. `checks-0-VADILALIND-HIGH_TIGHT_FLAG`, `strat-picks-Multibagger`) — 177 ids total |
| static-grep-only result | 12 ids look "unreferenced" — **all 12 are false positives**, e.g. `#view-funda` is built as `$("view-" + name)` (`app.js:66`). A naive grep would have you delete live containers. |

**`terminal/static/deployment.js` — CONFIRMED gone and unreferenced**: the file no longer exists, no `<script src>`
mentions it, and the string `deployment.js` appears nowhere in the tree. Its functionality now lives in
`app.js:830 loadDeployment()`, which writes `#deploymentBadge` (`index.html:634`, a live, touched element). Nothing is
broken and there is nothing left to delete here.

**Two genuinely unreferenced files exist** (repo hygiene, not visible clutter):

| file | size | grep proof |
|---|---|---|
| `terminal/static/wisdom.html` | 28,861 B | not loaded by `index.html`; the "What things mean" nav item points at `/glossary`, which is rendered by `glossary_ui.py` (`terminal_api.py:106`), not this file; `EXECUTION_LOG_FULL.md:1125` already records it as **out of sync with `traders/wisdom.py` (14 entries missing) and "queued for regen"** → a stale duplicate of `MARKET_WISDOM.md`. |
| `terminal/static/vendor/cn.js` + `vendor/clsx.js` + `vendor/tailwind-merge.js` + `vendor/lib/clsx.mjs` + `vendor/lib/tailwind-merge.mjs` | 568 B + 350 B + 545 B + 388 B + **109,671 B** | `index.html` loads exactly one module, `icons.js`, which imports only `vendor/lucide.js`. Nothing imports `vendor/cn.js` — the only occurrences of `cn.js` / `cn(` in the whole `terminal/static` tree are inside `cn.js`'s own comment header. So ~110 KB of vendored JS is never fetched by the browser. **Keep** `vendor/lucide.js` (5,924 B) and `icons.js` — both live. |

---

## 8. Trim plan — ordered by measured value

Savings marked **[measured]** are panel heights removed at 1440×900 (a removed panel removes exactly its height);
savings marked *[est]* are source/markup estimates that I did not render-test.

### 8a. Do these first — the two panels that hold 63% of all the scroll

| # | Item | Where | Evidence | Recommendation | Saving |
|---|---|---|---|---|---|
| 1 | **"Chart Patterns Found Today"** (`#patternList`) | research, panel #9 | **17,366 px tall = 19.3 screens = 78.3% of the research page**; 73 cards, 61 toggle buttons, 14,225 chars; pushes panel #10 to 21,007 px below the fold | **COLLAPSE / HIDE BY DEFAULT** — show the top ~8 patterns as a list, "Show all 73" behind a click (P8), and give the pattern lab its own view (the two-pillar model already lists "RESEARCH — analysis & pattern lab") | **≈15,000–17,000 px off research (≈70% of the page)** **[measured]** |
| 2 | **"Trading Methods"** (`#tradersIndex`) | traders, panel #1 | **16,058 px = 17.8 screens = 98.6% of that view**; 153 method rows fully expanded, 167 `?` buttons, 17,526 chars | **COLLAPSE per book** — the panel already has 3 `<details>` (one per pillar); make every book a `<details>` closed by default, keep pillar summaries (P8). This is deliberately deep (P2/P8) — collapse, don't cut | **≈14,000–16,000 px (≈90% of the view)** **[measured]** |
| 3 | **"Steady Uptrends"** (`#trendList`) + **"What Is Moving Today"** (radar) | swing, panels #3 and #4 | 5,038 px (31 cards) + 2,826 px (39 cards) = **7,864 px = 86% of the 9,166 px swing page**; at 390 they are 6,103 + 5,522 px | **CAP + COLLAPSE** — 10 cards each with "show all", or one tabbed "What is moving" panel. Three radar groups currently print 39 cards with no visible cap | **≈6,000–7,500 px off swing** **[measured]** |
| 4 | **"Companies You Can Research"** (`#researchUniverseBox`) | research, panel #7 | 51 rendered rows × 12 columns = **1,995 px = 9% of the page** (the "1522" tile is the *eligible* count, not the rows shown) | **COLLAPSE to 10 rows** with sort + "show all 51" (P4 sortable, P8 disclosure). Also fold in panel #8 "Industry Groups" as a tab of the same panel | **≈1,600 px** **[measured]** + one panel header saved |

### 8b. Merge the duplicates (each removes a "same number, two places" hazard)

| # | Item | Where | Evidence | Recommendation | Saving |
|---|---|---|---|---|---|
| 5 | `#stockPulse` "This Company at a Glance" **vs** `#researchBox` "Latest market state" | research panels #3 and #6 | same bar date, close, daily change, 60-session change and trend context in both (KEI: `2026-08-21`, `5527.60`, `-2.6%`, `+4.9%`, "above 20/50/200") | **MERGE INTO ONE** — keep "This Company at a Glance" as the single market-state card and delete the copy inside "One Company, In Detail" | 1 panel + ~5 rows; also removes the raw-float leak (`5527.60009765625`) **[measured]** ≈193 px |
| 6 | `#setupSummary` "The Pattern and How Much to Risk" **vs** the LIVE SETUP block in `#researchBox` | research panels #2 and #6 | VADILALIND: "Trigger 7505 · Stop 7400 · Target (3R) 7820" in #setupSummary and "entry 7505 · stop 7400 · 3R 7820" in #researchBox | **MERGE INTO #researchBox** (keep the levels once, next to the pattern context) and reduce #setupSummary to the Model Event Score row | ≈214 px + 1 empty row ("Target >50% —") **[measured]** |
| 7 | `#ledgerCompanies` "Which companies worked, and which did not" | ledger panel #3 | **3 tables / 16 rendered rows for 9 ideas**; the second panel re-renders the same 9 rows grouped WIN/LOSS | **MERGE INTO the single table** with a WIN/LOSS filter or group toggle instead of a second panel (previous audit's Cut 2 — confirmed) | ≈492 px (29% of the ledger view) + 2 tables **[measured]** |
| 8 | 4 **metric tiles** that navigate (swing / ledger ×2 / research) | research first screen | the same 4 destinations are already in the sidebar and the pill rail; the tiles are the 4th, 4th, 3rd and 2nd affordance for those views (§6) | **KEEP the numbers, REMOVE the navigation** (or keep one) — they are status, not a menu | Removes 4 of the 21 destination affordances; 116 px of first-screen chrome **[measured]** |

### 8c. First-screen chrome (matters most on mobile)

| # | Item | Where | Evidence | Recommendation | Saving |
|---|---|---|---|---|---|
| 9 | **Pill rail** repeating the sidebar item-for-item | every view, ≥950 px wide too | measured: 8 destinations in the sidebar **and** 8 identical items in the rail = 16 of the 23 affordances; the CSS already turns the sidebar into an off-canvas drawer **below 950 px** | **HIDE BY DEFAULT at ≥950 px** (sidebar is present); show the rail only when the sidebar is off-canvas. One navigation, not two | 38 px of first-screen chrome + 8 duplicate affordances **[measured]** |
| 10 | **"Regime unavailable — No benchmark data found for any candidate"** full-width banner | every view, first screen (y = 205 at 1440, y = 262 at 390) | 62 px tall amber card whose only content is an empty state; the sidebar's "Service status" card (99 px) is a second always-on status block | **HIDE BY DEFAULT** — collapse into a pulse dot + tooltip; show the banner only when a regime *is* available | ≈160 px of prime first-screen space at 1440, ≈100 px at 390 **[measured]** |
| 11 | **"Latest saved data reloaded. Use scan buttons to compute new results."** status sentence | topbar | at 390 it wraps to **4 lines** and occupies the same visual weight as the search box, pushing the rail and chart down | **SHORTEN / HIDE** — one word ("Saved") or a timestamp; put the instruction in the tooltip | ≈50–90 px at 390 (part of the 648 px of pre-chart chrome) **[measured]** |
| 12 | **Sidebar "Service status" card** (`#healthStatus` + "Research only · no orders are placed") | every view | 99 px card at the bottom of the sidebar duplicating the System view's "Is everything working" panel (699 px) | **MOVE INTO the System view** (P1: answer first, derivation on click) | 99 px of persistent sidebar **[measured]** |

### 8d. Safe to delete now (with grep proof)

| Item | Proof | Action |
|---|---|---|
| `terminal/static/deployment.js` | **already deleted**; file absent, no `<script src>`, no string reference anywhere | nothing to do — verified, not an action |
| `terminal/static/vendor/cn.js`, `vendor/clsx.js`, `vendor/tailwind-merge.js`, `vendor/lib/*.mjs` (**110 KB**) | `index.html` loads one module (`icons.js`) which imports only `vendor/lucide.js`; the only `cn.js` / `cn(` references in `terminal/static` are inside `cn.js`'s own header comment | **DELETE** (keep `vendor/lucide.js` + `icons.js`). Repo hygiene only — no visual effect |
| **Dead markup** | runtime observer: **0 of 93** ids untouched; all 93 mutated by a script | **nothing to delete.** Do **not** act on the 12 grep-only "unreferenced" ids — they are built dynamically (`app.js:66`) |
| `.level` CSS rules (`fintech.css:1113-1125`, `style.css:357-366, 802-810`) | 0 `.level` elements rendered in the 7 views, **but** the class is assigned by live code (`app.js:551,565`, `traders.js:265`) | **KEEP** — deleting the CSS would strand those code paths |

### 8e. Needs owner decision

| Item | Evidence | The decision |
|---|---|---|
| `terminal/static/wisdom.html` (28.8 KB) | not linked from anywhere; `/glossary` is Python-rendered (`glossary_ui.py`); `EXECUTION_LOG_FULL.md:1125` says it is out of sync and queued for regen | **DELETE** it and keep `/glossary` as the single home (P10 "if a section is unused after a week, remove it") — or regenerate it if you still want a static copy |
| Duplicate card list for mobile in the League panel (`lg-hide-sm`, 12 elements) | league panel = 11 rows in 1 table **plus** a mobile-only card re-render of the same rows | **KEEP** — it is a legitimate responsive form of the same component (P2), not clutter. Revisit only if the table becomes horizontally scrollable instead |
| 4 metric tiles | see 8b #8 | keep as status, or repurpose the first screen entirely (e.g. survival stats instead of nav) |
| Pattern lab as its own view | research is 24.6 screens, 78% of it patterns; PORTAL_REDESIGN already names "RESEARCH — analysis & pattern lab" | structural choice: separate view vs collapsed panel |

### 8f. Explicitly NOT worth doing

| Previous-audit suggestion | Why not |
|---|---|
| "Delete 15 repeated disclaimer sentences" | only **3** are rendered anywhere; the other ~12 are tooltips/collapsed text that satisfy **P7** ("no panel shows a number the owner can't act on") and **P9** ("the portal never recommends"). Deleting them removes no visual clutter and removes the compliance text. **Keep** the collapsed Methodology block and the per-number `?`. |
| "Fix the two different win rates" | they are the **same** number (14.3% = 1W/6L). No fix needed. |
| "Delete dead markup" | **zero** dead ids. |
| "Trim `.level` CSS" | live code paths use it. |

---

## 9. What NOT to touch (tied to `PORTAL_REDESIGN.md` principles)

- **P1 — default to answer, hide derivation behind a click.** The collapsed **Methodology & Disclaimers** block and the
  `data-tip` tooltips are the *correct* implementation of P1 (that is why only 3 disclaimer sentences are visible).
  Do not "clean them up".
- **P2 — one card component used everywhere.** The metric tiles, `unified-card`, `stock-card`, `metric-card` and the
  League's mobile card list are the same idea in different sizes. Trim by *collapsing* them, not by inventing new
  components; and keep the League mobile card list.
- **P3 — colour encodes meaning.** The dark fintech layer (`fintech.css`), the pulse-dot pills and the green/amber/red
  states are the design system — leave the visual language alone; all the trim above is structural, not cosmetic.
- **P4 — every table is sortable and self-explanatory.** When you collapse "Companies You Can Research" and "Every Idea
  We Recorded", keep the sort controls and the header explanation.
- **P5 — every scanner reports its rule in human language.** The strategy cards ("Rules You Have Written", "Custom
  Strategies") are 271 px and 437 px — they carry the rule text. Keep the rule/description, collapse only repetition.
- **P6 — every historical claim is backed by visible sample size.** Do not drop the `n`, `P=53%`, `+1R 88%`, "9 ideas
  recorded", "15 setups over 5y" numbers when collapsing the research/detail panels. They are the sample sizes that
  make the claims honest.
- **P7 — no panel shows a number the owner can't act on.** This is the test to apply to the pattern cards and the
  radar cards: each card should carry a decision (breakout level, stop, target), otherwise it is a list, not a panel.
- **P8 — progressive disclosure: simple by default, deep on demand.** Items 1–4 above are pure P8 work.
- **P9 — the portal never recommends; it presents.** Keep the "not advice / not a forecast" text that *is* visible
  (swing subtitle + the research method note).
- **The System view is not clutter** (1.8 screens): "Is everything working", "Where the numbers come from" and
  "For Developers" are the provenance story from the data-provenance work. Leave it.
- **The Funda view is not clutter** (1.1 screens, 4 panels, 3 cards): it is already the shape the other views should
  copy. Use it as the model for the collapsed research/swing views.
- **The two-pillar structure (FUNDA / SWING) and the RESEARCH / LEDGER / SYSTEM supporting sections** are the
  owner's stated model — do not renumber or merge views while trimming panels.

---

## 10. Limits — what I could not measure reliably

1. **All clutter numbers are for one symbol and one day.** `KEI` was the primary symbol for value/duplication
   measurements and `VADILALIND` for the live-setup case. Row counts and panel heights vary with the day's scan
   results (the research page measured 22,169 px with KEI and 23,692 px in the same session when the symbol panels
   filled in). Ratios are stable; absolute pixel counts are not.
2. **Panel `topAbs` values are one-point-in-time.** Panels above a measured panel grow as their data arrives, so the
   later offsets shift by a few hundred px between runs. The *ordering* and the huge gaps (3,943 px, 21,752 px) are
   stable.
3. **I could not measure what is below the recorded fold on a per-user basis.** Everything is measured at exactly
   1440×900 and 390×844, device scale factor 1, no OS font smoothing differences; a 1512×982 laptop or 412×915 phone
   will land differently.
4. **"Time to reach a panel" is not measured** — only pixels. I did not measure scroll counts, reading time, or how
   often you actually use each panel (that needs telemetry that does not exist). P10 ("if a section is unused after a
   week, remove it") therefore still needs your judgement.
5. **The rendered-disclaimer count is for the 7 hash views with data loaded.** An empty/unloaded state renders
   different strings; the collapsed Methodology block's own text is never in `innerText` by design, so "0 rendered" is
   correct but is not the same as "not in the source".
6. **My `#setupSummary` / trigger-stop-target conclusion is state-dependent.** The duplication renders only when a
   live setup exists (VADILALIND today; KEI shows "none triggered today"). It is real, but it will look absent on many
   days.
7. **Nav counts are for the 8 destinations wired in `index.html`.** Any destination reachable only from inside a panel
   (e.g. a symbol link that loads another symbol) is not counted as navigation; I counted only view-switching
   affordances and the Glossary link.
8. **Static-grep dead-markup analysis alone is unreliable** on this codebase — it produced 12 false positives out of
   93 ids because selectors are composed at runtime. I therefore relied on the runtime observer; ids that a script
   only *reads* (never mutates) are recorded as untouched, which is the correct definition for "safe to delete" but
   could mislabel a read-only hook.
9. **I did not test any of the proposed cuts.** Every saving above is a measured panel height, not a render of the
   trimmed design; collapsing a panel also changes what is above the fold, so re-measure after each cut with
   `node tools/ui-audit/audit.mjs --url http://127.0.0.1:8024 --routes research,traders,swing --viewports 1440x900 --settle 6000`.
10. **Nothing was modified.** This report is the only file written. No product file, no `tools/ui-audit/**`.
