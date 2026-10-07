# PORTAL REDESIGN — Vision, Roadmap, Principles

Created: 2026-09-12
Owner vision — Ankit. This document captures the shape the portal must
take. Every future build decision references this file.

---

## 1. THE MACHINE'S PURPOSE (owner's words, restated)

The system exists to do four things, in order of priority:

1. **Identify** stocks with uptrending potential and good expected returns.
2. **Serve two distinct product lines:**
   - **Funda (positional)** — for market downtrends, when quality becomes
     cheap. Hold months to years.
   - **Swing (midcap + smallcap)** — for market uptrends. Trade days to
     weeks. Never against the tide.
3. **Accept custom scanners** for each product line. Owner defines the
   conditions; the machine executes.
4. **Ingest data** from free external sources (TradingView, Chartink,
   ScanX, Yahoo, NSE archives) with fallback chains.

Secondary capabilities:
- Historical trend tracking and behaviour analysis.
- Candle-pattern identification (HTF, H&S, Ascending Triangle, etc.)
  with all conditions evaluated distinctly and closely.
- Pattern tags attached to current scan data.

---

## 2. THE TWO-PILLAR MODEL

The portal is divided into two pillars:

### FUNDA — long-term / positional
Strategies:
- **Multibagger** (to be designed with owner)
- **Value Radar** (already shipped)
- **Positional Picks** (already shipped)

Purpose: find quality names when the market is weak. Accumulate.

### SWING — midcap/smallcap momentum
Strategies:
- **RCP** (to be designed)
- **Episodic Pivot** (to be designed)
- **All-Weather** (already shipped — defensive-regime reversals)
- **Trend Scanner** (already shipped — EMA50/EMA200 confirmed trend)

Purpose: find short-horizon momentum setups when the market is rising.
Never fight the tide.

### Supporting sections
- **RESEARCH** — analysis & pattern lab (Cockpit, Universe, Sectors)
- **LEDGER** — track record (Swing performance, Strategy runs, Deploy)
- **SYSTEM** — config, data-source health, logs, rules editor

---

## 3. THE 10 INNOVATIVE IDEAS

### Idea 1 — Rule DSL (strategy engine)
Strategies become JSON rules stored in DB and edited in a UI. New
strategy = new row, zero code changes. Example:

    {
      "name": "Multibagger",
      "type": "fundamental",
      "universe": "nifty500",
      "conditions": [
        {"field": "roce", "op": ">=", "value": 20},
        {"field": "profit_growth_3y", "op": ">=", "value": 20}
      ],
      "score_weights": {"roce": 0.4, "profit_growth_3y": 0.6}
    }

### Idea 2 — Signature matching
Every historical setup gets a numeric signature (mother bar geometry,
context features, regime, sector). When a live setup appears, find the
N closest historical setups across ALL symbols — not just this symbol.
Show pooled stats for those.

### Idea 3 — Pattern transparency
Patterns return per-condition pass/fail, not just an aggregate score.
UI shows the checklist. Owner sees exactly which conditions edge cases
fail on.

### Idea 4 — Time-machine chart overlay
Every chart has markers at historical pattern signals, coloured by
outcome (green=WIN, red=LOSS, yellow=TIMEOUT/EXPIRED). Click any marker
to open that historical setup. Visual intuition over years.

### Idea 5 — Data source plugin system · IN PROGRESS (2026-09-26)
Each source implements `fetch`, `health`, and `rate_limit_ok`.
The registry auto-discovers adapters and applies explicit provider order
and result acceptance rules. `/api/sources` and the System page expose
state, local rate-limit availability, call/failure counts, and the last
error. Initial adapters route TradingView fundamentals, Yahoo daily
prices, NSE constituent fallbacks, and Chartink URL inputs. Remaining
direct Yahoo consumers and official dated-filing ingestion are not yet
migrated. ScanX stays a local research import, not an online fallback.

### Idea 6 — Unified stock card
Same card component everywhere (scanner, research, watchlist,
drill-down). One layout the eye learns once.

### Idea 7 — Backtest sandbox per strategy
Each strategy page has "Run on history". Change a rule → see new
backtest result in-browser. No VM, no git, no code.

### Idea 8 — Progressive disclosure everywhere
Default view = the answer. Click reveals derivation.
- Sizing shows "₹40,000 (4%)" — click reveals Kelly, regime, quality
- P(WIN) shows "49%" — click reveals SHAP features
- Pattern tag shows "HTF ✓" — click reveals checklist

### Idea 9 — Compare mode
Multi-select 2-4 stocks, side-by-side table aligned on metrics.

### Idea 10 — Strategy library page
List all strategies (existing + user-added), with rule preview,
today's pick count, 2-year backtest PF, DD, and enable/disable toggle.

---

## 4. FOUR-PHASE ROADMAP

Each phase is independently useful. No phase blocks a later one.

### Phase 1 — Portal redesign + noise reduction
- New nav: Funda / Swing / Research / Ledger / System
- Move existing panels to their right home
- Collapse advanced numbers behind "Show details" toggles
- Remove the noise (Kelly intermediates, SHAP defaults, delivery counts)
- **Deliverable:** a portal that is fast to use before new features land.

### Phase 2 — Rule engine + first strategies
- `rule_engine.py` — reads JSON, applies to universe, returns ranked
- `strategies` table — stores all strategy definitions
- Seed with **Multibagger**, **RCP**, **Episodic Pivot** — designed with owner
- Strategy pages under Funda and Swing tabs
- **Deliverable:** custom scanners that run from config, not code.

### Phase 3 — Research upgrades
- Signature matching across symbols (Idea 2)
- Pattern condition logging (Idea 3)
- Time-machine chart markers (Idea 4)
- **Deliverable:** research view that is predictive, not descriptive.

