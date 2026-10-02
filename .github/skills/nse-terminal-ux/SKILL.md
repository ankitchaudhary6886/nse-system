---
name: nse-terminal-ux
description: Design and improve the NSE terminal UI so market data, research, rules, and system status are minimal, accessible, visual, and explainable.
---

# NSE Terminal UX

Use this skill when changing the FastAPI terminal, its navigation, dashboards,
tables, charts, strategy explanations, data-source status, or responsive
behavior.

## Product principles

- Optimize for a clear decision-support workflow, not the number of visible
  widgets. Put the next useful action and the most important context first;
  progressively disclose secondary data.
- Make each metric explainable: show its label, unit, observation date/source
  where relevant, and a short definition or calculation on demand. Distinguish
  observed data, derived measures, model estimates, and research hypotheses.
- Keep evidence and status visible. Missing, stale, withheld, unverified, and
  failed data must not look like zero, a neutral success, or a confirmed
  recommendation.
- Keep existing API contracts, navigation destinations, and click-through
  behavior unless the change explicitly includes their replacement. Interactive
  elements must have a clear affordance and keyboard-accessible semantics.
- Use a consistent type scale, spacing rhythm, restrained palette, clear
  contrast, and aligned numeric values. Reserve color for semantic meaning;
  never use color alone to convey state.
- Prefer responsive cards and focused charts over dense tables when comparison
  is not the primary task. Tables must retain headings, units, and usable
  narrow-screen behavior.
- Keep financial and trading disclaimers proportionate and near the relevant
  decision or model output; do not imply that research or backtest results are
  investment advice or live execution.

## Implementation workflow

1. Inspect the existing route, page structure, CSS tokens, API calls, and
   interaction handlers before changing the UI.
2. Identify the primary user task and preserve a traceable path from summary
   metrics to their details, evidence, and related records.
3. Make the smallest coherent design change. Reuse shared components and
   existing API data rather than inventing front-end-only values.
4. Validate responsive layout, loading/error/empty/stale states, keyboard
   navigation, and every changed click target.
5. Run JavaScript syntax checks and relevant backend/UI tests. When available,
   use the integrated browser to inspect the actual rendered page at desktop
   and narrow viewport widths.

## Visual direction

Favor a quiet, premium research-terminal aesthetic: generous whitespace,
typographic hierarchy, understated borders, restrained accent colors, and
precise charts. Match the existing product palette where practical instead of
introducing a competing theme. Avoid decorative gradients, repeated cards,
unexplained abbreviations, and chart effects that exaggerate a move.
