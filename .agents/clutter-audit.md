# Clutter audit — NSE Research terminal

**Deliverable for the owner. Read-only audit; nothing was modified except this file.**

**Audited revision** (files were being edited by another agent while I read; every claim below was
re-verified against these hashes):

| file | sha256 (first 10) | real lines |
|---|---|---|
| `terminal/static/index.html` | `B1B7043862` | 708 |
| `terminal/static/app.js` | `693D8C17F7` | 1883 |
| `terminal/static/cards.js` | `F221215D19` | 237 |
| `terminal/static/research.js` | `E3D2A51F8A` | 283 |
| `terminal/static/research_universe.js` | `70575DE345` | 211 |
| `terminal/static/research_sector.js` | `FFC8DCB94F` | 162 |
| `terminal/static/scanners.js` | `5E488E2B8D` | 93 |
| `terminal/static/traders.js` | `514F49A4F0` | 734 |
| `terminal/static/league.js` | `A8A2025652` | 433 |
| `terminal/static/deployment.js` | `84BDAB327E` | 38 |
| `terminal_api.py` | `AC7E906EAF` | 1104 |

`app.js` grew from 1586 → 1883 lines **during this audit** (someone added an RSI pane, EMA-10 toggle
and crosshair readout). Line numbers for `app.js` may drift by a few lines; every citation therefore
carries its anchor text so it stays greppable. Two findings I had written up were **already fixed**
mid-audit and are excluded: EMA 10 is now legended and toggleable (`app.js:1133` `_renderChartChrome`,
`FX_EMA10_PREF` at `app.js:909`) and the chart legend names RSI 14.

---

## Executive summary

1. **The single biggest clutter source is the research view: 10 stacked panels (`index.html:469-571`), of which 6 restate data already on screen** — the same price bar date twice, the same scan date twice, the same close/1d/20d/60d/EMA-trend block twice, and the same trigger/stop/target twice.
2. **Cut 1 — merge the two live-setup/state renderers.** "This Company at a Glance" (`app.js:1533-1596`) and "One Company, In Detail" → "Latest market state" (`research.js:148-155`) print 4 identical numbers; "The Pattern and How Much to Risk" (`app.js:1386-1388`) and `research.js:159-163` print the same trigger/stop/target. Removes ~1 panel + ~8 rows.
3. **Cut 2 — collapse the ledger's third table.** `ledgerCompanies` (`app.js:786-820`) is a pure filtered re-render of the same `/api/ledger/trades` array that `ledgerTable` (`app.js:664-684`) already shows, minus trigger/stop/target. It adds 2 tables, 10 columns and a second panel header (`index.html:617`) for one word gloss. Removes 1 panel, 2 tables.
4. **Cut 3 — one home for the disclaimers.** The uncalibrated-score sentence exists in **7** places, the "not advice / not a forecast" family in **8** more (15 total); one copy is always-visible prose in a panel subtitle (`index.html:448`). Keep the collapsed methodology block (`index.html:656-680`), keep the per-number `?`, delete the restated subtitles. Removes 15 repeated sentences.
5. **Plus one correctness win hiding as clutter:** the tile "Graded win rate" (`index.html:357`) and the ledger row "Win Rate" (`app.js:657`) are **two different numbers under the same words, one click apart** — different endpoints, different denominators (see §2.5).

---

## 1. Per-view inventory of what the user actually sees

### 1.0 Global chrome (every view)

| Block | Where | What it shows | Route |
|---|---|---|---|
| Brand button → research | `index.html:235` | nav | — |
| Sidebar nav | `index.html:247-277` | 7 view buttons + 1 glossary `<a>` | — |
| Sidebar footer "Service status" | `index.html:282-287` | `#healthStatus` + "Research only · no orders are placed" | `GET /api/health` via `data-detail-url` |
| Topbar search + Open symbol + Refresh | `index.html:304-321` | symbol in, `#refreshStatus` out | drives `loadSymbol` / `refreshAll` (`app.js:1748`) |
| Pill rail | `index.html:323-339` | the same 7 views + Glossary | — |
| Metric tiles ×4 | `index.html:349-372` | Signals listed / Graded win rate / Open-pending / Companies you can research | `/api/swing/signals` (`app.js:306-308`), `/api/radar` (`app.js:590`) |
| Methodology & Disclaimers | `index.html:656-680` | 6 paragraphs, collapsed | none (static) |
| Data detail dialog | `index.html:683-692` | raw JSON / explain pane for any click | `/api/explain/{key}` |

**The market overview + 4 tiles are research-only.** `style.css:775` `.market-overview.is-collapsed{display:none}` and `app.js:98` toggles it on `name !== "research"`. So the 4 metric cards are a *fifth* nav mechanism that exists only on one view.

### 1.1 Nav duplication — 21 affordances for 8 destinations

| Destination | Affordances | Where |
|---|---|---|
| **research** | **4** | brand `index.html:235`; sidebar `:256`; rail `:324`; metric tile `:365` |
| **ledger** | **4** | sidebar `:265`; rail `:332`; tile "Graded win rate" `:355`; tile "Open / pending" `:360` |
| swing | 3 | sidebar `:251`; rail `:328`; tile `:350` |
| funda | 2 | sidebar `:247`; rail `:326` |
| traders | 2 | sidebar `:260`; rail `:330` |
| league | 2 | sidebar `:269`; rail `:334` |
| system | 2 | sidebar `:273`; rail `:336` |
| glossary | 2 | sidebar `:277`; rail `:338` |

