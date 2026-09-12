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

### Idea 5 — Data source plugin system
Each source implements the same interface (`fetch`, `health`,
`rate_limit_ok`). Registry auto-discovers. Fallback chain automatic.
System page shows green/yellow/red per source.

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
- Migrate TradingView + Yahoo + NSE
- Add Chartink + ScanX
- Health dashboard
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

- Exact rule grammar for RCP and Episodic Pivot — design session needed.
- Multibagger selection: growth-tilted, quality-tilted, or blend?
- Should Funda and Swing run on different universes, or same?
- Which data source becomes primary after plugin migration?
- Should signature matching use cosine similarity or L1 distance?
- Do we keep the legacy Streamlit app as backup, or retire it fully?

---

## 7. CHANGE LOG

- 2026-09-12 — vision captured. Roadmap defined. R25 added to backlog.