# SUBAGENTS — roster designed for this system

Derived from the 12 components in `.agents/cache/JOIN_HERE.md` §3. One teammate
per component boundary, so write scopes stay disjoint.

**How to use this file.** These are the *capability definitions*. In a session
where Agent Teams is available, spawn the 2–4 teammates the task actually needs
using the prompts below. When work is a single component, do it directly —
do not spawn a teammate for a one-file change.

**Universal brief (prepend to every teammate prompt):**

> Repo: `C:\Users\Ankit\Desktop\nse_system`. Read `.agents/cache/JOIN_HERE.md`
> and `.agents/cache/FINDINGS.md` first; use `.agents/cache/*.json` for module,
> DB, API and job facts instead of grepping. Owner rules are absolute: whole
> files only (never fragments), no paid services, every optional integration
> wrapped in `try/except`, DB changes via `CREATE TABLE IF NOT EXISTS` /
> `INSERT OR REPLACE` (never `DROP`), and never claim success without command
> output. Do not touch `PROJECT_HANDOFF.md` CHANGELOG or `EXECUTION_LOG.md`
> unless your task says so — the Lead owns those. Report file:line evidence for
> every claim; if you cannot verify something, say so instead of guessing.

---

## Roster

| # | Teammate | Owns (write scope) | Reads | Never touches |
|---|---|---|---|---|
| T1 | `data-plane` | `data_sources/**`, `ingest_*.py`, `universe*.py` | `db.py`, `config.py` | `terminal_api.py`, `traders/**` |
| T2 | `data-integrity` | `data_quality.py`, `*_import.py`, `*_reconcile.py`, `*_snapshot_report.py`, `fundamentals_store.py` | `db.py`, `data/*.db` (read-only) | live price/fundamental tables (writes only via approved promotion) |
| T3 | `strategy-core` | `setup.py`, `scanner.py`, `screener_engine.py`, `scoring.py`, `rule_engine.py`, `strategy_config.py` | `technicals.py` | `swing_live.py`, `top_picks.py` |
| T4 | `market-context` | `regime.py`, `regime_spectrum.py`, `breadth.py`, `sector_gate.py`, `macro.py`, `fund_veto.py` | `universe_helper.py` | `setup.py` |
| T5 | `flow-and-events` | `institutional.py`, `delivery.py`, `events.py`, `corporate.py` | `technicals.py` | `swing_live.py` |
| T6 | `patterns-and-shape` | `patterns.py`, `pattern_grader.py`, `template_match.py`, `build_setup_pool.py` | `technicals.py` | `meta_model.py` |
| T7 | `ml-and-pwin` | `meta_model.py`, `ml_features.py`, `ml_train.py`, `ml_predict.py`, `pwin_cache.py`, `model_report.py` | `data/*.pkl` (read-only) | `top_picks.py` |
| T8 | `signals-and-risk` | `swing_live.py`, `top_picks.py`, `all_weather.py`, `sizing.py`, `ledger.py`, `validate.py` | `setup.py`, `fund_veto.py` | `traders/**` |
| T9 | `traders-librarian` | `traders/*.py`, `EXIT_LOGIC.md` (their section only) | `traders/base.py`, `traders/__init__.py` | `trader_league.py` |
| T10 | `league-analyst` | `trader_league.py`, `strategy_backtest.py`, `strategy_runs.py`, `backtest.py`, `fast_wf.py` | `traders/**` (read-only) | `traders/*.py` |
| T11 | `terminal-frontend` | `terminal_api.py`, `terminal/static/*` | `.agents/cache/api_index.json` | `scheduler_bg.py` |
| T12 | `ops-and-deploy` | `scheduler_bg.py`, `daily_update.py`, `log_utils.py`, `verify_deployment.py`, `alerts.py` | `.agents/cache/jobs_index.json` | `terminal/static/*` |

**Conflict rule.** T8 owns `swing_live.py` and T3 owns `setup.py`; a change to
the gate order touches both — sequence it (T3 first, then T8) rather than
running them concurrently. Same for T7 ↔ T8 (`pwin_cache` feeds `top_picks`) and
T9 ↔ T10 (trader code changes invalidate `code_hash`, forcing a `--changed` replay).

---

## Per-teammate briefs

### T1 · `data-plane` — acquisition and providers

**Goal:** every external value enters through `data_sources/`, with an ordered
fallback, a recorded rate budget, and no silent loss.

