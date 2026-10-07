# Knowledge popup spec - "the one thing that matters most"

Status: proposal. Owner: knowledge-model (read-only scan task).
Write scope of this task: this file only. `explain.py`, `explainer.js`,
`explain.css`, `style.css`, `glossary_ui.py` and `terminal_api.py` were **read,
not changed** - section C and D are instructions for whoever implements this.

## The owner's requirement (verbatim)

> "every informational card is monotonous 4W1H, no i didnt wanted that. i wanted
> the click to pop up the most important thing about it (to make informative
> decision) that included what is it, how to use/identify it, whats the
> identification method (in non technical, lucid manner)"

Three asks, in the owner's own words, map to fields like this:

| Owner's ask | Field |
|---|---|
| "the most important thing about it (to make informative decision)" | `headline` (+ `caution` when there is a real trap) |
| "what is it" | `what` |
| "how to use/identify it" | `use`, then `action` |
| "whats the identification method (in non technical, lucid manner)" | `spot` |

The monotony is structural, not editorial. See section 0.

---

## 0. What the scan found (ground truth for the design)

### 0.1 Content inventory - `explain.py`

* 27 entries, all keyed `lower_snake_case`. Titles are all in plain words.
* **Every single one of the 27 entries populates all 7 sections** (verified by
  importing the module: `missing: none` for all 27). There is no naturally short
  entry, so the dialog always renders 7 labelled rows plus a lead plus a footer -
  9 blocks with the same shape for every term. That is the monotony.

### 0.2 How the fixed shape is produced

Three independent renderers consume `explain.SECTIONS`:

| Consumer | File | Behaviour |
|---|---|---|
| Click popup | `terminal/static/explainer.js` | `ORDER = ["what","why","look","where","when","how","sight"]`, loops it, emits one `.ex-row` per populated key, with `.ex-lead` (the `what` text) above and a `.ex-foot` meta note below |
| Full glossary page | `glossary_ui.py` (`render()`) | loops the same 7 sections into a `<dl>`, `.gsight` for `sight` |
| API index | `terminal_api.py` (`/api/explain`, `/api/explain/{key}`) | returns the entry verbatim plus the 7 `sections` labels |

So the shape is duplicated in three places and hard-coded as an array in one.
Layout facts (`terminal/static/style.css`):

* `.ex-row` is a 2-column grid: `148px 1fr` (stacks under 620px). A fixed label
  column is what makes the popup read as a form/table even for one-line answers.
* `.ex-lead` (15px) is the `what` sentence, then every section is equal weight.
  Nothing is emphasised, so nothing is "the one thing".
* `.ex-sight` is the only differentiated row today (blue tint, green label).
* `.ex-foot` ("Explanations live in explain.py...") is developer meta shown to a
  non-technical owner on every single click.

### 0.3 The real click targets

Static `data-explain="<key>"` usage, 21 distinct keys. Occurrences by element
kind are the basis of the ranking in section B.

| Key | Occurrences | Where |
|---|---|---|
| `setup` | 10 | 6 panel titles, 4 nav buttons |
| `signal` | 7 | 3 panel titles, 2 metric cards, 2 nav buttons |
| `target` | 5 | 2 panel titles, 2 nav buttons, 1 figure (swing table, `data-explain-stop`) |
| `p_win` | 5 | 1 panel title, 2 nav buttons, 2 deliberate affordances (app.js 1189/1190) |
| `data_quality` | 5 | 1 panel title, 2 nav buttons, 2 whole-box containers |
| `composite` | 3 | 3 panel titles |
| `sector_rs` | 3 | 1 panel title, 2 nav buttons |
| `pullback` | 2 | 2 figures |
| `impulse` | 2 | 2 figures |
| `risk_pct` | 2 | 1 figure, 1 metric card |
| `shape_score` | 2 | 1 panel title, 1 figure |
| `hit_rate` | 2 | 2 `?` chips on the research page |
| `mfe` | 2 | 2 `?` chips |
| `mae` | 2 | 2 `?` chips |
| `r_multiple` | 1 | 1 `?` chip (the Profit/loss column header) |
| `regime` | 1 | the whole market-weather banner (largest single element, top of page) |
| `stop` | 1 | 1 figure (swing table) |
| `volume`, `sizing`, `veto`, `sources` | 1 each | 1 panel title or 1 box each |

