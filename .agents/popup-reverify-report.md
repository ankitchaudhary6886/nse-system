# Popup re-verification - every one of the 27 keys

Task: resolve the owner's doubt that the decision-first popup rework is
finished. Scope of this round: explain.py, terminal/static/explainer.js,
terminal/static/explain.css. Server: 127.0.0.1:8022.

This file supersedes the earlier `.agents/popup-impl-report.md`
requirement (the Lead's re-assignment changed the report name and dropped
glossary_ui.py from my write scope). All of the earlier evidence - two curl
proofs, /glossary, the tier ladder - is folded in below and re-run on 8022.

## Verdict

**All 27 keys render the decision-first card: 1 headline + exactly 4
labelled rows + optional 'Careful' line, and `.ex-foot` is gone.**
- 27/27 keys: `data-explain-tier="1"`, `data-explain-legacy` never set.
- 27/27 keys: 4 rows with the same four labels, in the same order.
- 27/27 keys: `.ex-foot` absent; headline length 45-69 characters.
- 0 keys are on the Tier-2 derivation bridge (the bridge is proven working
  with a stubbed legacy payload, but no live key needs it).
- 16/16 ideal-only keys (`roce`, `pe`, `pledge_pct`, ...) open a Tier-3 card.

## 1. The 27-key browser sweep

```
node tools/ui-audit/eval.mjs --url http://127.0.0.1:8022 --hash "#research/KEI" \
     --wait 6000 --expr-file %TEMP%\sweep27.js
```

Each key is clicked through a throwaway `[data-explain]` element, so the real
delegated listener, the real `/api/explain/{key}` fetch and the real renderer
all run. Whole sweep: 27 keys in 4112 ms.

| # | key | tier | legacy attr | rows | labels | caution | headline chars | headline |
|---|---|---|---|---|---|---|---|---|
| 1 | `accum` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 52 | Buying on up days, heavier than selling on down days |
| 2 | `breadth` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 57 | A rising market carried by a few shares is a warning sign |
| 3 | `composite` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 57 | One blended score, used only to decide what to read first |
| 4 | `data_quality` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 61 | If this is not green, every other number on screen is suspect |
| 5 | `delivery` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 58 | Buyers choosing to hold shares, not flip them the same day |
| 6 | `expectancy` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 55 | The average result of one idea over every idea recorded |
| 7 | `hit_rate` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 68 | How many past similar cases reached each profit level before failing |
| 8 | `impulse` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 58 | The climb before the pause; too small or too big both fail |
| 9 | `mae` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 69 | The deepest dip against you while the idea was open, measured in risk |
| 10 | `max_drawdown` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 46 | The deepest fall from a peak, in units of risk |
| 11 | `mfe` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 57 | The best moment while the idea was open, measured in risk |
| 12 | `p_win` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 63 | The machine's rough lean that the price reaches +10% in a month |
| 13 | `profit_factor` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 55 | Rupees won for every rupee lost across all closed ideas |
| 14 | `pullback` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 61 | How far the price eased back - a step is fine, a cliff is not |
| 15 | `r_multiple` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 57 | One R is one bite of risk; every result is measured in it |
| 16 | `regime` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 53 | Market weather decides how much else is worth reading |
| 17 | `risk_pct` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 58 | The distance to your stop, as a share of the price you pay |
| 18 | `sector_rs` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 56 | A strong share in a strong industry has wind at its back |
| 19 | `setup` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 61 | A strong rise, then a quiet pause - that pause is the pattern |
| 20 | `shape_score` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 57 | A tidy, even pause continues more often than a jagged one |
| 21 | `signal` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 56 | A pattern match written down before the result was known |
| 22 | `sizing` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 51 | How many shares keeps one loss small and survivable |
| 23 | `sources` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 47 | If a source breaks, the numbers still look fine |
| 24 | `stop` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 58 | The price that proves you wrong, decided before you commit |
| 25 | `target` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 55 | Chosen in advance: three times your risk, not a feeling |
| 26 | `veto` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 56 | A blocked name is blocked, whatever the chart looks like |
| 27 | `volume` | 1 | - | 4 | What it is / How to use it / How to spot it / Do this next | yes | 45 | Quiet trading during a pause is the good sign |

Machine checks over that JSON: `tier==1` for all 27: **True**; `rowCount==4`
for all 27: **True**; any `.ex-foot`: **False**; any `data-explain-legacy`: **False**;
all 27 opened: **True**.

### Full card copy, key by key

**`accum`** - Quiet accumulation

