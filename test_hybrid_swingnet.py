#!/usr/bin/env python
"""Standalone test for the vendored HybridSwingNet (``stockxpert``) integration.

Run it exactly like this, from the repository root::

    .\\env\\Scripts\\python.exe test_hybrid_swingnet.py

Design rules
------------
* STANDALONE: no pytest, no fixtures, no config. Exits 0 on pass **or** skip.
* SKIPS GRACEFULLY with a printed reason when the heavy dependencies or the
  database are genuinely unavailable - it must never fail for that reason.
* It does not touch the production venv, the network, the service, or git.
* Read-only against ``data/app.db``.

What it proves
--------------
1. ``import hybrid_swingnet`` can never raise, and ``import_stockxpert()``
   degrades to a reason string instead of an exception (house rule: a missing
   dependency must not blank the live UI).
2. The vendored V3 model imports and its forward pass has the documented shapes.
3. Our ``app.db`` adapter produces correctly shaped, NaN-free windows.
4. Those windows are LEAKAGE-FREE: every input window ends exactly at the sample
   date and contains nothing after it, verified with a row-index sentinel column.
5. The multi-horizon targets are aligned to their horizons and match the
   documented Z-scored forward-return contract.
6. The cross-sectional split is disjoint by stock and separated in time by the
   embargo gap.
7. Our fast window builder returns IDENTICAL values to the vendor's own builder.
8. ``transform_preserving_traits`` really does keep ``stock_traits`` (regression
   test for an upstream bug that silently zeroes them).
"""

from __future__ import annotations

import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_results: list[tuple[str, str, str]] = []


@dataclass
class Unavailable(Exception):
    """Raised by a test to request a graceful skip."""


def record(status: str, name: str, detail: str = "") -> None:
    _results.append((status, name, detail))
    marker = {PASS: "ok  ", FAIL: "FAIL", SKIP: "skip"}[status]
    line = f"[{marker}] {name}"
    if detail:
        line += f"\n       {detail}"
    print(line, flush=True)


def run(name: str, fn) -> None:
    started = time.time()
    try:
        detail = fn() or ""
        record(PASS, name, f"{detail} ({time.time() - started:.1f}s)" if detail else f"({time.time() - started:.1f}s)")
    except Unavailable as exc:
        record(SKIP, name, str(exc))
    except AssertionError as exc:
        record(FAIL, name, f"assertion: {exc}")
    except Exception as exc:  # noqa: BLE001
        record(FAIL, name, f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}")


# --------------------------------------------------------------------------- #
# 1. Guarded / optional imports
# --------------------------------------------------------------------------- #
def test_package_import_is_safe() -> str:
    import hybrid_swingnet

    assert hybrid_swingnet.UPSTREAM_COMMIT, "no pinned upstream commit recorded"
    assert len(hybrid_swingnet.UPSTREAM_COMMIT) == 40, "upstream commit is not a full SHA"
    report = hybrid_swingnet.probe_dependencies()
    assert isinstance(report, dict) and "core" in report
    missing_core = report["missing_core"]
    return (
        f"commit={hybrid_swingnet.UPSTREAM_COMMIT[:12]} "
        f"core_missing={missing_core or 'none'} soft_missing={report['missing_soft'] or 'none'}"
    )


def test_import_guard_returns_reason_not_exception() -> str:
    """Force ``import stockxpert`` to fail and confirm we get a reason string."""
    import hybrid_swingnet

    saved = sys.modules.get("stockxpert", "ABSENT")
    sys.modules["stockxpert"] = None  # makes "import stockxpert" raise ImportError
    try:
        module, reason = hybrid_swingnet.import_stockxpert()
    finally:
        if saved == "ABSENT":
            sys.modules.pop("stockxpert", None)
        else:
            sys.modules["stockxpert"] = saved
    assert module is None, "expected no module when the import is blocked"
    assert reason, "expected a non-empty reason string"
    assert "ImportError" in reason or "failed" in reason, f"unhelpful reason: {reason!r}"
    return f"guard produced: {reason[:90]}"


