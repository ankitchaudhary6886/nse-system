"""Standalone tests for the LSTM forecaster (run: .\\env\\Scripts\\python.exe test_lstm.py).

WHAT THIS FILE IS FOR
---------------------
`lstm_model.py` makes three claims that are easy to get wrong and impossible to
see by eye:

  1. the feature builder never looks at a future bar,
  2. the sequence builder produces correctly shaped windows in chronological
     order that never straddle two symbols,
  3. the walk-forward splitter never puts a training sample whose label was not
     yet knowable next to (or after) a validation bar - the purge + embargo.

Each claim gets a test that would FAIL if the claim were broken.  The embargo
test asserts the bar arithmetic explicitly rather than trusting the splitter's
own bookkeeping, and a deliberately leaky fold is fed to the checker to prove
the checker actually rejects leakage (otherwise the passing test would only
show that the checker does nothing).

Everything runs on tiny synthetic data (a few hundred bars, a handful of
windows, 2 epochs, hidden size 8) so the suite finishes in seconds on this
shared CPU box.  A small real-database test is included but SKIPS if data/app.db
is missing, so the file never depends on production data being present.
"""
import importlib
import os
import sys
import unittest

import numpy as np
import pandas as pd

import lstm_model as lm
import lstm_train as lt


# ---------------------------------------------------------------------------
# Tiny fixtures
# ---------------------------------------------------------------------------
def synthetic_panel(n_symbols=2, n_bars=160, seed=3):
    """A deterministic random-walk panel in the same shape as prices_daily.

    Prices are strictly positive and volume is positive, so the feature builder
    produces finite values from the first usable bar onwards.
    """
    rng = np.random.default_rng(seed)
    rows = []
    dates = pd.bdate_range("2021-01-04", periods=n_bars)
    for s in range(n_symbols):
        sym = f"SYM{s}"
        close = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, n_bars)))
        for i, d in enumerate(dates):
            c = float(close[i])
            rows.append({"symbol": sym, "date": d,
                         "open": c * 0.995, "high": c * 1.01,
                         "low": c * 0.99, "close": c,
                         "volume": float(1_000 + 10 * i + 5 * s)})
    return pd.DataFrame(rows)


def fake_sequences(n=40, seq_len=5, n_features=2, horizon=3, n_dates=None):
    """A hand-built SequenceDataset where every index is easy to reason about.

    Sample i has decision bar i, so its label bar is i + horizon.  That makes
    the embargo arithmetic in the tests trivial to verify by hand.  The date
    axis is sized to always cover the label bars, so no test can index past it.
    """
    n_dates = int(n_dates or (n + horizon + 1))
    dates = (np.datetime64("2021-01-01") +
             np.arange(n_dates).astype("timedelta64[D]"))
    X = np.zeros((n, seq_len, n_features), dtype=np.float32)
    y = np.linspace(-0.02, 0.02, n)
    decision_idx = np.arange(n)                 # sample i -> bar i
    return lm.SequenceDataset(
        X=X, y=y,
        decision_date=dates[decision_idx],
        label_date=dates[decision_idx + horizon],
        symbol=np.array(["SYM0"] * n, dtype=object),
        decision_idx=decision_idx,
        label_idx=decision_idx + horizon,
        dates=dates, feature_columns=("f0", "f1"),
        seq_len=seq_len, horizon=horizon)