- HEADLINE (52 chars): Buying on up days, heavier than selling on down days
- WHAT IT IS: How much of recent trading has been buying rather than selling, judged by which days closed higher on heavier volume.
- HOW TO USE IT: A higher reading means demand has been more consistent. Around half means there is no clear story either way.
- HOW TO SPOT IT: The volume bars on the chart: do the bigger bars line up with the green days or with the red days?
- DO THIS NEXT: Check whether a strong reading lines up with the pause pattern rather than reading it on its own.
- CAREFUL: It is a clue about steady interest, never proof.
- copy note: Statement of the measurement, not the decision - the weakest headline of the 27; the `use` row carries the decision. Left as authored by the spec (C.3).

**`breadth`** - How many shares are joining in

- HEADLINE (57 chars): A rising market carried by a few shares is a warning sign
- WHAT IT IS: The share of tracked stocks trading above their own recent average price.
- HOW TO USE IT: More than half of tracked shares above their own recent average, with more rising than falling, is healthy. A narrow market is a warning.
- HOW TO SPOT IT: Scan a watchlist or the market overview: is most of it above its recent average, or only a few names?
- DO THIS NEXT: Check breadth before trusting a rising index, because a narrow rise fails more often than a broad one.
- CAREFUL: A handful of large companies can hold an index up while most shares fall.
- copy note: Decision-first: names the trap (a narrow rise).

**`composite`** - Overall ranking score

- HEADLINE (57 chars): One blended score, used only to decide what to read first
- WHAT IT IS: A single number mixing the model score with quiet accumulation, industry strength and delivery.
- HOW TO USE IT: Small gaps near the top mean nothing. Only a clear gap tells you one name is being ranked ahead of another.
- HOW TO SPOT IT: The Rank figure on each shortlist card, and the order of the Today's Shortlist panel.
- DO THIS NEXT: Open the top names and check the pattern, the stop and the data freshness for yourself.
- CAREFUL: It sets a queue order and is never a reason on its own.
- copy note: Says how far to trust it before you read it.

**`data_quality`** - Is our data trustworthy today

- HEADLINE (61 chars): If this is not green, every other number on screen is suspect
- WHAT IT IS: Six automatic checks on whether today's prices and company figures are complete and fresh.
- HOW TO USE IT: Green means you can act on what you are reading. Any red means treat results as wrong until the cause is fixed.
- HOW TO SPOT IT: The deployment check box at the bottom of the System page. Compare today's date with the newest date stored in the tables.
- DO THIS NEXT: Check here first whenever a result looks surprising.
- CAREFUL: Stale prices still produce confident-looking numbers.
- copy note: Strongest headline in the set - states the consequence of ignoring it.

**`delivery`** - Shares actually taken home

- HEADLINE (58 chars): Buyers choosing to hold shares, not flip them the same day
- WHAT IT IS: The share of traded stock that buyers chose to hold rather than resell the same day.
- HOW TO USE IT: A persistently high reading is interesting, while one odd day means nothing. It only matters when it stays high for many days alongside a pause.
- HOW TO SPOT IT: The delivery row on the research and data pages. It is not on the price chart at all; it comes from separate exchange figures.
- DO THIS NEXT: Check the figure across many days rather than one session before treating it as evidence of real holding.
- CAREFUL: A single big delivery day is often a one-off transfer, not steady accumulation.
- copy note: Plain description of the behaviour; no jargon.

**`expectancy`** - Average result per idea

- HEADLINE (55 chars): The average result of one idea over every idea recorded
- WHAT IT IS: The typical result of one idea, measured in R (the money risked), averaged over every idea the system recorded.
- HOW TO USE IT: Above zero means the average idea added to the pot, and below zero means the average idea lost money.
- HOW TO SPOT IT: The average result per idea figure on the performance page. It is not on any chart; it is a running average of the system's own record.
- DO THIS NEXT: Check it over many recorded ideas only, because a handful of results can look good or bad by luck.
- CAREFUL: A good average built on three ideas is not evidence of anything.
- copy note: Plain; `use` warns it only means something over many ideas.

**`hit_rate`** - How often it got there

- HEADLINE (68 chars): How many past similar cases reached each profit level before failing
- WHAT IT IS: The share of past cases that looked like today and then touched +1R, +2R or +3R, where one R is the amount that was risked.
- HOW TO USE IT: In a healthy set of cases +1R (one unit of the money risked) is the largest figure and +3R the smallest. A big drop from +1R to +2R means most cases stall early.
- HOW TO SPOT IT: The Hit rate (given trigger) row on the research page, printed as +1R, +2R and +3R, each one a multiple of the money risked.
- DO THIS NEXT: Pick a profit goal that past cases actually reached.
- CAREFUL: A high percentage worked out from a handful of cases is thin evidence.
- copy note: 68 characters, the longest, still one line at 375px (sweep: no overflow).

**`impulse`** - The earlier rise

