# FINDINGS — verified defects register

Every entry was **observed**, not inferred. Evidence is reproducible with the
command shown. Check this file before "fixing" anything: several items are
deliberately gated by owner rules and must not be touched.

Status legend: `OPEN` (needs a decision) · `FIX-READY` (safe, scoped, no owner
gate) · `GATED` (owner approval / upstream data required) · `FIXED`.

Verified 2026-10-05 on `C:\Users\Ankit\Desktop\nse_system` (laptop, stale DB)
against `main` @ `f483e68`.

> **STATUS REFRESH — 2026-10-19** (this entry is authoritative over the older
> status lines below, which are left in place for history).
>
> The 2026-10-05 pass is 14 days and ~15 commits old. Re-verified every entry
> against on-disk code and against **production** (`fe0f09d`, same HEAD as the
> laptop). What changed:
>
> | Was | Now | Why |
> |---|---|---|
> | F-01 laptop DB 40 days stale | **FIXED** | 2026-10-18 raw-history rebuild synced `data/app.db` to production — `prices_daily` → 2026-10-16, `ml_predictions` → 2026-10-18 |
> | F-02 CRITICAL, P(WIN) dead | already **RETRACTED** | was never true in production |
> | F-03 CRITICAL, `ml_predictions` empty | already **FIXED** | now 25,173 rows on both machines |
> | F-04 pattern gate vacuously open | **FIXED** | `settings.pattern_gate` populated 2026-10-18 with real win rates; `pattern_grades` = 59,697 rows (was 0) |
> | F-07 `window.loadResearchSectors` missing | **RETRACTED — false positive** | proven live in the browser, see entry |
> | F-08 `deployment.js` dead | **FIXED** | file no longer exists; `app.js:961` owns `loadDeployment` |
> | F-09 ML runs after scan | **FIXED** | `daily_update.py` now runs `ml` before `scan` (comment says so) |
> | F-10 `run N` alphabetical | **FIXED** 2026-10-19 | ranks by `mcap_cr DESC` before truncating |
> | F-11 log wiped every run | **FIXED** 2026-10-19 | append + prune to `HISTORY_RUNS = 60` |
> | F-13 double veto | **FIXED** 2026-10-19 | verdict passed through to the alert |
>
> **Facts that also moved:** 12 `daily_update` stages (was 10 — `fyers` and
> `breadth` were added); **23** scheduler jobs (was 19); suite is **363** tests
> (was 230); `matplotlib` is installed on the VM (optional locally, charts work
> in production).
>
> **New defect raised this pass — F-26: the agent bootstrap layer itself was
> stale.** See the end of this file.

---

## F-01 · Laptop DB is ~40 days stale — `FIXED` (2026-10-18, see note)

**Evidence**
```powershell
.\env\Scripts\python.exe -c "import json;d=json.load(open('.agents/cache/db_index.json'))['tables'];print({k:v.get('rows') for k,v in d.items() if k in ('prices_daily','technicals_daily','swing_signals','pattern_tags')});print(d['prices_daily'].get('latest'), d['technicals_daily'].get('latest'))"
```
`prices_daily` 1,130,292 rows, latest `2026-08-26` · `technicals_daily` 980 rows,
latest `2026-08-24` · `swing_signals` 9 rows, latest `2026-06-09`.

**Impact** Any conclusion drawn from local row counts is a stale-machine fact,
not production. `data_quality` locally reports CRITICAL staleness (≥5 days).

**Note** This is by design (`data/*.db` is gitignored; each machine keeps its
own). Do not "fix" it by copying a DB. Verify freshness against the VM.

---

## F-02 · Meta-model bundle is bare → the whole P(WIN) chain is dead — `RETRACTED: LOCAL-ONLY` (2026-10-05)

> **This finding was WRONG about production.** It was observed on the **laptop's**
> `data/meta_model.pkl`, which is a stale bare estimator. On the **VM** the bundle
> was already a correct `v8-pit-safe` dict with exactly 27 features, and
> `get_model()` never returned `None`. Verified on the VM 2026-10-05:
> `pwin_daily` = 19,065 rows through today (708/day), `top_picks` = 1,450 rows
> (50/day) through today, `meta_model.py train` exits 0 (AUC 0.646, top-10% win
> 66.2%). The P(WIN) chain was **healthy all along**.
>
> **Lesson recorded:** `data/*.pkl` are gitignored and per-machine. Local model
> state is NOT production state — never diagnose a model defect from the laptop.
> F-02 and F-03 were both raised before this was accounted for.

**Evidence**
```powershell
.\env\Scripts\python.exe -c "import joblib;o=joblib.load('data/meta_model.pkl');print(type(o))"
# <class 'lightgbm.sklearn.LGBMClassifier'>
```
`meta_model.get_model()` (meta_model.py:28-59) requires a `dict` with
`version == MODEL_VERSION == "v8-pit-safe"` (meta_model.py:23) and
`features == FEATURES` (27 entries, meta_model.py:74-86). A bare estimator hits
the explicit refusal at meta_model.py:56-59 and returns `None`.

**Chain of consequences**
`get_model()` → None → `score_symbol()` → None → `pwin_cache.refresh_all()`
stores nothing (`pwin_daily` = **0 rows**) → `top_picks.compute()` finds no
`p_win` and skips every symbol (`top_picks` = **0 rows**) → `/api/toppicks`
returns empty → the Overview/Top-Picks UI is blank.

**Fix direction (not yet applied)** Retrain on the machine that has fresh prices:
`python meta_model.py train`. That writes the correct `{model, features,
version, metadata}` bundle. Do **not** hand-patch the pickle.

---

