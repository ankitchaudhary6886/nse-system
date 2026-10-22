# EXECUTION LOG — durable record of every code batch

Purpose: survives chat migrations. New session reads `backlog.md` +
`EXECUTION_LOG.md` + `PORTAL_REDESIGN.md` and knows the full history.

Format: numbered batches. Session boundaries marked.
Status legend: DEPLOYED · VERIFIED · PARTIAL · REJECTED · AWAITING

---

## RECENT - last 6 entries (full text)

### #109 - Phase 1 close-out: delete the write-only weight from radar and the universe payload - DEPLOYED · VERIFIED

- **Why:** Phase 1's own deliverable is "a portal that is fast to use". The nav
  and noise work (#106) is done; what remained from the clutter audit was
  weight that is **paid for on every request** and never read.

- **Deleted** — each re-verified against the tree first, because several audit
  lines had drifted:
  - **`/api/radar` → `events`.** A `SELECT … FROM events` ran on *every* radar
    call, built a list, and shipped it in the JSON. No frontend file reads
    `.events`. Query and key both removed. Live check: the endpoint now returns
    exactly `groups, total` (1,535 symbols, all three groups intact).
  - **Six fields from `/api/research-universe`** — `latest_close`,
    `pct_from_52w_low`, `p_4r`, `p95_mfe_r`, `p5_mae_r`, `current_setup`. The
    universe table's `_COLUMNS` renders none of them; it *does* render
    `pct_from_52w_high`, which was kept. Live check: 52 rows × 13 row keys.
    **Nuance worth keeping:** `research.js` genuinely uses all six on the
    **symbol-detail** endpoint, which is a different builder (`analyze_symbol`,
    not `analyze_universe`). The audit was right only for the universe payload,
    so a blind repo-wide "unused field" grep would have been wrong in both
    directions.
  - **`#screenerBadge`** — a stray "—" badge nothing ever wrote to and the
    first screener run destroyed. Exactly one reference, confirmed before
    removal.
  - **`#methodologyBlock` id** — an unused id only; the `<details>` block stays.

- **Deliberately not changed, with the reason recorded in the audit:**
  `deployment.js` was **already gone** (F-08), so that item needed nothing.
  The radar `x.sector` read was left — `renderUnifiedCard` is shared and one
  dead `|| ""` is not worth the blast radius. The `_safeId` / `_num` duplicate
  globals were left because deleting the shadowed copy only trades a duplicate
  for a load-order dependency. The 14 uncalled routes remain owner-gated.

- **Verification:** `py_compile` clean on both touched modules; a live uvicorn
  smoke test returned `/api/health` **200**, `/api/radar` keys `groups,total`,
  and `/api/research-universe` 52 rows × 13 keys; full suite **365 tests, OK,
  exit 0**. No `?v=` bump — no static JS or CSS changed, and `index.html` is not
  cache-busted.
- **Deploy:** the VM pulled `e5b3556`; `Active: active (running)` and
  `/api/health` **200**. Confirmed **in production**, not merely locally:
  `/api/radar` now contains `groups` and `total` and **zero** `events` keys;
  `/api/research-universe` contains 52 × `pct_from_52w_high` and **zero**
  `current_setup`. The restart did not disturb the running League replay (a
  separate detached process), which kept advancing through the deploy.

### #108 - The F-15 deploy exposed two League defects: F-27 fixed, F-28 recorded - DEPLOYED · VERIFIED

- **What happened.** The #107 deploy itself was healthy — service active,
  health 200, 23-job banner — but the League replay it correctly triggered died
  instantly with `NameError: name 'U' is not defined` at `trader_league.py:674`.
  The failure was **not** caused by #107: that line arrived with `3057927`
  (2026-10-05) and nothing had executed it since, because no replay had run.

- **F-27 (fixed).** `build_context` called `U.band_universe` while the module
  imports `universe_helper` only locally (`from universe_helper import
  band_universe`, lines 504 and 980) — there is no `U` anywhere in the file. So
  every replay needing market gates or sector ranks (`home` / `singhal` in the
  slug list) had been impossible for **18 days**. Fixed at the call site in the
  file's own style. Verified live: the re-run logged
  `context ready in 5.5s (benchmark ^NSEI, 774 dates)` — the exact statement
  that previously raised.
  Why it hid: `NameError` is a call-time error, so import checks pass;
  `selftest` never enters that branch; live runs never call it. 365 green tests
  and a green `selftest` both missed it.

- **F-28 (found, recorded, deliberately not fixed yet).** Worse than the crash:
  `--fresh` deletes the player's signals **and** `league_progress` rows at lines
  985–990, *before* `build_context` at line 1010. `status()` reads `code_hash`
  back out of `league_progress` (line 2313), so with those rows deleted
  `code_changed` became `False` and `--changed` announced *"No player's code or
  settings changed since its replay — nothing to redo."* — while all 11 books
  sat at 0 signals. The repair command had been blinded by the damage it exists
  to repair. Recovery was an explicit `--fresh --players` list for all 11; the
  documented fix (delete last, not first) is in F-28 and is **not** applied.

- **Verification:** `unittest discover` → **365 tests, OK, exit 0** after the
  fix; the VM pulled `a186dc9`, `Active: active (running)`, `/api/health`
  **200**; the replay is running at 865 stocks × 3 years and writing signals.
- **Register lesson recorded:** green tests plus a green `selftest` do not cover
  every executable line. A change that touches a scheduler or CLI path must be
  *run* through that path, not merely imported.

### #107 - F-15 duplication closed where provable; screener VCP blocked on evidence - DEPLOYED · VERIFIED

- **Why:** F-15 was the last duplication item left from the 2026-10-19 survey,
  and the owner signed off ("do the needful"). It changes numeric behaviour,
  so every item needed before/after evidence before it could ship.

- **1. Yahoo direct call sites → one chain (FIXED, 14 files).** Every
  `yf.Ticker` / `yf.download` in the app now goes through `data_sources`:
  `fetch_price_history()` (daily OHLCV via `PRICE_HISTORY_PROVIDERS`) and
  `fetch_yahoo_field()` (one non-price `Ticker` field per call, preserving the
  old per-attribute failure isolation). New shared plumbing: `yahoo_ticker()`
  (adds `.NS` unless `^`-prefixed or already `.NS`), `_period_to_start()`
  (turns `5y` / `2y` / `1mo` into a concrete start date for the non-Yahoo
  providers), `YahooFieldAdapter`, and `end=` on the price adapter. A
  repo-wide grep now finds **zero** `yf.Ticker` / `yf.download` /
  `import yfinance` outside `data_sources/`. `auto_adjust=True` is preserved
  inside the adapter, so call sites that dropped the explicit kwarg
  (`traders/larry_spears.py`) keep adjusted prices — this was the one change
  in the batch that could have silently altered League benchmark returns, and
  it was checked directly rather than assumed.
  **Evidence:** 15 of 19 spot pairs **byte-identical**. The 4 diffs are fully
  characterised: `period=5y` DIXON/HDFCBANK (same 1237 rows, identical index
  and Volume) differ on ≤496 rows by Yahoo's float32 dividend-adjust factor —
  max relative error **2.3e-7 / 3.5e-7**, max Close deviation **0.0005 INR**,
  constant per-segment ratio ≈1 ± 4e-7, deterministic on re-run; and
  `_from_yahoo` DIXON.NS plus `fetch_index_data` ^NSEI differ only by tz-naive
  vs `Asia/Kolkata` and extra `Dividends` / `Stock Splits` columns, with
  **0 differing value cells**. The screener is tz-safe because each frame
  comes from exactly one source and `evaluate_stock` only uses `idxmax` /
  `get_loc` / label-slicing / `index[-1].date()`.

- **2. Stage-2/VCP — BLOCKED, deliberately not applied.** Over 745
  mutually-evaluated symbols the old `evaluate_stock` and the canonical
  `scanner.Screener.evaluate` + `setup.SetupDetector.detect` disagree on
  **VCP in 50 cases (old 13 pass vs canonical 41)**, `overall_signal` in 33
  (7 vs 28), `impulse%` on all 41 comparable pairs, `pullback%` on 41,
  `days_since_high` on 19, `momentum` on 5 (272-bar vs 240-bar gate), plus one
  baseline vol-window difference (INDOTECH `vol_sma50[i-1]` vs `vol_sma[i]`).
  Equivalent behaviour is unachievable without changing what the screener
  flags by ~3×, so `evaluate_stock` was left **completely untouched** — there
  is no partial edit to restore. Choosing which definition is authoritative is
  now an **owner decision, not a bug**.

- **3. Forward simulation — already consolidated, verified.** The pre-B5
  bodies recovered from `git show 3057927~1` were run against the surviving
  wrappers: **17,124 cases, 0 diffs** (HOLD_BARS=30, TRIGGER_WINDOW=3
  throughout). No edits were needed.

- **4. Sector PE medians — de-duplicated.** `positional_scanner._sector_pe_medians`
  deleted (along with the then-unused `import statistics`); the module imports
  `scoring.sector_pe_medians`. **11 sectors, 0 differing medians.**

- **Verification:** `unittest discover` → **365 tests, OK, exit 0** (confirmed
  by an independent run, not just the implementation run); `py_compile` clean
  and import clean on all 18 touched modules.
- **Deploy:** the VM pulled `f71234d`; `Active: active (running)`,
  `/api/health` **200**, and the scheduler banner reports **23 jobs** including
  all four that the old hand-written line omitted. This push also shipped
  #106. Because `traders/larry_spears.py` changed (import swap only), the
  League `code_hash` moved and `trader_league.py replay --changed` was run:
  `selftest` **28/28**, and then the replay **crashed immediately** on a latent
  `NameError` — `build_context` called `U.band_universe` with no `U` import,
  broken since `3057927` on 2026-10-05 and unrelated to this batch. Found,
  fixed and re-run the same day; see **F-27**. This is the concrete reason the
  "verify through the real path" rule exists: 365 green tests and a green
  `selftest` both missed a line that only the replay executes.
- **Deliberately left:** the two thin `simulate_forward` wrappers — verified
  byte-equivalent, and they are call-site shims rather than duplication.

### #106 - Kelly and machine-chosen sizing removed, scheduler banner derived, Phase 1 portal reorg - DEPLOYED · VERIFIED

- **Why:** the 2026-10-19 survey left three items owner-gated (F-12 sizing,
  F-15 duplication, scheduler banner) and the owner approved them together
  with a full Phase 1 portal overhaul — "clutter-free, minimal, dynamic,
  lively, easy to understand". Credential work was explicitly excluded and
  was not touched.

- **Item 1 — the machine no longer sizes (F-12 → RESOLVED by owner call).**
  `sizing.suggest()` no longer returns `kelly_pct`, `half_kelly_pct`,
  `p_win` or `payoff_b`, and it no longer proposes a quantity at all:
  `shares`, `suggested_value`, `risk_amount`, `actual_alloc_pct`,
  `actual_planned_risk_pct`, `value_by_risk_cap`, `binding_cap` and
  `actionable` went with them. What is left is capital, the two caps, the
  regime/shape multipliers, and `risk_pct` — the stop distance, a property
  of the prices rather than a size. The panel is now **"Position limits
  (you choose the size)"**: capital and risk cap by default, allocation cap
  and stop distance one tap away. The research page's *Try your own numbers*
  calculator is **kept on purpose** — it is the instrument the owner uses to
  pick a size, and it only turns the owner's own price, stop and capital
  into consequences.
  **Overlap audit (asked for explicitly):** exactly three Python consumers
  exist (`/api/sizing/{symbol}` is a pass-through, `/api/sizing/capital`,
  and the test); only `app.js` read the quantity fields; `p_win` had no
  sizing consumer anywhere; and `research.js` never receives `sizing_response`
  (that key is populated nowhere in the repo), so the mirror runs on its own
  fallbacks and could not break. Corrected the false "half-Kelly" claims in
  PROJECT_HANDOFF §5 and its 2026-09-07c entry, F-12, MEMORY, JOIN_HERE,
  SUBAGENTS and PORTAL_REDESIGN Idea 8. Left `MARKET_WISDOM` §2.7 and
  `traders/wisdom.py` untouched: they are sourced market knowledge, not
  claims about this codebase, and editing `traders/*.py` changes the League
  `code_hash` and would force a replay.

- **Item 4 — the scheduler banner can no longer drift.** The hand-written
  startup line listed 19 of the 23 jobs, silently omitting `official_eod`,
  `official_eod_retry`, `governance_feed` and `fyers_token`. It is now
  derived from `_scheduler.get_jobs()` with a new `_when()` trigger
  renderer, so the banner *is* the registered schedule by construction.

- **Items 5+6 — Phase 1 as written.** The top nav is now exactly the five
  named destinations **Funda / Swing / Research / Ledger / System**, in both
  the sidebar and the header pill rail (was 8 destinations and 21
  affordances). `Trading methods` and `Paper league` were **not** deleted:
  they are reached through segmented in-view tabs under Research and Ledger,
  so every existing loader and `league.js`'s replay poll keep working
  untouched, and `NAV_HOME` in `setView()` keeps the parent nav item lit
  while you are inside them. The glossary moved out of `<nav>` into a
  labelled Reference group.
  - **Biggest cuts:** Chart Patterns now shows the strongest 10 of 60 by
    default with **Show all 60** (that one panel was measured at 17,366px —
    78% of the research page); DTW Shape Matches folded behind a toggle; the
    only always-visible disclaimer subtitle became a tooltip, so it is still
    one tap away and still permanent in the methodology block.
  - **Correctness:** the "Graded win rate" tile was showing
    `swing_signals` data while linking to the **Ledger** — it is now
    **Swing win rate** and links to Swing, so label, value and destination
    agree. The "Companies you can research" tile was showing
    `universe_broad`'s row count while opening the research-universe panel —
    it is now written *by that panel* (`_setUniverseTile`) and
    `loadRadar()` no longer touches it.
  - **Understandability:** three rows all captioned "Status" are now
    "Universe freshness" / "Sector freshness" / "Pattern freshness".
    `setStatusRow` keeps the caption a row was given instead of overwriting
    it, and the three pattern status branches now use the same renderer.
  - **Rejected one audit recommendation:** clutter-audit item 7 says to
    merge the Funda and Swing strategy panels. They are filtered separately
    (`loadStrategyListFor("fundamental")` vs `("swing")`) and merging them
    would break the owner's 2026-09-26 decision that Funda and Swing keep
    their own universes. Both were kept; Swing's byte-identical subtitle was
    replaced and its missing help affordance added.
  - **Lively:** a new motion layer in `fintech.css` — view entrance,
    staggered panel rise, hover lift on nav / tabs / tiles / panels, an
    accent bar on the active destination, and focus-visible outlines. Only
    transform and opacity animate, so layout (and ui-audit geometry) never
    moves, and every rule collapses to the finished state under
    `prefers-reduced-motion`.

- **Verification:** `unittest discover` → **365 tests, OK, exit 0**
  (363 + the two rewritten sizing tests); `py_compile` clean;
  `node --check` clean on `app.js`, `research.js`, `research_universe.js`,
  `league.js`; a banner probe asserted 23 registered jobs and that every id
  appears in the banner (`RESULT: PASS`, exit 0). `?v=` bumped for
  `fintech.css` (5), `app.js` (22), `research.js` (19),
  `research_universe.js` (19).
- **Split out:** item 3 (F-15 duplication) is being handled separately — it
  changes numeric behaviour and needs its own before/after equivalence
  evidence and its own deploy.

### #105 - Register truth pass, three code fixes (F-10/F-11/F-13), new defect F-26 - DEPLOYED · VERIFIED
- **Why:** the session began by loading the mandated bootstrap
  (MEMORY → JOIN_HERE → FINDINGS) and every one of them disagreed with the
  code. The registers were verified 2026-10-05 @ `f483e68`; HEAD was `fe0f09d`
  ~15 commits later. Re-verified all 25 entries against on-disk source **and**
  against production over SSH rather than trusting any of it.
- **Cleared (were already fixed, still advertised as broken):** F-01 laptop DB
  (synced by the 2026-10-18 rebuild → `prices_daily` 2026-10-16), F-04 pattern
  gate (`settings.pattern_gate` populated 2026-10-18 with real win rates,
  `pattern_grades` = 59,697 vs the register's 0), F-08 (`deployment.js` no
  longer exists), F-09 (`daily_update` already runs `ml` **before** `scan`;
  chain is now 12 stages — `fyers` and `breadth` added).
- **RETRACTED F-07 as a false positive.** The entry assumed
  `research_sector.js` was an ES module. It is loaded as a **classic script**
  with no IIFE, so its top-level `function loadResearchSectors` already lands on
  `window`. Proved in the production browser instead of by reasoning:
  `typeof window.loadResearchSectors === "function"`, research scripts all
  `type: "classic"`, console **zero** errors. No fix applied — recording this
  stopped a one-line "fix" that was solving a non-problem.
- **SUPERSEDED F-05.** `Depends(verify_user)` now matches **0 times** — the
  gate was removed wholesale on 2026-10-07 (owner decision). The register still
  described opt-in-per-route auth and recommended re-adding a global dependency,
  which would have contradicted MEMORY §10. Rewrote it as "no auth anywhere, by
  design"; residual password/Telegram-token exposure in **git history** noted as
  rotation-gated (bot token already untracked in `3fd912f`).
- **FIX F-11 (real, live in production):** `data_quality.py` ran
  `DELETE FROM data_quality_log` on every run — production held **6 rows from a
  single run** (`2026-10-18T18:53`), so the audit trail was erased daily. Now
  appends, then prunes to `HISTORY_RUNS = 60` distinct runs. Verified: a seeded
  420-row / 70-run table prunes to 119 rows / 60 runs — retained and bounded.
  Nothing reads the table for display, so no UI impact.
- **FIX F-13:** `swing_live` vetoes **before** its INSERT, then
  `alerts.notify_setup()` re-ran the same veto on a **second connection**; a
  disagreement would Telegram "setup suppressed" for a row already committed as
  `PENDING`. Alert functions now take the caller's verdict
  (`notify_setup(st, veto=None)`, `notify_all_weather(sym, st, veto=None)`).
  **Gate order in `swing_live.scan()` untouched** — this forwards step 9's
  result, it does not add or resequence a gate. Verified with a call-counting
  `fund_veto` stub: verdict passed in → 0 calls; bare call → 1 call.
- **FIX F-10:** `fundamentals_tv._universe` truncated an alphabetical list, so
  `run 100` meant first-100 A–Z. Now ranks by `mcap_cr DESC` (unknown caps
  last, name breaks ties) before truncating. Severity downgraded: the scheduler
  calls `run()` with **no** limit, so production was never affected.
- **NEW F-26 (the important one):** the agent bootstrap layer itself was stale
  and actively wrong — MEMORY §14 still listed **two CRITICAL** outages cleared
  two weeks earlier, so a fresh session was primed to "fix" a healthy system.
  Stale-*healthy* registers are more dangerous than missing ones because they
  carry the appearance of evidence. Added the standing rule: check
  `MANIFEST.json.generated_at` against `git log -1`; if the cache is older than
  the code, every severity label is provisional.
- **Docs corrected:** `MEMORY.md` §14 (+ date), `JOIN_HERE.md` (12-stage table,
  defect table, auth trap #8, last-verified, F-13 note), `FINDINGS.md` (STATUS
  REFRESH precedence block, 10 entry statuses, F-25 route count 62→76, new F-26,
  restored the `Verified-healthy` header), `nse-terminal-pipeline-ops/SKILL.md`
  (stage table, F-09/F-11/F-13 notes, diagnosis table), `nse-terminal-data-provenance/SKILL.md`.
- **Verification:** `unittest discover` → **363 tests OK, EXIT=0** (identical to
  the pre-change baseline); `py_compile` clean on all four; a purpose-built
  harness asserted each fix; `git push` → `fe0f09d..8eae8f8`; VM `git pull`
  fast-forward + `COMPILE_OK`; `sudo systemctl restart nse-terminal` →
  `Active: active (running)`; `journalctl --since` → **0 tracebacks**;
  `GET /api/health` → `200 {"ok":true}`.
- **Noted, not acted on (owner-gated):** F-12 sizing has no Kelly maths;
  F-17 agent-layer git tracking; credential rotation (password + Telegram token
  readable in git history); F-15 duplication changes numeric behaviour.
- **New minor observation:** `scheduler_bg.py` registers **23** jobs but the
  startup banner only prints **19** — `official_eod`, `official_eod_retry`,
  `governance_feed` and `fyers_token` never appear in the operator's at-a-glance
  list. The jobs do run; the banner string is simply behind.

### #104 - Ideal values, explainable model terms, per-book methods, winner/loser names - VERIFIED
- **Six owner-reported gaps fixed**, each verified on the live VM.
- **FIXED 500:** `/api/traders/matches/{symbol}` returned 500 because trader
  methods compute with pandas/numpy and the handler returned `numpy.bool_`
  straight to FastAPI's encoder ("'numpy.bool' object is not iterable"). Added
  `_jsonable()` in `terminal_api.py` to coerce numpy scalars recursively, applied
  to matches/errors. Endpoint now returns 200 with 14 books checked, 11 methods
  matched, 0 errors.
- **NEW `ideal.py`** - "actual vs ideal" bands for 21 measures, grouped into six
  plain-English sections (Business quality, Safety, Price you pay, Growth, Who
  owns it, Your plan and the market). Every band records its **source**, and the
  sources are the system's own rules first (strategy_config gates, scoring.py and
  fund_veto thresholds, trader-library thresholds, trader_league confidence
  bands, the delivery conviction curve, the breadth gate) and convention only
  where the system is silent. `direction` marks whether higher or lower is better,
  so debt and P/E are not naively "bigger is greener". `assess()` is None-safe and
  never raises.
