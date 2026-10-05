---
name: nse-terminal-models
description: Use when training, loading, debugging, or changing the NSE terminal's LightGBM models and derived scores — the meta-model bundle guard, the ml_models version guard, feature-list changes, P(WIN) caching, the C3 lift ledger, and why the ML branch is currently inert.
---

# NSE Terminal — Models, P(WIN) and Derived Scores

There are **two independent model pipelines**. They do not share a file, a
version, or a feature list. Confusing them is the most common mistake here.

| | meta-model | ml_train / ml_predict |
|---|---|---|
| File | `data/meta_model.pkl` | `data/ml_models.pkl` |
| Module | `meta_model.py` | `ml_train.py` + `ml_predict.py` |
| Required version | `v8-pit-safe` | `v0.2-pit-safe` |
| Features | 27 (`FEATURES`) | 9 (`ml_features.FEATURE_COLUMNS`) |
| Output | `pwin_daily` (via `pwin_cache`) | `ml_predictions` |
| Consumed by | `top_picks.compute`, UI | `scan.run` (gate `MIN_ML = 70`) |
| Label | max high in next **20** sessions ≥ **+10 %** | return > train-median over 126/252 sessions |

## 1. The meta-model bundle is a strict contract

`meta_model.get_model()` refuses anything that is not:
```python
{"model": <LGBMClassifier>, "features": FEATURES,
 "version": "v8-pit-safe",
 "metadata": {"label": ..., "horizon_sessions": ...,
              "context_features_excluded": [...],
              "imputation_medians": {...}, "split": ..., "validation": ..., "test": ...}}
```
A bare estimator is rejected; a bundle with mismatched `version`, `FEATURES`, the
label, or the sorted `CONTEXT_FEATS` list is rejected. This is deliberate: a
silently-mismatched feature order produces plausible-looking garbage.

**Current state: the guard is failing (F-02).** `data/meta_model.pkl` on the
laptop is a bare `LGBMClassifier`, so `get_model()` returns `None`, so
`score_symbol()` returns `None`, so `pwin_daily` is empty, so `top_picks` is
empty and the Top-Picks UI is blank.

**Fix is a retrain, never a pickle edit:**
```bash
cd ~/nse-system
source venv/bin/activate
python meta_model.py train
python -c "import sqlite3;print(sqlite3.connect('data/app.db').execute('SELECT COUNT(*),MAX(date) FROM pwin_daily').fetchone())"
python top_picks.py
```
Retraining writes `model_runs` via `model_report.record`, so the run is auditable.

## 2. Feature-list changes are breaking changes

`FEATURES` (meta_model.py:74-86) currently has 27 entries:
momentum and distance (`mom1, mom3, mom6, d52, above200, slope200`), price
structure (`pb, d10, d20, atr, rv, vc, vcr, ret_std20, below52`), pattern flags
(`pat_htf, pat_tri, pat_db, pat_flag, pat_ihs, pat_bear, pat_any`), shape
(`dtw_sim`) and flow (`delivery_sim`), plus three newer ones
(`days_above_200_30, days_above_50_30, ema200_dist_z`).

**Excluded by design:** `CONTEXT_FEATS = {roce, pe, debt_eq, promoter,
sector_rs, sentiment}` (meta_model.py:87-88) are computed and then *not*
trained — they exist only as SHAP context. `PRICE_FEATS` = every feature minus
`CONTEXT_FEATS`, used by `lift_test()` to measure C3 lift.

If you add or remove a feature:
1. bump `MODEL_VERSION`;
2. retrain (an old bundle now refuses to load — that is correct);
3. expect `pwin_daily` and `ml_predictions` to be empty until the retrain lands;
4. record the lift delta (`model_report.record(..., note="c3_lift")`).

Two hygiene rules learned the hard way:
- Context columns must be `pd.to_numeric`-coerced with a median fill — LightGBM
  rejects `object` dtypes and will fail the whole train, not one row.