7 destinations, 19 view-switching affordances in persistent chrome, plus 2 glossary links = **21**.
The sidebar and rail also carry **byte-identical `title=` tooltips** for every item (e.g.
"Long-term quality views. Click the label to learn what is checked" at both `index.html:248` and `:327`).
The rail is the sidebar minus the labels — its only distinct job is narrow-screen access
(`.fx-navrail` visible, sidebar off-canvas), so it is a responsive duplicate, not a second navigation.

### 1.2 FUNDA — `#view-funda` (`index.html:376`) — **4 panels**

| # | Panel (header) | Filled by (id) | Route | Rows / fields | Fold |
|---|---|---|---|---|---|
| 1 | Rules You Have Written (`:377-386`) | `#fundamentalStrategyList` (`:385`), badge `:383` | `GET /api/strategies`, filter `type==="fundamental"` (`strategies.js:9-13`) | 1 card per strategy; each card = name + description + condition string + 3 buttons (Backtest/Edit/Run) (`strategies.js:38-53`) | below |
| 2 | Cheap But Solid Companies (`:388-394`) | `#valueRadarList` (`:393`) | `GET /api/value-radar?n=25` (`scanners.js:67`) | ≤25 cards × 4 mono kv cells (`cards.js:60` caps at 4) | below |
| 3 | Longer-Hold Ideas (`:396-402`) | `#positionalList` (`:401`) | `GET /api/positional?n=30` (`scanners.js:36`) | ≤30 cards | below |
| 4 | Today's Shortlist (`:404-407`) | `#picksList` (`:406`) | `GET /api/toppicks` (`app.js:270`) → `top_picks.top(15)` (`terminal_api.py:659`) | 15 cards | below |

Subtitle text: panel 1 = "Owner-authored rules. Edit or Run directly here." (`index.html:381`).

### 1.3 SWING — `#view-swing` (`index.html:411`) — **4 panels**

| # | Panel (header) | Filled by (id) | Route | Rows / fields | Fold |
|---|---|---|---|---|---|
| 1 | Custom Strategies (`:412-421`) | `#swingStrategyList` (`:420`), badge `:418` | `GET /api/strategies`, filter `type==="swing"` (`strategies.js:13`) | same renderer as FUNDA#1 | below |
| 2 | Short-Term Ideas (`:423-437`) | `#swingTable` (`:434`), `#swingScanStatus` (`:428`), Run button `:426` | `GET /api/swing/signals` (`app.js:301`) | **10 columns × ≤80 rows** (server cap `limit: int = 80`, `terminal_api.py:670`); no row-count or "showing 80 of N" indicator | below |
| 3 | Steady Uptrends (`:439-445`) | `#trendList` (`:444`) | `GET /api/trend?n=30` (`scanners.js:8`) | ≤30 cards | below |
| 4 | What Is Moving Today (`:447-465`) | `#radarMomentum` `:452`, `#radarVolume` `:456`, `#radarTurn` `:460` | `GET /api/radar` (`app.js:589`) | 3 columns × ≤18 cards = **≤54 cards**; server builds 40 per group (`terminal_api.py:767`) → 66 rows computed and discarded | below |

### 1.4 RESEARCH — `#view-research` (`index.html:467`) — **10 panels**

| # | Panel (header) | Filled by (id) | Route | Rows / fields | Fold |
|---|---|---|---|---|---|
| 1 | Chart Inspector (`:469-485`) | `#chartPrice` `:479`, `#chartRsi` `:480`, `#chartReadout` `:481`, toolbar `:477`, legend `:483`, mobile note `:484` | `GET /api/cockpit/{symbol}/chart`; markers from `GET /api/patterns/history/{symbol}?limit=500` (`app.js:1322`) | 1 candlestick + 1 RSI pane + 3 price lines (`app.js:1381-1383`) + RSI 30/70 lines (`app.js:1296-1297`) + 6-item legend (`app.js:1133`) + live readout | **above** |
| 2 | The Pattern and How Much to Risk (`:486-492`) | `#setupSummary` `:488`, `#newsList` `:489` | `/api/cockpit/{s}/summary`, `/api/sizing/{s}`, `/api/meta/{s}`, `/api/delivery/{s}` | **5 stacked blocks in 1 panel**: setup 3 rows + toggle (`app.js:1386-1390`); sizing block injected (`app.js:1607`); Model Event Score row + "What pushed this score" (`app.js:1481-1495`); Delivery % with own toggle (`app.js:1675`); Latest News list | **above** |
| 3 | This Company at a Glance (`:494-498`) | `#stockPulse` `:498` | `/api/cockpit/{s}/chart` candles | 5 rows + collapsed "Methodology & source" (`app.js:1582-1596`) | at fold |
| 4 | Which Book Ideas Fit This Stock (`:500-507`) | `#traderMatchBox` `:505`, `#refreshTraderMatches` `:503` | `GET /api/traders/matches/{symbol}` (`traders.js:601`) | 1 status line + N match buttons | below |
| 5 | Compare Companies (`:509-521`) | `#compareBox` `:518` | `GET /api/compare` (`app.js:635`) | **20 metric rows × 2–4 columns** (`cards.js:158-224`) | below |
| 6 | One Company, In Detail (`:523-529`) | `#researchBox` `:528` | `GET /api/research/{symbol}` (`research.js:289`) | **6 blocks**: header line; market-state box (4 rows + note); live-setup block (up to 6 rows); signature match (5 rows + 15-row detail table); symbol history (4 rows); candle table (8 cols × N); recent setups table (7 cols) | below |
| 7 | Companies You Can Research (`:531-541`) | `#researchUniverseBox` `:540`, badge `:539` | `GET /api/research-universe` (`research_universe.js:140`) | **12 columns × ≤200 symbols** (`research_cockpit.py:702` `max_symbols=200`) + reliability legend | below |
| 8 | Industry Groups (`:543-550`) | `#researchSectorBox` `:549`, badge `:548` | `GET /api/research-sector` (`research_sector.js:109`) | **10 columns × N sectors** + legend | below |
| 9 | Chart Patterns Found Today (`:552-559`) | `#patternList` `:558`, `#patternStatus` `:557` | `/api/patterns/latest?limit=60`, `/api/patterns/stats`, `/api/templates/latest?limit=12` (`app.js:381,388,430`) | **two lists in one panel**: ≤60 pattern cards (each with a hidden conditions panel) **+ an unlabelled second list "🧬 DTW Shape Matches"** built into a div appended at runtime (`app.js:431-446`) | below |
| 10 | Find Companies By Numbers (`:561-571`) | `#screenerMetrics` `:567`, `#screenerChecks` `:568` | `GET /api/screener/{symbol}` (`app.js:528`) | 9 metric rows + M rule rows + note | below |

