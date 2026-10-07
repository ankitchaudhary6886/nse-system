# FINDINGS — verified defects register

Every entry was **observed**, not inferred. Evidence is reproducible with the
command shown. Check this file before "fixing" anything: several items are
deliberately gated by owner rules and must not be touched.

Status legend: `OPEN` (needs a decision) · `FIX-READY` (safe, scoped, no owner
gate) · `GATED` (owner approval / upstream data required) · `FIXED`.

Verified 2026-10-05 on `C:\Users\Ankit\Desktop\nse_system` (laptop, stale DB)
against `main` @ `f483e68`.

---

## F-01 · Laptop DB is ~40 days stale — `OPEN` (informational)

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

## F-04 · The empirical pattern gate is vacuously open — `OPEN`

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

## F-05 · Auth is opt-in and part of the surface is public — `OPEN` (security)

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

## F-07 · `window.loadResearchSectors` is never exported — `FIX-READY`

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

## F-08 · `deployment.js` is dead and would double-bind if wired as-is — `FIX-READY`

`deployment.js` (39 lines) is **not** referenced by `index.html` (absent from
`api_index.json.asset_versions.script_tags`). Its own `DOMContentLoaded` handler
(deployment.js:33-38) binds `#refreshBtn` — which app.js:599-626 already owns via
`refreshAll` — and re-fetches `/api/deployment-check`. Either delete the file or
refactor it to an exported `window.loadDeployment` with no listeners, then wire it.

---

## F-09 · ML runs after scan in `daily_update` — `FIX-READY` (ordering)

`daily_update.py:46-49` — stage 3 `scan.run()`, stage 4
`ml_predict.predict_all()`. `scan.py:20-24` reads
`MAX(prediction_date)` from `ml_predictions`. So today's ML score can never
influence today's scan, and on a cold DB `mv is None` rejects everything
(scan.py:50). Swap the two stages (and keep F-03's retrain in mind — the swap
alone will not help while `ml_predictions` is empty).

---

## F-10 · `fundamentals_tv.run(N)` is not top-N — `FIX-READY`

`fundamentals_tv._universe()` returns symbols alphabetically sorted;
`run(limit=n)` truncates **after** sorting (fundamentals_tv.py:95-96). So
`python fundamentals_tv.py run 100` fetches the first 100 symbols alphabetically,
not the top 100 by market cap. Sort by `mcap_cr DESC` before truncating.

---

## F-11 · `data_quality` destroys its own history — `FIX-READY`

`data_quality.py:213` runs `DELETE FROM data_quality_log` before every run.
`data_quality_log` holds only the latest run (6 rows live). Either drop the
DELETE (keep append-only, filter by `run_at` in the UI) or retain the last N runs.

---

## F-12 · "half-Kelly" sizing does not exist — `OPEN` (doc vs code)

`sizing.py:125-126` hardcodes `kelly_pct = None` and `half_kelly_pct = None`;
`sizing.py:115` sets `p_win = None`. `strategy_config.SIZING.B_PAYOFF` (3.0) and
`FALLBACK_WINRATE` (0.35) are referenced nowhere outside `strategy_config.py`.
Only caps are implemented: `MAX_ALLOC 0.25`, `RISK_PER_TRADE 0.01`,
`QUALITY_TIERS` scaling. PROJECT_HANDOFF §5 calls it "half-Kelly position
sizing" — that is aspirational. Either implement Kelly from `p_win_daily` or
rename/document the caps-only behaviour.

---

## F-13 · Double veto + post-insert "suppressed" alert — `FIX-READY`

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

## F-15 · Duplication hotspots — `PARTIALLY FIXED` (2026-10-05)

| Duplicated thing | Copies | Status |
|---|---|---|
| Band universe SQL (`mcap_cr BETWEEN 1000 AND 8000 …`) | was **17** inline copies | **FIXED** — all now call `universe_helper.band_universe(conn, limit)`. Equivalence proven at all 15 refactored sites. `limit=None` added for the unbounded callers |
| Yahoo direct call sites | ~14 files bypass `data_sources` | **OPEN** (ID52) |
| Stage-2/VCP logic | `screener_engine.py` (hardcoded :138-173) vs `strategy_config.SCREENER` + `setup.py` | **OPEN** — changes numeric behaviour |
| Forward simulation (3-bar trigger, 30-bar hold, stop-first) | `build_setup_pool._simulate` :146-185 vs `research_cockpit._simulate_forward` :322-378 | **OPEN** |
| Sector PE medians | `scoring.sector_pe_medians` :41-53 vs `positional_scanner._sector_pe_medians` :119-128 | **OPEN** |

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

## F-17 · The entire agent/tooling layer is untracked in git — `OPEN` (data-loss risk)

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

## F-23 · `trading-agents-swarm/` is an unrelated third-party clone — `OPEN` (clarity)

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
| `PROJECT_HANDOFF.md:5`, §5 — module line counts and "half-Kelly" sizing | `terminal_api.py` is **1041** lines (not 885), `trader_league.py` is **3110** (not 2885); `sizing.py` has no Kelly maths (F-12) |
| `PROJECT_HANDOFF.md:86` — pattern gate thresholds from 86,422 graded tags | Live `pattern_grades` = **0 rows** (F-04) |
| `john_crane.py:20` cites a signal-shape docstring in `traders/__init__.py` | No such docstring exists |
| `meta_model.py` docstring "v7" vs `MODEL_VERSION = 'v8-pit-safe'` | Version drift across modules (`setup.py` "OFFICIAL v3" vs "v3.5"; `patterns.py` v6; `pattern_grader.py` v5) |

---

## Verified-healthy (so you don't re-investigate)

- `db.py` central schema: 31 declared tables, idempotent `executescript` + `MIGRATIONS` on every `get_conn()`.
- Scheduler: 19 jobs registered with correct IST times (`jobs_index.json.job_count == 19`).
- Source registry: `data_sources/core.py` discovery, health, rate windows and explicit-ordered fallback all consistent; `/api/sources` wired.
- Trader registry: 15 trader modules auto-discovered; `traders/base.py` contract honoured.
- `terminal_api.py`: 62 unique routes, all business routes except the webhook carry `Depends(verify_user)`.
- `stocks.sector` filled 500/500; `pipeline` 440 rows; `scanx_fundamentals_snapshots` 750 rows isolated correctly from live tables.