Deliverables when asked to work:
- Migrate one direct-Yahoo call site to the registry (there are ~14; the list is
  in the data-plane report and `system_map.json`). Never migrate all at once.
- Keep `SourceRegistry.fetch(dataset, providers, accept=...)` explicit-ordered.
- Fix `fundamentals_tv._universe()` truncation (F-10) **only if asked**.

Verification: `python -c "from data_sources import get_registry; print(get_registry().health())"`,
then the narrowest affected test (`test_data_sources.py`).

### T2 · `data-integrity` — quality, provenance, promotion

**Goal:** nothing enters a live table without a per-field rule and evidence;
nothing is silently deleted.

Non-negotiables (from `.github/skills/nse-data-research/SKILL.md` — follow it, do
not restate it): preview before apply, backup before apply, idempotence proof,
per-field before/after evidence, raw retained, unresolved rows kept visible.

Never: reuse the KITE/ScanX 1 % tolerance for another field without validating it;
treat a file mtime as publication time; let a snapshot outrank a newer daily bar.

### T3 · `strategy-core` — the official setup

**Goal:** `setup.SetupDetector` + `scanner.Screener` + `strategy_config` stay the
single source of truth for the entry pattern.

- All thresholds live in `strategy_config.SETUP` / `.SCREENER`; do not add
  literals to `setup.py` (only `0.08`, `0.03` in `shape_score` and the
  `1.02`/`0.98` EMA zone are still inline — flag, do not silently change).
- Changing any `SETUP`/`SCREENER` value invalidates the League: it changes
  `home`'s `code_hash` → a `replay --changed` is mandatory (rule I block in
  `TRADER_LEAGUE.md`).
- `screener_engine.py` duplicates Stage-2 with different numbers (F-15). Do not
  "reconcile" them without an owner decision — they are on different code paths.

### T4 · `market-context` — gates

**Goal:** regime, breadth, sector-RS and the fundamental veto behave as
documented and fail loudly, not silently.

Order matters. Documented order: regime → breadth → sector → history →
screener → setup → staleness → veto → insert. `regime.compute()` raising when no
benchmark exists is intentional; do not swallow it.

### T5 · `flow-and-events` — accumulation and calendar

**Goal:** delivery %, up-volume accumulation, corporate calendar and derived
events populate their tables on the VM.

Remember: NSE is blocked from datacenter IPs, so empty `delivery_daily` /
`macro_flow` on the VM is expected. Show the fetch error rather than a zero.

### T6 · `patterns-and-shape` — evidence-gated patterns

**Goal:** a pattern is only live if empirical grading earns it.

- The gate is ≥30 graded tags **and** ≥60 % WR (`pattern_grader.py:30-33`);
  ungraded patterns are provisional-enabled, which is why the gate is currently
  vacuous (F-04). Never loosen the bar to get a pass.
- Historical tags for killed patterns are **retained for audit** (2026-09-17
  BULL_FLAG decision). Do not delete them.
- `pattern_tag` dates and `pattern_grades` must stay in sync via
  `grade_all()`/`report()`.

### T7 · `ml-and-pwin` — models with hard compatibility guards

**Goal:** the model bundle format is law; a mismatch must refuse, never
silently score with a stale model.

- `meta_model` requires `{model, features, version, metadata}` with
  `version == "v8-pit-safe"` and 27 features. `ml_predict` requires
  `"v0.2-pit-safe"`. Both currently fail (F-02/F-03).
- Retraining writes `model_runs` via `model_report.record`; `lift_test()`
  records C3 lift as `note="c3_lift"`.
- Never hand-edit a `.pkl`. Retrain on a machine with fresh prices (the VM).
- A feature-list change is a breaking change: bump `MODEL_VERSION`, retrain,
  and expect `pwin_daily`/`ml_predictions` to be empty until then.

### T8 · `signals-and-risk` — the gates and the scorecard

**Goal:** a stored signal has survived every gate, and the scorecard never
overstates.

- Gate/veto/staleness order is load-bearing; see `JOIN_HERE.md` §2.3.
- `sizing.py` is caps-only today, not half-Kelly (F-12). If you implement Kelly,
  source `p_win` from `pwin_daily` and keep the caps as the upper bound.
- `validate.monte_carlo` needs ≥15 graded trades; with 9 rows live, any verdict
  is noise. Say so rather than reporting a number.

### T9 · `traders-librarian` — the book library