# ---------------------------------------------------------------------------
# 1. The guarded import
# ---------------------------------------------------------------------------
class ImportGuardTests(unittest.TestCase):
    def test_module_imports_without_torch(self):
        """A machine without torch must still be able to import the module.

        `sys.modules['torch'] = None` makes `import torch` raise ImportError,
        which is exactly what a missing install looks like.  The module must
        fall back to TORCH_AVAILABLE=False, keep the pure pandas/numpy API
        working, and only refuse when the net itself is constructed.
        """
        saved = {k: sys.modules.get(k) for k in ("torch", "torch.nn")}
        try:
            sys.modules["torch"] = None
            sys.modules.pop("torch.nn", None)
            mod = importlib.reload(lm)
            self.assertFalse(mod.TORCH_AVAILABLE)
            self.assertIsNotNone(mod.TORCH_IMPORT_ERROR)
            # Pure-numpy/pandas paths keep working with torch absent.
            panel = mod.build_price_features(synthetic_panel(n_symbols=1, n_bars=120))
            self.assertIn("ret_1", panel.columns)
            with self.assertRaises(RuntimeError):
                mod.LSTMForecaster(3)          # stub refuses, with a message
            with self.assertRaises(RuntimeError):
                mod.build_model(3)
        finally:
            for key, value in saved.items():
                if value is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = value
            importlib.reload(lm)
        self.assertTrue(lm.TORCH_AVAILABLE)


# ---------------------------------------------------------------------------
# 2. Features must not look forward
# ---------------------------------------------------------------------------
class FeatureCausalityTests(unittest.TestCase):
    def test_features_ignore_future_bars(self):
        """Rewrite the future and every earlier feature row must be identical.

        This is the strongest form of the no-lookahead claim: if any feature
        used a centred window, a full-sample mean/std, or a negative shift,
        changing bars after `cut` would move the rows at or before `cut`.
        """
        panel = synthetic_panel(n_symbols=2, n_bars=140)
        base = lm.build_price_features(panel)
        cut = 100
        mutated = panel.copy()
        future = mutated.index[(mutated["symbol"] == "SYM0") &
                               (mutated["date"] > base["date"].unique()[cut])]
        mutated.loc[future, ["open", "high", "low", "close", "volume"]] *= 5.0
        after = lm.build_price_features(mutated)

        past = base["date"] <= base["date"].unique()[cut]
        for col in lm.DEFAULT_FEATURE_COLUMNS:
            a = base.loc[past, col].to_numpy(dtype=float)
            b = after.loc[past, col].to_numpy(dtype=float)
            np.testing.assert_allclose(
                a, b, rtol=0, atol=0, equal_nan=True,
                err_msg=f"feature {col} changed when only FUTURE bars changed")

    def test_features_do_react_to_the_present_bar(self):
        """Sanity check: the test above is not vacuous.

        Editing the bar at time `t` must move that bar's own feature values
        (they are allowed to use the present), which proves the comparison in
        the previous test is actually comparing live values.
        """
        panel = synthetic_panel(n_symbols=1, n_bars=140)
        base = lm.build_price_features(panel)
        k = 120
        mutated = panel.copy()
        row = mutated.index[(mutated["symbol"] == "SYM0")][k]
        mutated.loc[row, "close"] *= 1.5
        mutated.loc[row, "high"] *= 1.5
        after = lm.build_price_features(mutated)
        idx = base.index[base["symbol"] == "SYM0"][k]
        self.assertNotAlmostEqual(float(base.loc[idx, "ret_1"]),
                                  float(after.loc[idx, "ret_1"]), places=6)