### Phase 4 — Data source plugins
- `data_sources/` with standard interface
- Registry, health and rate-limit reporting, explicit fallback order,
  first TradingView/Yahoo/NSE/Chartink adapters and System-page display
  are implemented; continue migration across remaining consumers.
- Official NSE/BSE filings are the selected authority for point-in-time
  fundamentals. Add this ingestion path only with financial period,
  public filing timestamp, source provenance and symbol/ISIN mapping.
- Keep ScanX as a research-only local import; do not let undated exports
  become live fundamentals or historical replay data.
- **Deliverable:** resilience — one source failing doesn't break the
  pipeline.

---

## 5. DESIGN PRINCIPLES (in force for every phase)

- **P1** Default to answer, hide derivation behind a click.
- **P2** One card component used everywhere.
- **P3** Colour encodes meaning (green/amber/red reliability).
- **P4** Every table is sortable and self-explanatory.
- **P5** Every scanner reports its rule in human language.
- **P6** Every historical claim is backed by visible sample size.
- **P7** No panel shows a number the owner can't act on.
- **P8** Progressive disclosure: simple by default, deep on demand.
- **P9** The portal never recommends. It presents.
- **P10** If a section is unused after a week, remove it.

---

## 6. OPEN QUESTIONS (to resolve as we build)

- RCP and Episodic Pivot already have concrete seed conditions in
  `rule_engine.py`; further changes are not currently requested.
- Multibagger is quality-led with multi-year growth confirmation
  (owner decision, 2026-09-26); the current scanner remains quality-only
  until dated growth data is available.
- Funda and Swing use separate universes (owner decision, 2026-09-26):
  broad quality-eligible Funda and liquid mid/small-cap Swing. Exact
  eligibility thresholds and membership still need definition.
- Official NSE/BSE filings are the authority for dated fundamentals;
  the full adapter framework is approved and in progress (owner
  decision, 2026-09-26).
- Signature matching already uses standardized L1 distance.
- Do we keep the legacy Streamlit app as backup, or retire it fully?

## 7. CHANGE LOG

- 2026-09-12 — vision captured. Roadmap defined. R25 added to backlog.
- 2026-09-26 — Terminal interaction pass deployed: symbol/view history,
  stock-to-research navigation, data detail dialogs, and keyboard-accessible
  research, sector, strategy, trader, and League rows. See EXECUTION_LOG #089.
- 2026-09-26 — Owner decisions recorded and initial source adapter
  framework added; see EXECUTION_LOG #091. Official dated filings and
  remaining provider migrations are still outstanding.

- 2026-10-07 — **Frontend overhaul: dark fintech design system.** New
  `terminal/static/fintech.css` design layer (zinc canvas `#090d16`, hairline
  glass surfaces, mono tabular figures, one accent per state) over the existing
  sheets, plus a real Tailwind v4 build (`tailwind.src.css` to `tailwind.css`,
  `npm run build:css`) with preflight excluded so the legacy cascade survives.
  `clsx` + `tailwind-merge` (via `vendor/cn.js`) and 15 Lucide icons
  (`vendor/lucide.js`, hydrated from `data-icon`) are vendored locally - no CDN.
  Fixed: the Model Event Score row no longer squashes into one-letter columns or
  wraps "43%" (flex `min-w-0` + `nowrap` + tabular figures); the header no
  longer stretches the search field to 130px; the sidebar becomes an off-canvas
  sheet under 950px with a hamburger, scrim, and Escape-close, plus a compact
  pill rail in the header. Chart pattern annotations now default to hidden below
  768px behind a `Show Patterns (N)` pill, and a four-item legend names Price /
  EMA 20 / 50 / 200. Read-only data is no longer boxed like a disabled input:
  metric rows are hairline key/value rows, and the Model Event Score row now
  renders even when no model score is stored (it says "no score stored" rather
  than vanishing), so the card layout requirement is observable on every symbol.
  Verbose disclaimers moved into
  `data-tip` tooltips and a collapsible **Methodology & Disclaimers** block, and
  regime / smart-money alerts became pulse-dot pill banners. Verified with
  `tools/ui-audit/audit.mjs` (headless Chrome over CDP): zero page-level
  horizontal overflow and zero text-outside-box at 375, 390, 768, and 1440 px
  across research, funda, swing, ledger, system, traders, and league.

- 2026-10-07 (pass 2) — **Charts, knowledge popups, clutter trim, and the login
  gate removed.** Chart: the price pane now carries EMA 20/50/200 by default with
  EMA 10 available behind a toggle (ships off), and a real RSI-14 pane sits
  beneath it with the 30/70 band shaded on its own 0-100 scale, sharing one time
  axis so pan and zoom stay in sync (`lightweight-charts` 4.1.3 has no pane API,
  so the pane is a second synced chart instance with equalized price-scale
  widths). Knowledge popups: the fixed 4W1H dump is replaced by a decision-first
  card - one headline plus "What it is / How to use it / How to spot it / Do this
  next" and an optional "Careful" - with a 5-tier fallback so no click is ever an
  empty shell and the 16 ideal-chip keys that had no entry now compose a real card
  from data already on screen. Clutter: deleted the orphaned `deployment.js`;
  see `.agents/clutter-audit.md` for the classified trim plan (research view's
  10 panels include 6 that restate data already on screen; 15 duplicated
  disclaimer sentences; 21 nav affordances for 8 destinations). Auth: the HTTP
  Basic login gate is removed entirely - every route answers without credentials
  - and the owner's `ankitc21` / `change_this_password` strings are gone from
  every tracked file. Verified: 30/30 viewport-route combinations clean at
  375/390/768/1440, all 9 `test_*.py` pass, zero credential hits repo-wide.