## F-03 · `ml_models.pkl` was frozen at v0.1 → ML scores went stale — `FIXED` (2026-10-05)

> **Two corrections.** (1) `scan` did **not** reject every symbol: it reads
> `MAX(prediction_date)` (2026-10-02, 721 symbols) and 34 cleared `MIN_ML=70`.
> The real impact was **3-day-stale ML gating**, not a lockout — again
> misdiagnosed from the stale laptop DB. (2) The root cause was not the version
> guard but `ml_train.py:_time_split`: the validation fold (15% of dates = 114)
> was **always** narrower than the 252-date purge horizon, so the purge emptied
> it every run and `train()` always raised "purged global-date split has an empty
> fold". `data/ml_models.pkl` could therefore never be regenerated, which is why
> it sat at `v0.1`.

**FIXED** by replacing the purge with an **explicit inter-fold embargo**
(`ml_train.py:_time_split`): a gap of `min(252, len(dates)//4)` dates is reserved
*between* folds instead of deleting rows from them. Leakage is still impossible —
no training label is observable before the validation window opens. Verified
locally on a 760-date frame (folds 1064/228/228, strictly ordered), then on the
VM: `ml_train.py` exit 0 (Test AUC 6M 0.550 / 12M 0.554) → `ml_models.pkl` =
**v0.2-pit-safe** → `ml_predict.py` stored **721** stocks → `ml_predictions` =
**15,733 rows, max 2026-10-05** (was 15,012 @ 2026-10-02).

**Evidence**
```powershell
.\env\Scripts\python.exe -c "import joblib;o=joblib.load('data/ml_models.pkl');print(o['version'], len(o['feat_cols']), list(o)[:5])"
# v0.1 9 ['m6','m12','feat_cols','version']
```
`ml_predict.MODEL_VERSION = "v0.2-pit-safe"` with a compatibility guard at
ml_predict.py:10-31. The stored bundle is `v0.1` → classified as incompatible →
`predict_all()` writes nothing → `ml_predictions` empty.

`scan.py` reads the prediction map and rejects a symbol when it is absent
(scan.py:50), so **every** symbol fails the scan. Combined with F-09 (ML runs
after scan), one daily run cannot self-heal.

**Fix direction** `python ml_train.py` then `python ml_predict.py`. Confirm with
`SELECT COUNT(*), MAX(prediction_date) FROM ml_predictions`.

---

## F-04 · The empirical pattern gate is vacuously open — `FIXED` (2026-10-18)

> **No longer true on either machine.** Verified 2026-10-19 on the laptop and
> on production: `settings.pattern_gate` = `{"date": "2026-10-18", "gate": …}`
> with all 6 patterns carrying real statistics (e.g. `ASCENDING_TRIANGLE`
> win_rate 0.697 over n=5740), and `pattern_grades` = **59,697** rows (was 0).
> The gate now filters on evidence as designed. The fail-open default
> (`enabled_patterns` treating an unknown pattern as enabled) remains in code —
> it is harmless while the gate is populated, but note it if the gate is ever
> cleared again.

**Evidence**
```powershell
.\env\Scripts\python.exe -c "import sqlite3;c=sqlite3.connect('data/app.db');print(c.execute(\"SELECT value FROM settings WHERE key='pattern_gate'\").fetchone());print('grades',c.execute('SELECT COUNT(*) FROM pattern_grades').fetchone()[0])"
# ('{"date":"2026-09-11","gate":{}}',)  grades 0
```
`pattern_grader.enabled_patterns()` treats an unknown pattern as **enabled**
(pattern_grader.py:273-274) and the gate dict is empty, so all 6 patterns
(including the killed `BULL_FLAG`) pass. The documented bar — ≥30 graded tags and
≥60 % win rate (pattern_grader.py:30-33) — currently filters nothing.

**Related** `pattern_grades` = 0 rows even though `pattern_tags` = 1154 rows.
Only `patterns.run()` calls `grade_all()` + `report()` to populate the gate
(patterns.py:761-766), so the gate self-heals only after a successful pattern
run on a fresh DB.

---

## F-05 · Auth is opt-in and part of the surface is public — `SUPERSEDED` (see reality below)

> **The premise is no longer true.** There is **no auth anywhere** now — a grep
> for `Depends(verify_user)` in `terminal_api.py` returns **zero matches**. The
> gate was removed wholesale on **2026-10-07** and independently verified in
> `.agents/auth-verify-report.md`: 67 live probes across `/`, `/glossary`,
> `/docs`, `/redoc`, `/openapi.json`, `/static/*` and every `/api/*` returned
> **0× 401 and 0× 403**; `openapi.json` has no `securitySchemes` and no
> top-level `security`.
>
> **So the real posture is:** the terminal is fully public by design, and only
> `POST /api/webhook/ingest` is guarded (by `x-webhook-token`, compared with
> `secrets.compare_digest` — terminal_api.py:946-962).
>
> **Do NOT "fix" this.** `.agents/MEMORY.md` §10 is explicit: the login gate
> was removed by owner decision and a per-route dependency must not be re-added
> without an explicit owner decision. The original "fix direction" below
> contradicts the owner rule and must not be followed.
>
> **Residual, still open (owner-gated):** the owner's password remains readable
> in **git history** (pushed to GitHub) and the Telegram bot token was committed
> in 3 historical commits — it was **untracked** in `3fd912f` and is now
> correctly ignored (`.gitignore:23 data/*secret*`), but it is still recoverable
> from history. Both are fixed only by **rotation**, which MEMORY §13 lists as
> owner-gated. Report, do not act.

**Original 2026-10-05 text (kept for history, and for its one still-useful
point — a future route added without a gate will also be public, which is now
the intended behaviour rather than an oversight):**