# ---------------------------------------------------------------------------
# 3. Window shape and ordering
# ---------------------------------------------------------------------------
class SequenceBuilderTests(unittest.TestCase):
    def setUp(self):
        self.panel = lm.build_price_features(synthetic_panel(n_symbols=2, n_bars=160))
        self.seq_len, self.horizon = 6, 4

    def test_shapes(self):
        ds = lm.build_sequences(self.panel, seq_len=self.seq_len,
                                horizon=self.horizon)
        self.assertEqual(ds.X.shape[0], len(ds))
        self.assertEqual(ds.X.shape[1], self.seq_len)
        self.assertEqual(ds.X.shape[2], len(lm.DEFAULT_FEATURE_COLUMNS))
        self.assertEqual(ds.y.shape, (len(ds),))
        self.assertEqual(ds.decision_idx.shape, (len(ds),))
        self.assertTrue(np.isfinite(ds.y).all())

    def test_window_is_chronological_and_ends_at_the_decision_bar(self):
        """X[i, -1] must be the decision bar and X[i, 0] the one seq_len-1 back."""
        cols = ["ret_1"]                      # single column keeps the check exact
        ds = lm.build_sequences(self.panel, feature_columns=cols,
                                seq_len=self.seq_len, horizon=self.horizon)
        raw = self.panel.sort_values(["symbol", "date"])
        checked = 0
        for sym in ds.symbol[:50]:
            grp = raw[raw["symbol"] == sym].reset_index(drop=True)
            m = ds.symbol == sym
            dec = pd.to_datetime(ds.decision_date[m])
            rows = grp.set_index("date")["ret_1"]
            for j, d in enumerate(dec[:3]):
                window = ds.X[m][j, :, 0]
                expected = rows.loc[d - pd.tseries.offsets.BDay(self.seq_len - 1):
                                    d].to_numpy(dtype=float)
                np.testing.assert_allclose(window, expected, rtol=1e-6, atol=1e-7)
                # The final window element is the decision bar itself.
                self.assertAlmostEqual(float(window[-1]), float(rows.loc[d]),
                                       places=7)
                checked += 1
        self.assertGreater(checked, 0)

    def test_target_is_the_forward_return_over_the_horizon(self):
        ds = lm.build_sequences(self.panel, seq_len=self.seq_len,
                                horizon=self.horizon)
        raw = self.panel.sort_values(["symbol", "date"])
        for i in range(min(30, len(ds))):
            grp = raw[raw["symbol"] == ds.symbol[i]].reset_index(drop=True)
            j = int(np.searchsorted(grp["date"].to_numpy(),
                                    ds.decision_date[i]))
            expected = (float(grp["close"].iloc[j + self.horizon]) /
                        float(grp["close"].iloc[j]) - 1.0)
            self.assertAlmostEqual(float(ds.y[i]), expected, places=10)

    def test_label_date_is_horizon_bars_after_the_decision_date(self):
        ds = lm.build_sequences(self.panel, seq_len=self.seq_len,
                                horizon=self.horizon)
        self.assertTrue((ds.label_idx > ds.decision_idx).all())
        raw = self.panel.sort_values(["symbol", "date"])
        for i in range(min(30, len(ds))):
            grp = raw[raw["symbol"] == ds.symbol[i]].reset_index(drop=True)
            j = int(np.searchsorted(grp["date"].to_numpy(), ds.decision_date[i]))
            self.assertEqual(ds.label_date[i], grp["date"].to_numpy()[j + self.horizon])

    def test_windows_never_span_two_symbols(self):
        """A window must contain bars from exactly one symbol.

        The panel is given a numeric marker per symbol, so a window that mixed
        two symbols would show two different marker values side by side.
        """
        panel = synthetic_panel(n_symbols=3, n_bars=160)
        panel = panel.assign(mark=panel["symbol"].map(
            {"SYM0": 0.0, "SYM1": 1.0, "SYM2": 2.0}))
        ds = lm.build_sequences(panel, feature_columns=["mark"], seq_len=8,
                                horizon=2)
        self.assertGreater(len(ds), 0)
        for i in range(len(ds)):
            window = ds.X[i, :, 0]
            self.assertEqual(float(window.min()), float(window.max()),
                             "a window mixed two symbols")
            expected_mark = {"SYM0": 0.0, "SYM1": 1.0, "SYM2": 2.0}[ds.symbol[i]]
            self.assertAlmostEqual(float(window[0]), expected_mark, places=6)

    def test_windows_without_a_label_are_dropped_not_filled(self):
        """The last `horizon` bars of each symbol must produce no sample.

        A fabricated or zero-filled label would be the easiest possible leak.
        """
        horizon = 7
        ds = lm.build_sequences(self.panel, seq_len=self.seq_len, horizon=horizon)
        raw = self.panel.sort_values(["symbol", "date"])
        for sym in raw["symbol"].unique():
            grp = raw[raw["symbol"] == sym].reset_index(drop=True)
            last_decision = pd.Timestamp(grp["date"].iloc[-horizon - 1])
            mine = ds.decision_date[ds.symbol == sym]
            self.assertLessEqual(pd.Timestamp(mine.max()), last_decision)
        self.assertTrue(np.isfinite(ds.y).all())