**Six of the 27 keys are unreachable from the UI**: `accum`, `breadth`,
`delivery`, `expectancy`, `profit_factor`, `max_drawdown`. They exist in
`explain.py`, and `/glossary` lists them, but nothing on screen carries their
`data-explain`. Content for them is currently written for nobody.

### 0.4 The bigger hole: 16 keys are clicked that have no entry at all

`ideals.js` (line 113) stamps `data-explain="<ideal key>"` onto **every** label
row it decorates, using keys from `ideal.py`. Its `MATCHERS` list covers 19
ideal keys. Only 3 of those have a matching `explain.py` entry (`risk_pct`,
`shape_score`, `p_win`).

The remaining **16 keys are clickable today and every click falls into the
"Not explained yet" branch**: `debt_to_equity`, `roce`, `roe`, `operating_margin`,
`net_profit_margin`, `interest_coverage`, `cfo_positive`, `pe`, `pb`, `peg`,
`dividend_yield`, `sales_growth_3y`, `profit_growth_3y`, `promoter_holding`,
`pledge_pct`, `fii_holding`.

These are the numbers a non-finance owner most often taps ("what is ROCE 8.1?"),
and `ideals.js` already inserts a sibling chip next to each one carrying
`ideal <band> — <source>`. That existing chip is the raw material for the
tier-3 fallback in section D. This is the single highest-value finding of the
scan: the popup's worst monotony is that for 16 of its most-tapped targets it
has nothing to say at all.

### 0.5 Voice check (`GLOSSARY.md`, `ideals.js`, `explain.py`)

The house voice is: short declarative sentences, second person only for actions,
British-leaning spelling ("sceptical"), concrete Indian-market framing (rupees,
₹ crore), acronyms always expanded on first use, no exclamation, no emoji, no
imperative that sounds like a broker. `ideals.js`'s comment ("ROCE 8.1 says
nothing. 8.1% - below the 15% we look for says everything.") is the tone to
match. Everything in section B is written to that tone.

---

## A. Proposed entry schema

### A.1 Schema (Python-shaped, since `explain.py` is Python)

```python
# One entry per key. Field order below is the order the popup renders.
{
    "title":    str,   # existing field, unchanged. Dialog heading + aria-labels.
    "headline": str,   # NEW. The one thing. HARD LIMIT 70 characters. No full stop.
    "what":     str,   # what it is, in plain words. 1-2 sentences, <= 240 chars.
    "use":      str,   # what a high / low / missing value tells you to check next.
                       # 1-2 sentences, <= 260 chars.
    "spot":     str,   # identification method, non-technical: where it sits on
                       # screen first, then how to see it by eye. 1-2 sentences.
    "action":   str,   # the single concrete next step. 1 sentence, <= 140 chars.
    "caution":  str,   # OPTIONAL. One sentence, <= 120 chars. Real trap only.
    "method":   str,   # existing "how" text, kept for /glossary only.
                       # MUST NOT be rendered by the click popup.
}
```

Why these and nothing else: the owner asked for three things and one lead. Four
labelled rows plus an optional caution is the maximum that still reads as "one
thing that matters", and it is 4 rows instead of 7 for every key.

### A.2 Field rules (the anti-wall-of-text law)

1. **Strict budget: no field over 2 sentences.**
   `headline` 1 line, <= 70 chars, no trailing full stop (it is a headline, and
   it is the only field allowed to be a fragment).
2. `what` never repeats the `title`. The title names it; `what` explains it.
3. `use` must contain the decision content: thresholds, high/low meaning, or
   "which of these two do I read first". It may carry a band moved out of the
   old `look` field. If a fact is not a number, a comparison or a next check,
   it does not belong in `use`.