- HEADLINE (58 chars): The climb before the pause; too small or too big both fail
- WHAT IT IS: How much the stock climbed before it started pausing.
- HOW TO USE IT: Roughly a fifth to three-quarters higher over a few months is the sweet spot. A bigger climb than that is usually spent.
- HOW TO SPOT IT: The Impulse column in Short-Term Ideas, and the earlier rise row under Show setup details.
- DO THIS NEXT: Confirm there was a real climb before reading anything else about the name.
- CAREFUL: No earlier rise means there is no pattern, whatever else looks good.
- copy note: States the band as a two-sided test up front.

**`mae`** - The worst it ever looked

- HEADLINE (69 chars): The deepest dip against you while the idea was open, measured in risk
- WHAT IT IS: How far the price went against you while the idea was open, as a multiple of the money you had risked.
- HOW TO USE IT: Well under one R (one unit of the money risked) is a comfortable ride. Reaching or passing one R means your safety line was tested or hit.
- HOW TO SPOT IT: The row labelled MAE in R on the research page, directly under the best-moment row - MAE means the deepest dip against you, in units of risk.
- DO THIS NEXT: Ask whether you could sit through that dip without exiting at the bottom.
- CAREFUL: Ideas that go far against you first are the ones people abandon early.
- copy note: Rewritten this round so the on-screen label comes first and MAE is glossed where it appears.

**`max_drawdown`** - Worst fall from a peak

- HEADLINE (46 chars): The deepest fall from a peak, in units of risk
- WHAT IT IS: The deepest the running total of results fell from its highest point, counted in R (the money risked on one idea).
- HOW TO USE IT: Smaller is easier to live with. Compare it with the average result per idea: a big fall against a small average means a rough ride.
- HOW TO SPOT IT: The figure labelled worst fall from a peak on the performance page. Look at the losing results in order and ask how many in a row would make you quit.
- DO THIS NEXT: Check the worst fall against what you could sit through before trusting a good-looking average.
- CAREFUL: A plan abandoned in a bad patch is no plan at all.
- copy note: Headline rewritten this round: the bare `R` is gone.

**`mfe`** - The best it ever looked

- HEADLINE (57 chars): The best moment while the idea was open, measured in risk
- WHAT IT IS: The furthest the price went in your favour while the idea was open, as a multiple of the money you had risked.
- HOW TO USE IT: A high figure next to a flat final result means profit was given back. Around one R (one unit of the money risked) or less means it never really went your way.
- HOW TO SPOT IT: The row labelled MFE in R on the research page - MFE means the best moment, counted in units of risk. It shows a middle figure and a best-case figure.
- DO THIS NEXT: Compare the best moment with the final result to see whether the exit plan handed money back.
- CAREFUL: It is a high point that may never have been reachable in real trading.
- copy note: Rewritten this round (label first, MFE glossed in the same row).

**`p_win`** - Chance of a good move

- HEADLINE (63 chars): The machine's rough lean that the price reaches +10% in a month
- WHAT IT IS: A model score for how likely this stock is to touch a price 10% higher at some point in the next 20 trading sessions.
- HOW TO USE IT: Above half is the model's genuine interest; near half is a coin flip. It ranks ideas, it does not say whether your trade will work.
- HOW TO SPOT IT: The chip beside the symbol that reads Event 62%, and the Model Event Score line on the research page.
- DO THIS NEXT: Use it to decide what to read first, then check the pattern and the stop on that name.
- CAREFUL: This score is a rough machine guess and has been wrong in bulk before; it is not the odds of a trade working out.
- copy note: Plain ('rough lean', 'coin flip'); 'uncalibrated' replaced with 'rough machine guess' this round.

**`profit_factor`** - Profit per unit lost

- HEADLINE (55 chars): Rupees won for every rupee lost across all closed ideas
- WHAT IT IS: How many rupees of winning ideas there are for every one rupee of losing ideas.
- HOW TO USE IT: Above 1 means the winners outweigh the losers, and around 1.5 or more is solid. Below 1 means the losses are bigger than the gains.
- HOW TO SPOT IT: The profit per unit lost figure on the performance page. Compare the total of the green results with the total of the red ones.
- DO THIS NEXT: Check it alongside the win rate, because many small wins can still lose money when the rare losses are large.
- CAREFUL: One huge winner can flatter this figure for a long time.
- copy note: 'Rupees won for every rupee lost' is the plain way to say it.

**`pullback`** - The pause dip