def test_import_stockxpert_success_or_skip() -> str:
    import hybrid_swingnet

    module, reason = hybrid_swingnet.import_stockxpert()
    if reason:
        raise Unavailable(f"vendored stockxpert unusable here: {reason}")
    assert hasattr(module, "__version__")
    namespace, ns_reason = hybrid_swingnet.import_stockxpert_v3()
    if ns_reason:
        raise Unavailable(f"V3 entry points unavailable: {ns_reason}")
    missing = {"StockXpertModelV3", "SampleBuilder", "FeatureBuilder"} - set(namespace)
    assert not missing, f"missing V3 entry points: {missing}"
    return f"stockxpert {module.__version__}, {len(namespace)} V3 symbols resolved"


# --------------------------------------------------------------------------- #
# 2. Real V3 model forward pass
# --------------------------------------------------------------------------- #
def test_v3_model_forward_shapes() -> str:
    import torch

    from hybrid_swingnet import import_stockxpert_v3

    namespace, reason = import_stockxpert_v3()
    if reason:
        raise Unavailable(reason)
    torch.manual_seed(0)
    model = namespace["StockXpertModelV3"](
        short_dim=8, mid_dim=12, long_dim=8, context_dim=24, num_horizons=5,
        hidden_dim=96, stock_embed_dim=16, stock_traits_dim=7,
    )
    batch = 4
    outputs = model(
        torch.randn(batch, 7, 8), torch.randn(batch, 21, 12), torch.randn(batch, 60, 8),
        torch.randn(batch, 24), torch.randn(batch, 9), torch.randn(batch, 7),
    )
    direction, magnitude, confidence = outputs[0], outputs[1], outputs[2]
    assert direction.shape == (batch, 5), direction.shape
    assert magnitude.shape == (batch, 5), magnitude.shape
    assert confidence.shape == (batch, 5), confidence.shape
    assert torch.isfinite(direction).all(), "non-finite direction logits"
    params = sum(p.numel() for p in model.parameters())
    return f"direction/magnitude/confidence all (4, 5); {params:,} params"


def test_v3_loss_runs() -> str:
    import torch

    from hybrid_swingnet import import_stockxpert_v3

    namespace, reason = import_stockxpert_v3()
    if reason:
        raise Unavailable(reason)
    torch.manual_seed(0)
    model = namespace["StockXpertModelV3"](8, 12, 8, 24, 5)
    criterion = namespace["StockXpertV3Loss"](
        direction_weight=1.0, magnitude_weight=0.4, horizon_weights=[1.2, 1.0, 0.9, 0.7, 0.5]
    )
    outputs = model(
        torch.randn(6, 7, 8), torch.randn(6, 21, 12), torch.randn(6, 60, 8),
        torch.randn(6, 24), torch.randn(6, 9), torch.randn(6, 7),
    )
    targets = {
        "magnitude": torch.randn(6, 5),
        "zone": torch.zeros(6, 5, dtype=torch.long),
        "trend": torch.zeros(6, 1),
        "levels": torch.zeros(6, 5, 3),
    }
    loss, parts = criterion(
        outputs[0], outputs[1], outputs[2], outputs[3], outputs[4], outputs[5], targets
    )
    assert torch.isfinite(loss), "loss is not finite"
    assert parts["total"] > 0
    return f"loss={parts['total']:.4f} (direction {parts['direction']:.4f}, magnitude {parts['magnitude']:.4f})"