- **NEW `terminal/static/ideals.js`** - fetches the bands once, then sweeps the
  page for labels it recognises (ROCE, Debt/Equity, P/E, Promoter holding, MFE,
  ...) and attaches an "ideal ..." chip plus a plain verdict. Colour is
  reinforced by a dot and by words, never carried by colour alone. Works on
  panels rendered later (re-sweeps 12 times), and degrades silently if the API
  is unavailable so the page still functions.
- **NEW endpoints:** `GET /api/ideals` and `GET /api/ideals/{key}?actual=`.
- **Image 1 fixed:** the model block is now explainable. "Model event score" is a
  `data-explain="p_win"` target, `MODEL_EVENT_SCORE_HELP` was rewritten in plain
  words, the toggle reads "Show what pushed this score up or down", the note
  explains a plus does not mean the company is good, and all 26 internal feature
  codes (`atr`, `vc`, `slope200`, `d10`, `ret_std20`, ...) now carry human glosses
  ("How jumpy the price normally is", "How tight the recent trading range is") so
  nobody has to read machine names.
- **Image 3 fixed:** four new explanation terms answer the owner's "what is 1R,
  2R?" - `r_multiple`, `mfe`, `mae`, `hit_rate`, each with all seven sections
  verified programmatically. `ledger.py` gained an additive `trade_r_multiple()`
  and `get_trades()` now returns `r_multiple` (stats maths untouched). The
  research history rows carry "?" buttons.
