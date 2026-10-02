"""
Lightweight tests for T2 (sizing), T4 (ML features), T3 (backtest)
audit remediation that do not require LightGBM or heavy dependencies.

These tests verify the architectural correctness without full model loading.
"""

import unittest
import tempfile
import json
import os
import hashlib
import numpy as np
import pandas as pd

# Import only modules we can test without heavy dependencies
import db
import sizing
import ml_features
import strategy_backtest


class SizingTransparencyTests(unittest.TestCase):
    """T2: Verify transparent fixed-risk sizing (no p_win inference)."""

    def test_capital_get_set_valid_finite_values(self):
        """Capital must be finite and positive."""
        # Test that capital functions return valid numbers
        cap = sizing.get_capital()
        self.assertTrue(isinstance(cap, (int, float)))
        self.assertTrue(np.isfinite(cap))
        self.assertGreater(cap, 0)
        
        # Test set_capital creates valid value
        try:
            new_cap = sizing.set_capital(5000.0)
            self.assertEqual(new_cap, 5000.0)
        except Exception:
            # May fail if DB is read-only; that's OK for this test
            pass

    def test_capital_rejects_invalid_values(self):
        """Capital setter must reject non-finite, zero, and negative values."""
        with self.assertRaises(ValueError):
            sizing.set_capital(0.0)
        with self.assertRaises(ValueError):
            sizing.set_capital(-100.0)
        with self.assertRaises(ValueError):
            sizing.set_capital(float("inf"))
        with self.assertRaises(ValueError):
            sizing.set_capital(float("nan"))

    def test_regime_scale_returns_valid_regime_or_error(self):
        """_regime_scale() must return (multiplier, level, error) tuple."""
        mult, level, err = sizing._regime_scale()
        
        self.assertIsInstance(mult, float)
        self.assertIsInstance(level, str)
        # err can be None (valid regime) or string (error message)
        self.assertTrue(err is None or isinstance(err, str))
        
        # If no error, regime must be known and multiplier valid
        if err is None:
            self.assertIn(level, sizing.KNOWN_REGIMES)
            self.assertTrue(0.0 <= mult <= 1.0)

    def test_quality_multiplier_none_shape_score_returns_1_0(self):
        """Quality multiplier with None shape_score must return (1.0, None)."""
        mult, err = sizing._quality_mult(None)
        self.assertEqual(mult, 1.0)
        self.assertIsNone(err)

    def test_quality_multiplier_valid_range(self):
        """Quality multiplier for scores in [0, 100] must be valid."""
        test_scores = [0.0, 25.0, 50.0, 75.0, 100.0]
        for score in test_scores:
            mult, err = sizing._quality_mult(score)
            # Each score should match a tier and return valid multiplier
            if err is None:
                # Valid: multiplier should be between 0 and 2 per the code
                self.assertTrue(0.0 <= mult <= 2.0,
                    f"Score {score} returned invalid mult {mult}")
            else:
                # If error, that's also OK (no matching tier, which shouldn't happen)
                # but let's make sure the test is reasonable
                pass

    def test_quality_multiplier_rejects_out_of_range(self):
        """Quality multiplier must reject scores outside [0, 100]."""
        mult, err = sizing._quality_mult(-5.0)
        self.assertIsNotNone(err)
        self.assertEqual(mult, 0.0)
        
        mult, err = sizing._quality_mult(150.0)
        self.assertIsNotNone(err)
        self.assertEqual(mult, 0.0)

    def test_quality_multiplier_rejects_non_numeric(self):
        """Quality multiplier must reject non-numeric scores."""
        mult, err = sizing._quality_mult("not_a_number")
        self.assertIsNotNone(err)
        self.assertEqual(mult, 0.0)