**This is the panel-count problem in one line:** 10 panels and ~110 rendered rows/fields, of which
panels 3 and 6 share 4 numbers, panel 6 repeats panel 2's levels, and panels 7 and 8 print the same
scan date twice.

### 1.5 TRADERS — `#view-traders` (`index.html:574`) — **1 panel, huge body**

`#tradersIndex` (`:583`) + `#tradersIntroTotal` (`:582`). Renders one `<details>` per pillar
(`traders.js:434-447`) containing one card per book, each card listing every method row
(`tmMethodRow`, `traders.js:385-401`). Copy says **14 books** (`index.html:579`; confirmed
`trader_league.py:2` and `:172` "our system + the 14 books"). Each method row = name + `?` button +
description paragraph + direction. This is intentionally deep (P2/P8), but it is a single
undifferentiated scroll with no per-book collapse state.

### 1.6 LEAGUE — `#view-league` (`index.html:588`) — **1 panel, ~10 sub-blocks**

`#leagueRoot` (`:596`) composes (`league.js:46-55`): controls (2 segmented switches + Re-simulate);
run line; **Signal Genome `<details>`** with 2 tables × 8 columns; **"Is our system ready for real
money?"** card with up to 14 check rows (`league.js:130-142`); main **10-column × ≤15-row** table;
a **duplicate card view of the same rows** for mobile (`league.js:164-172`); idle-players note;
player drill-down with **14 stat tiles** (`league.js:268-274`) + equity chart + yearly chips +
checklist + **3 group tables** + open positions table + closed trades table; replay `<details>` with
3 inputs, button, log tail and a 5-column coverage table; help `<details>` with 8 definition
paragraphs. This is the densest view in the app but almost all of it is already behind
`<details>` or a click, so it is **not** a cut candidate.

### 1.7 LEDGER — `#view-ledger` (`index.html:601`) — **4 panels**

| # | Panel (header) | Filled by (id) | Route | Rows / fields | Fold |
|---|---|---|---|---|---|
| 1 | How The System Has Done (`:603-606`) | `#ledgerStats` `:605` | `GET /api/ledger/stats` (`app.js:649`) | 7 kv rows (`app.js:655-661`) | **above** |
| 2 | Every Idea We Recorded (`:607-616`) | `#ledgerTable` `:612` | `GET /api/ledger/trades` (`app.js:648`) | **7 columns × ≤100 rows** (`terminal_api.py:1034` `limit: int = 100`) | **above** |
| 3 | Which companies worked, and which did not (`:617-619`) | `#ledgerCompanies` `:617` | **same** `rows` array, passed straight through (`app.js:684`) | **2 tables × 5 columns**, 6 rows each by default (`LEDGER_LIST_CAP = 6`, `app.js:696`) + "Show all N" | below |
| 4 | Rule Testing History (`:620-627`) | `#strategyRunsBox` `:625` | `/api/strategy-runs?n=15` + `/api/strategy-summary` (`strategy_runs.js:9-10`) | **10-column × 15-row table + a second 7-column "Summary by target R" table** (`strategy_runs.js:20-88`) | below |

### 1.8 SYSTEM — `#view-system` (`index.html:630`) — **3 panels**

| # | Panel (header) | Filled by (id) | Route | Rows / fields | Fold |
|---|---|---|---|---|---|
| 1 | Is everything working (`:631-637`) | `#deploymentBox` `:636`, badge `:634` | `GET /api/deployment-check` (`app.js:829`) | **14 check rows** (`terminal_api.py:158-217`: 9 tables + `strategy_runs` + `setup_pool` + 2 "today" checks + `telegram creds`) | **above** |
| 2 | Where the numbers come from (`:638-644`) | `#sourceHealthBox` `:643` | `GET /api/sources` (`app.js:863`) | 1 row per registered adapter, each `state / rate ok / calls/failures` | above |
| 3 | For Developers (`:645-654`) | static | none | 5 external GitHub links | below |

### 1.9 Totals

| view | panels | panels with a subtitle `<p>` | panels with 2-sentence subtitle |
|---|---|---|---|
| funda | 4 | 4 | 2 |
| swing | 4 | 3 | 1 |
| research | **10** | 8 | 1 |
| traders | 1 | 1 | 0 |
| league | 1 | 1 | 0 |
| ledger | 4 | 4 | 0 |
| system | 3 | 3 | 1 |
| **total** | **27** | **24** | **5** |