4. `spot` is the owner's "identification method" and must be **screen-first**:
   name the column, chip, line, colour or panel where the thing actually sits
   *before* any "look at a chart" advice. This is what kills the abstraction.
5. `action` is a *check*, not an order. Allowed verbs: check, compare, write
   down, confirm, ask, wait, size, look again. Forbidden: buy, sell, should,
   must, recommended, guaranteed, will rise. Never a quantity of money.
6. `caution` is for a genuine trap that would change a decision (a known
   weakness, an uncalibrated score, a small sample). **No boilerplate
   disclaimer**, and no "not investment advice" line - the portal's
   no-advice rule is carried by the *voice of every field*, not by a footer.
7. Acronyms: expand at first use inside the same field, in plain words
   ("MFE - the best it ever looked - counted in R"). Never leave a bare
   `p_win`, `MFE`, `MAE`, `R`, `EMA`, `P95`.
8. No markdown, no HTML, no emoji in any field. Text only; the renderer escapes.

### A.3 Render contract (what the popup must do)

```
POPUP_LEAD   = "headline"                     -> .ex-headline, unlabelled, bold
POPUP_ORDER  = ["what", "use", "spot", "action"]  -> .ex-row, one per populated field
POPUP_LAST   = "caution"                      -> .ex-caution, only when set
NEVER IN POPUP = "title" (it is the heading), "method", "sections", "key"
```

* Labels (replace the old 7): `what` -> "What it is", `use` -> "How to use it",
  `spot` -> "How to spot it", `action` -> "Do this next", `caution` -> "Careful".
* `spot` takes the differentiated styling that `.ex-sight` has today (tinted
  block, accent label). `action` becomes the closing emphasised row.
* Delete the `.ex-foot` line from the popup. It is developer meta and appears on
  every single click.
* Never print the raw key in the popup. Today the unknown-key branch prints the
  code key inside `<code>`; the owner should see the label they actually tapped.
* Maximum rendered block: 1 headline + 4 rows + 1 optional caution. That is the
  monotony fix: the *shape is the same law* but it is four rows, one of which is
  a headline, instead of seven equal-weight paragraphs.

---

## B. Filled mapping - the 12 most-clicked keys

### B.1 How the list was ranked

There is **no click telemetry in this repository** (checked: no analytics,
`sendBeacon`, or explain-click logging in `terminal/static`), so "most-clicked"
was derived structurally. Each static `data-explain` occurrence was scored by
how deliberate the click is:

* **W3 - deliberate affordance.** The element exists only to be tapped for an
  explanation: a `?` chip (`.ledger-sight`) or a `data-explain-stop` figure in a
  table row. The owner taps it *because* they do not know the number.
* **W2 - panel title (`h2.panel-title`).** Tapped while scanning a panel; the
  popup is a side effect of curiosity, but the opportunity count is high.
* **W1 - container or nav button.** A metric card, a whole box, a nav button.
  Mostly incidental, and nav keys are double-counted (desktop + mobile markup).

Score = sum of weights. Ranking is robust: **the top 12 is identical whether
nav/container clicks are weighted 1 or 0**, so the list does not depend on that
judgement call. Ties were broken by deliberate-affordance count first, then by
how early the element appears in the main reading journey (regime banner and
research page first).

| # | Key | Score | Deliberate taps | Why it is in the top 12 |
|---|---|---|---|---|
| 1 | `setup` | 16 | 0 (6 titles + 4 nav) | The pattern everything else is judged against; most-attached key |
| 2 | `signal` | 10 | 0 (3 titles + 2 cards + 2 nav) | Every row of the two history tables is a signal |
| 3 | `p_win` | 10 | 2 | Labelled "Event" / "Model Event Score" on screen - the most confusing label in the app |
| 4 | `target` | 9 | 1 | Third column of the swing table plus 2 panel titles |
| 5 | `composite` | 6 | 0 (3 titles) | Top of the research view and the shortlist card |
| 6 | `data_quality` | 6 | 0 (title + 2 nav + 2 boxes) | First thing to check when a result looks wrong |
| 7 | `hit_rate` | 6 | 2 | `?` chip on every research page, next to +1R/+2R/+3R |
| 8 | `mfe` | 6 | 2 | `?` chip, unexplained acronym |
| 9 | `mae` | 6 | 2 | `?` chip, unexplained acronym |
| 10 | `pullback` | 6 | 2 | Swing-table figure + setup-details row |
| 11 | `impulse` | 6 | 2 | Swing-table figure + setup-details row |
| 12 | `shape_score` | 5 | 1 | Panel title on the swing view + setup-details row |