- HEADLINE (61 chars): How far the price eased back - a step is fine, a cliff is not
- WHAT IT IS: The distance the price has dropped from its recent high while it pauses.
- HOW TO USE IT: A gentle dip of a few percent up to about a quarter is normal. A sudden sharp fall means the earlier rise is already broken.
- HOW TO SPOT IT: The PB (pause dip) column in Short-Term Ideas, and the pause dip row under Show setup details.
- DO THIS NEXT: If the dip is deep or violent, leave it and read the next name.
- CAREFUL: A violent drop is not a pause, however good the earlier rise looked.
- copy note: Step-versus-cliff metaphor makes the band legible without numbers.

**`r_multiple`** - R - one bite of risk

- HEADLINE (57 chars): One R is one bite of risk; every result is measured in it
- WHAT IT IS: One R (one bite of risk) is the money risked on an idea: the gap between the price you paid and the stop below it.
- HOW TO USE IT: At plus 2R (two units of risk) the result is twice what was risked, and at minus 1R it is exactly what had already been accepted as a loss. Zero R means the idea ended flat.
- HOW TO SPOT IT: The R column (one R is one bite of risk) on the performance page. Measure the gap from the entry price down to the stop, then compare the final move with that gap.
- DO THIS NEXT: Read the result in units of risk after the idea closes, and use it to compare ideas of very different size.
- CAREFUL: This measure shows the size of a result, not whether the idea was any good.
- copy note: R is glossed in the headline, `what` and `spot` - necessary because R is the on-screen unit.

**`regime`** - Market weather

- HEADLINE (53 chars): Market weather decides how much else is worth reading
- WHAT IT IS: A one-word read on whether the overall market is going up, going down, or undecided.
- HOW TO USE IT: A calm, rising market is the safest backdrop for a new idea. A falling one holds new ideas back and leaves only deeply fallen shares worth a look.
- HOW TO SPOT IT: The weather banner at the top of the page. On any index chart, check whether the line is above or below its recent average, and which way that average points.
- DO THIS NEXT: Check the banner before reading anything else, and treat every idea as fragile while it says the market is weak.
- CAREFUL: Every share tends to follow the market on a bad day, however good its own chart looks.
- copy note: Plain after this round's 'deep-value bargains' fix.

**`risk_pct`** - How much you are risking

- HEADLINE (58 chars): The distance to your stop, as a share of the price you pay
- WHAT IT IS: The percentage of your entry price you would lose if the safety line is hit.
- HOW TO USE IT: Up to about 5% is acceptable, and more than that means the system skips the idea. A wide stop also means a smaller position.
- HOW TO SPOT IT: The risk percentage column on the research page. Compare where the pause low sits with the price you would pay.
- DO THIS NEXT: Check the distance before deciding on a position, and wait for a tighter pattern when it is too wide.
- CAREFUL: The figure is planned distance only; a gap down can lose more than planned.
- copy note: The 5% line is in `use`; `spot` names the column.

**`sector_rs`** - Sector strength

- HEADLINE (56 chars): A strong share in a strong industry has wind at its back
- WHAT IT IS: How the stock's industry group is performing compared with other groups.
- HOW TO USE IT: Top-three industries are allowed for a new idea. Leading means beating other groups over the past one to three months.
- HOW TO SPOT IT: The industry strength column on the research page, or compare a few industry charts over the past month.
- DO THIS NEXT: Check the industry ranking whenever a chart looks good, and be more sceptical when the group is weak.
- CAREFUL: A weak industry can drag a good-looking chart down with it.
- copy note: Metaphor headline; decision content (top-three gate) is in `use`.

**`setup`** - The pattern we look for

- HEADLINE (61 chars): A strong rise, then a quiet pause - that pause is the pattern
- WHAT IT IS: A stock that climbed hard, then went quiet and sideways just above its recent average price.
- HOW TO USE IT: A real climb followed by a calm, quiet pause is the one shape worth watching. Excitement at the top of a long run is not the pattern.
- HOW TO SPOT IT: Find the flat, boring stretch after a climb. On the chart it sits between the green trigger line and the pink stop line.
- DO THIS NEXT: Wait for the price to push above the pause before doing anything with it.
- CAREFUL: All five plain checks have to pass together; four out of five is not the pattern.
- copy note: The pattern in one line - the most-clicked key in the app.

**`shape_score`** - How tidy the pause is

- HEADLINE (57 chars): A tidy, even pause continues more often than a jagged one
- WHAT IT IS: A tidiness grade from 0 to 100 for the sideways pause.
- HOW TO USE IT: Above 60 is a clean pause and below 40 is messy. Use it to choose between two names that look otherwise alike.
- HOW TO SPOT IT: The how tidy the pause is row under Show setup details, shown as a figure out of 100.
- DO THIS NEXT: When two names look alike, read the tidier one first.
- CAREFUL: A high grade measures tidiness, not what happens next.
- copy note: Relative claim ('more often than'), which is what the score can support.

**`signal`** - A recorded setup