**Evidence** `terminal_api.py:31-32` — `FastAPI(...)` has no `dependencies=`.
Each route opts in with `user: str = Depends(verify_user)`. Compare with:
- `terminal_api.py:33-34` — `app.mount("/static", StaticFiles(directory="terminal/static"))`, no auth → every JS/CSS/HTML file is public.
- FastAPI defaults leave `/docs`, `/redoc`, `/openapi.json` public.
- Exactly one business route is intentionally exempt: `POST /api/webhook/ingest` (terminal_api.py:812-852), guarded by `x-webhook-token`.

**Impact** A future route written without `Depends(verify_user)` is silently
public. `terminal/static/` must never hold a secret.

**Fix direction** Add `dependencies=[Depends(verify_user)]` to `FastAPI(...)`,
set `docs_url=None, redoc_url=None, openapi_url=None` (or protect them), and
carve out the webhook explicitly. **Whole-file change**, then
`sudo systemctl restart nse-terminal`.

---

## F-06 · `{symbol}` catch-all routes shadow later literals — `FIX-READY` (advisory)

Starlette matches in registration order. Literals must precede catch-alls:

| Prefix | Catch-all | Correctly-placed literals |
|---|---|---|
| `/api/strategies` | `GET/POST {name}` @426/435 | `POST /seed` @399, `/run-all` @406, `/backtest-cache/clear` @415 |
| `/api/traders` | `GET {slug}` @217 | `/matches/{symbol}` @242 (3 segments, safe) |
| `/api/research` | `GET {symbol}` @482 | `/research-universe` @491, `/research-sector` @502 (hyphenated *because* of this) |
| `/api/patterns` | `GET {symbol}` @574 | `/latest` @540, `/stats` @546, `/history/{symbol}` @555 |
| `/api/delivery` | `GET {symbol}` @765 | `/top` @753, `/accum` @759 |
| `/api/meta` | `GET {symbol}` @948 | — |
| `/api/sizing` | `GET {symbol}` @996 | `POST /capital` @1007 (method-split, safe) |
| `/api/screener` | `GET {symbol}` @1030 | `/scan` @1019 |

No fix needed today; the rule matters for the *next* endpoint added.

---

## F-07 · `window.loadResearchSectors` is never exported — `RETRACTED` (false positive)

> **This finding was WRONG.** It assumed `research_sector.js` was an ES module.
> It is a **classic script** — `index.html:722` loads it with
> `<script src="/static/research_sector.js?v=18">` and no `type="module"`, and
> the file has no IIFE wrapper. In a classic script a top-level `function`
> declaration *does* become a property of the global object, so
> `window.loadResearchSectors` already exists and the `typeof` guard in
> `app.js:2042` picks it up.
>
> **Proved live, not reasoned** — evaluated in the production terminal at
> `http://140.238.226.249:8000` on 2026-10-19:
> ```
> typeof window.loadResearchSectors  -> "function"
> typeof window.loadResearchUniverse -> "function"
> document.scripts (research*)       -> all type "classic"
> browser console                    -> zero errors
> ```
> **Do not "fix" this.** The explicit `window.loadResearchUniverse = …` in
> `research_universe.js:174` is harmless but *redundant*, not evidence that
> `research_sector.js` is broken. Lesson: verify a frontend claim in the
> browser before recording it as a defect.

**Evidence** `app.js:1080` pushes `window.loadResearchSectors` into
`refreshAll`'s task list and guards with `typeof fn === "function"`
(app.js:1081). `research_sector.js:103` defines `loadResearchSectors` at module
scope and never assigns it to `window` (`research.js:299` and
`research_universe.js:165` do). The guard silently drops it.

**Impact** The Research → Sectors panel is never refreshed by the global
Refresh button; only its own `#refreshResearchSector` handler
(research_sector.js:168-171) works.

**Fix** One line in `research_sector.js`: `window.loadResearchSectors = loadResearchSectors;`
Bump `research_sector.js?v=` in `index.html` (currently `18`). No restart.

---

## F-08 · `deployment.js` is dead and would double-bind if wired as-is — `FIXED` (file removed)

> **Moot — the file no longer exists** (verified 2026-10-19:
> `terminal/static/deployment.js` → not found). `app.js:961` defines
> `loadDeployment()` and `app.js:2034` calls it from `refreshAll`, so the
> deployment panel is live with a single owner and no double-binding.

`deployment.js` (39 lines) is **not** referenced by `index.html` (absent from
`api_index.json.asset_versions.script_tags`). Its own `DOMContentLoaded` handler
(deployment.js:33-38) binds `#refreshBtn` — which app.js:599-626 already owns via
`refreshAll` — and re-fetches `/api/deployment-check`. Either delete the file or
refactor it to an exported `window.loadDeployment` with no listeners, then wire it.

---

## F-09 · ML runs after scan in `daily_update` — `FIXED` (stage order corrected)

> **Already fixed.** `daily_update.py` now runs stage `ml` **before** stage
> `scan`, with an explicit comment at the call site:
> ```
> # ORDER MATTERS: the scan consumes today's ML scores. Running scan before
> # ml (the old order) silently used yesterday's predictions.
> results["ml"]    = _safe("ml",    lambda: __import__("ml_predict").predict_all())
> results["scan"]  = _safe("scan",  lambda: __import__("scan").run())
> ```
> `refresh_pipeline.py` (the one-click refresh) uses the same ML → scan order.
> Verified 2026-10-19 by reading the file.
> **Also note the stage list grew:** `fyers` now runs first and `breadth` was
> inserted after `technicals`, so the chain is **12 steps**, not 10.