# --------------------------------------------------------------------------- #
# 3-5. Dataset adapter: shapes, leakage, target alignment
# --------------------------------------------------------------------------- #
def _require_dataset():
    try:
        import pandas  # noqa: F401
        import numpy  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise Unavailable(f"pandas/numpy unavailable: {exc}") from exc

    from hybrid_swingnet.appdb_dataset import DEFAULT_DB_PATH

    if not Path(DEFAULT_DB_PATH).is_file():
        raise Unavailable(f"database not found: {DEFAULT_DB_PATH}")
    from hybrid_swingnet import import_stockxpert_v3

    namespace, reason = import_stockxpert_v3()
    if reason:
        raise Unavailable(reason)
    return namespace


def _tiny_spec(**overrides):
    from hybrid_swingnet.appdb_dataset import DatasetSpec

    base = dict(max_symbols=4, min_rows=700)
    base.update(overrides)
    return DatasetSpec(**base)


def test_adapter_window_shapes() -> str:
    _require_dataset()
    import numpy as np

    from hybrid_swingnet.appdb_dataset import build_dataset

    bundle = build_dataset(_tiny_spec())
    assert bundle.samples, "no samples built"
    assert bundle.short_features == [
        "log_return", "volume_change", "rsi_6", "volatility_7", "bb_zscore",
        "rsi_delta", "obv_divergence", "price_vs_vwap",
    ], bundle.short_features

    expected_context = 24
    for sample in bundle.samples[:50]:
        assert sample.X_short.shape == (7, 8), sample.X_short.shape
        assert sample.X_mid.shape == (21, 12), sample.X_mid.shape
        assert sample.X_long.shape == (60, 8), sample.X_long.shape
        assert sample.X_context.shape == (expected_context,), sample.X_context.shape
        assert sample.X_sentiment.shape == (9,), sample.X_sentiment.shape
        assert sample.y.shape == (5,), sample.y.shape
        assert sample.y_zone.shape == (5,), sample.y_zone.shape
        assert sample.y_levels.shape == (5, 3), sample.y_levels.shape
        assert not np.isnan(sample.X_short).any(), "NaN in X_short"
        assert not np.isnan(sample.X_mid).any(), "NaN in X_mid"
        assert not np.isnan(sample.X_long).any(), "NaN in X_long"
        assert not np.isnan(sample.X_context).any(), "NaN in X_context"
        assert not np.isnan(sample.y).any(), "NaN in target y"
        traits = getattr(sample, "stock_traits", None)
        assert traits is not None and traits.shape == (7,), "stock_traits missing/ill-shaped"
    return (
        f"{len(bundle.samples)} samples over {len(bundle.symbols)} symbols; "
        "X_short(7,8) X_mid(21,12) X_long(60,8) X_ctx(24,) X_sent(9,) y(5,)"
    )


def test_windows_are_leakage_free() -> str:
    """A monotonic row-index sentinel must never exceed the sample's own row."""
    _require_dataset()
    import numpy as np

    from hybrid_swingnet.appdb_dataset import build_dataset, load_feature_groups

    bundle = build_dataset(_tiny_spec(extra_columns=("__rowidx",)))
    assert bundle.samples, "no samples built"
    groups = load_feature_groups()
    assert bundle.short_features[0] == "__rowidx", bundle.short_features[0]

    checked = 0
    for sample in bundle.samples:
        frame = bundle.feature_data[sample.symbol]
        position = frame.index.get_loc(sample.date)
        assert isinstance(position, (int, np.integer)), "duplicate dates in feature frame"

        short = sample.X_short[:, 0]
        mid = sample.X_mid[:, 0]
        long = sample.X_long[:, 0]
        assert short[-1] == position, f"X_short ends at {short[-1]}, sample row is {position}"
        assert mid[-1] == position, f"X_mid ends at {mid[-1]}, sample row is {position}"
        assert long[-1] == position, f"X_long ends at {long[-1]}, sample row is {position}"
        assert short[0] == position - 6, f"X_short starts at {short[0]}, expected {position - 6}"
        assert mid[0] == position - 20, f"X_mid starts at {mid[0]}, expected {position - 20}"
        assert long[0] == position - 59, f"X_long starts at {long[0]}, expected {position - 59}"
        # The decisive check: nothing from the future leaked into any input window.
        assert max(short.max(), mid.max(), long.max()) == position, "future row present in input window"
        assert short.max() == short[-1] and mid.max() == mid[-1] and long.max() == long[-1]
        checked += 1
        if checked >= 400:
            break
    return f"checked {checked} windows: every window ends exactly at t, no t+1..t+60 rows present"