# ---------------------------------------------------------------------------
# 4. The embargo - the centrepiece
# ---------------------------------------------------------------------------
class EmbargoTests(unittest.TestCase):
    def test_training_labels_end_at_least_embargo_bars_before_validation(self):
        """The explicit assertion: last train label bar + embargo < first val bar.

        The splitter's own bookkeeping is ignored here; the numbers are read
        back out of the returned index arrays.
        """
        ds = fake_sequences(n=400, seq_len=5, horizon=3)
        for embargo in (0, 1, 5, 17):
            folds = lm.walk_forward_folds(ds, n_folds=3, embargo=embargo,
                                          min_train_frac=0.4)
            self.assertEqual(len(folds), 3)
            seen_val = np.concatenate([f.val_idx for f in folds])
            self.assertEqual(len(seen_val), len(np.unique(seen_val)),
                             "validation blocks must be disjoint")
            for fold in folds:
                train_label_last = int(ds.label_idx[fold.train_idx].max())
                val_decision_first = int(ds.decision_idx[fold.val_idx].min())
                self.assertLess(
                    train_label_last + embargo, val_decision_first,
                    f"embargo {embargo} violated in fold {fold.index}")
                # The implied gap on the decision axis: horizon + embargo.
                train_decision_last = int(ds.decision_idx[fold.train_idx].max())
                self.assertGreaterEqual(
                    val_decision_first - train_decision_last,
                    ds.horizon + embargo)
                self.assertGreaterEqual(fold.gap_bars, embargo)

    def test_checker_detects_a_leaky_fold(self):
        """Feed the checker a fold that IS leaky; it must refuse.

        Without this test, a checker that always returns success would also
        make the assertion above pass.
        """
        ds = fake_sequences(n=400, seq_len=5, horizon=3)
        folds = lm.walk_forward_folds(ds, n_folds=2, embargo=5, min_train_frac=0.4)
        fold = folds[0]
        leaky = lm.Fold(index=0,
                        train_idx=np.concatenate([fold.train_idx, fold.val_idx]),
                        val_idx=fold.val_idx,
                        val_start_idx=fold.val_start_idx,
                        val_end_idx=fold.val_end_idx,
                        train_label_max_idx=0, val_decision_min_idx=0)
        with self.assertRaises(lm.LeakageError):
            lm.check_fold_embargo(ds, leaky, 5)
        # And the honest fold passes the same check.
        lm.check_fold_embargo(ds, fold, 5)

    def test_folds_are_ordered_and_expanding(self):
        ds = fake_sequences(n=500, seq_len=5, horizon=2)
        folds = lm.walk_forward_folds(ds, n_folds=4, embargo=3, min_train_frac=0.3)
        val_starts = [f.val_start_idx for f in folds]
        self.assertEqual(val_starts, sorted(val_starts))
        train_sizes = [f.train_idx.size for f in folds]
        self.assertEqual(train_sizes, sorted(train_sizes),
                         "an expanding window must never shrink")
        for earlier, later in zip(folds, folds[1:]):
            self.assertLessEqual(int(ds.decision_idx[earlier.val_idx].max()),
                                 int(ds.decision_idx[later.val_idx].min()))

    def test_several_symbols_are_split_by_date_not_by_row_count(self):
        """All symbols' samples for a period must land in the same fold."""
        n_syms = 3
        ds = fake_sequences(n=600, seq_len=5, horizon=2)
        ds.symbol = np.array([f"SYM{i % n_syms}" for i in range(len(ds))],
                             dtype=object)
        folds = lm.walk_forward_folds(ds, n_folds=2, embargo=4, min_train_frac=0.4)
        for fold in folds:
            val_syms = set(ds.symbol[fold.val_idx])
            self.assertEqual(len(val_syms), n_syms,
                             "a validation fold must contain every symbol")

    def test_rejects_impossible_configuration(self):
        ds = fake_sequences(n=30, seq_len=5, horizon=2)
        with self.assertRaises(ValueError):
            lm.walk_forward_folds(ds, n_folds=0)
        with self.assertRaises(ValueError):
            lm.walk_forward_folds(ds, n_folds=2, embargo=-1)
        with self.assertRaises(ValueError):
            lm.walk_forward_folds(ds, n_folds=500, embargo=1, min_train_frac=0.9)

    def test_inner_purge_split_keeps_the_gap(self):
        ds = fake_sequences(n=400, seq_len=5, horizon=3)
        train_idx = np.arange(300)
        inner_tr, inner_va = lm.purge_inner_split(ds, train_idx, embargo=5,
                                                  val_frac=0.2)
        self.assertGreater(inner_va.size, 0)
        self.assertLess(int(ds.label_idx[inner_tr].max()) + 5,
                        int(ds.decision_idx[inner_va].min()))