`daily_update.py:46-49` — stage 3 `scan.run()`, stage 4
`ml_predict.predict_all()`. `scan.py:20-24` reads
`MAX(prediction_date)` from `ml_predictions`. So today's ML score can never
influence today's scan, and on a cold DB `mv is None` rejects everything
(scan.py:50). Swap the two stages (and keep F-03's retrain in mind — the swap
alone will not help while `ml_predictions` is empty).

---

## F-10 · `fundamentals_tv.run(N)` is not top-N — `FIXED` (2026-10-19)

**Was** `fundamentals_tv._universe()` returned `sorted(syms)` and `run(limit=n)`
truncated **after** the alphabetical sort (fundamentals_tv.py:89-90), so
`python fundamentals_tv.py run 100` fetched the first 100 symbols A–Z.

**Fixed** — the union is now ranked by `mcap_cr DESC` (symbols with no known cap
sort last, symbol name breaks ties) *before* truncating; `limit=None` still
returns the full set alphabetically.

**Scope note (downgrades the original severity):** the scheduler calls
`fundamentals_tv.run()` with **no** limit (scheduler_bg.py:168), so production
was never affected — only explicit CLI calls like `run 100`.

**Evidence (2026-10-19)** `_universe(conn, 2)` over three symbols whose caps are
AAA=1100, MMM=3000, ZZZ=7900 returns `['ZZZ', 'MMM']`, i.e. largest first and
deliberately *not* alphabetical; `_universe(conn)` returns `['AAA','MMM','ZZZ']`.

`fundamentals_tv._universe()` returns symbols alphabetically sorted;
`run(limit=n)` truncates **after** sorting (fundamentals_tv.py:95-96). So
`python fundamentals_tv.py run 100` fetches the first 100 symbols alphabetically,
not the top 100 by market cap. Sort by `mcap_cr DESC` before truncating.

---

## F-11 · `data_quality` destroys its own history — `FIXED` (2026-10-19)

**Was** `data_quality.py` ran `DELETE FROM data_quality_log` before every run,
so the table held only the newest run. Confirmed **in production** on
2026-10-19: `data_quality_log` = **6 rows, 1 run, `2026-10-18T18:53`** — every
earlier audit record had been erased, so there was no way to see whether data
quality was improving or degrading.

**Fixed** — the run now **appends** its rows first and then prunes to the
newest `HISTORY_RUNS = 60` distinct `run_at` values. The daily job therefore
retains ~2 months of history at ~6 rows/run (a few hundred rows total), and an
empty/failed run can no longer wipe the table.

**Verified (2026-10-19)**: a seeded table of 420 rows / 70 runs prunes to 119
rows / **60 distinct runs** — retained, bounded, not wiped.

**Note** nothing reads this table for display (no API route, no JS), so adding
history cannot change any UI. `data_quality.py` has no other consumer than
`db.py`'s schema declaration.

`data_quality.py:213` runs `DELETE FROM data_quality_log` before every run.
`data_quality_log` holds only the latest run (6 rows live). Either drop the
DELETE (keep append-only, filter by `run_at` in the UI) or retain the last N runs.

---

## F-12 · "half-Kelly" sizing does not exist — `RESOLVED` by owner call (2026-10-19)

**Was** a pure doc-vs-code split. `sizing.py` returned `kelly_pct`,
`half_kelly_pct`, `p_win` and `payoff_b` as hard-coded `None`;
`strategy_config.SIZING.B_PAYOFF` (3.0) and `FALLBACK_WINRATE` (0.35) were
referenced nowhere outside `strategy_config.py`; PROJECT_HANDOFF §5 still
called it "half-Kelly position sizing". The register asked whether to
implement Kelly or rename it.

**Owner decision: neither — delete the pretence.** Position size is the
owner's decision, not the machine's (2026-10-19).

- The four dead fields (`kelly_pct`, `half_kelly_pct`, `p_win`, `payoff_b`)
  are **gone** from the `suggest()` response.
- The machine no longer proposes a size at all: `shares`, `suggested_value`,
  `risk_amount`, `actual_alloc_pct`, `actual_planned_risk_pct`,
  `value_by_risk_cap`, `binding_cap` and `actionable` were removed with it.
  `suggest()` now reports capital, the two caps, the regime/shape multipliers,
  and `risk_pct` — the stop distance, which is a property of the prices and
  not a size.
- `app.js` no longer prints "Quantity at trigger" or "Research position size";
  the panel is now **Position limits (you choose the size)**.
- The research page's "Try your own numbers" calculator is **kept on
  purpose** — it is the instrument the owner uses to pick a size, and it only
  turns the owner's own price, stop and capital into consequences.
- `test_sizing_safety.py` asserts none of those fields can ever come back.
- `MARKET_WISDOM.md` §2.7 and `traders/wisdom.py` were left alone: they are
  sourced market knowledge, not claims about this codebase, and editing
  `traders/*.py` would change the League `code_hash` and force a replay.

---

## F-13 · Double veto + post-insert "suppressed" alert — `FIXED` (2026-10-19)

**Was** `swing_live.py` ran `fund_veto.vetoed()` before its INSERT, then
`alerts.notify_setup()` **re-ran the same veto on a second DB connection**. If
the two reads ever disagreed, Telegram sent "FUND VETO … setup suppressed" for a
signal whose row was already committed as `PENDING` — the message and the
database contradicted each other. Also two DB round-trips per accepted symbol.