def test_targets_align_to_horizons() -> str:
    """``y[h]`` must equal the documented Z-scored forward return at that horizon."""
    _require_dataset()
    import numpy as np

    from hybrid_swingnet.appdb_dataset import build_dataset

    bundle = build_dataset(_tiny_spec())
    horizons = [1, 3, 5, 7, 10]
    eps = 1e-8
    worst = 0.0
    checked = 0

    for symbol, price in bundle.price_data.items():
        frame = bundle.feature_data.get(symbol)
        if frame is None or frame.empty:
            continue
        close = price["Close"].astype(float)
        log_return = np.log(close / close.shift(1))
        rolling_std = log_return.rolling(10).std() + eps
        log_close = np.log(close)
        expected = {}
        for horizon in horizons:
            raw = log_close.shift(-horizon) - log_close
            window = max(3, min(horizon, 7))
            smoothed = raw.rolling(window, center=True).mean().fillna(raw)
            expected[horizon] = (smoothed / rolling_std).clip(-5, 5)

        for sample in bundle.samples:
            if sample.symbol != symbol:
                continue
            for idx, horizon in enumerate(horizons):
                want = expected[horizon].get(sample.date, np.nan)
                if not np.isfinite(want):
                    continue
                got = float(sample.y[idx])
                worst = max(worst, abs(got - float(want)))
                checked += 1
            if checked > 3000:
                break
        if checked > 3000:
            break

    assert checked > 0, "no targets checked"
    assert worst < 1e-4, f"target mismatch: worst absolute error {worst:.3e} over {checked} targets"
    return f"{checked} targets match the contract (worst abs error {worst:.2e})"


# --------------------------------------------------------------------------- #
# 6. Split integrity + embargo
# --------------------------------------------------------------------------- #
def test_split_is_disjoint_and_embargoed() -> str:
    _require_dataset()
    import pandas as pd

    from hybrid_swingnet import import_stockxpert_v3
    from hybrid_swingnet.appdb_dataset import build_dataset
    from hybrid_swingnet.oos import SplitSpec, split_samples

    namespace, reason = import_stockxpert_v3()
    if reason:
        raise Unavailable(reason)

    bundle = build_dataset(_tiny_spec(max_symbols=12))
    spec = SplitSpec(
        train_end="2024-06-30", val_end="2025-03-31", test_end="2026-06-30",
        val_stocks=2, test_stocks=2, blind_stocks=2, embargo_days=10, seed=42,
    )
    split = split_samples(bundle.samples, spec, bundle.symbols)
    train, val, test = split["train"], split["val"], split["test"]
    assert train and val and test, f"empty split: {{k: len(v) for k, v in split.items()}}"

    namespace["assert_no_leakage"](train, val, test, split["blind_holdout"])

    train_end = pd.Timestamp(spec.train_end)
    val_end = pd.Timestamp(spec.val_end)
    embargo = pd.Timedelta(days=spec.embargo_days)
    train_max = max(pd.Timestamp(s.date) for s in train)
    val_min = min(pd.Timestamp(s.date) for s in val)
    val_max = max(pd.Timestamp(s.date) for s in val)
    test_min = min(pd.Timestamp(s.date) for s in test)

    assert train_max <= train_end, f"train sample after train_end: {train_max}"
    assert val_min >= train_end + embargo, f"val starts {val_min}, embargo needs >= {train_end + embargo}"
    assert val_max <= val_end, f"val sample after val_end: {val_max}"
    assert test_min >= val_end + embargo, f"test starts {test_min}, embargo needs >= {val_end + embargo}"

    counts = {k: len(v) for k, v in split.items()}
    return (
        f"disjoint stocks; embargo respected: train<= {train_max.date()}, "
        f"val {val_min.date()}..{val_max.date()}, test>={test_min.date()}; sizes {counts}"
    )


