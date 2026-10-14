"""Honest out-of-sample measurement of the vendored HybridSwingNet V3 model.

READ THIS FIRST
---------------
The upstream authors report that their own pre-registered walk-forward OOS
protocol (2018-2026) returned **-64.3% with Sharpe -0.79**, and that this is the
honest finding rather than a bug. This module exists to *measure*, and every
number it prints must be reported with that context attached.

This is NOT the authors' protocol
---------------------------------
Two reasons we cannot run theirs:

1. ``scripts/walkforward_v3.py`` imports ``backtest_historical``
   (``from backtest_historical import PROFILES, Prediction``) and that module is
   **not present anywhere in the upstream repository** at the pinned commit. The
   144-config grid, ``simulate_portfolio`` and ``INDIA_DELIVERY_COSTS`` it needs
   live in ``backtest_v3``/``backtest_historical``. The pre-registered protocol is
   therefore not reproducible from this commit.

2. Their protocol needs 2018 data; our ``prices_daily`` starts 2021-08-17.

So we run OUR OWN, deliberately simple and fully documented protocol:

* Cross-sectional stock split with a temporal purged/embargoed gap
  (``train_end`` -> +embargo -> val -> +embargo -> test), using upstream's
  unmodified ``cross_sectional_split`` / ``time_split`` so held-out stocks never
  appear in training.
* Train the unmodified V3 model with the unmodified V3 loss and upstream's V3
  ``Trainer``.
* Measure per-horizon direction accuracy on train (in-sample) vs test (OOS).
* Compile a non-overlapping, equal-weight, long-only top-N cohort backtest at one
  horizon, net of an India *delivery* round-trip cost.

Because the protocol is simpler than theirs, the sign of the result is the only
thing that can meaningfully be compared with -64.3% / Sharpe -0.79.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from hybrid_swingnet import UPSTREAM_COMMIT, import_stockxpert_v3
from hybrid_swingnet.appdb_dataset import (
    CANONICAL_CONFIG,
    DEFAULT_DB_PATH,
    DatasetBundle,
    DatasetSpec,
    build_dataset,
)

# Copied verbatim from upstream scripts/backtest_v3.py:306 (INDIA_DELIVERY_COSTS)
# so we do not have to import that heavy module. Percentages.
INDIA_DELIVERY_COSTS = {
    "slippage_pct": 0.05,
    "stt_pct": 0.10,
    "stamp_pct": 0.015,
    "gst_pct": 18.0,
    "exchange_pct": 0.00345,
}

# Authors' walk-forward result, for the side-by-side comparison.
AUTHORS_OOS_RETURN_PCT = -64.3
AUTHORS_OOS_SHARPE = -0.79


@dataclass
class SplitSpec:
    train_end: str = "2024-06-30"
    val_end: str = "2025-03-31"
    test_end: str = "2026-06-30"
    val_stocks: int = 10
    test_stocks: int = 10
    blind_stocks: int = 10
    embargo_days: int = 10
    seed: int = 42


@dataclass
class TrainSpec:
    epochs: int = 6
    batch_size: int = 256
    lr: float = 1.5e-4
    weight_decay: float = 3e-3
    grad_clip: float = 1.0
    early_stopping_patience: int = 3
    train_stride: int = 2
    """Keep every Nth training sample - bounds CPU time on a shared machine."""

    threads: int = 2


@dataclass
class BacktestSpec:
    horizon: int = 5
    threshold: float = 0.60
    top_n: int = 3
    use_costs: bool = True


@dataclass
class OOSResult:
    upstream_commit: str = UPSTREAM_COMMIT
    dataset: dict[str, Any] = field(default_factory=dict)
    splits: dict[str, Any] = field(default_factory=dict)
    accuracy: dict[str, Any] = field(default_factory=dict)
    backtest: dict[str, Any] = field(default_factory=dict)
    benchmark: dict[str, Any] = field(default_factory=dict)
    runtime_seconds: float = 0.0
    warnings: list[str] = field(default_factory=list)
    authors_reference: dict[str, Any] = field(
        default_factory=lambda: {
            "oos_return_pct": AUTHORS_OOS_RETURN_PCT,
            "oos_sharpe": AUTHORS_OOS_SHARPE,
            "source": "upstream README.md / docs/CANONICAL_RESULTS_V2.md",
        }
    )


def round_trip_cost_pct(costs: dict[str, float] | None = None) -> float:
    """India delivery round-trip cost in percent (buy + sell).

    Mirrors upstream's model: slippage both ways, STT on the sell leg, stamp duty
    on the buy leg, exchange charges both ways, GST on the exchange component.
    Brokerage is not in upstream's dict and is omitted here too.
    """
    c = costs or INDIA_DELIVERY_COSTS
    gross = 2 * c["slippage_pct"] + c["stt_pct"] + c["stamp_pct"] + 2 * c["exchange_pct"]
    gst = (2 * c["exchange_pct"]) * c["gst_pct"] / 100.0
    return gross + gst


# --------------------------------------------------------------------------- #
# Splitting / scaling
# --------------------------------------------------------------------------- #
def split_samples(samples: list[Any], split: SplitSpec, symbols: Sequence[str]) -> dict[str, list[Any]]:
    """Upstream cross-sectional + purged temporal split. Unmodified upstream code."""
    namespace, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)
    return namespace["cross_sectional_split"](
        samples,
        list(symbols),
        split.train_end,
        split.val_end,
        split.test_end,
        val_stocks=split.val_stocks,
        test_stocks=split.test_stocks,
        blind_holdout_stocks=split.blind_stocks,
        embargo_days=split.embargo_days,
        seed=split.seed,
    )


def transform_preserving_traits(scaler: Any, samples: list[Any]) -> list[Any]:
    """``ScalerGroup.transform`` but keeping ``stock_traits``.

    UPSTREAM BUG WORKED AROUND: ``stockxpert.dataset.scaling.ScalerGroup.transform``
    rebuilds each ``Sample`` with a positional constructor and never copies the
    ``stock_traits`` attribute that V3's ``SampleBuilder`` attached. Downstream,
    ``stockxpert.v3.dataset.dataloaders.stock_traits_from_sample`` then finds no
    attribute and silently substitutes ZEROS. Without this fix the whole point of
    V3 - static stock traits replacing learned stock IDs - is silently disabled
    for every training run.
    """
    transformed = scaler.transform(samples)
    for source, target in zip(samples, transformed):
        traits = getattr(source, "stock_traits", None)
        if traits is not None:
            setattr(target, "stock_traits", traits)
    return transformed


# --------------------------------------------------------------------------- #
# Model / training
# --------------------------------------------------------------------------- #
def load_canonical_config(path: Path | str = CANONICAL_CONFIG) -> dict[str, Any]:
    import yaml

    with Path(path).open("r") as handle:
        return yaml.safe_load(handle) or {}


def build_model(bundle: DatasetBundle, config: dict[str, Any]):
    namespace, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)
    first = bundle.samples[0]
    model_cfg = config.get("model", {}) or {}
    return namespace["StockXpertModelV3"](
        short_dim=first.X_short.shape[-1],
        mid_dim=first.X_mid.shape[-1],
        long_dim=first.X_long.shape[-1],
        context_dim=first.X_context.shape[-1],
        num_horizons=len(bundle.horizons),
        hidden_dim=int(model_cfg.get("hidden_dim", 96)),
        stock_embed_dim=int(model_cfg.get("stock_embed_dim", 16)),
        stock_traits_dim=int(model_cfg.get("stock_traits_dim", 7)),
        attn_heads=int(model_cfg.get("attn_heads", 4)),
        dropout=float(model_cfg.get("dropout", 0.15)),
        use_regime_head=False,
    )


def build_criterion(config: dict[str, Any], horizons: Sequence[int]):
    namespace, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)
    weights = config.get("loss_weights", {}) or {}
    train = config.get("train", {}) or {}
    horizon_weights = train.get("horizon_weights")
    if not horizon_weights:
        horizon_weights = [1.0] * len(horizons)
    return namespace["StockXpertV3Loss"](
        direction_weight=float(weights.get("direction", 1.0)),
        magnitude_weight=float(weights.get("magnitude", 0.4)),
        regime_weight=float(weights.get("regime", 0.0)),
        confidence_weight=float(weights.get("confidence", 0.0)),
        aux_trend_weight=float(weights.get("aux_trend", 0.0)),
        consistency_weight=float(weights.get("consistency", 0.0)),
        legacy_loss_mode=bool(weights.get("legacy_loss_mode", False)),
        horizon_weights=[float(w) for w in horizon_weights],
    )


def make_loader(samples: list[Any], batch_size: int, shuffle: bool, traits_dim: int) -> DataLoader:
    namespace, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)
    dataset = namespace["StockXpertV3Dataset"](samples, traits_dim)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=0)


# --------------------------------------------------------------------------- #
# Prediction + metrics
# --------------------------------------------------------------------------- #
def collect_predictions(
    model: Any,
    samples: list[Any],
    batch_size: int,
    device: torch.device,
    traits_dim: int = 7,
) -> np.ndarray:
    """Sigmoid direction probabilities, shape (n_samples, n_horizons), sample order."""
    loader = make_loader(samples, batch_size, shuffle=False, traits_dim=traits_dim)
    probs: list[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for inputs, _ in loader:
            outputs = model(
                inputs["X_short"].to(device),
                inputs["X_mid"].to(device),
                inputs["X_long"].to(device),
                inputs["X_context"].to(device),
                inputs["X_sentiment"].to(device),
                inputs["stock_traits"].to(device),
            )
            probs.append(torch.sigmoid(outputs[0]).cpu().numpy())
    if not probs:
        return np.zeros((0, len(samples)), dtype=np.float32)
    return np.concatenate(probs, axis=0)


def direction_accuracy(
    samples: list[Any],
    probs: np.ndarray,
    horizons: Sequence[int],
) -> dict[str, Any]:
    """Per-horizon direction accuracy plus an always-up baseline.

    Target sign convention is upstream's: ``target_h{h}`` is the Z-scored smoothed
    forward log return, so the label is ``target > 0``.
    """
    if not samples:
        return {}
    targets = np.stack([np.asarray(s.y, dtype=np.float64) for s in samples])
    if probs.shape[0] != targets.shape[0]:
        raise ValueError(f"prediction/target row mismatch: {probs.shape[0]} vs {targets.shape[0]}")
    labels = (targets > 0).astype(np.int8)

    out: dict[str, Any] = {"n_samples": int(len(samples))}
    per_horizon = {}
    for idx, horizon in enumerate(horizons):
        pred = (probs[:, idx] > 0.5).astype(np.int8)
        actual = labels[:, idx]
        acc = float((pred == actual).mean()) if len(actual) else float("nan")
        baseline = float((actual == 1).mean()) if len(actual) else float("nan")
        per_horizon[f"H{horizon}"] = {
            "accuracy": round(acc, 4),
            "always_up_baseline": round(baseline, 4),
            "edge_vs_baseline": round(acc - baseline, 4),
            "up_rate": round(baseline, 4),
        }
    out["per_horizon"] = per_horizon
    macro = float(np.mean([v["accuracy"] for v in per_horizon.values()])) if per_horizon else float("nan")
    macro_base = (
        float(np.mean([v["always_up_baseline"] for v in per_horizon.values()])) if per_horizon else float("nan")
    )
    out["macro_accuracy"] = round(macro, 4)
    out["macro_always_up_baseline"] = round(macro_base, 4)
    out["macro_edge_vs_baseline"] = round(macro - macro_base, 4)
    return out


def information_coefficient(
    samples: list[Any],
    probs: np.ndarray,
    horizons: Sequence[int],
) -> dict[str, float]:
    """Spearman IC between predicted magnitude proxy and realised target."""
    from scipy.stats import spearmanr

    if not samples:
        return {}
    targets = np.stack([np.asarray(s.y, dtype=np.float64) for s in samples])
    out: dict[str, float] = {}
    for idx, horizon in enumerate(horizons):
        ic = spearmanr(probs[:, idx], targets[:, idx]).statistic
        out[f"H{horizon}"] = round(float(ic) if ic is not None and not math.isnan(ic) else 0.0, 4)
    return out


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #
def _forward_returns(price_data: dict[str, pd.DataFrame], horizon: int) -> dict[str, pd.Series]:
    return {
        symbol: (frame["Close"].shift(-horizon) / frame["Close"] - 1.0)
        for symbol, frame in price_data.items()
    }


def cohort_backtest(
    samples: list[Any],
    probs: np.ndarray,
    price_data: dict[str, pd.DataFrame],
    horizons: Sequence[int],
    spec: BacktestSpec,
) -> dict[str, Any]:
    """Non-overlapping, equal-weight, long-only top-N cohort backtest.

    Mechanics (deliberately simple and stated so the number can be argued with):
    cohort *k* starts at the first date not yet held by cohort *k-1*; on that date
    up to ``top_n`` symbols with ``p_up >= threshold`` are bought at ``close_t``
    and sold at ``close_{t+h}``. Cohort return = mean trade return minus
    round-trip cost. Cohorts are non-overlapping in time and compound into an
    equity curve. Sharpe is the cohort-return mean/std scaled by
    ``sqrt(252/h)``.
    """
    if spec.horizon not in horizons:
        raise ValueError(f"horizon {spec.horizon} not among {list(horizons)}")
    idx = list(horizons).index(spec.horizon)
    fwd = _forward_returns(price_data, spec.horizon)
    cost = round_trip_cost_pct() / 100.0 if spec.use_costs else 0.0

    rows = []
    for pos, sample in enumerate(samples):
        series = fwd.get(sample.symbol)
        if series is None:
            continue
        value = series.get(pd.Timestamp(sample.date))
        if value is None or not np.isfinite(value):
            continue
        rows.append(
            {
                "date": pd.Timestamp(sample.date),
                "symbol": sample.symbol,
                "prob": float(probs[pos, idx]),
                "fwd_ret": float(value),
            }
        )
    if not rows:
        return {"error": "no usable trades"}

    frame = pd.DataFrame(rows).sort_values(["date", "prob"], ascending=[True, False])
    dates = sorted(frame["date"].unique())
    date_index = {d: i for i, d in enumerate(dates)}

    cohort_returns: list[float] = []
    trade_returns: list[float] = []
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    held_until = -1

    for pos, date in enumerate(dates):
        if pos <= held_until:
            continue
        day = frame[frame["date"] == date]
        picks = day[day["prob"] >= spec.threshold].head(spec.top_n)
        if picks.empty:
            continue
        rets = picks["fwd_ret"].to_numpy(dtype=float) - cost
        cohort = float(np.mean(rets))
        cohort_returns.append(cohort)
        trade_returns.extend(rets.tolist())
        equity *= 1.0 + cohort
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        held_until = pos + spec.horizon

    if not cohort_returns:
        return {
            "error": "no cohort triggered (threshold too high for this model/window)",
            "threshold": spec.threshold,
            "top_n": spec.top_n,
            "horizon": spec.horizon,
            "round_trip_cost_pct": round(cost * 100, 4),
            "n_cohorts": 0,
            "n_trades": 0,
            "n_candidate_samples": int(len(frame)),
        }

    arr = np.asarray(cohort_returns, dtype=float)
    periods_per_year = 252.0 / spec.horizon
    sharpe = float(arr.mean() / arr.std(ddof=1) * math.sqrt(periods_per_year)) if arr.size > 1 and arr.std(ddof=1) > 0 else float("nan")
    return {
        "horizon": spec.horizon,
        "threshold": spec.threshold,
        "top_n": spec.top_n,
        "round_trip_cost_pct": round(cost * 100, 4),
        "n_cohorts": int(arr.size),
        "n_trades": int(len(trade_returns)),
        "total_return_pct": round((equity - 1.0) * 100, 4),
        "sharpe_annualised": round(sharpe, 4) if not math.isnan(sharpe) else None,
        "max_drawdown_pct": round(max_dd * 100, 4),
        "mean_trade_return_pct": round(float(np.mean(trade_returns)) * 100, 4),
        "win_rate": round(float(np.mean(np.asarray(trade_returns) > 0)), 4),
        "first_cohort": str(dates[0].date()),
        "last_cohort": str(dates[min(len(dates) - 1, held_until)].date()) if dates else None,
    }


def backtest_threshold_sweep(
    samples: list[Any],
    probs: np.ndarray,
    price_data: dict[str, pd.DataFrame],
    horizons: Sequence[int],
    spec: BacktestSpec,
    thresholds: Sequence[float] = (0.50, 0.52, 0.55, 0.60),
) -> dict[str, Any]:
    """Run the cohort backtest at several entry thresholds plus unconditional top-N.

    A freshly trained model often emits probabilities clustered near 0.5, so a
    single high threshold can produce zero trades and tell you nothing. Reporting
    the whole sweep makes the sensitivity visible instead of hiding it behind one
    silent null.
    """
    sweep: dict[str, Any] = {}
    for threshold in thresholds:
        variant = BacktestSpec(
            horizon=spec.horizon, threshold=float(threshold), top_n=spec.top_n, use_costs=spec.use_costs
        )
        sweep[f"thr_{threshold:.2f}"] = cohort_backtest(samples, probs, price_data, horizons, variant)

    unconditional = BacktestSpec(
        horizon=spec.horizon, threshold=float("-inf"), top_n=spec.top_n, use_costs=spec.use_costs
    )
    sweep["unconditional_top_n"] = cohort_backtest(samples, probs, price_data, horizons, unconditional)

    primary_key = f"thr_{spec.threshold:.2f}"
    primary = sweep.get(primary_key)
    if not primary or primary.get("n_cohorts", 0) == 0:
        primary = dict(sweep["unconditional_top_n"])
        primary["note"] = (
            f"requested threshold {spec.threshold} produced no trades; primary shown is the "
            "unconditional top-N variant"
        )
    return {"primary": primary, "by_threshold": sweep}


def buy_and_hold_benchmark(
    price_data: dict[str, pd.DataFrame],
    symbols: Sequence[str],
    start: str,
    end: str,
) -> dict[str, Any]:
    """Equal-weight buy-and-hold of the test-universe stocks over the test window."""
    rets = []
    for symbol in symbols:
        frame = price_data.get(symbol)
        if frame is None or frame.empty:
            continue
        window = frame.loc[(frame.index >= pd.Timestamp(start)) & (frame.index <= pd.Timestamp(end))]
        if len(window) < 2:
            continue
        rets.append(float(window["Close"].iloc[-1] / window["Close"].iloc[0] - 1.0))
    if not rets:
        return {"error": "no benchmark data"}
    return {
        "universe": "equal-weight test stocks",
        "start": start,
        "end": end,
        "n_symbols": len(rets),
        "total_return_pct": round(float(np.mean(rets)) * 100, 4),
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_oos(
    dataset_spec: DatasetSpec | None = None,
    split_spec: SplitSpec | None = None,
    train_spec: TrainSpec | None = None,
    backtest_spec: BacktestSpec | None = None,
    verbose: bool = True,
) -> OOSResult:
    """Build data, train the vendored V3 model, and measure OOS honestly."""
    started = time.time()
    dataset_spec = dataset_spec or DatasetSpec()
    split_spec = split_spec or SplitSpec()
    train_spec = train_spec or TrainSpec()
    backtest_spec = backtest_spec or BacktestSpec()
    warnings: list[str] = []

    torch.set_num_threads(max(1, int(train_spec.threads)))
    torch.manual_seed(split_spec.seed)
    np.random.seed(split_spec.seed)

    def log(message: str) -> None:
        if verbose:
            print(f"[oos] {message}", flush=True)

    log(f"upstream commit {UPSTREAM_COMMIT}")
    log(f"building dataset from {dataset_spec.db_path} (max_symbols={dataset_spec.max_symbols})")
    bundle = build_dataset(dataset_spec)
    log(f"symbols={len(bundle.symbols)} samples={len(bundle.samples)}")

    config = load_canonical_config()
    split = split_samples(bundle.samples, split_spec, bundle.symbols)
    counts = {key: len(value) for key, value in split.items()}
    log(f"split sizes {counts}")
    if not split["train"] or not split["test"]:
        raise RuntimeError(f"empty train/test split: {counts}")

    traits_dim = int((config.get("model", {}) or {}).get("stock_traits_dim", 7))
    _, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)
    namespace, _ = import_stockxpert_v3()
    scaler = namespace["ScalerGroup"]()
    scaler.fit(split["train"])
    train_samples = transform_preserving_traits(scaler, split["train"])
    val_samples = transform_preserving_traits(scaler, split["val"])
    test_samples = transform_preserving_traits(scaler, split["test"])

    device = torch.device("cpu")
    model = build_model(bundle, config).to(device)
    criterion = build_criterion(config, bundle.horizons)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=train_spec.lr, weight_decay=train_spec.weight_decay
    )
    trainer = namespace["Trainer"](
        model,
        criterion,
        optimizer,
        device,
        grad_clip=train_spec.grad_clip,
        early_stopping_patience=train_spec.early_stopping_patience,
        use_amp=False,
    )

    train_used = (
        train_samples[:: train_spec.train_stride] if train_spec.train_stride > 1 else train_samples
    )
    log(f"training on {len(train_used)}/{len(train_samples)} samples for {train_spec.epochs} epochs")
    train_loader = make_loader(train_used, train_spec.batch_size, True, traits_dim)
    val_loader = make_loader(val_samples, train_spec.batch_size, False, traits_dim)
    history = trainer.train(train_loader, val_loader, train_spec.epochs)
    log(f"train history:\n{history.to_string(index=False)}")

    result = OOSResult()
    result.warnings = warnings
    result.dataset = {
        "db_path": str(dataset_spec.db_path),
        "max_symbols": dataset_spec.max_symbols,
        "symbols_used": len(bundle.symbols),
        "samples": len(bundle.samples),
        "horizons": list(bundle.horizons),
        "feature_dims": {
            "short": len(bundle.short_features),
            "mid": len(bundle.mid_features),
            "long": len(bundle.long_features),
            "context": len(bundle.context_features),
            "sentiment": len(bundle.sentiment_features),
        },
    }
    result.splits = {
        "mode": "cross_sectional + purged temporal (upstream split code)",
        "train_end": split_spec.train_end,
        "val_end": split_spec.val_end,
        "test_end": split_spec.test_end,
        "embargo_days": split_spec.embargo_days,
        "counts": counts,
        "train_stocks": len({s.symbol for s in split["train"]}),
        "test_stocks": len({s.symbol for s in split["test"]}),
        "train_used_after_stride": len(train_used),
    }

    # ---- in-sample vs out-of-sample direction accuracy -------------------- #
    train_probs = collect_predictions(model, train_used, train_spec.batch_size, device, traits_dim)
    test_probs = collect_predictions(model, test_samples, train_spec.batch_size, device, traits_dim)
    accuracy = {
        "train_in_sample": direction_accuracy(train_used, train_probs, bundle.horizons),
        "test_out_of_sample": direction_accuracy(test_samples, test_probs, bundle.horizons),
        "test_ic_spearman": information_coefficient(test_samples, test_probs, bundle.horizons),
    }
    result.accuracy = accuracy
    log(
        "in-sample macro acc {:.4f} | OOS macro acc {:.4f} | OOS baseline {:.4f}".format(
            accuracy["train_in_sample"].get("macro_accuracy", float("nan")),
            accuracy["test_out_of_sample"].get("macro_accuracy", float("nan")),
            accuracy["test_out_of_sample"].get("macro_always_up_baseline", float("nan")),
        )
    )

    # ---- cost-aware long-only cohort backtest ---------------------------- #
    result.backtest = backtest_threshold_sweep(
        test_samples, test_probs, bundle.price_data, bundle.horizons, backtest_spec
    )
    result.benchmark = buy_and_hold_benchmark(
        bundle.price_data,
        sorted({s.symbol for s in test_samples}),
        split_spec.val_end,
        split_spec.test_end,
    )
    result.runtime_seconds = round(time.time() - started, 2)
    return result


def result_to_json(result: OOSResult, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2, default=str), encoding="utf-8")
    return path


__all__ = [
    "AUTHORS_OOS_RETURN_PCT",
    "AUTHORS_OOS_SHARPE",
    "BacktestSpec",
    "OOSResult",
    "SplitSpec",
    "TrainSpec",
    "backtest_threshold_sweep",
    "buy_and_hold_benchmark",
    "cohort_backtest",
    "collect_predictions",
    "direction_accuracy",
    "run_oos",
    "result_to_json",
    "round_trip_cost_pct",
]