**Fixed** — the alert functions now take the caller's verdict:
`notify_setup(st, veto=None)` and `notify_all_weather(sym, st, veto=None)`.
`swing_live` passes `veto=(bad, why)` from the gate it already executed, so the
veto is computed **once**. `veto=None` preserves the old self-serve check for
any direct caller, so the public behaviour of calling the function bare is
unchanged. **Gate order in `swing_live.scan()` is untouched** — this passes the
step-9 result forward; it does not add, remove or resequence a gate.

**Evidence (2026-10-19)** with a stubbed `fund_veto` that counts calls:
- `notify_setup(st, veto=(False, None))` → alerts sent, `fund_veto.vetoed()`
  called **0** times (the duplicate read is gone).
- `notify_setup(st)` → still self-checks, `vetoed()` called **1** time.
- `notify_setup(st, veto=(True, "..."))` → returns `False` and emits the
  suppression message exactly once, before any risk maths runs.

**Note** the two call sites are the only ones in the repo
(`notify_setup` ← swing_live.py, `notify_all_weather` ← swing_live.py), so no
other caller needed updating.

`swing_live.py:158-162` vetoes before INSERT. `alerts.notify_setup()`
re-computes the veto (alerts.py:117-125) and, on a mismatch, sends a
"FUND VETO … suppressed" Telegram **after** the row is already in
`swing_signals`. Two DB reads per accepted symbol and a confusing user message.
Compute once and pass the verdict through.

---

## F-14 · `BULL_FLAG` is a zombie — `FIX-READY` (cleanup, gated by evidence)

Killed as a detector 2026-09-17 (patterns.py:8, changelog 2026-09-17a) after
rescue variants scored 53.0-55.9 % WR against a 60 % bar. Still present in:
- `pattern_grader.ALL_PATTERNS` (pattern_grader.py:39)
- `template_match.TEMPLATES` (template_match.py:41-43)
- `meta_model.PAT_MAP` / `FEATURES` (`pat_flag`)
- live DB: 161 orphan `pattern_tags` rows

**Do not** delete historical tags/grades — the 2026-09-17 decision explicitly
retained them for audit. Remove only the live-path references.

---

## F-15 · Duplication hotspots — `1 OF 5 REMAINS` (2026-10-23)

| Duplicated thing | Copies | Status |
|---|---|---|
| Band universe SQL (`mcap_cr BETWEEN 1000 AND 8000 …`) | was **17** inline copies | **FIXED** — all now call `universe_helper.band_universe(conn, limit)`. Equivalence proven at all 15 refactored sites. `limit=None` added for the unbounded callers |
| Yahoo direct call sites | ~14 files bypass `data_sources` | **FIXED (2026-10-23)** — every call site now goes through `data_sources.fetch_price_history` / `fetch_yahoo_field`; repo-wide grep finds zero `yf.Ticker` / `yf.download` / `import yfinance` outside `data_sources/`. 15 of 19 spot pairs byte-identical; the 4 diffs are float32 dividend-adjustment rounding between the `period=` and `start=` request paths (max relative error 3.5e-7, max Close deviation 0.0005 INR) plus tz / extra-column shape deltas — equivalent at any meaningful precision. `auto_adjust=True` is preserved in the adapter, so `traders/larry_spears.py` dropping its explicit kwarg is safe |
| Stage-2/VCP logic | `screener_engine.py` (hardcoded :138-173) vs `strategy_config.SCREENER` + `setup.py` | **BLOCKED — not equivalent; needs an owner decision.** Measured over 745 mutually-evaluated symbols: VCP **50 disagreements (old 13 pass vs canonical 41)**, `overall_signal` 33 (7 vs 28), `impulse%` differs on all 41 comparable pairs, `pullback%` 41, `days_since_high` 19, `momentum` 5 (272-bar vs 240-bar gate), and one baseline vol-window difference (INDOTECH `vol_sma50[i-1]` vs `vol_sma[i]`). Consolidating would change what the screener flags by ~3×, so `evaluate_stock` was left **completely untouched** — nothing to restore |
| Forward simulation (3-bar trigger, 30-bar hold, stop-first) | `build_setup_pool._simulate` :146-185 vs `research_cockpit._simulate_forward` :322-378 | **FIXED (2026-10-23)** — already consolidated before this pass; the pre-B5 bodies recovered from `git show 3057927~1` were run against the surviving wrappers: **17,124 cases, 0 diffs** (HOLD_BARS=30, TRIGGER_WINDOW=3 throughout) |
| Sector PE medians | `scoring.sector_pe_medians` :41-53 vs `positional_scanner._sector_pe_medians` :119-128 | **FIXED (2026-10-23)** — `positional_scanner` imports the `scoring` copy and its own was deleted (along with the now-unused `import statistics`); **11 sectors, 0 differing medians** |

**B2 consolidation detail.** 16 files changed: `universe_helper.py` (helper
hardened with `limit=None`), `all_weather.py`, `breadth.py`, `data_quality.py`,
`fundamentals_tv.py`, `fund_veto.py`, `institutional.py`, `meta_model.py`,
`patterns.py`, `pwin_cache.py`, `rule_engine.py`, `screener_engine.py`,
`sectors_refresh.py`, `template_match.py`, `top_picks.py`, `trader_league.py`.

Evidence: 16 × `py_compile` clean, 16 × import clean, and each site's old-vs-new
symbol SET compared equal for its own limit (60/300/400/500/600/800/855/900/1500
and unbounded). The helper truncates by `mcap_cr DESC` *before* returning A–Z, so
limits stay faithful while output order changes from mcap-desc to alphabetical —
no consumer depends on that order.

Note `data_quality.py` and `fundamentals_tv.py` previously selected *all* band
rows with no LIMIT; they now pass `None` / an explicit 1500, which is equivalent
today (855 band rows) and no longer silently caps at the helper's default 1000.