- `dtw_sim` and `delivery_sim` default to a neutral constant when their source
  tables are empty (`template_scores`, `delivery_daily`). A dead feature is
  worse than a missing one: it looks like signal. `setup_pool` **does not exist**
  on the laptop, so `dtw_sim` is a constant 0 there.

## 3. The ml_train/ml_predict pipeline

- `ml_train.py` learns the label threshold **on the training split only**
  (`ret > train median`), splits 70/15/15 with purging, and writes
  `data/ml_models.pkl` as `{"m6", "m12", "feat_cols", "version"}`.
- `ml_predict.predict_all()` verifies `version`, `feat_cols`,
  `metadata.features`, and `imputation_medians` before scoring. Score =
  `50*p6 + 50*p12` (0-100); rank = `100*(n-i)/n`; needs ≥252 closes.
- **Current state: the guard is failing (F-03).** `data/ml_models.pkl` is
  `v0.1`; the loader demands `v0.2-pit-safe`. So `predict_all()` writes nothing,
  `ml_predictions` is empty, and `scan.run` rejects **every** symbol with
  `mv is None`. This is why `scan_results.passed` can be all-zero — it is not a
  market condition.

Fix: `python ml_train.py` then `python ml_predict.py`, and verify
`SELECT COUNT(*), MAX(prediction_date) FROM ml_predictions`.

## 4. P(WIN) and the composite score

- `pwin_cache.refresh_all()` stores only rows whose `model_version` matches
  `meta_model.MODEL_VERSION` (so a version bump invalidates the cache by
  design). Batch 600 band ∪ active; commit every 50.
- `top_picks.compute()` composite:
  `0.45*p_win + 0.25*accum + 0.15*sector_rs + 0.15*delivery`, plus **+0.10** for
  a live-setup match. Missing inputs default to `0.5`, so an empty
  `institutional`/`delivery_daily`/`breadth_daily` table silently produces
  neutral scores — check the inputs before trusting the ranking.
- `delivery` conviction = `clip((avg10d delivery% − 30)/50, 0, 1)`.
- `top_picks` stores the top 50 and **skips vetoed symbols**.

## 5. Rule: an empty table is not a zero

Every model-derived number degrades to a neutral constant when its upstream is
empty (`p_win` → skip, `accum`/`sector_rs`/`delivery` → 0.5, `dtw_sim` → 0,
`delivery_sim` → 0.5). Before reporting a score, confirm each input table has
rows for the date:
```sql
SELECT (SELECT COUNT(*) FROM pwin_daily)      AS pwin,
       (SELECT COUNT(*) FROM ml_predictions)  AS ml,
       (SELECT COUNT(*) FROM institutional)   AS inst,
       (SELECT COUNT(*) FROM delivery_daily)  AS deliv,
       (SELECT COUNT(*) FROM breadth_daily)   AS breadth,
       (SELECT COUNT(*) FROM template_scores) AS tmpl;
```

## 6. Validation and drift

- `validate.py` Monte Carlo needs **≥15 graded trades** (`swing_signals` with
  WIN/LOSS); with 9 rows live, any verdict is statistically meaningless — say so.
- Walk-forward verdicts: `n < 20 = insufficient`; WR ≥ 0.45 & PF ≥ 1.5 = EDGE
  HOLDS; WR ≥ 0.40 & PF ≥ 1.2 = WEAK EDGE; else NO EDGE. PF caps at 999 with no
  losses — never present that as a strong result.
- `scheduler_bg._drift_check()` alerts when the live win rate over the last 40
  graded signals falls below **0.35**.
- `model_report.py` is the ledger (`model_runs`): `record`, `history`, `run_lift`.

## 7. Things not to do

- **Never hand-edit a `.pkl`.** Retrain.
- **Never relax a version guard** to make a stale model load.
- **Never train on the laptop** and treat the result as production — local
  `prices_daily` is ~40 days stale (F-01). Train on the VM.
- **Never report an AUC, PF, or win rate without its sample size.**
- **Do not run a retrain concurrently with the 15:30-19:00 IST chain** or with a
  League replay on the free-tier VM.