**Goal:** one file per book, setup-identification only.

Hard rules:
- **R30** — setup identification only; no execution, stop placement, sizing or
  trailing logic in trader code. The book's exit philosophy goes in prose, into
  `EXIT_LOGIC.md`.
- **R35** — `_fmt_num` + `_try_emit` so one bad symbol cannot kill a scan.
- **R38/R40** — five books ship structured `raw.exits` (nison R38 shape;
  chande/oneil/mcallen/singhal R40 with `thesis`+`hard_number`+`condition`).
  Exits are **suggestive, not directive**.
- **R41** — `overlaps_with=[...]` where a signal echoes another book.
- **R42** — inline indicators with the book's exact parameters; no proxies.
- **R43** — `LONG_ENTRY` vs `TOP_WARNING` (warnings are informational).
- **R44** — add the `EXIT_LOGIC.md` section. **R45** — add the wisdom artifact.
- Register in `traders/__init__.py` (explicit list, not auto-discovery).
- Any trader code change alters `code_hash` → the League must re-run
  `replay --changed`.

Doc drift to fix when you touch them: `EXIT_LOGIC.md` claims exit blocks for
`oshaughnessy`, `quantitative_value`, `value_investing_made_easy` and
`apurva_parikh` that do not exist in code.

### T10 · `league-analyst` — the harness

**Goal:** the League stays a faithful, point-in-time, cost-realistic simulator,
and its verdict is never softened.

- The no-lookahead guarantee is enforced by the self-test: replay over the last
  80 days must equal scanning a chart cut at each day. Keep it green (`28/28`).
- Readiness thresholds are fixed (trades ≥50, PF ≥1.3, DD ≤25 %, CAGR > Nifty,
  ≥60 % of years positive, MC DD95 ≤35 %, worst-fill PF ≥1.0, ≥30 live paper
  trades at PF ≥1.0). A failed gate stays failed.
- A signal-side change → `replay --changed --background`, then confirm `status`
  shows no `code changed`.
- Current verdict: **NOT READY** (PF 0.93, −6.2 % vs Nifty +5.5 %). Do not
  present any result as real-money-ready.

### T11 · `terminal-frontend` — API and UI

**Goal:** the phone UI never blanks and never leaks.

- Auth is opt-in per route: every new route needs `Depends(verify_user)`
  (F-05). Never put a secret in `terminal/static/`.
- Register literal paths **before** the same prefix's `{symbol}` catch-all (F-06).
- Editing a static file means bumping its `?v=` in `index.html`; the current
  versions are in `api_index.json.asset_versions`.
- Optional integrations stay in `try/except`; a handler returning
  `{"error": ...}` with HTTP 200 is the house style — keep it consistent.
- Backend change → `sudo systemctl restart nse-terminal`. Static change → no
  restart, hard refresh.

### T12 · `ops-and-deploy` — automation and evidence

**Goal:** the 19 IST jobs run, and every deploy is verified before it is called
successful.

- New job → a `_x_job()` wrapper with `log_utils.get_logger`, `try/except`,
  `add_job(..., id=..., replace_existing=True)`, and the `start()` banner updated.
- Scheduler times are IST; `journalctl` is UTC. Never confuse them in a diagnosis.
- A DB-only change needs no restart; a `.py` change does.
- `verify_deployment.py` hardcodes credentials (F-16) — read them from env if you
  touch it.
- Failures must remain visible: log the exception, never convert it into an
  empty-but-successful result.

---

## Delegation patterns that work here

| Situation | Fan-out |
|---|---|
| "Why is Top Picks empty?" | T7 (model bundles — F-02) then T8 (composite inputs). Sequential: T8 depends on T7's verdict. |
| "The terminal shows nothing on the phone" | T11 alone. It is one component. |
| "Deploy and verify X" | T12 owns the deploy; the component owner prepares the diff. Never two writers in one file. |
| "Add a 15th trading book" | T9 writes the trader + `EXIT_LOGIC.md` + `__init__`; T10 then runs `replay --changed`. Ordered, disjoint files. |
| "Is the system healthy?" | Read-only: `verify_deployment.py` locally is meaningless (stale DB) — the check belongs on the VM. Do not spawn writers for this. |
| Broad audit across many files | Use the `workflow` tool with a per-file pipeline rather than 12 teammates. |

**Do not spawn a teammate** for: a single-file read, a cache regeneration, a
doc edit, or anything the Lead can finish in one step.