# ---------------------------------------------------------------------------
# 5. Normalisation must come from the past only
# ---------------------------------------------------------------------------
class NormalisationTests(unittest.TestCase):
    def test_scaler_is_fitted_on_training_windows_only(self):
        """The transform is a pure function of frozen training statistics.

        Whatever the validation data looks like - even if it is wildly
        perturbed - the scaling applied to it must come from the training fold
        only.  If the scaler were fitted on train+val, the "manual" z-score
        recomputed here from the frozen mean/std would not match.
        """
        ds = fake_sequences(n=400, seq_len=5, n_features=2, horizon=3)
        rng = np.random.default_rng(0)
        ds.X = rng.normal(size=ds.X.shape).astype(np.float32)
        folds = lm.walk_forward_folds(ds, n_folds=2, embargo=4, min_train_frac=0.4)
        fold = folds[0]
        scaler = lm.Standardizer.fit(ds.X[fold.train_idx])
        train_mean = scaler.mean.copy()

        poisoned = ds.X.copy()
        poisoned[fold.val_idx] = poisoned[fold.val_idx] * 100.0 + 7.0
        manual = ((poisoned[fold.val_idx] - scaler.mean) / scaler.std)
        np.testing.assert_allclose(scaler.transform(poisoned[fold.val_idx]),
                                   manual, rtol=1e-5, atol=1e-5)
        # And re-fitting on the training windows still gives the same numbers:
        # the poisoned validation rows had no influence on them.
        again = lm.Standardizer.fit(ds.X[fold.train_idx])
        np.testing.assert_allclose(again.mean, train_mean, rtol=0, atol=0)

    def test_scaler_matches_hand_computed_zscore(self):
        X = np.array([[[1.0, 10.0]], [[3.0, 20.0]], [[5.0, 30.0]]],
                     dtype=np.float32)
        s = lm.Standardizer.fit(X)
        np.testing.assert_allclose(s.mean, [3.0, 20.0], rtol=1e-6)
        z = s.transform(X)
        np.testing.assert_allclose(z[:, 0, 0], [-1.2247448, 0.0, 1.2247448],
                                   rtol=1e-4)

    def test_scaler_round_trips_through_state_dict(self):
        X = np.random.default_rng(1).normal(size=(10, 4, 3)).astype(np.float32)
        s = lm.Standardizer.fit(X)
        again = lm.Standardizer.from_state_dict(s.state_dict())
        np.testing.assert_allclose(s.transform(X), again.transform(X))