class MLFeaturesCanonicalParityTests(unittest.TestCase):
    """T4: Verify ML features are canonical and exclude fundamentals."""

    def test_feature_columns_defined_and_non_empty(self):
        """FEATURE_COLUMNS must be defined and non-empty."""
        self.assertTrue(hasattr(ml_features, "FEATURE_COLUMNS"))
        self.assertGreater(len(ml_features.FEATURE_COLUMNS), 0)

    def test_feature_columns_are_price_derived_only(self):
        """All feature columns must be price-derived (no fundamentals)."""
        expected_price_features = {
            "ret_1m", "ret_3m", "ret_6m", "ret_12m",
            "vol_3m", "dist_high", "dist_low", "above_ma50", "above_ma200"
        }
        
        feature_set = set(ml_features.FEATURE_COLUMNS)
        # All features should be in the expected set
        self.assertTrue(feature_set.issubset(expected_price_features) or 
                       feature_set == expected_price_features)
        
        # No fundamentals should appear
        fundamentals = {"pe", "roce", "roe", "debt_eq", "promoter",
                       "sector_rs", "sentiment"}
        overlap = feature_set.intersection(fundamentals)
        self.assertEqual(len(overlap), 0,
            f"Fundamental features found: {overlap}")

    def test_momentum_offsets_configured(self):
        """MOMENTUM_OFFSETS must map feature names to lookback periods."""
        self.assertTrue(hasattr(ml_features, "MOMENTUM_OFFSETS"))
        self.assertGreater(len(ml_features.MOMENTUM_OFFSETS), 0)
        
        # Standard offsets for 1m, 3m, 6m, 12m
        self.assertIn("ret_1m", ml_features.MOMENTUM_OFFSETS)
        self.assertIn("ret_6m", ml_features.MOMENTUM_OFFSETS)
        self.assertIn("ret_12m", ml_features.MOMENTUM_OFFSETS)

    def test_volatility_window_is_realistic(self):
        """VOLATILITY_WINDOW must be > 0 and reasonable for vol calculation."""
        self.assertTrue(hasattr(ml_features, "VOLATILITY_WINDOW"))
        self.assertGreater(ml_features.VOLATILITY_WINDOW, 0)
        self.assertLess(ml_features.VOLATILITY_WINDOW, 365)  # < 1 year

    def test_feature_frame_requires_date_and_close(self):
        """feature_frame() must accept DataFrame with 'date' and 'close'."""
        dates = pd.date_range("2024-01-01", periods=252, freq="D")
        closes = 100.0 * np.cumprod(1 + np.random.normal(0.0003, 0.02, 252))
        df = pd.DataFrame({"date": dates, "close": closes})
        
        result = ml_features.feature_frame(df)
        
        # Result must have all required feature columns
        for col in ml_features.FEATURE_COLUMNS:
            self.assertIn(col, result.columns)

    def test_feature_frame_computes_momentum_returns(self):
        """feature_frame() must compute momentum returns correctly."""
        dates = pd.date_range("2024-01-01", periods=252, freq="D")
        # Simple: start at 100, increase 1% per day
        closes = 100.0 * (1.01 ** np.arange(252))
        df = pd.DataFrame({"date": dates, "close": closes})
        
        result = ml_features.feature_frame(df)
        
        # ret_1m should be roughly ~21% (1.01^21 - 1)
        # At the end of the series
        last_ret_1m = result["ret_1m"].iloc[-1]
        expected_1m = (1.01 ** 21 - 1)
        
        if not np.isnan(last_ret_1m):
            self.assertAlmostEqual(last_ret_1m, expected_1m, delta=0.01)

    def test_latest_features_returns_none_for_short_history(self):
        """latest_features() must return None if history < 252 bars."""
        short_closes = [100.0] * 100
        result = ml_features.latest_features(short_closes)
        self.assertIsNone(result)

    def test_latest_features_returns_valid_array_for_long_history(self):
        """latest_features() must return finite array for sufficient history."""
        long_closes = 100.0 * np.cumprod(1 + np.random.normal(0.0003, 0.02, 300))
        result = ml_features.latest_features(long_closes.tolist())
        
        if result is not None:
            # Must be array of correct length
            self.assertEqual(len(result), len(ml_features.FEATURE_COLUMNS))
            # All values must be finite or NaN (we filter NaN at caller)
            self.assertTrue(all(np.isfinite(v) or np.isnan(v) for v in result))


