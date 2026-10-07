# Popup implementation report — decision-first knowledge card

Task: task-5. Spec: `.agents/knowledge-popup-spec.md` (583 lines).
Contract implemented: spec A (schema + render), B.2 (top-12 entries), C.5
(additive rollout), D (5-tier fallback). Acceptance: spec section E.

Status: **implemented and verified by the Lead**; the delegated writer stopped
before marking the task complete, so the evidence below was gathered by the
Lead against the on-disk result.

## What shipped

| File | Change |
|---|---|
| `explain.py` | 27 entries gained `headline`, `use`, `spot`, `action`, optional `caution`. All legacy fields (`what`/`why`/`look`/`where`/`when`/`how`/`sight`) retained additively; `how` is also exposed as `method` for /glossary. `SECTIONS` and `get`/`all_keys`/`catalog` still work. |
| `terminal/static/explainer.js` | Fixed 7-row `ORDER` renderer replaced by `POPUP_LEAD` (headline) + `POPUP_ORDER` (what/use/spot/action) + optional caution. `.ex-foot` removed. 5-tier resolution. |
| `terminal/static/explain.css` | New `.ex-headline`, `.ex-caution`, tinted `spot` row, emphasised `action` row. `.ex-foot` styling neutralised. |

Render contract as shipped:

```
POPUP_LEAD  = headline                        -> .ex-headline  (unlabelled, bold)
POPUP_ORDER = what, use, spot, action         -> .ex-row, labels:
               "What it is" / "How to use it" / "How to spot it" / "Do this next"
POPUP_LAST  = caution                         -> .ex-caution, only when set
NEVER SHOWN = title (it is the heading), method, sections, key
```

## Field budget law — verified

Checked programmatically across all 27 keys:

```
keys: 27
violations: 0
```

Rules enforced and all passing: every key has a `headline`; `len(headline) <= 70`;
no headline ends in a full stop; `what <= 240`, `use <= 260`, `action <= 140`,
`caution <= 120` characters; no field exceeds two sentences; no advice verb
(`buy|sell|should|must|recommended|guaranteed`) in `use`/`action`/`caution`.

## Tier evidence — real browser, 390x844, `#research/KEI`

Clicking a throwaway `[data-explain]` element so the delegated capture-phase
listener runs exactly as it does for a real target:

| Tier | Key probed | Result |
|---|---|---|
| 1 (migrated) | `p_win` | headline present, **4 rows** + caution, `.ex-foot` absent, `legacyTier=null`, key does not leak into title/headline |
| 1 (migrated) | `setup` | headline present, **4 rows** + caution, `.ex-foot` absent |
| 3 (ideal chip) | `roce` | title "Return on capital", headline "The level we look for here is 15% or more", 4 rows, no caution — composed from the on-screen `.ideal-chip`, **no backend entry exists for `roce`** |
| 4 (unknown) | `zzz-totally-unknown-key` | title taken from the tapped label ("Mystery Figure"), headline "No plain-language note is stored for this yet", 2 rows, single footnote — never an empty shell, never a raw key |

Shape consistency across two fully migrated keys: `_shapeConsistent: true`.

Before this change the same click produced **9 identical blocks** for every key
(lead + 7 equal-weight rows + developer footer). Now it is 1 headline + 4 rows,
with the footer gone.

## Regression checks

- `GET /glossary` -> **200**, 27 term sections still rendered (server-rendered
  Python page, never loaded `explainer.js`).
- `GET /api/explain/p_win` -> `ok: true`, `sections` still present alongside the
  new fields, so any legacy consumer keeps working.
- `import terminal_api, explain, glossary_ui` -> clean; 72 routes; 27 explain keys.
- All 9 `test_*.py` files pass.
- `node --check terminal/static/explainer.js` -> clean.

## Deliberately not done

1. **`method` is not rendered by the popup**, per spec A.3. It survives for
   /glossary only. If the owner wants the derivation available from the popup,
   it needs a deliberate second disclosure, not a re-added row.
2. **The 15 remaining keys use the Tier-2 derivation bridge, not authored copy.**
   Spec C.5 step 3 is the follow-up: author `use`/`spot`/`action` by hand for the
   keys that are still derived. They render correctly today, but authored text
   would read better than text lifted from `look`/`sight`/`when`.
3. **No click telemetry exists**, so "most-clicked" was ranked structurally from
   `data-explain` occurrence and context weight, not from real usage. The top-12
   set is stable whether nav clicks are weighted 1 or 0, which is why it was
   considered safe to fill first.
4. **6 orphaned keys** (`accum`, `breadth`, `delivery`, `expectancy`,
   `profit_factor`, `max_drawdown`) are written in `explain.py` but no element
   carries those `data-explain` values. They are harmless but unused; `delivery`
   additionally has an `ideal.py` band with no `ideals.js` matcher.

## Cosmetic defect found by the Lead, then fixed

The `.ex-caution` block originally rendered the label and the sentence with no
separator:

```
"CarefulThis score is uncalibrated and has been wrong in bulk before; ..."
```

The label and text were adjacent nodes with no space between them, so the
concatenated `textContent` was wrong and it read badly for screen readers. The
same was true of every `.ex-row` label/text pair. Fixed in `explainer.js` by
emitting an explicit space between the label and text spans.

Re-verified after the fix:

```
"caution": "Careful This score is uncalibrated and has been wrong in bulk before; it is not the odds of a trade working out."
"bodyText": "...What it is A model score for how likely this stock is to touch a price 10% higher..."
```

All four tiers re-checked clean: `p_win` 4 rows + caution, `setup` 4 rows +
caution, `roce` 4 rows via the ideal chip, unknown key 2 rows with footnote.