Next in line (fill these before touching the orphans): `risk_pct` (4),
`sector_rs` (4), `stop` (3), `r_multiple` (3), `regime` (1 container but the
largest element on the first screen), then the six unreachable keys and the 16
missing ones from section 0.4.

### B.2 The 12 entries (ready to paste into `explain.py`)

Old fields (`why`, `look`, `where`, `when`, `how`, `sight`) are kept where they
exist so nothing breaks mid-migration; section C says which to delete when.

```python
PROPOSED_TOP12 = {
    "setup": {
        "title": "The pattern we look for",
        "headline": "A strong rise, then a quiet pause - that pause is the pattern",
        "what": "A stock that climbed hard, then went quiet and sideways just above "
                "its recent average price.",
        "use": "A real climb followed by a calm, quiet pause is the one shape worth "
               "watching. Excitement at the top of a long run is not the pattern.",
        "spot": "Find the flat, boring stretch after a climb. On the chart it sits "
                "between the green trigger line and the pink stop line.",
        "action": "Wait for the price to push above the pause before doing anything "
                  "with it.",
        "caution": "All five plain checks have to pass together; four out of five is "
                   "not the pattern.",
    },
    "signal": {
        "title": "A recorded setup",
        "headline": "A pattern match written down before the result was known",
        "what": "A dated record that a stock matched the pattern, with the trigger, "
                "stop and goal frozen at that moment.",
        "use": "Read many of them, never one. The tally of finished outcomes is the "
               "only honest scorecard the system has.",
        "spot": "Rows in Short-Term Ideas and in Every Idea We Recorded. The badge at "
                "the end of the row says WIN, LOSS, TIMEOUT or OPEN.",
        "action": "Judge the method on the whole list rather than on the newest row.",
        "caution": "One record proves nothing either way.",
    },
    "p_win": {
        "title": "Chance of a good move",
        "headline": "The machine's rough lean that the price reaches +10% in a month",
        "what": "A model score for how likely this stock is to touch a price 10% "
                "higher at some point in the next 20 trading sessions.",
        "use": "Above half is the model's genuine interest; near half is a coin flip. "
               "It ranks ideas, it does not say whether your trade will work.",
        "spot": "The chip beside the symbol that reads Event 62%, and the Model Event "
                "Score line on the research page.",
        "action": "Use it to decide what to read first, then check the pattern and the "
                  "stop on that name.",
        "caution": "This score is uncalibrated and has been wrong in bulk before; it is "
                   "not the odds of a trade working out.",
    },
    "target": {
        "title": "The point where you take profit",
        "headline": "Chosen in advance: three times your risk, not a feeling",
        "what": "A price above your trigger where the plan says the idea is finished.",
        "use": "A target sitting close to your trigger means little is being asked of "
               "the price. Further away means more has to go right.",
        "spot": "The dashed blue line labelled Target 3R on the chart, and the Target "
                "column of the ideas table.",
        "action": "Fix the number before you decide anything, then work out where you "
                  "would move the stop up to.",
        "caution": "The hit-rate table shows how often targets of this size were "
                   "actually reached.",
    },
    "composite": {
        "title": "Overall ranking score",
        "headline": "One blended score, used only to decide what to read first",
        "what": "A single number mixing the model score with quiet accumulation, "
                "industry strength and delivery.",
        "use": "Small gaps near the top mean nothing. Only a clear gap tells you one "
               "name is being ranked ahead of another.",
        "spot": "The Rank figure on each shortlist card, and the order of the Today's "
                "Shortlist panel.",
        "action": "Open the top names and check the pattern, the stop and the data "
                  "freshness for yourself.",
        "caution": "It sets a queue order and is never a reason on its own.",
    },
    "data_quality": {
        "title": "Is our data trustworthy today",
        "headline": "If this is not green, every other number on screen is suspect",
        "what": "Six automatic checks on whether today's prices and company figures "
                "are complete and fresh.",
        "use": "Green means you can act on what you are reading. Any red means treat "
               "results as wrong until the cause is fixed.",
        "spot": "The deployment check box at the bottom of the System page. Compare "
                "today's date with the newest date stored in the tables.",
        "action": "Check here first whenever a result looks surprising.",
        "caution": "Stale prices still produce confident-looking numbers.",
    },
    "hit_rate": {
        "title": "How often it got there",
        "headline": "How many past similar cases reached each profit level before failing",
        "what": "The share of past cases that looked like today and then touched +1R, "
                "+2R or +3R, where one R is the amount that was risked.",
        "use": "In a healthy set of cases +1R is the largest figure and +3R the "
               "smallest. A big drop from +1R to +2R means most cases stall early.",
        "spot": "The Hit rate (given trigger) row on the research page, printed as "
                "+1R, +2R and +3R.",
        "action": "Pick a profit goal that past cases actually reached.",
        "caution": "A high percentage worked out from a handful of cases is thin "
                   "evidence.",
    },
    "mfe": {
        "title": "The best it ever looked",
        "headline": "The best moment while the idea was open, counted in R",
        "what": "The furthest the price went in your favour while the idea was open, "
                "as a multiple of what you had risked.",
        "use": "A high figure next to a flat final result means profit was given back. "
               "Around 1R or less means it never really went your way.",
        "spot": "The MFE in R row on the research page, shown as a middle figure and a "
                "best-case figure.",
        "action": "Compare the best moment with the final result to see whether the "
                  "exit plan handed money back.",
        "caution": "It is a high point that may never have been reachable in real "
                   "trading.",
    },
    "mae": {
        "title": "The worst it ever looked",
        "headline": "The deepest dip against you while the idea was open, in R",
        "what": "How far the price went against you while the idea was open, as a "
                "multiple of what you had risked.",
        "use": "Well under 1R is a comfortable ride. Reaching or passing 1R means your "
               "safety line was tested or hit.",
        "spot": "The MAE in R row on the research page, directly under the MFE row.",
        "action": "Ask whether you could sit through that dip without selling at the "
                  "bottom.",
        "caution": "Ideas that go far against you first are the ones people abandon "
                   "early.",
    },
    "pullback": {
        "title": "The pause dip",
        "headline": "How far the price eased back - a step is fine, a cliff is not",
        "what": "The distance the price has dropped from its recent high while it "
                "pauses.",
        "use": "A gentle dip of a few percent up to about a quarter is normal. A "
               "sudden sharp fall means the earlier rise is already broken.",
        "spot": "The PB column in Short-Term Ideas, and the pause dip row under Show "
                "setup details.",
        "action": "If the dip is deep or violent, leave it and read the next name.",
        "caution": "A violent drop is not a pause, however good the earlier rise "
                   "looked.",
    },
    "impulse": {
        "title": "The earlier rise",
        "headline": "The climb before the pause; too small or too big both fail",
        "what": "How much the stock climbed before it started pausing.",
        "use": "Roughly a fifth to three-quarters higher over a few months is the "
               "sweet spot. A bigger climb than that is usually spent.",
        "spot": "The Impulse column in Short-Term Ideas, and the earlier rise row "
                "under Show setup details.",
        "action": "Confirm there was a real climb before reading anything else about "
                  "the name.",
        "caution": "No earlier rise means there is no pattern, whatever else looks "
                   "good.",
    },
    "shape_score": {
        "title": "How tidy the pause is",
        "headline": "A tidy, even pause continues more often than a jagged one",
        "what": "A tidiness grade from 0 to 100 for the sideways pause.",
        "use": "Above 60 is a clean pause and below 40 is messy. Use it to choose "
               "between two names that look otherwise alike.",
        "spot": "The how tidy the pause is row under Show setup details, shown as a "
                "figure out of 100.",
        "action": "When two names look alike, read the tidier one first.",
        "caution": "A high grade measures tidiness, not what happens next.",
    },
}
```