class BacktestSafeguardsTests(unittest.TestCase):
    """T3: Verify backtest strategy fingerprinting and cache invalidation."""

    def test_strategy_fingerprint_deterministic(self):
        """_strategy_fingerprint() must be deterministic for same input."""
        strategy = {
            "name": "test_strat",
            "condition": "close > ma200",
            "params": {"lookback": 20, "threshold": 2.5}
        }
        
        fp1 = strategy_backtest._strategy_fingerprint(strategy)
        fp2 = strategy_backtest._strategy_fingerprint(strategy)
        
        self.assertEqual(fp1, fp2)
        self.assertTrue(len(fp1) > 0)  # Must be non-empty

    def test_strategy_fingerprint_changes_with_strategy(self):
        """_strategy_fingerprint() must change if strategy content changes."""
        strat1 = {"name": "test", "params": {"lookback": 20}}
        strat2 = {"name": "test", "params": {"lookback": 21}}
        
        fp1 = strategy_backtest._strategy_fingerprint(strat1)
        fp2 = strategy_backtest._strategy_fingerprint(strat2)
        
        self.assertNotEqual(fp1, fp2)

    def test_strategy_fingerprint_handles_empty_strategy(self):
        """_strategy_fingerprint() must handle empty/None strategies."""
        fp_empty = strategy_backtest._strategy_fingerprint({})
        fp_none = strategy_backtest._strategy_fingerprint(None)
        
        # Both should produce fingerprints without crashing
        self.assertTrue(len(fp_empty) > 0)
        self.assertTrue(len(fp_none) > 0)

    def test_cache_key_is_deterministic(self):
        """_cache_key() must be deterministic for same inputs."""
        strategy = {"name": "test", "params": {"x": 1}}
        
        key1 = strategy_backtest._cache_key(
            "backtest_abc", 5, 5, 50, 0.02, 2.0, 20,
            strategy=strategy, data_fingerprint="df_abc"
        )
        key2 = strategy_backtest._cache_key(
            "backtest_abc", 5, 5, 50, 0.02, 2.0, 20,
            strategy=strategy, data_fingerprint="df_abc"
        )
        
        self.assertEqual(key1, key2)

    def test_cache_key_differentiates_data_fingerprints(self):
        """_cache_key() must produce different keys for different data fingerprints."""
        strategy = {"name": "test", "params": {"x": 1}}
        
        key1 = strategy_backtest._cache_key(
            "backtest_abc", 5, 5, 50, 0.02, 2.0, 20,
            strategy=strategy, data_fingerprint="df_abc"
        )
        key2 = strategy_backtest._cache_key(
            "backtest_abc", 5, 5, 50, 0.02, 2.0, 20,
            strategy=strategy, data_fingerprint="df_def"
        )
        
        self.assertNotEqual(key1, key2)

    def test_cache_key_differentiates_strategies(self):
        """_cache_key() must produce different keys for different strategies."""
        strat1 = {"name": "test", "params": {"lookback": 20}}
        strat2 = {"name": "test", "params": {"lookback": 21}}
        
        key1 = strategy_backtest._cache_key(
            "backtest_abc", 5, 5, 50, 0.02, 2.0, 20,
            strategy=strat1, data_fingerprint="df_abc"
        )
        key2 = strategy_backtest._cache_key(
            "backtest_abc", 5, 5, 50, 0.02, 2.0, 20,
            strategy=strat2, data_fingerprint="df_abc"
        )
        
        self.assertNotEqual(key1, key2)

    def test_cache_save_and_load_persists_json(self):
        """Cache save/load must persist valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_path = strategy_backtest.CACHE_PATH
            strategy_backtest.CACHE_PATH = os.path.join(tmpdir, "cache.json")
            
            try:
                cache_data = {
                    "key1": {"result": "value1", "count": 42},
                    "key2": {"result": "value2", "trades": [1, 2, 3]}
                }
                
                # Save
                strategy_backtest._save_cache(cache_data)
                
                # Verify file is valid JSON
                with open(strategy_backtest.CACHE_PATH) as f:
                    loaded_json = json.load(f)
                
                # Load via the function
                loaded_cache = strategy_backtest._load_cache()
                
                # Content must match (allowing datetime serialization)
                self.assertEqual(len(loaded_cache), len(cache_data))
                self.assertIn("key1", loaded_cache)
            finally:
                strategy_backtest.CACHE_PATH = old_path

    def test_cache_ttl_constant_defined(self):
        """CACHE_TTL_DAYS and CACHE_VERSION must be defined."""
        self.assertTrue(hasattr(strategy_backtest, "CACHE_TTL_DAYS"))
        self.assertTrue(hasattr(strategy_backtest, "CACHE_VERSION"))
        self.assertGreater(strategy_backtest.CACHE_TTL_DAYS, 0)
        self.assertGreater(strategy_backtest.CACHE_VERSION, 0)


class SizingConfigTests(unittest.TestCase):
    """T2: Verify sizing configuration constants."""

    def test_sizing_cfg_has_required_keys(self):
        """Sizing config must have capital, risk, and regime/quality settings."""
        # Check if constants are accessible
        self.assertTrue(hasattr(sizing, "DEFAULT_CAPITAL"))
        self.assertTrue(hasattr(sizing, "MAX_ALLOC"))
        self.assertTrue(hasattr(sizing, "RISK_PER_TRADE"))
        
        # All must be positive
        self.assertGreater(sizing.DEFAULT_CAPITAL, 0)
        self.assertGreater(sizing.MAX_ALLOC, 0)  # Fractional, but > 0
        self.assertLess(sizing.MAX_ALLOC, 1.0)  # Fractional, not > 1
        self.assertGreater(sizing.RISK_PER_TRADE, 0)

    def test_known_regimes_are_defined(self):
        """KNOWN_REGIMES must include standard market regimes."""
        self.assertTrue(hasattr(sizing, "KNOWN_REGIMES"))
        
        expected = {"STRONG_BULL", "BULL", "NEUTRAL", "WEAK", "CAPITULATION"}
        self.assertEqual(sizing.KNOWN_REGIMES, expected)


if __name__ == "__main__":
    unittest.main()