- HEADLINE (56 chars): A pattern match written down before the result was known
- WHAT IT IS: A dated record that a stock matched the pattern, with the trigger, stop and goal frozen at that moment.
- HOW TO USE IT: Read many of them, never one. The tally of finished outcomes is the only honest scorecard the system has.
- HOW TO SPOT IT: Rows in Short-Term Ideas and in Every Idea We Recorded. The badge at the end of the row says WIN, LOSS, TIMEOUT or OPEN.
- DO THIS NEXT: Judge the method on the whole list rather than on the newest row.
- CAREFUL: One record proves nothing either way.
- copy note: States why the record exists rather than what it is.

**`sizing`** - How much money to put in

- HEADLINE (51 chars): How many shares keeps one loss small and survivable
- WHAT IT IS: A suggested number of shares based on your total capital and how far away your safety line is.
- HOW TO USE IT: A wider distance to the stop means fewer shares, and a hard maximum keeps any single idea from dominating the account.
- HOW TO SPOT IT: The position-size box on the research page. It turns the distance to the stop into a number of shares.
- DO THIS NEXT: Check the loss at the suggested size and compare it with the rest of the list before deciding.
- CAREFUL: Size decides how a bad streak feels, not how often one happens.
- copy note: Answers the owner's own question ('how many shares').

**`sources`** - Where the numbers come from

- HEADLINE (47 chars): If a source breaks, the numbers still look fine
- WHAT IT IS: A live health list of every outside service the system reads from.
- HOW TO USE IT: Every source needs to show healthy with a recent success. Warnings and errors are informative, not cosmetic.
- HOW TO SPOT IT: The source health box on the System page. It lists each outside service with its last success and its last error.
- DO THIS NEXT: Check the source list first whenever many results look wrong at once.
- CAREFUL: A quiet connector can fail for days while the numbers still look plausible.
- copy note: Rewritten this round: the old headline trailed off ('...but is not').

**`stop`** - The point where you admit you were wrong

- HEADLINE (58 chars): The price that proves you wrong, decided before you commit
- WHAT IT IS: A price chosen in advance, below your entry price, where the idea has clearly failed and the loss stays small.
- HOW TO USE IT: Usually just below the low of the quiet pause. If that price is more than about 5% below your entry price, the idea is skipped as too risky.
- HOW TO SPOT IT: The pink stop line on the chart and the stop column of the ideas table. It is the lowest point of the flat pause.
- DO THIS NEXT: Confirm the stop level before the idea begins, and leave it where it was set.
- CAREFUL: Widening the stop after the idea begins is how a small planned loss turns into a large one.
- copy note: Plain and decision-first; the 5% band is in `use`.

**`target`** - The point where you take profit

- HEADLINE (55 chars): Chosen in advance: three times your risk, not a feeling
- WHAT IT IS: A price above your trigger where the plan says the idea is finished.
- HOW TO USE IT: A target sitting close to your trigger means little is being asked of the price. Further away means more has to go right.
- HOW TO SPOT IT: The dashed blue line labelled Target 3R (three times the money risked) on the chart, and the Target column of the ideas table.
- DO THIS NEXT: Fix the number before you decide anything, then work out where you would move the stop up to.
- CAREFUL: The hit-rate table shows how often targets of this size were actually reached.
- copy note: The three-times-risk default is up front.

**`veto`** - Automatic disqualification

- HEADLINE (56 chars): A blocked name is blocked, whatever the chart looks like
- WHAT IT IS: A rule that blocks a stock because its company finances look unsafe, regardless of how good the chart is.
- HOW TO USE IT: It blocks when debt is far above profits, when the return on capital is very low, or when the owners hold very little of their own company.
- HOW TO SPOT IT: The blocked label on a name, and the company-finance rows on the research page. None of it is visible on a chart.
- DO THIS NEXT: Check whether a name is blocked before studying its chart, and move on when it is.
- CAREFUL: A missing company figure passes the check by default, which is a known weakness.
- copy note: Absolute and unambiguous.

**`volume`** - Trading quietness

- HEADLINE (45 chars): Quiet trading during a pause is the good sign
- WHAT IT IS: Whether the number of shares changing hands has gone quiet.
- HOW TO USE IT: Volume clearly below its recent normal is what you want to see. The last few days are compared with the average of the past month.
- HOW TO SPOT IT: The volume bars under the price chart. Are the recent bars visibly shorter than the ones before them?
- DO THIS NEXT: Check the volume bars whenever the price drifts sideways, and wait while the trading is still heavy.
- CAREFUL: Heavy trading during a pause usually means a large holder is leaving.
- copy note: One sign, stated.

## 2. Tier split and copy provenance

Three different things could be called a "tier", so they are separated here:

**Renderer tier (what the browser used)** - measured, not assumed:

- Tier 1 (authored entry): **27/27 keys**.
- Tier 2 (derivation bridge, `look`/`sight`/`when`): **0/27 keys in use**; the
  code path is proved with a stubbed legacy payload (section 5).
- Tiers 3/4/5 apply only to keys with no explain.py entry at all.

**Copy provenance (who wrote the words)** - this is what the owner should
know, because "hand-authored" and "derived then edited" read differently:

- **Hand-authored (12)** - spec section B.2, written for this card:
  `setup`, `signal`, `p_win`, `target`, `composite`, `data_quality`, `hit_rate`, `mfe`, `mae`, `pullback`, `impulse`, `shape_score`.
- **Derived then edited (15)** - the headline is the spec's (C.3); `use` was
  carried across from the old `look` band, `spot` from `sight` (plus `where`),
  `action` from `when`, and each one was then rewritten for the budget law,
  the no-advice law and the acronym gloss. **These 15 are the provisional
  copy**: `regime`, `breadth`, `volume`, `accum`, `delivery`, `sector_rs`, `stop`, `risk_pct`, `sizing`, `r_multiple`, `expectancy`, `profit_factor`, `max_drawdown`, `veto`, `sources`.
- **Generated, not authored (16)** - ideal-only keys get the Tier-3 card in
  section 4. Only the headline and definition vary; `use`/`spot`/`action` are
  the same two sentences for all 16. This is the largest remaining copy gap.
- **Unreachable (6)** - `accum`, `breadth`, `delivery`, `expectancy`,
  `profit_factor`, `max_drawdown` exist in explain.py and /glossary but no
  element on screen carries their `data-explain`, so the owner cannot tap
  them. Wiring them needs app.js/cards.js, which are not in my scope.

## 3. Copy review as a non-finance reader

For every key: the first thing shown is the headline, and it is the one thing
that matters (per-key notes are in section 1). Jargon sweep over
`what`/`use`/`spot`/`action`/`caution`/`headline`: **no bare acronyms**; the
only technical terms left are ones the app itself shows as panel names
(`accumulation`, `delivery`, `pattern`), each explained by its own card.

Copy fixed in this round (9 fields on 7 keys, plus one renderer fix):

| key.field | before | after | why |
|---|---|---|---|
| `max_drawdown.headline` | The worst fall from a peak, in R; the number that tests nerve | The deepest fall from a peak, in units of risk | bare `R` acronym in a rendered field |
| `max_drawdown.spot` | The worst fall from a peak figure on the performance page. | The figure labelled worst fall from a peak on the performance page. | grammar; keeps the on-screen label |
| `p_win.caution` | This score is uncalibrated and has been wrong in bulk before ... | This score is a rough machine guess and has been wrong in bulk before ... | "uncalibrated" is jargon for a non-finance reader |
| `regime.use` | ... leaves only deep-value bargains worth reading. | ... leaves only deeply fallen shares worth a look. | "deep-value" is jargon |
| `sizing.use` | A wider distance to the stop means fewer shares. Hard ceilings stop any single idea ... | A wider distance to the stop means fewer shares, and a hard maximum keeps any single idea ... | plainer; one sentence |
| `mfe.spot` | The row labelled MFE in R - the best moment, counted in units of risk - on the research page, shown as ... | The row labelled MFE in R on the research page - MFE means the best moment, counted in units of risk. It shows ... | on-screen label first, gloss after |
| `mae.spot` | The row labelled MAE in R - the deepest dip against you, counted in units of risk - ... | The row labelled MAE in R on the research page, directly under the best-moment row - MAE means the deepest dip against you, in units of risk. | same |
| `sources.headline` | If a data source breaks, everything looks fine but is not | If a source breaks, the numbers still look fine | headline trailed off |
| `sources.spot` | ... on the system page. | ... on the System page. | consistency with `data_quality` |
| `explainer.js` `bandPhrase()` | first segment before `;`, `(` or ` - ` | longest leading segment that still fits 70 chars, comma/parenthesis aware | the `pe` Tier-3 headline was cut mid-phrase: "The level we look for here is under 15x, ideally near or below its" |

Earlier rounds (same shipped file) also removed: `mfe`/`mae` headlines
"counted in R" -> "measured in risk"; `mae.action` "without selling" ->
"without exiting"; `accum.use` "buying pressure" -> "demand"; `accum.caution`
"who is buying" -> "steady interest"; `delivery.action` "real buying" ->
"evidence of real holding"; `delivery.caution` "steady buying" -> "steady
accumulation"; `r_multiple` spot/action/caution de-jargoned; `target.spot`
`3R` and `pullback.spot` `PB` glossed; `hit_rate` R glossed in `use` and `spot`.