# --------------------------------------------------------------------------- #
# 7. Fast builder equivalence
# --------------------------------------------------------------------------- #
def test_fast_builder_matches_upstream() -> str:
    """Our vectorised builder must be value-identical to the vendor's builder."""
    _require_dataset()
    import numpy as np
    import pandas as pd

    from hybrid_swingnet import import_stockxpert_v3
    from hybrid_swingnet.appdb_dataset import (
        SENTIMENT_FEATURES,
        add_market_context,
        add_sentiment_placeholders,
        add_static_stock_traits,
        load_feature_groups,
    )
    from hybrid_swingnet.fast_builder import FastSampleBuilder

    namespace, reason = import_stockxpert_v3()
    if reason:
        raise Unavailable(reason)

    # Synthetic frame: cheap for the slow builder, still exercises every branch.
    rng = np.random.default_rng(7)
    rows = 260
    index = pd.bdate_range("2022-01-03", periods=rows)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.015, rows))
    frame = pd.DataFrame(
        {
            "Open": close * (1 + rng.normal(0, 0.003, rows)),
            "High": close * 1.012,
            "Low": close * 0.988,
            "Close": close,
            "Volume": rng.integers(100_000, 900_000, rows).astype(float),
        },
        index=index,
    )
    frame.index.name = "Date"
    # Give it the same context/sentiment/trait columns the real adapter supplies,
    # otherwise the canonical context feature group is missing from the frame.
    prepared = add_sentiment_placeholders({"TEST": frame})
    prepared = add_market_context(prepared)
    prepared = add_static_stock_traits(prepared, {})
    frame = namespace["FeatureBuilder"](horizons=[1, 3, 5, 7, 10]).build_features(prepared)["TEST"]
    groups = load_feature_groups()

    kwargs = dict(
        window_short=7, window_mid=21, window_long=60,
        short_features=groups["short_features"], mid_features=groups["mid_features"],
        long_features=groups["long_features"], context_features=groups["context_features"],
        sentiment_features=SENTIMENT_FEATURES, horizons=[1, 3, 5, 7, 10],
    )
    slow = namespace["SampleBuilder"](**kwargs).build_samples({"TEST": frame}, {"TEST": 0})
    fast = FastSampleBuilder(**kwargs).build_samples({"TEST": frame}, {"TEST": 0})
    assert slow, "the vendor's own builder produced no samples on the synthetic frame"
    assert len(slow) == len(fast), f"sample count mismatch: {len(slow)} vs {len(fast)}"

    arrays = ("X_short", "X_mid", "X_long", "X_context", "X_sentiment", "y", "y_zone", "y_levels", "stock_traits")
    for left, right in zip(slow, fast):
        assert left.symbol == right.symbol and left.date == right.date and left.stock_idx == right.stock_idx
        assert left.close_t == right.close_t, f"close_t mismatch at {left.date}"
        assert left.vol_ref == right.vol_ref, f"vol_ref mismatch at {left.date}"
        assert left.y_trend == right.y_trend, f"y_trend mismatch at {left.date}"
        for name in arrays:
            a, b = getattr(left, name), getattr(right, name)
            assert np.array_equal(a, b), f"{name} differs at {left.symbol} {left.date}"
    return f"{len(slow)} windows identical across {len(arrays)} arrays + 4 scalars"