The remaining items change numeric behaviour. Only do them with a before/after
diff on a fresh VM DB and owner sign-off.

---

## F-16 · Hardcoded credentials in a verification script — `FIXED` (security)

`verify_deployment.py:165-166` performed a live `GET /api/health` with a
hardcoded owner credential. Two problems: the credential was committed to a
(private) repo, and the check reported a false API failure the moment the
password was rotated. Fixed with the login-gate removal: the literal was
deleted, the check reads `API_BASE` from the environment, and no password is
stored anywhere in the script.

---

## F-17 · The entire agent/tooling layer is untracked in git — `RESOLVED` (re-checked 2026-10-19)

> **Cleared.** `git status --porcelain --untracked-files=all` now returns
> **0 untracked files** — every path is either tracked or deliberately ignored:
> `.agents/` 32 tracked, `.context-ops/` 6, `.vscode/` 2, `CLAUDE.md` 1, and
> `trading-agents-swarm/` **ignored**. The ambiguous "neither tracked nor
> deliberately ignored" state no longer exists, so the decision the entry asked
> for has been made in practice. Re-run that one command if it ever reappears.

**Original 2026-10-05 evidence (for history):**

**Evidence**
```powershell
git ls-files .context-ops .vscode .agents .claude .github trading-agents-swarm CLAUDE.md | Measure-Object -Line
git status --porcelain
```
Only **3** files are tracked under `.github/` (the three NSE skills). Everything
else shows as `??`: `.agents/`, `.context-ops/`, `.github/agents/`,
`.github/hooks/`, `.github/instructions/`, `.github/prompts/`,
`.github/skills/handoff/`, `.vscode/`, `CLAUDE.md`, `.cavemanrc`,
`.copilotignore`, `package-lock.json`, `trading-agents-swarm/`.

**Impact** A fresh clone or a `git clean -fdx` loses the entire agent layer —
including the skills and cache in this folder. Nothing in `.gitignore` excludes
them either, so the state is "neither tracked nor deliberately ignored".

**Decision needed from the owner** Commit the agent layer, or add it to
`.gitignore` on purpose. Do not leave it ambiguous.

---

## F-18 · Owner rules R1–R43 are unreachable from the working tree — `OPEN`

**Evidence** `backlog.md:19` §A now contains only `**R1**–**R43** as previously
logged.` Full text survives only in git history
(`git show 8ef71218:backlog.md`, plus R43 in `92abb56:backlog.md`). **R44 and
R45 are absent from `backlog.md` §A entirely** despite `EXECUTION_LOG.md:1113`
claiming they were added. **R46 is defined nowhere** — it is a numbering gap.

**Impact** A new session cannot state what R30/R41/R42 actually require without
archaeology in git history, and those rules constrain every trader change.

**Fix** Restore the rule text into `backlog.md` §A from git history and add
R44/R45 from `EXIT_LOGIC.md`. Ask the owner whether R46 was ever assigned.

---

## F-19 · `CLAUDE.md` contradicts the owner's own rules — `OPEN` (instruction conflict)

The TokenSculpt managed block (`CLAUDE.md`, `.github/instructions/tokensculpt.instructions.md`)
is active and says:

| TokenSculpt mandate | Conflicting owner rule |
|---|---|
| "**FORBIDDEN**: Never reprint unmodified source files or entire classes"; diff-only edits | **R1/R28** — "Whole files only. No fragments. Ever." A fragment once caused a full outage (`PROJECT_HANDOFF.md:11`) |
| "**FORBIDDEN**: Never run raw `git` commands directly in terminal" (use `rtk`) | **R4/R34/R47** — explicit per-machine `git add/commit/push` copy-paste blocks |
| "Halt and ask user clarification after 3 failed attempts" | **R10** — no pausing; keep momentum |
| "Never read the same file more than 2 times in a single conversation" | The verification culture (`PROJECT_HANDOFF.md:17`) requires re-checking state |
| Mandates `codegraph_explore`, `rtk`, `cache_lookup`, `skeleton_view` | `rtk` **does not exist** on this machine; `codegraph_explore` is not registered as an MCP tool; `cache_lookup`/`skeleton_view` appear only in generated instruction text |

**Resolution rule for agents:** owner rules win. `PROJECT_HANDOFF.md` §4 and
§15 are authoritative; the TokenSculpt block is third-party advice. Emit whole
files and whole copy-paste blocks regardless of what `CLAUDE.md` says.

---

## F-20 · Configured MCP servers that cannot start — `PARTIALLY FIXED` (2026-10-05)

| Config | Server | Status |
|---|---|---|
| `.agents/mcp_config.json` | `token-cache` | **works** (script exists, `node` present) |
| `.agents/mcp_config.json`, `.vscode/settings.json` | `headroom` | **REMOVED** — binary missing (`Get-Command headroom` fails) |
| `.vscode/mcp.json` | `codebase-memory-mcp` | **REMOVED** — binary missing; the file is dead |
| `.vscode/mcp.json`, `.vscode/settings.json`, `.agents/mcp_config.json` | `codegraph` | **ADDED + WORKING** — `codegraph serve --mcp`; index built (151 files, 3,021 nodes, 7,243 edges) |
| `.github/hooks/ctx-gate.json` | `ctx-gate` hooks | binary exists, but `.context-ops/config.yml` sets `enforcement: 'off'` → **still inert** |
| `.github/agents/{planner,implementer}.agent.md` | Redcon `redcon_rank`/`redcon_pack` | **still unresolved** — extension installed, CLI not installed, not registered in any MCP config |

