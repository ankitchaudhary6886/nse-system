"""A drop-in, value-identical fast replacement for upstream's ``SampleBuilder``.

WHY
---
Upstream ``stockxpert.dataset.make_samples.SampleBuilder._build_single_sample``
materialises a full ``pandas`` row (``df.iloc[t]``) about ten times per sample.
On our data (pandas 3.0, ~130 feature columns, ~1150 samples per symbol) that
measures **~30 ms per sample**, i.e. ~35 s per symbol, i.e. ~47 minutes for an
80-symbol run just to build windows - before any training happens. On a machine
shared with four other agents that is not an acceptable cost.

WHAT THIS DOES NOT DO
---------------------
It does not change the window semantics, the target alignment, the horizon
handling, the row range, or the float dtype. It only replaces repeated row
materialisation with pre-extracted NumPy arrays and slicing. ``test_hybrid_swingnet.py``
asserts that this builder returns **identical** values to the upstream builder on
real data, field by field.

The static-trait logic is still upstream's ``compute_stock_traits``.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from stockxpert.dataset.make_samples import Sample
from stockxpert.v3.dataset.make_samples import STOCK_TRAIT_COLUMNS, SampleBuilder as V3SampleBuilder
from stockxpert.v3.dataset.make_samples import compute_stock_traits

FIB_COLUMNS = [
    "fib_0.0",
    "fib_23.6",
    "fib_38.2",
    "fib_50.0",
    "fib_61.8",
    "fib_78.6",
    "fib_100.0",
]


class FastSampleBuilder(V3SampleBuilder):
    """Identical output to :class:`V3SampleBuilder`, without the row churn."""

    def build_samples(
        self, feature_data: Dict[str, pd.DataFrame], symbol_map: Dict[str, int]
    ) -> List[Sample]:
        all_samples: List[Sample] = []
        for symbol, df in feature_data.items():
            stock_idx = symbol_map[symbol]
            samples = self._build_samples_for_symbol_fast(df, symbol, stock_idx)
            traits = compute_stock_traits(
                df, self.stock_trait_columns, len(self.stock_trait_columns)
            )
            for sample in samples:
                setattr(sample, "stock_traits", traits)
            all_samples.extend(samples)
        return all_samples

    # -- internals ---------------------------------------------------------- #
    def _build_samples_for_symbol_fast(
        self, df: pd.DataFrame, symbol: str, stock_idx: int
    ) -> List[Sample]:
        if df.empty:
            return []

        max_horizon = max(self.horizons)
        end_idx = len(df) - max_horizon
        if end_idx <= self.max_window:
            return []

        short_np = df[self.short_features].to_numpy(dtype=np.float64)
        mid_np = df[self.mid_features].to_numpy(dtype=np.float64)
        long_np = df[self.long_features].to_numpy(dtype=np.float64)
        context_np = df[self.context_features].to_numpy(dtype=np.float64)

        if self.sentiment_features:
            valid = [c for c in self.sentiment_features if c in df.columns]
            if len(valid) == len(self.sentiment_features):
                sentiment_np = df[self.sentiment_features].to_numpy(dtype=np.float64)
            else:
                sentiment_np = np.zeros((len(df), len(self.sentiment_features)), dtype=np.float64)
        else:
            sentiment_np = np.zeros((len(df), 0), dtype=np.float64)

        target_np = df[[f"target_h{h}" for h in self.horizons]].to_numpy(dtype=np.float64)
        fib_np = df[FIB_COLUMNS].to_numpy(dtype=np.float64)
        level_cols = []
        for horizon in self.horizons:
            level_cols.extend(
                [
                    f"level_target_h{horizon}_res",
                    f"level_target_h{horizon}_sup",
                    f"level_target_h{horizon}_tgt",
                ]
            )
        level_np = df[level_cols].to_numpy(dtype=np.float64).reshape(len(df), len(self.horizons), 3)

        close_np = df["Close"].to_numpy(dtype=np.float64)
        vol_ref_np = (
            df["vol_ref"].to_numpy(dtype=np.float64)
            if "vol_ref" in df.columns
            else np.ones(len(df), dtype=np.float64)
        )
        index = df.index

        horizon_offsets = np.asarray(self.horizons, dtype=np.int64)
        samples: List[Sample] = []
        for t in range(self.max_window, end_idx):
            try:
                future_close = close_np[t + horizon_offsets]
                current_fibs = fib_np[t]
                y_zone = np.argmin(np.abs(current_fibs[None, :] - future_close[:, None]), axis=1)

                future_prices = close_np[t + 1 : t + 11]
                if future_prices.size > 0:
                    y_trend = 1.0 if float(np.mean(future_prices)) > close_np[t] else 0.0
                else:
                    y_trend = 0.5

                samples.append(
                    Sample(
                        X_short=short_np[t - self.window_short + 1 : t + 1].astype(np.float32),
                        X_mid=mid_np[t - self.window_mid + 1 : t + 1].astype(np.float32),
                        X_long=long_np[t - self.window_long + 1 : t + 1].astype(np.float32),
                        X_context=context_np[t].astype(np.float32),
                        X_sentiment=sentiment_np[t].astype(np.float32),
                        y=target_np[t].astype(np.float32),
                        y_zone=y_zone.astype(np.int64),
                        y_levels=level_np[t].astype(np.float32),
                        y_trend=float(y_trend),
                        date=index[t],
                        symbol=symbol,
                        stock_idx=stock_idx,
                        close_t=float(close_np[t]),
                        vol_ref=float(vol_ref_np[t]),
                    )
                )
            except Exception:
                continue
        return samples


__all__ = ["FIB_COLUMNS", "FastSampleBuilder", "STOCK_TRAIT_COLUMNS"]