def test_scaling_preserves_stock_traits() -> str:
    """Regression test for the upstream trait-dropping bug we work around."""
    _require_dataset()
    import numpy as np

    from hybrid_swingnet import import_stockxpert_v3
    from hybrid_swingnet.oos import transform_preserving_traits

    namespace, reason = import_stockxpert_v3()
    if reason:
        raise Unavailable(reason)

    # Two-sample stand-in so the scaler has something to fit.
    samples = []
    for offset in (0.0, 1.0):
        sample = __import__("stockxpert.dataset.make_samples", fromlist=["Sample"]).Sample(
            X_short=np.full((7, 2), 1.0 + offset, dtype=np.float32),
            X_mid=np.full((21, 2), 1.0 + offset, dtype=np.float32),
            X_long=np.full((60, 2), 1.0 + offset, dtype=np.float32),
            X_context=np.full((3,), 1.0 + offset, dtype=np.float32),
            X_sentiment=np.full((4,), 1.0 + offset, dtype=np.float32),
            y=np.zeros((5,), dtype=np.float32),
            y_zone=np.zeros((5,), dtype=np.int64),
            y_levels=np.zeros((5, 3), dtype=np.float32),
            y_trend=0.0, date="2024-01-01", symbol=f"S{int(offset)}", stock_idx=int(offset),
            close_t=100.0, vol_ref=0.01,
        )
        sample.stock_traits = np.arange(7, dtype=np.float32) + offset
        samples.append(sample)

    scaler = namespace["ScalerGroup"]()
    scaler.fit(samples)

    dropped = scaler.transform(samples)
    assert getattr(dropped[0], "stock_traits", None) is None, (
        "upstream ScalerGroup started preserving stock_traits - the workaround may be removable now"
    )

    kept = transform_preserving_traits(scaler, samples)
    for source, target in zip(samples, kept):
        assert np.array_equal(source.stock_traits, target.stock_traits), "traits not preserved"
        assert target.X_short.shape == source.X_short.shape
    return "upstream drops stock_traits; our transform keeps them (7 values per sample)"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> int:
    import logging

    # The vendor logs a warning for every sample it cannot build; keep our output
    # readable so a real failure is obvious.
    logging.getLogger("stockxpert").setLevel(logging.ERROR)

    print("=" * 78)
    print("HybridSwingNet (stockxpert) vendor integration test")
    print(f"repo root: {REPO_ROOT}")
    print("=" * 78)

    run("guarded package import", test_package_import_is_safe)
    run("import guard degrades to a reason (never raises)", test_import_guard_returns_reason_not_exception)
    run("vendored stockxpert + V3 entry points import", test_import_stockxpert_success_or_skip)
    run("V3 model forward pass shapes", test_v3_model_forward_shapes)
    run("V3 loss runs on CPU", test_v3_loss_runs)
    run("app.db adapter window shapes", test_adapter_window_shapes)
    run("windows are leakage-free", test_windows_are_leakage_free)
    run("targets align to horizons", test_targets_align_to_horizons)
    run("split is disjoint + embargoed", test_split_is_disjoint_and_embargoed)
    run("fast window builder == upstream builder", test_fast_builder_matches_upstream)
    run("scaling preserves stock_traits", test_scaling_preserves_stock_traits)

    passed = sum(1 for status, _, _ in _results if status == PASS)
    failed = sum(1 for status, _, _ in _results if status == FAIL)
    skipped = sum(1 for status, _, _ in _results if status == SKIP)

    print("-" * 78)
    print(f"RESULT: {passed} passed, {failed} failed, {skipped} skipped")
    if skipped:
        print("\nSKIPPED (with reasons - this is a graceful skip, not a failure):")
        for status, name, detail in _results:
            if status == SKIP:
                print(f"  - {name}: {detail}")
    if failed:
        print("\nFAILURES:")
        for status, name, detail in _results:
            if status == FAIL:
                print(f"  - {name}: {detail}")
    print("=" * 78)

    if failed:
        return 1
    if passed == 0:
        print("NOTHING RAN - treat as skipped, not as a pass.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