Plus 3 global blocks (`#marketOverview`, methodology `<details>`, detail dialog) = **30 panel-level boxes**.

---

## 2. Repetition, quantified

### 2.1 "Model event score" / `p_win` renders in **5 places**, across 3 views

| # | Where | Line |
|---|---|---|
| 1 | FUNDA · Today's Shortlist card → `Event 43%` | `app.js:278` |
| 2 | SWING · Short-Term Ideas row → `Event 43%` + tooltip | `app.js:312` |
| 3 | SWING · What Is Moving Today radar card → `Event 43%` | `app.js:598` |
| 4 | RESEARCH · Pattern-and-Risk → "Model Event Score" row + target chip + `?` | `app.js:1485-1487` |
| 5 | RESEARCH · Compare Companies → "Model event score" row | `cards.js:184-185` |

Plus a **6th presentation**: `ideals.js:45` matches the label `p_win` and injects an extra
"ideal …" chip beside whatever it decorates (`ideals.js:105-110`), so one number can carry a value,
a tooltip, a `?` button, a target chip and an ideal chip simultaneously.

### 2.2 Uncalibrated-score disclaimer: **7 copies**; advice/forecast disclaimers: **8 more** = 15

Uncalibrated-score sentence:
1. `index.html:405` — `data-tip` on Today's Shortlist
2. `index.html:425` — `data-tip` on Short-Term Ideas
3. **`index.html:448` — always-visible prose in a panel subtitle** ("Model scores describe an uncalibrated +10% high / 20-session event, not trade win odds.")
4. `index.html:511` — `data-tip` on Compare Companies
5. `index.html:667-669` — methodology paragraph
6. `app.js:17` — `window.MODEL_EVENT_SCORE_HELP`, injected as a `title` at `app.js:312`, `:598`, `:1485`
7. `cards.js:183` — a second hard-coded copy of the same sentence as a fallback