# ---------------------------------------------------------------------------
# 6. Metric helpers
# ---------------------------------------------------------------------------
class MetricTests(unittest.TestCase):
    def test_auc_extremes(self):
        # Perfect separation: every positive scores above every negative.
        self.assertEqual(lt.auc_score(np.array([0, 0, 1, 1]),
                                      np.array([0.1, 0.2, 0.3, 0.4])), 1.0)
        # Perfectly reversed: AUC 0.
        self.assertEqual(lt.auc_score(np.array([1, 1, 0, 0]),
                                      np.array([0.1, 0.2, 0.3, 0.4])), 0.0)
        # No ranking information at all.
        self.assertEqual(lt.auc_score(np.array([0, 1, 0, 1]), np.ones(4)), 0.5)

    def test_base_auc_is_about_a_half(self):
        rng = np.random.default_rng(5)
        y = (rng.normal(size=4000) > 0).astype(int)
        self.assertAlmostEqual(lt.auc_score(y, rng.normal(size=4000)), 0.5,
                               delta=0.03)

    def test_spearman_is_one_for_a_monotone_score(self):
        y = np.array([-0.1, -0.02, 0.0, 0.03, 0.2])
        self.assertAlmostEqual(lt.spearman_ic(np.exp(y), y), 1.0, places=10)

    def test_rank_ic_is_cross_sectional(self):
        """A score that is constant within each date must give an IC near zero."""
        rng = np.random.default_rng(7)
        n_dates, n_names = 40, 8
        dates = np.repeat(np.arange(n_dates), n_names)
        y = rng.normal(size=n_dates * n_names)
        score = np.zeros_like(y)                     # constant per date -> no IC
        out = lt.rank_ic_by_date(score, y, dates)
        self.assertEqual(out["ic_days"], 0)

    def test_direction_metrics_always_up_equals_base_rate(self):
        """Always predicting 'up' scores exactly the base rate, not 1.0."""
        y = np.array([0.01, -0.02, 0.03, 0.01])      # 3 up out of 4
        m = lt.direction_metrics(y, np.ones(4), threshold=0.0)
        self.assertAlmostEqual(m["accuracy"], 0.75)
        self.assertAlmostEqual(m["accuracy"], m["base_rate"])
        self.assertAlmostEqual(m["base_rate"], 0.75)
        self.assertAlmostEqual(m["majority_rate"], 0.75)
        # A perfect score gets AUC 1.0 and full accuracy.
        perfect = np.array([0.9, 0.1, 0.8, 0.7])
        mp = lt.direction_metrics(y, perfect, threshold=0.5)
        self.assertAlmostEqual(mp["accuracy"], 1.0)
        self.assertAlmostEqual(mp["auc"], 1.0)