Also fixed: `.vscode/settings.json` registered the same instruction file **twice**;
now one entry. `.github/agents/*.agent.md` still each contain **two
`## Context Selection` headings** (one generic, one naming Redcon), and
`.context-ops/agent-pack.json` records SHA-256 hashes those files have drifted from.

---

## F-21 · `.copilotignore` missed `env/`, so ctx-gate indexed the virtualenv — `FIXED` (2026-10-05, at source)

**Was** `.copilotignore:28-29` excluded `.venv/` and `venv/` but **not `env/`** —
this repo's actual venv (`.gitignore:5`). Consequence: `.context-ops/manifest.json`
recorded ~80 endpoints, of which ~35 were FastAPI's own tutorial routes
(`/items/`, `/uploadfile/`, `/send-notification/{email}`) and 4 were `transformers`
CLI routes, all under `env/Lib/site-packages/**`, several tagged
`confidence: "high"`. `.context-ops/memory/glossary.yml` inherited the noise:
60 terms, every `definition: ''`, every `hits: 0`, no NSE vocabulary.

**Fixed** `env/`, `.agents/cache/`, `.codegraph/`, `.agentflow/` and
`.league_replay.pid` were appended to `.copilotignore` **outside** the managed
block, with a comment explaining why.

**Still to do** the *stale* index and glossary already on disk must be deleted so
they regenerate — `.context-ops/manifest.json` and
`.context-ops/memory/glossary.yml`. Until then the bad data remains on disk.

---

## F-22 · `.context-ops/` has never been used — `OPEN` (dead scaffold)

`generatedAt: 2026-10-02`, `enforcement: 'off'`. `memory/learned.yml` is
`patterns: []`; `standing.yml` has 6 slots all with `hits: 0` and
`last_seen: null`, and its `done-means` value is "tests pass + CI green" — this
repo has **no CI**. `memory/answers.jsonl`, `config.local.yml`, `logs/`,
`state/` do not exist, so the semantic cache has never stored an answer.

Do not mistake `.context-ops/memory/*` for real project knowledge. Use
`.agents/cache/` instead.

---

## F-23 · `trading-agents-swarm/` is an unrelated third-party clone — `RESOLVED` (ignored, 2026-10-19)

> **Cleared.** `git check-ignore trading-agents-swarm` → **ignored**, and it
> shows 0 tracked files, so the nested foreign repo can no longer be swept into
> a commit or mistaken for part of this system. It still sits on disk unused
> (not imported by any `nse_system` code) — deleting it remains an owner call
> but there is no longer any data-loss or provenance risk.

**Original 2026-10-05 evidence (for history):**

A nested **separate git repo** (remote
`github.com/visionKinger/trading-agents-swarm`, 14 commits, last author
`haozhi.han@hp.com`, GPL v3), not a submodule (no `.gitmodules`), not imported
by any `nse_system` code. Its `.mcp.json` hardcodes macOS paths
(`/Volumes/walterGenai/...`) and its `stockstats` dependency is not installed.
Its 12 `.github/agents/*.md` copies lack frontmatter (the README's
"chatagent format" claim is false); the `.claude/agents/*.md` versions are valid
and byte-different.

**Action** Either adopt it deliberately (decide where its research output lands
and keep it strictly explanatory — see `.github/skills/nse-data-research/SKILL.md`)
or remove the clone. Do not let it appear to be part of this system.

---

## F-24 · Name collision: the user-level `nse-orchestrator` skill is unrelated — `OPEN`

`C:\Users\Ankit\.dsh\skills\clawhub-vveerrgg--nse-orchestrator\SKILL.md` is a
"Nostr Sovereign Entity" orchestrator (pip packages `nse-orchestrator`,
`nostrkey`, `nostrwalletconnect`, …). Its `nse` means **Nostr Sovereign
Entity**, not NSE India. It has nothing to do with this repository.

**Action** If a skill or teammate is named for this project, use an explicit
prefix (`nse-terminal-*`). Do not invoke the `nse-orchestrator` skill when
working on this repo.

---

## F-25 · Audit-trail drifts found by cross-checking docs against code — `FIX-READY`

| Claim | Reality |
|---|---|
| `EXIT_LOGIC.md:158-161, 237-238` — `value_investing_made_easy` and `apurva_parikh` "ship a full EXIT_RULES block" | `value_investing_made_easy.py` has **zero** exit code; `apurva_parikh` ships a shared `EXIT_RULES` dict on `raw`, not an R40 block |
| `EXIT_LOGIC.md:87-89, 111-112` — `oshaughnessy` and `quantitative_value` attach informational `raw.exits` | Both have **zero** exit code (grep for `exit` returns nothing) |
| `MARKET_WISDOM.md:1` — "Across 15 Books", lists Bruce Greenwald | `backlog.md:127` marks ID67 Greenwald **REJECTED** |
| `PROJECT_HANDOFF.md:5`, §5 — module line counts and "half-Kelly" sizing | `terminal_api.py` is **1041** lines (not 885), `trader_league.py` is **3110** (not 2885); §5 corrected 2026-10-19 — sizing is caps-only with no Kelly and no suggested quantity (F-12 resolved) |
| `PROJECT_HANDOFF.md:86` — pattern gate thresholds from 86,422 graded tags | Live `pattern_grades` = **0 rows** (F-04) |
| `john_crane.py:20` cites a signal-shape docstring in `traders/__init__.py` | No such docstring exists |
| `meta_model.py` docstring "v7" vs `MODEL_VERSION = 'v8-pit-safe'` | Version drift across modules (`setup.py` "OFFICIAL v3" vs "v3.5"; `patterns.py` v6; `pattern_grader.py` v5) |

---