Budget check on the block above (verified by parsing this file): see section E.

---

## C. Migration note

### C.1 Fate of the 7 existing sections

| Old section | Fate | Why |
|---|---|---|
| `what` | **SURVIVES** as `what` | It is the correct "what is it" answer and is already used by `catalog()` and `/glossary`. Trim any entry that runs past 2 sentences. |
| `sight` | **SURVIVES, renamed `spot`** | "How to spot it yourself" is exactly the owner's "identification method". Re-scope it to name the on-screen location first (absorbing the useful half of `where`), then the by-eye method. |
| `why` | **DIES as a section; MERGES into `headline` + `action`** | It is the longest field and the main wall-of-text generator. Its job splits cleanly: the "so what" becomes the `headline`, the consequence becomes `action`. Test: if a `why` cannot be squeezed into those two, it was two separate ideas. |
| `look` | **DIES; SPLITS into `use` and `spot`** | It mixes two different things: the band ("up to about 5% is acceptable") and the appearance. Numeric bands move into `use` verbatim; appearance moves into `spot`. Losing the bands would be the one real risk of this migration - they are decision content, so they must be carried across, not paraphrased away. |
| `when` | **DIES; MERGES into `action`** | Timing is the tense of the action. "Check it before acting on anything else" *is* an action. Keeping both produced two rows saying the same thing in different words. |
| `where` | **DIES; one clause absorbed into `spot`** | It answers "where else in the system is this used" - codebase inventory for a developer, not something the owner can act on. In practice it names panels, which is exactly what `spot` needs (screen-first location). One clause survives there; the rest is dropped. |
| `how` | **DIES FROM THE POPUP; KEPT as `method`, glossary-only** | Machine internals ("we compare the volume on up days with the volume on down days") is the opposite of lucid identification for a non-finance reader, and it is what made every card read like a manual. Note the owner's "identification method" means how *they* identify it, which is `spot`, not `how`. Keep the text as `method` so the knowledge is not lost: `/glossary` may show it inside a collapsed "How it is worked out" block, and the popup must never render it. |

