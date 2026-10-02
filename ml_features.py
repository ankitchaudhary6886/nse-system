"""Canonical feature definitions shared by ML training and prediction.

Keep these calculations in one place: a score produced by the batch and
deep-dive paths must mean the same thing as a score produced during training.
"""
import numpy as np
import pandas as pd

MOMENTUM_OFFSETS = {"ret_1m": 21, "ret_3m": 63, "ret_6m": 126,
                    "ret_12m": 252}
FEATURE_COLUMNS = ["ret_1m", "ret_3m", "ret_6m", "ret_12m", "vol_3m",
                   "dist_high", "dist_low", "above_ma50", "above_ma200"]
VOLATILITY_WINDOW = 63


def feature_frame(group):
    """Return legacy ML features with the exact canonical definitions."""
    g = group.sort_values("date").copy()
    c = pd.to_numeric(g["close"], errors="coerce")
    for name, offset in MOMENTUM_OFFSETS.items():
        g[name] = c / c.shift(offset) - 1.0
    # Volatility is the rolling standard deviation of log returns, not the
    # standard deviation of simple returns.
    g["vol_3m"] = np.log(c).diff().rolling(VOLATILITY_WINDOW).std()
    g["dist_high"] = c / c.rolling(252).max()
    g["dist_low"] = c / c.rolling(252).min()
    g["ma50"] = c.rolling(50).mean()
    g["ma200"] = c.rolling(200).mean()
    g["above_ma50"] = (c > g["ma50"]).astype(int)
    g["above_ma200"] = (c > g["ma200"]).astype(int)
    return g


def latest_features(closes):
    """Build one prediction row from chronological close values."""
    c = np.asarray(closes, dtype=float)
    if len(c) < 252:
        return None
    # Use the frame implementation so training and inference cannot drift.
    dates = pd.date_range("2000-01-01", periods=len(c), freq="D")
    row = feature_frame(pd.DataFrame({"date": dates, "close": c})).iloc[-1]
    values = row[FEATURE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        return None
    return values.tolist()