Advice/forecast family:
`index.html:286` ("Research only · no orders are placed") · `index.html:496` · `index.html:502` ·
`index.html:665-666` (methodology) · `app.js:574` ("Screening result only; not a forecast or trade
instruction.") · `research.js:154` · `traders.js:321` · `traders.js:327` · `traders.js:366`.
That is 9 more; 15 total across 9 files.

### 2.3 The research view prints two different dates, **four of them literally identical**

| # | Where | Value source |
|---|---|---|
| 1 | `#researchUniverseBadge` (`research_universe.js:154-155`) | `data.date` |
| 2 | `#researchSectorBadge` (`research_sector.js:120-121`) | `data.date` |
| 3 | `#patternStatus` (`app.js:390-392`) | `rows[0].date` (patterns table) |
| 4 | `#stockPulse` "Latest stored close ⟨date⟩" (`app.js:1582`) + collapsed "Source bar date" | newest candle |
| 5 | `#researchBox` header "as of ⟨date⟩" (`research.js:138`) | `data.as_of` |
| 6 | `#researchBox` "Latest market state · ⟨date⟩" (`research.js:149`) | `state.as_of \|\| data.as_of` |

**Verified identical, not merely similar:** #1 and #2 come from the *same* helper — both
`analyze_universe` and `sector_aggregate` return `{**status}` where `status["date"] = max(swing scan
date, trend scan date)` (`research_cockpit.py:686-688`, `:705`+`:737`, `:743`). #5 and #6 are the same
`as_of` / `state.as_of` pair from one payload (`research_cockpit.py:596`, `:612`).

### 2.4 "Status" appears as a row label **6 times**

- `index.html:539`, `:548`, `:557` — three static rows, all rendered by one helper that hard-codes the literal word `Status` at `app.js:51` (called at `app.js:390` and from both research modules). Each also restates its own count.
- `app.js:1406` — stockPulse "Status" when no setup
- `app.js:1701`, `app.js:1705` — Delivery "Status" no-data / endpoint-unavailable
- `index.html:284` — sidebar footer "Service status"

### 2.5 Same label, **two different numbers**, one click apart — "win rate"

The "Graded win rate" tile (`index.html:357`) is set at `app.js:307` from `GET /api/swing/signals`
`win_rate`, computed as `100 · WIN / (WIN + LOSS)` (`terminal_api.py:697-700`).
Its click target is `data-view="ledger"` (`index.html:355`). The ledger panel's "Win Rate"
(`app.js:657`) comes from `GET /api/ledger/stats` → `ledger.compute_stats()`
(`terminal_api.py:1027-1030`), computed as `100 · wins / total` where **`total` includes TIMEOUT
rows at 0 R** and rows with missing/≤0 stop geometry are dropped first (`ledger.py:13-49`).

So `swing_win_rate ≥ ledger_win_rate` on the same table, and the tile hands you a different number
than the panel it navigates to. The same split affects "Open / pending" (tile, `app.js:308`, from the
`/api/swing/signals` scorecard) vs "Ideas Recorded / Wins / Losses" (`app.js:655-656`, from
`/api/ledger/stats`). This is the one finding here that is a **correctness** bug, not just pixels.

### 2.6 The "Companies you can research" tile measures something else than the panel it scrolls to

- Tile label: "Companies you can research / Names with enough history to analyse" (`index.html:369`).
- Its value: `app.js:590` `data.total` ← `GET /api/radar` ← `len(rows)` of **`universe_broad`** (`terminal_api.py:751-753`, `:783`).
- Its click target (`index.html:365-368`, `data-scroll-target="researchUniverseBox"`, `data-load="research-universe"`) loads `/api/research-universe`, which lists **only symbols that have a stored swing or trend scan setup** (`research_cockpit.py:663-680`, `:705-707`), capped at 200 (`research_cockpit.py:702`).

Two different populations under one phrase, and neither is the "enough history" count the caption promises.

### 2.7 The same panel exists in two views with byte-identical subtitles

FUNDA panel 1 (`index.html:377-386`) and SWING panel 1 (`index.html:412-421`) are
the **same renderer** (`loadStrategyListFor(kind)`, `strategies.js:3-29`), the **same endpoint**
(`/api/strategies`, `strategies.js:9`), differing only by `type === kind` (`strategies.js:13`), and
their visible subtitles are identical strings at `index.html:381` and `index.html:416`
("Owner-authored rules. Edit or Run directly here."). One of the two views does not need it.

### 2.8 The ledger renders **three tables over one payload**

`loadLedger` fetches `rows` once and passes the same array to both `ledgerTable`
(`app.js:664-684`) and `_renderLedgerCompanies` (`app.js:684` → `:786-820`). Company / Date /
Outcome / Profit-loss appear in all three tables (`app.js:676-679` vs `app.js:737-741`); the two
company columns add only the word gloss (`_outcomeWords`, `app.js:706-715`) and filter to
WIN-only and LOSS+TIMEOUT-only.

### 2.9 The research view renders the same market state and the same levels twice

| Numbers | First site | Second site |
|---|---|---|
| close, 1-session change, 20-session change, 60-session change, EMA trend context | `#stockPulse` (`app.js:1582-1588`) | "Latest market state": Close/daily, "20 / 60 session move", "Trend context" (`research.js:150-152`) |
| trigger, stop, target | `#setupSummary` (`app.js:1386-1388`) | "LIVE SETUP TODAY entry / stop / 3R" + Risk % (`research.js:159-163`) |

4 of 5 numbers in the first pair and 3 of 3 in the second are duplicates **within one view**.

### 2.10 Compare Companies: 20 rows, several overlapping

`cards.js:158-224`. Two rows restate figures shown elsewhere in the same view (`Model event score`
`:184`, `Swing W-L` `:186-188`), and the HISTORY and SIGNATURE MATCH sections both publish a "P(+2R)"
style estimate (`:206-208` vs `:220-221`) from different methods with no on-screen distinction beyond
the section heading.

### 2.11 The pattern panel silently contains a second, unlabelled list

`loadPatterns` renders `#patternList`, then appends a **new sibling div** into the same panel
(`app.js:430-446`) headed "🧬 DTW Shape Matches" fed by a *different* endpoint
(`/api/templates/latest?limit=12`, `app.js:430`). The panel header (`index.html:554`) says only
"Chart Patterns Found Today · HTF · Asc Triangle · Double Bottom · Inv H&S · H&S Top warning",
so 12 rows of a different data source have no panel header of their own.

---

## 3. Dead or write-only weight

### 3.1 Safe to delete now (direct evidence)

| # | Item | Evidence |
|---|---|---|
| 1 | **`<span id="screenerBadge">`** (`index.html:568`) | Repo-wide search across all non-vendor `.js` / `.html` / `.css` / `.py` returns **only** `index.html:568`. Nothing assigns its text, and it is destroyed on the first screener run by `checks.replaceChildren()` (`app.js:558`). It renders a stray "—" badge until then. |
| 2 | **`terminal/static/deployment.js`** (whole file, 38 lines) | `index.html:693-706` loads 13 scripts and does **not** include it; `terminal_api.py` never references it. It re-declares `loadDeployment` (`deployment.js:4`) already defined at `app.js:829`, and its `DOMContentLoaded` block adds a **second** `click` listener to `#refreshBtn` (`deployment.js:36-38`) — if the tag is ever added, one click fires both `refreshAll` (bound at `app.js:1802-1803`) and `loadDeployment`. |
| 3 | **`/api/radar` → `events`** | Built on every call including a DB query (`terminal_api.py:768-776`, returned at `:783`). No frontend file reads `.events` — the only grep hit is a comment at `league.js:349`. |
| 4 | **Radar card subtitle read** | `app.js:596` reads `x.sector`, but `/api/radar` items never contain a `sector` key (`terminal_api.py:757-759`) → `subtitle` is always `""` and `renderUnifiedCard` skips the element (`cards.js:78`). |
| 5 | **6 fetched-but-never-rendered universe fields** | `/api/research-universe` returns `p_4r`, `p95_mfe_r`, `p5_mae_r`, `latest_close`, `pct_from_52w_low`, `current_setup` per symbol (`research_cockpit.py:719-733`); `_COLUMNS` renders none of them (`research_universe.js:9-22`) and no other reference exists in the renderer. Up to 200 symbols × 6 fields per call. |
| 6 | **Unused id `#methodologyBlock`** | `index.html:656`. The id is referenced nowhere (same repo-wide search), but the `<details>` itself is functional static markup — **drop the id, keep the block**. |
| 7 | **12–14 frontend-uncalled routes** | No caller in any non-vendor JS for: `/api/ideals/{key}` (`:94`), `/api/traders/{slug}` (`:265`), `/api/traders/{slug}/scan` (`:275`), `/api/strategies/run-all` (`:480`), `/api/strategies/backtest-cache/clear` (`:489`), `/api/research-cache/clear` (`:580`), `/api/patterns/{symbol}` (`:641`), `/api/pwin/refresh` (`:662`), `/api/trend/scan` (`:795`), `/api/delivery/top` (`:819`), `/api/delivery/accum` (`:825`), `/api/model/runs` (`:1021`), `/api/validate/latest` (`:1039`), `/api/screener/scan` (`:1082`). That is **14 of 67 routes**. Some are legitimately CLI/scheduler-facing — see §3.2. |
| 8 | **Duplicate global function names** | `_safeId` in `app.js` and `strategies.js` (identical bodies); `_num` in `research.js:16-19` and `research_universe.js:37-40` (near-identical; `research_universe.js` loads later via `index.html:700-701` and silently wins for `research.js`'s own calls); `loadDeployment` (`app.js:829` vs `deployment.js:4`). Latent hazard, equivalent behaviour today. |

### 3.2 Needs owner decision (not obviously dead)

| # | Item | Question |
|---|---|---|
| 1 | `#refreshTraderMatches` (`index.html:503`) | The check already runs automatically on **every** symbol load (`app.js:1363`, `:1374`), so the button only re-runs the same call. Making it worse: `loadTraderMatches` replaces the button's entire contents (`btn.textContent = "Check books"`, `traders.js:638`, `:646`), which deletes the `data-icon="search"` SVG permanently — `icons.js` will not restore it because it skips elements already flagged `data-iconDone` (`icons.js:16`, `:28`). Its label also changes from "Check methods" (`index.html:503`) to "Check books" (`traders.js:646`). Delete the button, or keep it and fix the icon+label. |
| 2 | `terminal/static/wisdom.html` | 571 lines / 28 KB, **no route serves it** (`/glossary` returns `glossary_ui.render()`, `terminal_api.py:106-110`). Delete, or route it. |
| 3 | 14 uncalled routes (§3.1 #7) | Are they part of the API surface for CLI/cron (`scheduler_bg.py`, `verify_deployment.py`) or genuinely abandoned? Only the owner can say. Do not delete blindly. |
| 4 | 4 legacy stylesheets | `index.html:222-226` loads `style.css` (916 L) + `polish.css` (316 L) + `explain.css` (109 L) + `fintech.css` (1216 L) + `tailwind.css`. `PORTAL_REDESIGN.md:207-211` describes `fintech.css` as the new layer over "the existing sheets", so this is deliberate during migration — but it is 5 sheets and ~2550 CSS lines for one page. Needs a consolidation decision, not a blind cut. |
| 5 | `tailwind.css` | 2 lines / 3.3 KB built from a 47-line `tailwind.src.css`. Currently needed only for `flex flex-wrap items-center gap-2` on `#chartLegend` (`index.html:483`). Decide: keep the build, or replace that one class and drop the toolchain. |

---

## 4. Disproportionate weight (against the owner's P7)

`PORTAL_REDESIGN.md:174` — **P7: "No panel shows a number the owner can't act on."**
`.github/skills/nse-terminal-ux/SKILL.md:32-34` — disclaimers must be "proportionate and near the
relevant decision"; `SKILL.md:20-22` — staleness/failure must stay visible.

| Finding | Count | Detail |
|---|---|---|
| Panels with a prose subtitle | 24 of 27 | Of these, **5** carry a visibly two-sentence subtitle (`index.html:381`, `:416`, `:398`, `:448`, `:545`). The rest are one-liners. |
| Panels whose subtitle hides a long disclaimer in `data-tip` | 9 | `index.html:405`, `:425`, `:496`, `:502`, `:511`, `:533`, `:579`, `:592`, `:633` — invisible normally, but each duplicates prose that already exists in the methodology block (`index.html:659-680`) and in `explain.py`. |
| Always-visible disclaimer prose in a *panel subtitle* | 1 | `index.html:448`. This is the only one that costs real vertical space; the project's own changelog (`PORTAL_REDESIGN.md:224-226`) says verbose disclaimers were already moved into tooltips, so this one is a leftover. |
| Deployment check rows that are counts, not verdicts | 14 rows, ≥8 non-actionable | `terminal_api.py:179-180` renders `"latest 2026-09-30 (7d), 12,345 rows"` per table, plus `setup_pool` ("N setups", `:191-192`) and `swing signals today` / `trend candidates today` (`:196-205`) which are always reported as **pass** (`add(True, …)`). The pass/fail is actionable; the row counts are not. |
| Universe table column that is an internal code | 1 of 12 | `Src` (`research_universe.js:11`) prints the raw source tag from `research_cockpit.py:669-677` — `SWING` or `TREND`. |
| Compare table rows that are derivation, not decision | 5 of 20 | `Best candle (n)` (`cards.js:213-216`), `k / pool size` (`:222-224`), and the two overlapping P(+2R) estimates (`:206-208`, `:220-221`), plus `Fund score` (`:177-178`) with no band shown. |
| Radar rows computed then discarded | 66 of 198 | Server caps 40/group (`terminal_api.py:767`), client renders 18/group (`app.js:595`) → 22 discarded per group. |
| Swing table rows | capped at 80 silently | `terminal_api.py:670` `limit: int = 80`; the table (`index.html:423-437`) has no total or "of N" marker, while the tile (`index.html:352`) labels the same figure "Signals listed". |
| Research universe rows | capped at 200 silently | `research_cockpit.py:702` `max_symbols=200`; the badge (`research_universe.js:154-155`) reports the *returned* count as if complete. |

---

## 5. Classified findings — Item | Where | Problem | Recommendation | Rough visual saving

| # | Item | Where | Problem | Recommendation | Rough saving |
|---|---|---|---|---|---|
| 1 | "This Company at a Glance" market-state block | `index.html:494-498`; `app.js:1582-1588` | 4 of its 5 numbers (close, 1d, 20d, 60d change, EMA trend) are re-printed by "One Company, In Detail" | **MERGE INTO** `#researchBox`'s "Latest market state" (`research.js:150-152`); keep one copy in the research view | −1 panel, −5 rows |
| 2 | `#researchBox` "Latest market state" | `research.js:148-155` | Duplicates #1 | **KEEP** as the survivor; add the volume row so nothing is lost | — |
| 3 | Setup levels | `app.js:1386-1388` vs `research.js:159-163` | trigger/stop/target rendered twice in one view | **MERGE INTO** `#setupSummary` (it already draws the 3 price lines on the chart at `app.js:1381-1383`); reduce the research block to risk %, pullback, impulse, zone, shape | −3 rows |
| 4 | Ledger "Which companies worked, and which did not" | `index.html:617-619`; `app.js:786-820` | 3 tables over 1 payload; adds only a word gloss | **COLLAPSE BEHIND DETAILS** — put the win/loss filter as two toggle chips above `#ledgerTable`, or move the two columns into a `<details>` | −1 panel, −2 tables, −10 columns |
| 5 | "Graded win rate" tile | `index.html:357`; `app.js:307` | Different number from the ledger "Win Rate" (`app.js:657`) under the same words; different endpoints/denominators | **MERGE INTO** a single source (`/api/ledger/stats`) for both, or rename the tile to what it actually measures. Correctness first | — (bug fix) |
| 6 | "Companies you can research" tile | `index.html:369`; `app.js:590` | Value is `universe_broad` row count; click target shows scan-setup symbols | **MERGE** — fill the tile from `/api/research-universe` so tile and panel agree, or relabel it "Broad universe rows" | — (bug fix) |
| 7 | Strategy panel duplicated in FUNDA and SWING | `index.html:377-386` vs `:412-421` | Same renderer, same route, same subtitle string (`:381`/`:416`) | **MERGE INTO** FUNDA (owner-authored long-term rules) and put a one-line "Run a saved rule" link in SWING | −1 panel |
| 8 | Uncalibrated-score disclaimer, 7 copies | `index.html:405,425,448,511,667-669`; `app.js:17`; `cards.js:183` | Repeated 7×, one copy always visible (`:448`) | **COLLAPSE BEHIND DETAILS** — keep the methodology paragraph (`:667-669`) + the per-number `?`; delete the 5 `data-tip`/subtitle copies and `cards.js:183`'s fallback | −15 repeated sentences |
| 9 | Advice/forecast disclaimers, 8 copies | `index.html:286,496,502,665-666`; `app.js:574`; `research.js:154`; `traders.js:321,327,366` | Same prohibition stated 8× | **KEEP** exactly 2 (sidebar footer `:286` as the persistent statement + methodology `:665-666`); **DELETE** the rest — they are not state indicators | −6 sentences |
| 10 | Scan date ×2, bar date ×2 | `research_universe.js:154-155`, `research_sector.js:120-121`, `research.js:138`, `research.js:149` | Same values printed twice each (verified identical sources) | **MERGE** — one scan-date chip and one bar-date chip in the view header (`#viewSubtitle`) | −4 date restatements |
| 11 | Three "Status" rows | `index.html:539,548,557` | The literal word "Status" ×3 with pulsing dots, each restating count+date | **KEEP** (they are the staleness/state indicators `SKILL.md:20-22` requires) but **relabel** from "Status" to what is being checked ("Universe freshness", "Sector freshness", "Pattern freshness") | 0 (relabel) |
| 12 | DTW Shape Matches list inside the patterns panel | `app.js:430-446` | 12 rows from a different endpoint with no header of its own | **HIDE BY DEFAULT** behind a `<details>` inside the patterns panel, labelled "Shape matches (DTW)" | 12 rows moved |
| 13 | Pattern panel default volume | `app.js:381` `limit=60` | Up to 60 cards, each a multi-line card with a hidden conditions panel | **HIDE BY DEFAULT** — show top 10 by confidence + "Show all 60" | −50 cards |
| 14 | Radar "What Is Moving Today" | `index.html:447-465`; `app.js:595` | 3 × 18 = 54 cards in one panel; 66 rows computed then discarded | **KEEP** (it is the swing view's discovery surface) but consider 3 × 10 and a "more" control | −24 cards |
| 15 | `#screenerBadge` | `index.html:568` | Dead markup, no writer, destroyed on first run | **DELETE** | −1 element |
| 16 | `terminal/static/deployment.js` | whole file | Orphaned duplicate of `loadDeployment`; adds a second `#refreshBtn` listener if ever loaded | **DELETE** the file | −38 lines, −1 duplicate fn |
| 17 | `/api/radar` `events` | `terminal_api.py:768-776,783` | Built + queried, never read | **DELETE** the key (or render it) | −1 query/call |
| 18 | `x.sector` in radar cards | `app.js:596` | Field never present in the payload (`terminal_api.py:757-759`) | **DELETE** the read, or add `sector` to the payload | — |
| 19 | 6 universe fields | `research_cockpit.py:719-733` | Fetched for ≤200 symbols, never rendered | **DELETE** from the payload, or add as hidden columns | −6 fields × ≤200 |
| 20 | `#refreshTraderMatches` | `index.html:503`; `traders.js:638,646` | Redundant re-run; `textContent` deletes its own icon permanently (`icons.js:16,28`); label changes mid-use | **HIDE BY DEFAULT** (or delete) — the check is already automatic | −1 control |
| 21 | Deployment row counts | `app.js:829`; `terminal_api.py:179-180,191-192,196-205` | 14 rows, ≥8 non-actionable counts; 2 rows always pass | **HIDE BY DEFAULT** — show failures + last-checked time; reveal all 14 behind "Show all checks" | −10 rows |
| 22 | Compare table | `cards.js:158-224` | 20 rows; 2 duplicate other panels, 5 are derivation | **COLLAPSE BEHIND DETAILS** per section (Overview / Fundamentals / Signal / History / Signature) closed by default except Overview+Signal | −10 rows |
| 23 | `Src` column | `research_universe.js:11` | Internal tag (`SWING`/`TREND`) | **DELETE** from the visible columns (keep in the row detail) | −1 column |
| 24 | Universe 200-cap / swing 80-cap not disclosed | `research_cockpit.py:702`; `terminal_api.py:670` | Silent truncation looks like completeness | **KEEP** the caps, add "of N" to the badges/tile | — (honesty fix) |
| 25 | `#methodologyBlock` id | `index.html:656` | Unused id | **KEEP** the block, **DELETE** the id | 0 |
| 26 | `terminal/static/wisdom.html` | 571 lines, no route | Orphaned artifact | **HIDE BY DEFAULT / DELETE** — owner decision: route it or remove it | −571 lines |
| 27 | 14 uncalled API routes | `terminal_api.py` §3.1 #7 | Dead weight on the portal surface | **NEEDS OWNER DECISION** — CLI/cron may depend on them | −14 routes (if truly dead) |
| 28 | Duplicate globals `_num`, `_safeId` | `research.js:16`, `research_universe.js:37`, `app.js`, `strategies.js` | Last-loaded file silently wins | **MERGE INTO** one shared helper | −2 duplicate defs |
| 29 | 5 stylesheets | `index.html:222-226` | ~2550 CSS lines, migration-in-progress | **NEEDS OWNER DECISION** — consolidation plan, not a cut | — |

---

## 6. What I would NOT touch (and why)

| Keep | Why |
|---|---|
| The **6-item chart legend + RSI pane + crosshair readout** | Colour/licence-per-series and the readout are the primary evidence surface; `PORTAL_REDESIGN.md:175` P2 and the EMA-10 toggle (`app.js:1128-1189`) are exactly the progressive-disclosure pattern the owner asked for. |
| The **three "Status" rows** and every pass/fail icon | `SKILL.md:20-22` explicitly requires missing/stale/failed data to stay visible. Relabel them; do not hide them. |
| **Reliability pills** (`rel-strong/mod/thin/none`, `index.html:13-17`; legends at `research_universe.js:109-115`, `research_sector.js:93-99`) | P3 colour-encodes-meaning + P6 visible sample size. This is the best-built thing in the app. |
| The **methodology `<details>`** (`index.html:656-680`) and `explain.py` / `/api/explain` | It is the *single* home for prose. Every disclaimer cut in §5 should land here, not vanish. |
| The **paper-league view** (`index.html:588-597`) | Densest view, but ~all content is already behind `<details>` or a click — measured clutter is low even though raw content is high. |
| The **traders library** (`index.html:574-585`) | P5 (rule in human language) + P8. The only cost is scroll length; collapse state per book is a nice-to-have, not clutter. |
| The **unified stock card** (`cards.js:63-102`) | P2 — one component everywhere, 4-value cap built in (`cards.js:60`). Do not fork it. |
| The **`(?)` explain affordances** (`explainer.js`) | One delegated listener for every term; cheapest possible progressive disclosure. |
| The **`data-tip` mechanism itself** | Hidden by default; the problem is the duplicated *wording*, not the mechanism. |

---

## 7. Could not verify / limits of this audit

- **Pixel "fold" positions are an estimate from DOM order and panel count, not a measurement.**
  No terminal server was running (`/api/health` unreachable on 8000/8080/5000/8001) and I did not
  start one, so no headless-browser measurement was possible. `tools/ui-audit/` exists
  (`tools/ui-audit/audit.mjs`, per `PORTAL_REDESIGN.md:227-229`) if the owner wants real numbers.
- **Row counts are derived from code caps, not from live data.** `/api/toppicks` → 15
  (`terminal_api.py:659`); patterns ≤60 (`app.js:381`); templates ≤12 (`app.js:430`); trend ≤30
  (`scanners.js:8`); positional ≤30 (`scanners.js:36`); value-radar ≤25 (`scanners.js:67`);
  radar ≤18×3 (`app.js:595`); ledger trades ≤100 (`terminal_api.py:1034`); strategy runs 15
  (`strategy_runs.js:9`); universe ≤200 (`research_cockpit.py:702`); swing ≤80 (`terminal_api.py:670`).
- **Actual on-disk clutter figures I did not open:** `explain.css`, `polish.css`, `style.css` and
  `fintech.css` selector-level dead code. I only checked that `style.css:775` drives the
  `is-collapsed` behaviour and `fintech.css:1030-1031` hides the mobile chart note. A CSS-level
  orphan-selector audit is unstarted work.
- **`app.js` was still being edited at the end of this audit** (1883 lines, hash `693D8C17F7`).
  Two findings (EMA-10 legend, chart legend naming) were fixed mid-audit and removed. Re-grep the
  anchors before acting on any `app.js` line.