Net: a term's popup goes from 7 equal-weight rows to 1 headline + 4 rows
(+1 optional caution), and no content category is silently destroyed.

### C.2 Section count after migration

`SECTIONS` in `explain.py` should become the popup contract, not a flat list:

```python
SECTIONS = [
    ("what",   "What it is"),
    ("use",    "How to use it"),
    ("spot",   "How to spot it"),
    ("action", "Do this next"),
]
CAUTION_LABEL = "Careful"
METHOD_LABEL  = "How it is worked out"   # /glossary only, never the popup
```

Keep `SECTIONS` shaped as `(key, label)` pairs so `/api/explain` and
`glossary_ui.py` keep working without a rewrite, and so `explainer.js` can keep
reading `payload.sections` for labels.

### C.3 Per-key mapping for all 27 keys

The 12 in section B are done. The remaining 15, with a proposed `headline` each
so the migration has no blank slots. All are <= 70 characters.

| Key | Proposed `headline` | Migration note |
|---|---|---|
| `regime` | Market weather decides how much else is worth reading | `why` becomes headline; the size multiplier goes into `use`; banner pills are the `spot` |
| `breadth` | A rising market carried by a few shares is a warning sign | Unreachable today; needs `data-explain="breadth"` on the market overview before content matters |
| `volume` | Quiet trading during a pause is the good sign | `look` becomes `use`; volume bars are `spot` |
| `accum` | Buying on up days, heavier than selling on down days | Unreachable today; content is fine, wiring is missing |
| `delivery` | Buyers choosing to hold shares, not flip them the same day | Unreachable: `ideal.py` has a `delivery` band but `ideals.js` has no matcher for it. Add the `data-explain` or the content is dead |
| `sector_rs` | A strong share in a strong industry has wind at its back | `look`'s top-three rule moves into `use` (it is a gate, i.e. a decision) |
| `stop` | The price that proves you wrong, decided before you commit | `look`'s "about 5%" band moves into `use`; the pink PDL Stop line is `spot` |
| `risk_pct` | The distance to your stop, as a share of the price you pay | Band ("up to about 5%") moves into `use`; the Risk % column is `spot` |
| `sizing` | How many shares keeps one loss small and survivable | `where`/`how` drop; the research-page sizing box is `spot` |
| `r_multiple` | One R is one bite of risk; every result is measured in it | Longest entry today (3 long paragraphs); `how` becomes `method`, the rest compresses to 4 rows |
| `expectancy` | The average result of one idea over every idea recorded | Unreachable today; needs a `data-explain` on the performance panel |
| `profit_factor` | Rupees won for every rupee lost across all closed ideas | Unreachable today; the 1.5 threshold is decision content and moves to `use` |
| `max_drawdown` | The worst fall from a peak, in R; the number that tests nerve | Unreachable today |
| `veto` | A blocked name is blocked, whatever the chart looks like | The known weakness ("a missing figure passes by default") becomes `caution` - exactly the kind of real trap `caution` is for |
| `sources` | If a data source breaks, everything looks fine but is not | `sight` was "not applicable"; `spot` should name the source health box instead |