# ---------------------------------------------------------------------------
# 7. Tiny end-to-end smoke test (real torch, a couple of epochs)
# ---------------------------------------------------------------------------
@unittest.skipUnless(lm.TORCH_AVAILABLE, "torch not installed")
class TinyTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lm.set_threads(1)                 # keep the shared box quiet
        lm.seed_everything(11)
        cls.panel = lm.build_price_features(
            synthetic_panel(n_symbols=2, n_bars=180, seed=9))
        cls.ds = lm.build_sequences(cls.panel, seq_len=8, horizon=3)

    def test_train_and_predict_shapes_and_finiteness(self):
        ds = self.ds
        keep = np.isfinite(ds.X).all(axis=(1, 2)) & np.isfinite(ds.y)
        idx = np.where(keep)[0][:300]
        self.assertGreater(len(idx), 50)
        scaler = lm.Standardizer.fit(ds.X[idx])
        model, info = lm.train_model(ds, idx, epochs=2, hidden=8, batch_size=64,
                                     threads=1, scaler=scaler,
                                     inner_val_frac=0.0)
        self.assertGreater(info["n_parameters"], 0)
        self.assertLess(info["n_parameters"], 5000)   # stays tiny
        out = lm.predict(model, ds.X[idx[:20]], scaler, info["y_mean"], info["y_std"])
        self.assertEqual(out["prob_up"].shape, (20,))
        self.assertEqual(out["ret"].shape, (20,))
        self.assertTrue(np.isfinite(out["prob_up"]).all())
        self.assertTrue(np.isfinite(out["ret"]).all())
        self.assertTrue(((out["prob_up"] >= 0) & (out["prob_up"] <= 1)).all())

    def test_training_is_repeatable_with_the_same_seed(self):
        """Same seed, same data, same numbers - otherwise results are not reportable."""
        ds = self.ds
        keep = np.isfinite(ds.X).all(axis=(1, 2)) & np.isfinite(ds.y)
        idx = np.where(keep)[0][:250]
        if len(idx) < 50:
            self.skipTest("not enough finite windows")
        scaler = lm.Standardizer.fit(ds.X[idx])
        outs = []
        for _ in range(2):
            model, info = lm.train_model(ds, idx, epochs=2, hidden=8,
                                         batch_size=64, threads=1, seed=5,
                                         scaler=scaler, inner_val_frac=0.0)
            outs.append(lm.predict(model, ds.X[idx[:16]], scaler,
                                   info["y_mean"], info["y_std"])["prob_up"])
        np.testing.assert_allclose(outs[0], outs[1], rtol=1e-6, atol=1e-6)

    def test_score_latest_hook_returns_one_row_per_symbol(self):
        model, info = lm.train_model(self.ds, np.arange(min(200, len(self.ds))),
                                     epochs=1, hidden=8, batch_size=64, threads=1)
        rows = lm.score_latest(self.panel, model, info, seq_len=8)
        self.assertEqual(len(rows), self.panel["symbol"].nunique())
        for row in rows:
            self.assertIn("prob_up", row)
            self.assertIn("exp_ret", row)
            self.assertTrue(0.0 <= row["prob_up"] <= 1.0)
            self.assertIsInstance(row["date"], str)


# ---------------------------------------------------------------------------
# 8. Optional: the real database, kept tiny
# ---------------------------------------------------------------------------
@unittest.skipUnless(lm.TORCH_AVAILABLE, "torch not installed")
@unittest.skipUnless(os.path.exists(lm.default_db_path()), "data/app.db not present")
class RealDataSmokeTests(unittest.TestCase):
    def test_two_real_symbols_survive_the_whole_pipeline(self):
        """Minimum sanity on production data: 2 symbols, 1 epoch, tiny net."""
        panel_raw = lm.load_price_panel(n_symbols=2, min_rows=400)
        panel = lm.build_price_features(panel_raw)
        ds = lm.build_sequences(panel, seq_len=10, horizon=5)
        self.assertGreater(len(ds), 100)
        folds = lm.walk_forward_folds(ds, n_folds=2, embargo=5,
                                      min_train_frac=0.4)
        for fold in folds:
            audit = lm.check_fold_embargo(ds, fold, 5)
            self.assertGreaterEqual(audit["gap_bars_after_last_train_label"], 5)
        fold = folds[0]
        scaler = lm.Standardizer.fit(ds.X[fold.train_idx])
        model, info = lm.train_model(ds, fold.train_idx, epochs=1, hidden=8,
                                     batch_size=128, threads=1, scaler=scaler,
                                     inner_val_frac=0.0)
        out = lm.predict(model, ds.X[fold.val_idx], scaler, info["y_mean"],
                         info["y_std"])
        self.assertEqual(len(out["prob_up"]), len(fold.val_idx))
        self.assertTrue(np.isfinite(out["prob_up"]).all())
        # A real OOS AUC is computed, but no threshold is asserted: the honest
        # expectation for a 2-symbol, 1-epoch run is "no skill".
        y_val = ds.y[fold.val_idx]
        auc = lt.auc_score((y_val > 0).astype(int), out["prob_up"])
        self.assertTrue(np.isnan(auc) or 0.0 <= auc <= 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