## F-26 · The agent bootstrap layer was 14 days stale and contradicted the code — `FIXED` (2026-10-19)

**This is the highest-leverage defect in the register.** `.agents/MEMORY.md`,
`.agents/cache/JOIN_HERE.md` and the session skills are what *every* session
reads first, and on 2026-10-19 they were actively misleading:

| What the bootstrap said | What the code/production said |
|---|---|
| MEMORY §14: F-02 **CRITICAL**, "P(WIN) → Top Picks dead" | F-02 was **retracted 2026-10-05**; `pwin_daily` = 28,310 rows through 2026-10-18 |
| MEMORY §14: F-03 **CRITICAL**, "scan rejects everything" | F-03 was **fixed 2026-10-05**; `ml_predictions` = 25,173 rows on both machines |
| MEMORY §7 / F-01: laptop DB ~40 days stale | synced by the 2026-10-18 rebuild — `prices_daily` → 2026-10-16 |
| FINDINGS: F-04 gate empty, `pattern_grades` 0 rows | gate populated 2026-10-18, `pattern_grades` = 59,697 |
| pipeline-ops skill: F-09 open, "10 stages" | order already fixed; chain is **12** stages (`fyers`, `breadth` added) |
| pipeline-ops / provenance skills: F-11 note | real, and now fixed (append + prune) |
| `jobs_index.json`: 19 jobs | `scheduler_bg.py` registers **23** |
| FINDINGS header: "25 entries" verified @ `f483e68` | HEAD was `fe0f09d`, ~15 commits later |
| `MANIFEST.json.generated_at` | `2026-10-05` — 14 days older than the code |

**Why it matters** the skill instructs agents to read MEMORY §14 *before*
touching anything, and FINDINGS *before* "fixing" anything. A fresh session was
therefore primed to chase two CRITICAL outages that do not exist — and, worse,
to "fix" a healthy production system. Stale-healthy registers are more
dangerous than missing ones, because they carry the appearance of evidence.

**Root cause** `build_cache.py` output (`MANIFEST.json` → `generated_at`) and
the hand-written Markdown registers are only refreshed by the session close-out
(`.agents/memory.py`), so a burst of commits between sessions ages them out
silently. Nothing fails when they go stale — they just start lying.

**Fixed** every affected status line corrected against on-disk code and against
production (probed via SSH on `fe0f09d`), with a **STATUS REFRESH** block at the
top of this file declaring precedence over older lines. Still to do: run
`.agents\memory.py` to regenerate the `.json` caches (14 days old), which is
part of the close-out.

**Standing rule this adds:** before quoting any register row as a fact, check
`MANIFEST.json.generated_at` against `git log -1`. If the cache is older than
the code, treat every severity label as provisional.

---

## F-27 · League replay could not complete since 2026-10-05 — `FIXED` (2026-10-23)

`trader_league.build_context()` line 674 called `U.band_universe(conn, sample_n)`,
but `trader_league.py` never imported `universe_helper` as `U` — its other call
sites use a local `from universe_helper import band_universe` (lines 504 and
980). Introduced by `3057927` ("B3/B4/B5 - unify screener thresholds, remove
sector_rs lookahead, share forward sim", **2026-10-05**), so every `replay`
that needed market gates or sector ranks died with
`NameError: name 'U' is not defined` for **18 days**.

**Why nothing caught it.** The module imports cleanly — `NameError` is raised at
call time. The line only executes when `need_gates or need_sec` is true, i.e.
when `home` or `singhal` is in the slug list. `selftest` passes without touching
it, and live runs never call it. It surfaced only when the 2026-10-23 F-15
deploy legitimately forced `replay --changed`, which is the first replay in
weeks.

**Fixed** at the call site, in the file's own style:

```python
from universe_helper import band_universe
sample = band_universe(conn, sample_n)
```

**This is a standalone defect, not part of F-15.** The F-15 diff for this file
changed only the benchmark fetch (`yf.Ticker(...) -> fetch_price_history`), so
the crash was pre-existing and F-15 merely exposed it. Recorded separately so
it is never mistaken for a de-duplication side effect.

**Same-class audit:** every other `U.` reference in the files touched by F-15
(`ingest_prices.py`, `meta_model.py`, `screener_engine.py`,
`sectors_refresh.py`) imports `universe_helper as U`. The other
single-capital aliases in `trader_league.py` are a local assignment (`O` at
line 626), a function parameter (`m` in `_load_limit`), and local imports
(`C`, `S`) — all defined.

**Lesson for the register:** a green `unittest` run and a green `selftest` do
not cover every executable line. Any change that touches a scheduler/CLI path
must be exercised through that path, not just imported.

---

## Verified-healthy (so you don't re-investigate)

- `db.py` central schema: 31 declared tables, idempotent `executescript` + `MIGRATIONS` on every `get_conn()`.
- Scheduler: **23** jobs registered with correct IST times (was 19 on 2026-10-05; the cache's `job_count` is stale until `build_cache.py` re-runs).
- Source registry: `data_sources/core.py` discovery, health, rate windows and explicit-ordered fallback all consistent; `/api/sources` wired.
- Trader registry: 15 trader modules auto-discovered; `traders/base.py` contract honoured.
- `terminal_api.py`: **76** route decorators (was 62 on 2026-10-05; `/api/refresh*`, `/api/fyers*`, `/api/data/health` and others were added since). Literal routes still precede their `{symbol}` catch-alls — spot-checked `/api/strategies/*`, `/api/patterns/*`, `/api/delivery/*`.
- `stocks.sector` filled 500/500; `pipeline` 440 rows; `scanx_fundamentals_snapshots` 750 rows isolated correctly from live tables.