### C.4 Copy changes to existing fields

* `signal.title` "A recorded buy idea" -> **"A recorded setup"**. The word "buy"
  in a dialog heading is the one place the no-advice rule is visibly wobbling,
  and the record is research evidence, not an instruction.
* `p_win.title` "Chance of a good move" stays, but the screen label is
  "Event"/"Model Event Score"; `spot` bridges the two names so the owner can see
  they are the same thing.
* Any `why` sentence containing "we buy the pause" (in `setup`) is rewritten in
  section B to describe the shape rather than the action.

### C.5 Rollout order (additive, never breaking)

1. Add `headline`/`use`/`spot`/`action`/`caution` to entries; **do not delete**
   `why`/`look`/`where`/`when`/`how`/`sight` yet. `get()` and `catalog()` keep
   working, `/glossary` is untouched, the old popup keeps working.
2. Ship the new popup render (section A.3) with the tier-2 fallback from section
   D, so un-migrated keys still render sensibly.
3. Migrate the 12 top keys (section B), then the 15 remaining (section C.3).
4. Only then delete the dead sections from `explain.py`, update `SECTIONS` per
   C.2, and switch `glossary_ui.py` to render `method` in a collapsed block.

---

## D. Fallback rule - the popup must never be an empty shell

Resolution runs in strict order; the first tier that produces a `headline` wins.
Every tier must produce a heading, a lead line and at least one body row.

**Tier 1 - new entry.** `entry.headline` exists -> render section A.3 exactly.

**Tier 2 - legacy entry (no `headline` yet).** Derive, do not give up:

| Missing field | Derived from | Rule |
|---|---|---|
| `headline` | `what` | First sentence of `what`, cut at the last word boundary <= 70 chars, no trailing full stop; if cut, do not add an ellipsis (the text is a headline, not a quote) |
| `what` | `what` | used as-is |
| `use` | `look` | used as-is (the band text is the decision content) |
| `spot` | `sight`, else `where` | `sight` first; `where` only if `sight` is empty |
| `action` | `when` | used as-is |
| `caution` | - | omitted |

Set `data-explain-legacy="1"` on the dialog so the state is visible in devtools
and a test can assert it. Tier 2 is temporary and must disappear once C.5 step 3
is done; it is the bridge that makes step 1 and 2 safe.