## 4. Tier 3 - the 16 clickable keys with no authored entry

```
node tools/ui-audit/eval.mjs --url http://127.0.0.1:8022 --hash "#research/KEI" \
     --wait 6000 --expr-file %TEMP%\ideal16.js
```

Each key is clicked with the exact sibling `.ideal-chip` markup `ideals.js`
produces, built from the live `/api/ideals` response (21 bands).

| key | band found | tier | rows | headline chars | raw key printed as a word | title shown | headline |
|---|---|---|---|---|---|---|---|
| `debt_to_equity` | yes | 3 | 4 | 40 | no | Borrowing vs own money | The level we look for here is below 0.5x |
| `roce` | yes | 3 | 4 | 41 | no | Return on capital | The level we look for here is 15% or more |
| `roe` | yes | 3 | 4 | 41 | no | Return on shareholder money | The level we look for here is 15% or more |
| `operating_margin` | yes | 3 | 4 | 41 | no | Profit kept from each sale | The level we look for here is 15% or more |
| `net_profit_margin` | yes | 3 | 4 | 41 | no | Profit left at the end | The level we look for here is 10% or more |
| `interest_coverage` | yes | 3 | 4 | 40 | no | Cushion for interest bills | The level we look for here is 3x or more |
| `cfo_positive` | yes | 3 | 4 | 49 | no | Cash actually coming in | The level we look for here is yes, cash coming in |
| `pe` | yes | 3 | 4 | 39 | no | Price vs yearly profit | The level we look for here is under 15x |
| `pb` | yes | 3 | 4 | 40 | no | Price vs book value | The level we look for here is under 1.5x |
| `peg` | yes | 3 | 4 | 40 | no | Price paid for growth | The level we look for here is under 1.0x |
| `dividend_yield` | yes | 3 | 4 | 40 | no | Yearly cash paid to owners | The level we look for here is 3% or more |
| `sales_growth_3y` | yes | 3 | 4 | 48 | no | Sales growth, 3 years | The level we look for here is 15% or more a year |
| `profit_growth_3y` | yes | 3 | 4 | 48 | no | Profit growth, 3 years | The level we look for here is 15% or more a year |
| `promoter_holding` | yes | 3 | 4 | 41 | no | How much owners keep | The level we look for here is 50% or more |
| `pledge_pct` | yes | 3 | 4 | 38 | no | Owner shares pledged as collateral | The level we look for here is under 5% |
| `fii_holding` | yes | 3 | 4 | 41 | no | Held by foreign institutions | The level we look for here is 10% or more |

Machine checks: all 16 `tier==3`: **True**; all 16 with 4 rows: **True**; any
`.ex-foot`: **False**; any raw key printed as a word: **False**; legacy attr:
**False**.

## 5. The five-tier ladder, proved on 8022

```
node tools/ui-audit/eval.mjs --url http://127.0.0.1:8022 --hash "#research/KEI" \
     --wait 6000 --expr-file %TEMP%\popup-eval.js
```

| case | tier | legacy attr | dialog open | rows | headline chars | `.ex-foot` absent | footnote | key in visible text |
|---|---|---|---|---|---|---|---|---|
| tier1-new-entry (p_win) | 1 | - | True | 4 | 63 | True | False | False |
| tier2-legacy-bridge (legacy_demo, stubbed fetch) | 2 | 1 | True | 4 | 68 | True | False | False |
| tier3-ideal-band (roce) | 3 | - | True | 4 | 41 | True | False | False |
| tier3-band-from-api (roe, no chip) | 3 | - | True | 4 | 41 | True | False | False |
| tier4-unknown-key (zzz) | 4 | - | True | 2 | 45 | True | True | False |
| tier4-empty-entry (empty_demo) | 4 | - | True | 2 | 45 | True | True | False |
| tier5-failed-fetch (tier5_demo) | 5 | - | True | 2 | 33 | True | False | False |

- Tier 1: real DOM element `[data-explain=p_win]`, real API.
- Tier 2: `fetch` stubbed with a legacy entry (no headline, no `use`/`spot`/
  `action`). Derived headline = first sentence cut on a word boundary (68
  chars), rows filled from `look`/`sight`/`when`, `data-explain-legacy="1"`.
- Tier 3: `roce` with a chip, and `roe` with no chip at all (band read from
  the loaded `/api/ideals` data).
- Tier 4: made-up key `zzz`, and an entry of `{}` (invariant 4).
- Tier 5: `fetch` forced to reject.

## 6. /glossary is untouched and complete

```
curl.exe -s http://127.0.0.1:8022/glossary
```

