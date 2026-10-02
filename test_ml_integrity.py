import unittest

import numpy as np
import pandas as pd

import meta_model
import ml_features
import ml_train


class MLIntegrityTests(unittest.TestCase):
    def test_shared_feature_builder_matches_latest_row(self):
        dates = pd.date_range("2020-01-01", periods=300, freq="D")
        closes = np.linspace(100, 180, 300)
        frame = ml_features.feature_frame(
            pd.DataFrame({"date": dates, "close": closes}))
        latest = ml_features.latest_features(closes)
        self.assertTrue(np.allclose(
            frame.iloc[-1][ml_features.FEATURE_COLUMNS].to_numpy(float),
            latest, equal_nan=True))

    def test_time_split_is_global_and_purged(self):
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        data = pd.DataFrame({
            "date": dates, "label_available_date": dates + pd.Timedelta(days=5),
            "x": np.arange(100),
        })
        tr, va, te = ml_train._time_split(data, .6, .2)
        self.assertLess(tr["date"].max(), va["date"].min())
        self.assertLess(tr["label_available_date"].max(), va["date"].min())
        self.assertLess(va["label_available_date"].max(), te["date"].min())

    def test_legacy_meta_bundle_is_rejected_and_metadata_call_is_safe(self):
        old_model = meta_model._MODEL
        old_meta = meta_model._MODEL_METADATA
        try:
            meta_model._MODEL = object()
            meta_model._MODEL_METADATA = {"label": "test"}
            self.assertEqual(meta_model.model_bundle_metadata(object())["label"],
                             "test")
        finally:
            meta_model._MODEL = old_model
            meta_model._MODEL_METADATA = old_meta


if __name__ == "__main__":
    unittest.main()