**Tier 3 - unknown key that has an ideal band on screen (the 16 keys in 0.4).**
The click target itself is already decorated by `ideals.js`, which inserts a
sibling `.ideal-chip` whose text is `ideal <ideal_text>` and whose `title` is
`<ideal_text> — <source>`. So:

* `title` = the tapped element's own visible label (e.g. "ROCE"), not the key.
* `headline` = the chip's `ideal_text` (e.g. "15% or more"), prefixed so it reads
  as a sentence: "The level we look for here is 15% or more".
* `what` = `"<label> - " + chip.title` truncated at the first " - " source
  separator so the source name is not read aloud as part of the definition.
* `use` = `"Compare the figure beside it with that level. A figure below it is a
  weak spot, not a verdict on the company."`
* `spot` = `"The label you just tapped, with the ideal chip beside it."`
* `action` = `"Read the number against the level before using it in a decision."`
* `caution` = omitted. No `method`.

If the chip is absent but `/api/ideals` has been loaded, use the band entry
instead of the DOM chip (same fields). This tier needs no backend change: it
reads data the page already renders. It converts the 16 dead clicks into useful
cards immediately, before any of that content is author-written.

**Tier 4 - truly unknown, no band.** Never an empty modal, never a raw key:

* `title` = tapped element's visible text, trimmed to 70 chars; if that is also
  empty, the page's panel heading; if that is empty, "This item".
* `headline` = `"No plain-language note is stored for this yet"`.
* `what` = `"You tapped <label>. It is a value the terminal is showing you, and
  its meaning has not been written down yet."`
* `spot` = `"It is the <label> you just tapped."`
* `use`, `action`, `caution` = omitted.
* A single footnote may say: *"Notes live in one file, so every screen says the
  same thing."* (This replaces today's `.ex-foot`, which is shown to the owner on
  every successful click - it belongs only here.)

**Tier 5 - request failed or returned no body.** Do not open an empty dialog:

* If the key has a cached payload from an earlier click, render the cache.
* Otherwise render Tier 4's card with `headline` = `"Could not load the note
  right now"` and no footnote, and keep the Close button working.

**Non-negotiable invariants for all tiers:**

1. The dialog never opens without visible text in the heading and body.
2. The raw `key` string appears only in a `data-explain-open` attribute, never in
   visible text.
3. Empty-string fields are skipped, never rendered as a blank labelled row.
4. If every resolved field is empty (author error, e.g. `headline: ""`), fall
   through to Tier 4 rather than rendering a titled blank box.
5. `method` is never rendered by this popup in any tier.

---

## E. Acceptance checks

1. **Budget.** For all 12 entries in section B: `len(headline) <= 70`; every
   field is <= 2 sentences; no field exceeds `what` 240 / `use` 260 /
   `action` 140 / `caution` 120 characters. Verified by parsing the
   `PROPOSED_TOP12` block in this file: 12 entries, longest headline 68 chars,
   zero violations. The 15 headlines in C.3 were checked the same way: longest
   61 chars.
2. **No advice.** For all sections B and C.3: no occurrence of buy, sell, should,
   recommended, guaranteed, or a rupee amount in `use`/`action`/`caution`. The
   three descriptive uses of "buy" in existing `why` text are rewritten.
3. **No bare acronyms.** Every `MFE`, `MAE`, `R`, `EMA`, `P95`, `ROCE`, `PE`,
   `D/E` in a filled field carries its plain gloss within the same field.
4. **Shape.** Every click renders exactly 1 headline + 4 rows (+1 caution when
   set) and no `.ex-foot`; the count never varies between two fully migrated keys.
5. **Never empty.** Each of the 16 keys in section 0.4 opens a Tier 3 card and
   none of them shows "Not explained yet". A made-up key (`data-explain="zzz"`)
   opens a Tier 4 card. A key whose entry is `{}` opens a Tier 4 card. A failed
   fetch opens a Tier 5 card.
6. **Tier 2 bridge.** Every one of the 27 keys opens a card with a headline
   before any content is rewritten (Tier 2 derivation), so step 2 of C.5 is safe.