Measured on the response: **27** `class="gterm"` sections (one per key),
**27** "How it is worked out" rows (the method text survives), 33,654
characters. Spot checks: `Market weather` 1 hit,
`Quiet accumulation` 1, `Worst fall from a peak` 2 (performance-page
reference + glossary row), `R - one bite of risk` 1.

`/glossary` is server-rendered by glossary_ui.py and does not load
explainer.js, so the popup rework cannot affect it. It reads the legacy
seven-question list, which explain.py still carries beside the new card
fields (additive rollout).

## 7. Budget-law result (all 27 entries)

Script: `%TEMP%\check_explain.py` (imports explain.py, no repo changes).
Checks per key: headline non-empty, <=70 chars, no trailing full stop, <=1
sentence; `what`<=240, `use`<=260, `spot`<=240, `action`<=140,
`caution`<=120; no field over 2 sentences; no advice stems
(buy/buying/bought/sell/selling/sold/should/must/recommend/guarantee) in
`use`/`spot`/`action`/`caution`; no rupee amounts there; no markup
characters; every `MFE`/`MAE`/`R`/`EMA`/`P95`/`ROCE`/`PE`/`D/E` token
carries a plain gloss in the same field (headline included); `popup()`
returns exactly 4 non-empty rows.

Result: **27 keys, 0 failures**, jargon watch 0. Headline lengths 45-69
(longest `hit_rate` 68). Every field inside budget; every key has a
caution line, and each caution is a specific trap rather than boilerplate.

## 8. Syntax, tests, mobile audit

- `node --check terminal/static/explainer.js` -> OK.
- `.\env\Scripts\python.exe -m unittest discover -s . -p "test_*.py"` ->
  **Ran 36 tests ... OK**, exit code 0.
- `node tools/ui-audit/audit.mjs --url http://127.0.0.1:8022 --routes research
  --viewports 375x812 --settle 6000` -> **PASS**, 1/1 clean, page-level
  overflow 0px, no single-word line breaks, no text outside its own box.

## 9. Not verified, and caveats

1. **16 ideal keys carry generated copy.** The card is useful and correct
   (level + definition + generic advice), but it is not authored per
   measure. Authoring those 16 short cards is the next real copy job.
2. **6 keys are unreachable from the UI** (section 2, "Unreachable").
   Content is verified; wiring a `data-explain` onto the relevant panel is
   not in my write scope.
3. **Tier 2 is code-only right now.** No live key needs it, so it is proved
   with a stubbed fetch, not with a live key.
4. **The sweep drives throwaway elements**, not the 93 real tagged elements
   on the page. The real-element path is separately proven for `p_win`
   (tier 1) and `roce` (tier 3) in section 5. `ideals.js` produced 0 chips on
   `#research/KEI` in headless Chrome (no matching fundamentals rows on that
   route), which is why the Tier-3 run supplies the exact chip markup itself
   as well as the no-chip `/api/ideals` path.
5. **The readability notes in section 1 are my judgement**, not the owner's.
   Nothing here replaces the owner reading two or three cards.
6. **Other teammates' concurrent work** (terminal/static/app.js and
   fintech.css chart rework) was not part of this verification. It did not
   affect my files or the runs above; the 375px audit passed at the moment I
   ran it.
7. **glossary_ui.py**: one minimal edit was made in the previous assignment
   round (read the method text under either `how` or `method`). It was
   read-only in this round and was not touched; /glossary is verified working.

## 10. Reproduce

```
# server (login gate removed)
.\env\Scripts\python.exe -m uvicorn terminal_api:app --host 127.0.0.1 --port 8022

# budget law
.\env\Scripts\python.exe %TEMP%\check_explain.py

# browser evidence (expr files and JSON output live in %TEMP%)
node tools/ui-audit/eval.mjs --url http://127.0.0.1:8022 --hash "#research/KEI" --wait 6000 --expr-file %TEMP%\sweep27.js
node tools/ui-audit/eval.mjs --url http://127.0.0.1:8022 --hash "#research/KEI" --wait 6000 --expr-file %TEMP%\ideal16.js
node tools/ui-audit/eval.mjs --url http://127.0.0.1:8022 --hash "#research/KEI" --wait 6000 --expr-file %TEMP%\popup-eval.js

# glossary, syntax, tests, audit
curl.exe -s http://127.0.0.1:8022/glossary
node --check terminal/static/explainer.js
.\env\Scripts\python.exe -m unittest discover -s . -p "test_*.py"
node tools/ui-audit/audit.mjs --url http://127.0.0.1:8022 --routes research --viewports 375x812 --settle 6000
```

Note for a future reader: uvicorn here runs without `--reload`, so explain.py
edits need a server restart before the browser sees them. One sweep in this
round initially showed the pre-fix `max_drawdown` headline for exactly that
reason; every table above was generated after a restart.