- **Image 5 fixed:** the Trading methods view no longer presents one merged
  method. `traders.js` (rewritten, 735 lines) groups all 14 books by horizon
  (Long-term quality / Short-term swings / Both horizons), gives each book its own
  section with that book's own methods and a method count, and adds 44
  plain-language glosses for jargon. Verified live: 14 books, own method counts
  (John Crane 13, O'Shaughnessy 19, Lowe 21, Singhal 18, ...).
- **Image 6 fixed:** the Performance page gained a "Which companies worked, and
  which did not" panel with actual **symbol names** for winners and losers,
  newest first, capped at 6 with a show-all toggle, each row showing the date,
  what happened in ordinary words, and the result in R with its own "?".
  Metric labels were plain-worded at the same time ("Profit Factor" -> "Profit
  per unit lost", "Max Drawdown" -> "Worst fall from a peak", "Expectancy" ->
  "Average result per idea"). Live data shows 2 winners (KSCL, PROTEAN) and
  losses from 143 recorded ideas.
- **Image 4 (how setups are identified, why they end in loss)** is now answered
  by the `setup` explanation plus the new `r_multiple`/`hit_rate`/`mae` terms and
  the winner/loser panel; the honest framing is that most recorded ideas lost,
  which is what the panel now makes visible instead of hiding behind counts.
- **Verification:** 36 unit tests OK; 13/13 static JS pass `node --check`;
  4 Python modules compile; HTML tag balance clean; all six endpoints return 200
  on the VM; local and VM both at the deployed commit with nothing uncommitted.
- **Note:** the trader-methods subagent reported failure after writing its file;
  the output was nevertheless verified independently (syntax, structure and live
  API) before being committed. Untrusted-but-real work was checked, not trusted.

### #103 - Plain-language explanations for everything clickable - VERIFIED
- **Owner request:** the terminal must be minimal, polished and understandable in
  ordinary words, and **everything clickable must answer 5W1H** - what it is, why
  it matters, what to look for, where else it is used, when to act, how it is
  worked out, plus how to spot it by eye with no tools.
- **New `explain.py`** - the single source of truth for 20 terms, each authored
  in plain English (no jargon). Keeping the wording in one place means the
  terminal, the API and the alerts can never drift apart, and fixing a confusing
  sentence fixes it everywhere. Seven sections per term.
- **New endpoints:** `GET /api/explain` (index of terms) and
  `GET /api/explain/{key}` (one term's full 5W1H). Both auth-protected. An
  unknown key returns a helpful message plus the known keys instead of a 404.
- **New `terminal/static/explainer.js`** - one delegated click listener, so
  anything carrying `data-explain="<key>"` becomes explainable, including
  elements rendered later. Reuses the existing `#dataDetailDialog` rather than
  inventing a second modal. Keyboard-accessible (Enter/Space), responses cached
  per key.
- **Wired 14 click targets:** the four market-overview metric cards, the market
  weather banner, all seven navigation items, and the system-status panes. Labels
  were rewritten in human language at the same time (e.g. "Loading market
  regime..." -> "Loading market weather..."; "Deployment Check" -> "Is everything
  working"; "Data Source Health" -> "Where the numbers come from").
- **CSS appended** to `style.css` (not replaced): explainer styling reusing the
  existing palette tokens, a distinct highlighted block for the
  "spot it yourself" answer, and a stacked layout under 620px because the phone
  is the owner's main screen. Brace balance verified 186/186.
- **Verification before claiming success:** all 13 static JS files pass
  `node --check`; `explain.py` and `terminal_api.py` compile; HTML tag balance
  clean; every `data-explain` key resolves in `explain.py`; on the VM, all 9
  wired terms return 200 with **7/7 sections each**, the index lists 20 terms,
  and `index`/`explainer.js`/`style.css` all return 200. One missing section
  (`volume.how`) was found by the completeness check and fixed.
- **Deployed:** pushed and pulled on the VM; service restarted and `active`.
  Static assets need a hard refresh (phone: incognito or `?v=2`).
- **Known gap:** 11 further terms are authored and API-reachable but not yet
  attached to screen elements (`accum`, `breadth`, `composite`, `delivery`,
  `impulse`, `pullback`, `shape_score`, `sizing`, `stop`, `veto`, `volume`).

### #102 - B2: consolidate band-universe SQL into universe_helper - VERIFIED
- **Owner-approved batch B2** — the codebase's largest single-point-of-failure.
  The band SQL (`mcap_cr BETWEEN 1000 AND 8000 …`) existed as **17 inline
  copies**; a threshold change previously needed 17 edits with silent
  divergence risk. All now route through `universe_helper.band_universe(conn, limit)`.
- Helper hardened first: `limit=None` added for the whole band, and documented
  that it truncates by `mcap_cr DESC` **before** returning A-Z, so the selected
  SET is faithful for any limit while output order changed mcap-desc -> alpha.
- 16 files changed: `universe_helper.py`, `all_weather.py`, `breadth.py`,
  `data_quality.py`, `fundamentals_tv.py`, `fund_veto.py`, `institutional.py`,
  `meta_model.py`, `patterns.py`, `pwin_cache.py`, `rule_engine.py`,
  `screener_engine.py`, `sectors_refresh.py`, `template_match.py`,
  `top_picks.py`, `trader_league.py`.
- Two consumers previously selected **all** band rows with no LIMIT
  (`data_quality`, `fundamentals_tv`); they now pass `None` / an explicit 1500 —
  equivalent today (855 band rows) and no longer silently capped at 1000.
- Verification, completed before any claim of success: 16/16 `py_compile` clean;
  16/16 imports clean (no circular-import regression); old-vs-new symbol SET
  equal at every site for its own limit (60/300/400/500/600/800/855/900/1500 and
  unbounded) — all `set-equal True`.
- Not yet deployed. Backend `.py` changed, so the VM needs `git pull` +
  `sudo systemctl restart nse-terminal` + the `journalctl` check.
- No trader / setup / scanner / strategy_config file touched, so no League
  `--changed` replay is required (`home` `code_hash` unchanged).

### #096 - Audit remediation: sizing, ML, and backtest safeguards - VERIFIED
- Sizing uses fixed-risk calculations, rejects invalid inputs, caps position
  allocation and planned risk, and does not infer sizing from `p_win`.
- ML uses canonical price-derived features, model-version checks, and global-date
  splits purged by label availability. Imputation values are learned from the
  training fold and reused for inference.
- Backtests fingerprint strategy/data for cache separation, reject unsupported
  current-context fields, handle entry gaps and stop/target ties conservatively,
  and mark incomplete windows as right-censored rather than closed trades.
- Validation: `python -m unittest discover -p 'test_*.py' -v` passed 30 tests;
  Python compilation checks passed. The complete suite ran after installing
  already-declared dependencies missing from the local environment.
- No live database import, training run, or VM deployment occurred during
  validation. The unverified NIFTY 50 CSV remains uncommitted and unpromoted.
- Legacy ambiguous values remain unchanged pending the owner's policy choice.

### #097 - Publish and deploy audit remediation - VERIFIED
- Main merged and published to GitHub at `33ee8fc`; VM fast-forwarded to the
  same commit. No source/data import or ML training was run.
- Created online SQLite backup
  `data/app.db.pre-audit-20261002-183658.bak`; `PRAGMA integrity_check`
  returned `ok` for both backup and live DB.
- Confirmed migration columns `fundamentals.source_metadata` and
  `pwin_daily.model_version` are present. Fundamentals (1,268), daily prices
  (815,135), and broad-universe rows (1,535) match the pre-deployment backup.
- `nse-terminal.service` is active; authenticated `/api/health` returned HTTP
  200 with `ok=true`. The 30-test suite passed locally and on the VM.
- `/api/deployment-check` returned HTTP 200 with one failed freshness check:
  `universe_broad` last updated 34 days ago (1,535 rows). This is a visible
  data freshness issue, not a code-deployment failure; no refresh was triggered.
- The provenance-unknown NIFTY CSV remains uncommitted, unapplied, and absent
  from the VM.

### #098 - Preserve and deprecate ambiguous fundamentals values - IMPLEMENTED
- Owner decision: keep potentially legacy `cfo_positive` and `roce` values
  temporarily for production compatibility and tag affected rows
  `legacy_deprecated`. After DR-01 v2 dated-fundamentals backfill satisfies
  its period/public-availability acceptance criteria, clear only the flagged
  legacy values; keep physical columns until separately reviewed.
- Added `flag_legacy_deprecated(conn, apply=False)` with preview by default,
  exact per-field provenance checks, idempotent apply behavior, and no numeric
  value mutation. Known non-TradingView per-field values are not tagged merely
  because another field on the row came from TradingView.
- Validation: focused tests verify preview-only behavior, preservation of
  current values and existing flags, source-specific targeting, and idempotence.
  Full local suite is now 31 tests; production tagging and its checks are in #099.

### #099 - Apply legacy deprecation flags on VM - VERIFIED
- Preview identified 887 rows with ambiguous legacy values: 860
  `cfo_positive` fields and 878 `roce` fields (some rows have both). The
  selection requires missing field-level provenance or explicit TradingView
  provenance; known non-TradingView field sources were not tagged.
- Created `/home/ubuntu/nse-system/data/app.db.pre-legacy-deprecated-20261002-191739.bak`;
  backup `PRAGMA integrity_check` returned `ok`.
- Applied only the row quality flag `legacy_deprecated` to 887 rows.
  Existing numeric values were compared against the backup and unchanged;
  existing flags were preserved. A second preview found all 887 rows already
  flagged and proposed zero further changes.
- Fundamentals (1,268), prices (815,135), and broad-universe rows (1,535)
  remain unchanged. The 31-test suite passes on both laptop and VM;
  authenticated `/api/health` returns HTTP 200 and the service is active.
- Removal gate: clear only the flagged legacy values immediately after DR-01
  v2 dated-fundamentals backfill is verified against period-end and
  public-availability requirements. Keep schema columns until compatibility
  is reviewed separately.

### #100 - Publish and deploy terminal UX and operating skills - VERIFIED
- Published commit `782c401` to `origin/main` and fast-forwarded the VM to the
  same commit. The terminal service remained active; no restart was needed for
  static assets and project skills.
- Deployed UI updates clarify navigation, market snapshot metrics, event-score
  meaning, and fixed-risk sizing. Added project skills for recurring/one-time
  operations and terminal UX principles.
- Deployed `/static/index.html`, `/static/app.js`, and `/static/style.css`
  returned HTTP 200. SHA-256 hashes for all four changed web assets matched
  between the canonical main worktree and VM.
- Targeted sizing, ML, backtest, and fundamentals tests passed (16 total);
  `node --check` passed for `app.js` and `cards.js`. Browser checks confirmed
  mobile-width overflow is absent, accessible navigation works, and sizing
  does not present win probability or Kelly as sizing inputs.
- An unauthenticated `/api/health` request returned HTTP 401; this probe does
  not verify the authenticated API health response. The application service
  was active. API behavior was not changed by this static UI release.
- Existing untracked user configuration, data, and VM backup files were
  preserved and not included in the release.

### #101 · Repair refresh, research, and trader-method flows — VERIFIED
- Research uses the newest stored swing/trend scan dates instead of requiring
  a scan dated today; it exposes source dates and warns when scans lag prices.
  Per-symbol research preserves the latest market state with short history,
  while withholding historical setup statistics until the 280-bar minimum.
  Research cache entries now invalidate when that symbol's latest price date
  advances.
- The company view launches current-state research and trader-method matching
  for the selected stock. Implemented scanners can target a single symbol
  within the established universe; cross-sectional rankers remain full-universe
  to preserve their ranking logic. Trader-method rows and matches open a
  plain-language guide instead of raw method JSON.
- Wired scan/screener controls to their APIs, added scan status/error feedback,
  made refresh behavior explicit (reload saved data versus run a scan), and
  removed duplicate refresh listeners. Added coverage for latest scan dates,
  price staleness, short histories, cache freshness, and the target-universe
  gate.
- Performance review was diagnostic only: production ledger shows 2 wins /
  44 graded signals (4.5%). The three-year common-book replay's highest listed
  win rate was 39.6% (PF 0.82, negative expectancy); no tested method supports
  a >60% claim. No signal thresholds or outcome labels were altered to improve
  the displayed rate.
- Validation: 36 unit tests passed locally and on the VM; changed Python
  modules compiled, browser scripts passed `node --check`, and diff hygiene
  passed.
- Published and deployed to main/VM at `7f0243e`. The terminal service is
  active, `/static/app.js?v=19` returns HTTP 200, and unauthenticated root/API
  probes correctly return HTTP 401. Static JS checksums match local files.
  No production database rows or trading settings were changed.
- Status: DEPLOYED · VERIFIED on main and VM at `7f0243e`.

---

## HOW NEW SESSIONS USE THIS
1. Read `backlog.md` — rules, instructions, current status.
2. Read `EXECUTION_LOG.md` — exactly what shipped.
3. Read `DATA_REQUESTS.md` — what the owner provides next.
4. Read `PORTAL_REDESIGN.md` — vision & roadmap.
5. Continue from the last entry's status.

---

## INDEX - #001..#093, one line each (85 entries)

Full text for these lives in `EXECUTION_LOG_FULL.md`.

| # | what changed |
|---|---|
| #001 | regime.py — yfinance period fix |
| #002 | screener_engine.py — yfinance period + index fallback |
| #003 | db.py — central schema (29 tables) |
| #004 | meta_model.py — feature guard + bundle format |
| #005 | events + swing_live + deepdive — three fixes |
| #006 | backtest + swing_live + screener_engine — staleness |
| #007 | app.py — optional-panel guards |
| #008 | log_utils + daily_update + scheduler_bg + requirements split |
| #009 | setup.py v3.1 — impulse indexing bug fix |
| #010 | all_weather.py — all-weather swing mode |
| #011 | value_radar.py |
| #012 | value_radar wiring |
| #013 | fundamentals_tv.py — canonical fetcher |
| #014 | BACKLOG + EXECUTION_LOG restructure |
| #015 | Feature C — regime spectrum |
| #016 | Value Radar v2 — tiers + promoter/CFO enrichment |
| #017 | Sizing — fallback win-rate 0.35 |
| #018 | positional_scanner.py (ID3a) |
| #019 | alerts.py — unified alerts (ID7) |
| #020 | universe_helper.py (ID7) |
| #021 | trend_scanner.py (ID8) |
| #022 | universe_helper migration (ID7 cont.) |
| #023 | Scanners UI (ID9) |
| #024 | Trend v2 + meta_model v7 (33 features) |
| #025 | Trend v3 — unbounded score |
| #026 | validate.py v3 — fast walk-forward |
| #027 | Setup v3.2 — widen impulse |
| #028 | Setup v3.3 — widen 1c / PB |
| #029 | fast_wf.py — target sweep |
| #030 | Sizing v4 — quality multiplier |
| #031 | strategy_runs.py — durable ledger |
| #032 | Tranche exits tested (ID18) |
| #033 | Strategy runs dashboard |
| #034 | strategy_config.py — central config (ID19) |
| #035 | Deployment verification (ID21) |
| #036 | Graceful skips — ml_predict + sheets_sync |
| #037 | research_cockpit.py (ID22 v1) |
| #038 | Research Universe (ID22b) |
| #039 | Warm cache scheduler (ID22c) |
| #040 | Sector aggregation + sortable UI (ID23 / R24) |
| #041 | Fix warm_cache --force + CACHE_VERSION |
| #042 | Portal Phase 1 redesign |
| #043 | Rule engine + seed strategies (Phase 2 start) |
| #044 | Fix rule_engine numpy truth-value bug |
| #045 | Rule engine: failure breakdown diagnostic |
| #046 | Gap-up + impulse/pullback features; RCP/EP rewrite |
| #047 | Route ordering fix for /api/strategies/seed |
| #048 | strategies.js — use JSON key for API calls |
| #049 | ID42: in-browser strategy editor |
| #050 | ID43: strategy backtest sandbox |
| #051 | TV column probe (ID44 step 1) |
| #052 | Fundamentals v5 + schema migration (ID44 step 2) |
| #053 | Percentile scoring (ID45) |
| #054 | Candle behaviour analytics (ID47) |
| #055 | Signature matching (ID46) |
| #056 | Weekly setup_pool rebuild scheduler job |
| #057 | Pattern transparency + chart markers (ID48 + ID49) |
| #058 | Bearish pattern grading fix (ID53) |
| #059 | Compare mode + unified stock card (ID50 + ID51) |
| #060 | Famous Traders framework + John Crane (ID54 + ID55) |
| #062 | Trader #2 — Larry Spears (ID56) |
| #063 | Fix Larry Spears `_ma_trend` slope-check bug |
| #064 | Book extraction standard + feature registry (ID57 + ID58) |
| #065 | Trader #3 — James O'Shaughnessy |
| #066 | Trader #4 — Wesley Gray & Tobias Carlisle |
| #069 | Trader #5 — Janet Lowe |
| #070 | Trader #6 — Curtis Faith (Way of the Turtle) |
| #073 | Trader #7 — Alpesh Patel & Paresh Kiri |
| #075 | Trader #8 — Apurva Parikh |
| #076 | Trader #9 — Ishaan Agnihotri |
| #078 | Trader #10 — Steve Nison (Beyond Candlesticks) |
| #079 | Rule R39 + D12 logged |
| #080 | Trader #11 — Tushar Chande |
| #081 | Trader #12 — William O'Neil |
| #085 | Trader #14 — Aseem Singhal |
| #086 | R44 + R45 — Exit logic + wisdom extraction mandatory |
| #087 | Trader League + pre-deployment backtest (D20, ID77) |
| #088 | Copy-paste blocks rule (R47) + league replay hardening |
| #089 | Terminal data-clickability and navigation |
| #090 | Verify VM pre-season replay and real-money readiness |
| #091 | Source adapter framework and first migrations |
| #092 | Import KITE export as a quarantined research snapshot |
| #093 | Cross-attest KITE against ScanX and refresh confirmed fields |
| #094 | Apply source-aware NSE research audit |
| #095 | Audit remediation: fundamentals integrity |
