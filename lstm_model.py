"""LSTM forward-return forecaster for NSE daily bars (CPU-only).

WHY THIS FILE EXISTS
--------------------
The existing production models (`ml_train.py` -> LightGBM on hand-made features)
predict 6/12 month forward returns from a *single* feature row per stock.  The
academic equity-forecasting literature usually feeds a *sequence* of past bars
into a recurrent net instead, and that is what this module provides: one LSTM
that reads `seq_len` consecutive daily feature vectors and emits
  * `ret`  - a point estimate of the forward return over `horizon` bars, and
  * `dir`  - a logit for "the forward return is positive".

Two properties matter more than accuracy, and both are enforced here:

1. NO LOOKAHEAD.  Every feature is computed from *backward-looking* pandas
   operators only (`diff`, `rolling`, `ewm(adjust=False)`), i.e. the feature row
   dated `t` uses bars up to and including `t` and nothing after it.  A sample
   whose window ends at `t` has its label at `t + horizon`, so the label is
   *later* than the input by construction.  Normalisation statistics are fitted
   on the training fold and then frozen before touching validation data
   (`Standardizer`), so no validation bar can influence the inputs it is scored
   on.  `walk_forward_folds()` additionally purges every training sample whose
   label is not fully observed before the validation window opens, plus an
   explicit `embargo` of extra bars.  `check_fold_embargo()` re-derives that
   guarantee from the data so tests can assert it.

2. HONEST EVALUATION.  The training CLI (`lstm_train.py`) reports only
   out-of-sample numbers and always prints a naive baseline next to them.
   Nothing in this module reports in-sample fit as if it were skill.

ENVIRONMENT
-----------
torch is CPU-only here (no GPU, `torch.cuda.is_available()` is False).  The
import is guarded so that a machine without torch can still import this module
and the web app can never blank out because of it: with torch missing,
`TORCH_AVAILABLE` is False, `build_price_features` / `build_sequences` /
`walk_forward_folds` still work (they are pure numpy/pandas), and only
`LSTMForecaster` raises, with a plain-English message, at construction time.
"""
from __future__ import annotations

import os
import random
import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Guarded optional import.  This is the house rule: a missing torch must never
# break the app, only the code path that actually needs a neural net.
# ---------------------------------------------------------------------------
try:  # pragma: no cover - exercised by test_lstm.py via a blocked import
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
    TORCH_IMPORT_ERROR = None
except Exception as exc:  # ImportError, but also any broken install
    torch = None
    nn = None
    TORCH_AVAILABLE = False
    TORCH_IMPORT_ERROR = exc


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
# Every feature below is causal: it is a function of bars up to and including
# the row's own date.  See build_price_features() for the exact formula.
DEFAULT_FEATURE_COLUMNS = (
    "ret_1",      # 1-bar log return (short-term reversal / noise)
    "ret_5",      # 1-week log return (momentum)
    "ret_21",     # 1-month log return (momentum)
    "vol_21",     # 21-bar realised volatility of 1-bar log returns
    "ma_gap",     # close / 50-bar mean - 1 (trend position)
    "range_pct",  # (high - low) / close (intraday range, a risk proxy)
    "vol_z",      # volume z-score vs its own 21-bar history
    "rsi_14",     # Wilder RSI, 0..1 scaled
)
FEATURE_COLUMNS = list(DEFAULT_FEATURE_COLUMNS)  # house-style alias

DEFAULT_SEQ_LEN = 30
DEFAULT_HORIZON = 5
DEFAULT_MIN_ROWS = 400
VERSION = "lstm-v0.1-cpu"

# Default path to a saved bundle.  Nothing writes here unless the caller passes
# --save-model explicitly, so importing this module never creates files.
DEFAULT_MODEL_PATH = "data/lstm_model.pt"


class LeakageError(RuntimeError):
    """Raised when a fold would let future information reach the training set."""


def default_db_path() -> str:
    """Absolute path of data/app.db, independent of the current directory.

    The production scripts use the relative path "data/app.db" and are always
    run from the repo root.  Tests may be run from elsewhere, so resolve
    relative to this file instead.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "data", "app.db")


# ---------------------------------------------------------------------------
# Determinism / CPU hygiene
# ---------------------------------------------------------------------------
def seed_everything(seed: int = 7) -> None:
    """Seed python, numpy and torch so a run is repeatable.

    On CPU the LSTM is deterministic as long as the thread count is fixed; with
    several threads the order of floating-point reductions can vary, so callers
    that need bit-exact repeatability should use `set_threads(1)` (the default
    in the CLI, which is also the polite choice on a shared machine).
    """
    random.seed(seed)
    np.random.seed(seed)
    if TORCH_AVAILABLE:
        torch.manual_seed(seed)


def set_threads(n: int = 1) -> None:
    """Cap torch's CPU thread pool.  Default 1 keeps the shared box responsive."""
    if TORCH_AVAILABLE:
        try:
            torch.set_num_threads(max(1, int(n)))
        except Exception:
            pass


def device() -> str:
    """Always "cpu": this environment has no GPU and torch is a +cpu build."""
    return "cpu"


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------
def load_price_panel(db_path: str | None = None,
                     symbols: list[str] | None = None,
                     n_symbols: int | None = None,
                     min_rows: int = DEFAULT_MIN_ROWS) -> pd.DataFrame:
    """Read daily OHLCV from SQLite, read-only.

    Parameters
    ----------
    db_path : path to app.db (default: <repo>/data/app.db)
    symbols : optional explicit symbol list
    n_symbols : when `symbols` is None, take this many symbols with the most
        complete history (deterministic: row count desc, then symbol asc).
    min_rows : drop symbols with less history than this.

    Returns a DataFrame sorted by (symbol, date) with columns
    symbol, date, open, high, low, close, volume.
    """
    path = db_path or default_db_path()
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"price database not found: {path} (expected data/app.db)")
    # mode=ro guarantees this module can never write to the production DB.
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if symbols:
            placeholders = ",".join("?" for _ in symbols)
            sel = (f"SELECT symbol, COUNT(*) FROM prices_daily "
                   f"WHERE symbol IN ({placeholders}) GROUP BY symbol "
                   f"HAVING COUNT(*) >= ? ORDER BY symbol", list(symbols) + [min_rows])
        else:
            sel = ("SELECT symbol, COUNT(*) FROM prices_daily GROUP BY symbol "
                   "HAVING COUNT(*) >= ? ORDER BY COUNT(*) DESC, symbol ASC",
                   [min_rows])
        rows = conn.execute(sel[0], sel[1]).fetchall()
        if not rows:
            raise ValueError("no symbols matched the requested filters")
        if n_symbols is not None:
            rows = rows[:int(n_symbols)]
        wanted = [r[0] for r in rows]
        placeholders = ",".join("?" for _ in wanted)
        q = (f"SELECT symbol, date, open, high, low, close, volume "
             f"FROM prices_daily WHERE symbol IN ({placeholders}) "
             f"ORDER BY symbol, date")
        df = pd.read_sql_query(q, conn, params=wanted)
    finally:
        conn.close()
    if df.empty:
        raise ValueError("prices_daily returned no rows")
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    return df.sort_values(["symbol", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Feature engineering (strictly backward-looking)
# ---------------------------------------------------------------------------
def build_price_features(df: pd.DataFrame,
                         feature_columns: list[str] | None = None) -> pd.DataFrame:
    """Add the causal feature columns to a (symbol, date, ohlcv) frame.

    WHY CAUSAL: each line below is `diff`, `rolling` or `ewm(adjust=False)`
    applied *within* one symbol and in date order.  All three pandas operators
    are backward-looking: the value at date `t` is a function of rows at dates
    <= t.  There is no `shift(-n)`, no centred window and no full-sample
    statistic, so changing a future bar cannot change an earlier feature row.
    `test_lstm.py::test_features_ignore_future_bars` proves that empirically by
    rewriting the future and diffing the output.

    Note the deliberate omission of any whole-history normalisation here:
    scaling happens later and only with training-fold statistics, because a
    per-symbol full-history z-score would smuggle the future into the past.
    """
    cols = list(feature_columns or DEFAULT_FEATURE_COLUMNS)
    out = df.sort_values(["symbol", "date"]).copy()
    g = out.groupby("symbol", sort=False)

    close = out["close"].astype(float)
    logc = np.log(close.where(close > 0))          # NaN for non-positive junk
    out["_logc"] = logc
    g = out.groupby("symbol", sort=False)

    # Momentum: differences of the log price.  diff(n) at t uses t and t-n.
    out["ret_1"] = g["_logc"].diff(1)
    out["ret_5"] = g["_logc"].diff(5)
    out["ret_21"] = g["_logc"].diff(21)

    # Realised volatility of 1-bar returns over the trailing 21 bars.
    out["vol_21"] = g["ret_1"].transform(
        lambda s: s.rolling(21, min_periods=10).std())

    # Distance from the trailing 50-bar mean (a trend-position feature).
    ma50 = g["close"].transform(lambda s: s.rolling(50, min_periods=25).mean())
    out["ma_gap"] = close / ma50 - 1.0

    # Intraday range relative to the close: a cheap risk/illiquidity proxy.
    out["range_pct"] = (out["high"].astype(float) -
                        out["low"].astype(float)) / close

    # Volume z-score against its own trailing 21-bar history.
    vol_mean = g["volume"].transform(
        lambda s: s.rolling(21, min_periods=10).mean())
    vol_std = g["volume"].transform(
        lambda s: s.rolling(21, min_periods=10).std())
    out["vol_z"] = (out["volume"].astype(float) - vol_mean) / vol_std.replace(0, np.nan)

    # Wilder RSI on a 0..1 scale.  ewm(adjust=False) is a recursive filter that
    # only ever consumes the current and previous rows.
    delta = g["close"].diff(1)
    up = delta.clip(lower=0.0)
    dn = (-delta).clip(lower=0.0)
    avg_up = up.groupby(out["symbol"], sort=False).transform(
        lambda s: s.ewm(alpha=1.0 / 14.0, adjust=False).mean())
    avg_dn = dn.groupby(out["symbol"], sort=False).transform(
        lambda s: s.ewm(alpha=1.0 / 14.0, adjust=False).mean())
    rs = avg_up / avg_dn.replace(0, np.nan)
    out["rsi_14"] = 1.0 - 1.0 / (1.0 + rs)

    out = out.drop(columns=["_logc"])
    missing = [c for c in cols if c not in out.columns]
    if missing:
        raise ValueError(f"unknown feature columns requested: {missing}")
    return out


# ---------------------------------------------------------------------------
# Sequence dataset
# ---------------------------------------------------------------------------
@dataclass
class SequenceDataset:
    """Rolling windows ready for the LSTM, plus the dates needed to purge.

    X            : (n, seq_len, n_features) float32
    y            : (n,) realised forward return, close[t + horizon]/close[t] - 1
    decision_date: date of the LAST bar in each window (the information date)
    label_date   : date of bar t + horizon (when the label became knowable)
    symbol       : symbol of each window
    decision_idx : position of decision_date on the global trading-date axis
    label_idx    : position of label_date on the same axis
    dates        : the sorted global trading-date axis
    """
    X: np.ndarray
    y: np.ndarray
    decision_date: np.ndarray
    label_date: np.ndarray
    symbol: np.ndarray
    decision_idx: np.ndarray
    label_idx: np.ndarray
    dates: np.ndarray
    feature_columns: tuple
    seq_len: int
    horizon: int

    def __len__(self) -> int:
        return int(self.y.shape[0])

    @property
    def n_features(self) -> int:
        return int(self.X.shape[2])


def build_sequences(panel: pd.DataFrame,
                    feature_columns: list[str] | None = None,
                    seq_len: int = DEFAULT_SEQ_LEN,
                    horizon: int = DEFAULT_HORIZON,
                    max_samples_per_symbol: int | None = None) -> SequenceDataset:
    """Cut each symbol's feature history into (window -> forward return) pairs.

    Ordering / shape contract (asserted in test_lstm.py):
      * X[i, -1, :] is the feature row of `decision_date[i]` and X[i, 0, :] is
        exactly `seq_len - 1` bars earlier, in chronological order.
      * windows never span two symbols, and rows are emitted per symbol in date
        order, so a window is always a contiguous stretch of that symbol's bars.
      * y[i] uses close at decision bar + horizon.  If that bar does not exist
        yet (its label is not knowable today) the sample is dropped rather than
        filled - a fabricated label is the easiest way to leak.

    Leakage note: the *features* never look forward (see build_price_features);
    only `y`, `label_date` and `label_idx` deliberately point forward, and they
    are used exclusively for purging (`walk_forward_folds`) and scoring, never
    as model inputs.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1 bar")
    if seq_len < 1:
        raise ValueError("seq_len must be >= 1 bar")
    cols = list(feature_columns or DEFAULT_FEATURE_COLUMNS)
    missing = [c for c in cols if c not in panel.columns]
    if missing:
        raise ValueError(f"panel is missing feature columns: {missing}")

    df = panel.sort_values(["symbol", "date"]).reset_index(drop=True)
    global_dates = np.sort(df["date"].unique())

    X_parts, y_parts = [], []
    dec_parts, lab_parts, sym_parts = [], [], []
    for sym, grp in df.groupby("symbol", sort=True):
        grp = grp.sort_values("date")
        feat = grp[cols].to_numpy(dtype=np.float32)
        close = grp["close"].to_numpy(dtype=float)
        dts = grp["date"].to_numpy()
        n = len(grp)
        if n < seq_len + horizon:
            continue

        # A window is usable only if every bar in it has finite features.
        finite = np.isfinite(feat).all(axis=1)
        cum = np.concatenate([[0], np.cumsum(finite)])
        idx = np.arange(seq_len - 1, n)                 # possible window ends
        window_ok = (cum[idx + 1] - cum[idx + 1 - seq_len]) == seq_len
        # ...and only if the label bar already exists in the history.
        has_label = (idx + horizon) < n
        sel = idx[window_ok & has_label]
        if sel.size == 0:
            continue
        y = close[sel + horizon] / close[sel] - 1.0
        good = np.isfinite(y)
        sel, y = sel[good], y[good]
        if sel.size == 0:
            continue
        if max_samples_per_symbol is not None and sel.size > max_samples_per_symbol:
            # Keep the most recent windows; older history is dropped, never the
            # other way round (dropping recent windows would bias the folds).
            sel, y = sel[-max_samples_per_symbol:], y[-max_samples_per_symbol:]

        # sliding_window_view returns a read-only view; fancy-indexing copies
        # only the windows we keep, which keeps memory sane at 1000+ symbols.
        view = np.lib.stride_tricks.sliding_window_view(feat, seq_len, axis=0)
        windows = view.transpose(0, 2, 1)               # (n-seq+1, seq, feat)
        X_parts.append(np.ascontiguousarray(windows[sel - (seq_len - 1)],
                                            dtype=np.float32))
        y_parts.append(y.astype(float))
        dec_parts.append(dts[sel])
        lab_parts.append(dts[sel + horizon])
        sym_parts.append(np.full(sel.size, sym, dtype=object))

    if not X_parts:
        raise ValueError(
            "no usable sequences: need symbols with at least "
            f"seq_len({seq_len}) + horizon({horizon}) rows of finite features")

    X = np.concatenate(X_parts, axis=0)
    y = np.concatenate(y_parts, axis=0)
    decision_date = np.concatenate(dec_parts)
    label_date = np.concatenate(lab_parts)
    symbol = np.concatenate(sym_parts)
    # Global positions let the splitter compare dates as plain integers.
    decision_idx = np.searchsorted(global_dates, decision_date)
    label_idx = np.searchsorted(global_dates, label_date)
    return SequenceDataset(X=X, y=y, decision_date=decision_date,
                           label_date=label_date, symbol=symbol,
                           decision_idx=decision_idx, label_idx=label_idx,
                           dates=global_dates, feature_columns=tuple(cols),
                           seq_len=int(seq_len), horizon=int(horizon))


# ---------------------------------------------------------------------------
# Walk-forward splits with purge + embargo
# ---------------------------------------------------------------------------
@dataclass
class Fold:
    """One walk-forward fold: an expanding training set and an OOS window."""
    index: int
    train_idx: np.ndarray
    val_idx: np.ndarray
    val_start_idx: int
    val_end_idx: int
    train_label_max_idx: int
    val_decision_min_idx: int

    @property
    def gap_bars(self) -> int:
        """Bars between the last training label and the first validation bar.

        This must be >= `embargo`.  Training labels *are* observed before the
        validation window opens, so a positive gap is the concrete proof that
        the fold is purged.
        """
        return int(self.val_decision_min_idx - self.train_label_max_idx)


def walk_forward_folds(ds: SequenceDataset, n_folds: int = 3,
                       embargo: int = 5,
                       min_train_frac: float = 0.5) -> list[Fold]:
    """Expanding-window walk-forward split with an explicit purge + embargo.

    HOW LEAKAGE IS PREVENTED
    ------------------------
    A sample's label is `close[t + horizon] / close[t] - 1`.  At decision date
    `t` that label is *unknown* - it needs `horizon` more bars.  So a training
    sample may only be used for a fold if its label bar has already been
    observed before the validation window opens.  With `v_lo` the global bar
    index of the first validation decision date, the rule implemented here is

        label_idx(sample) + embargo < v_lo

    i.e. training labels must all sit strictly more than `embargo` bars before
    the validation window.  `embargo` is the usual extra cushion for serial
    correlation / overlapping labels: even if the feature windows of adjacent
    samples overlap, no training label overlaps the valuation period.
    Because `label_idx = decision_idx + horizon` (exactly, for a symbol with no
    missing bars; larger when bars are missing), this also implies
    `decision_idx(sample) + horizon + embargo < v_lo`.

    Folds are built out of the *global date axis*, not row counts, so every
    symbol's samples for a given period land in the same fold.  Validation
    blocks are disjoint and cover the later part of the sample: each OOS bar is
    predicted by exactly one model, which is what makes the pooled metric a
    genuine walk-forward number rather than a re-used sample.

    `check_fold_embargo()` re-verifies the invariant from the data itself; the
    CLI calls it on every fold and test_lstm.py asserts it directly.
    """
    n_folds = int(n_folds)
    embargo = int(embargo)
    if n_folds < 1:
        raise ValueError("n_folds must be >= 1")
    if embargo < 0:
        raise ValueError("embargo must be >= 0 bars")
    if not 0.0 < min_train_frac < 1.0:
        raise ValueError("min_train_frac must be in (0, 1)")

    lo = int(ds.decision_idx.min())
    hi = int(ds.decision_idx.max())
    span = hi - lo + 1
    first_val = lo + max(1, int(span * min_train_frac))
    remaining = hi - first_val + 1
    if remaining < n_folds:
        raise ValueError(
            f"not enough distinct decision dates for {n_folds} folds "
            f"({remaining} bars left after the initial training span); "
            "reduce --folds or --min-train-frac")
    block = remaining // n_folds

    folds: list[Fold] = []
    for k in range(n_folds):
        v_lo = first_val + k * block
        v_hi = hi if k == n_folds - 1 else first_val + (k + 1) * block - 1
        # Purge + embargo: a training label is only usable if it was fully
        # observed at least `embargo` bars before the validation window opens.
        train_idx = np.where(ds.label_idx + embargo < v_lo)[0]
        val_idx = np.where((ds.decision_idx >= v_lo) &
                           (ds.decision_idx <= v_hi))[0]
        if train_idx.size == 0 or val_idx.size == 0:
            raise ValueError(
                f"fold {k} is empty (train={train_idx.size}, "
                f"val={val_idx.size}); widen the date range or lower "
                "min_train_frac / embargo")
        train_label_max = int(ds.label_idx[train_idx].max())
        val_decision_min = int(ds.decision_idx[val_idx].min())
        if train_label_max + embargo >= val_decision_min:
            raise LeakageError(
                f"fold {k}: last training label (bar {train_label_max}) is not "
                f"at least {embargo} bars before the first validation bar "
                f"({val_decision_min})")
        folds.append(Fold(index=k, train_idx=train_idx, val_idx=val_idx,
                          val_start_idx=v_lo, val_end_idx=v_hi,
                          train_label_max_idx=train_label_max,
                          val_decision_min_idx=val_decision_min))
    return folds


def check_fold_embargo(ds: SequenceDataset, fold: Fold, embargo: int) -> dict:
    """Re-derive the no-leakage guarantee from the fold's own sample indices.

    Returns a small dict of evidence (usable in logs / reports) and raises
    LeakageError if any training label sits inside or after the validation
    window.  Tests call this instead of trusting the splitter's arithmetic.
    """
    tr_label_max = int(ds.label_idx[fold.train_idx].max())
    tr_decision_max = int(ds.decision_idx[fold.train_idx].max())
    va_decision_min = int(ds.decision_idx[fold.val_idx].min())
    va_label_min = int(ds.label_idx[fold.val_idx].min())
    if tr_label_max + int(embargo) >= va_decision_min:
        raise LeakageError(
            f"embargo violated: train label bar {tr_label_max} + embargo "
            f"{embargo} >= first validation bar {va_decision_min}")
    if tr_decision_max >= va_decision_min:
        raise LeakageError(
            f"train decision bar {tr_decision_max} is not before the first "
            f"validation bar {va_decision_min}")
    return {
        "n_train": int(fold.train_idx.size),
        "n_val": int(fold.val_idx.size),
        "train_label_max_bar": tr_label_max,
        "train_decision_max_bar": tr_decision_max,
        "val_decision_min_bar": va_decision_min,
        "val_label_min_bar": va_label_min,
        "embargo_bars": int(embargo),
        "gap_bars_after_last_train_label": int(va_decision_min - tr_label_max),
        # Bars of cushion between the last training *decision* and the first
        # validation decision.  Must be >= horizon + embargo.
        "decision_gap_bars": int(va_decision_min - tr_decision_max),
    }


def purge_inner_split(ds: SequenceDataset, train_idx: np.ndarray,
                      embargo: int, val_frac: float = 0.15) -> tuple:
    """Split an outer training set into (inner-train, inner-val) for early stop.

    The same purge rule is applied: an inner training label must be observed at
    least `embargo` bars before the inner validation window.  This keeps model
    selection inside the training period - the outer validation fold is never
    used to choose an epoch, so the reported OOS number stays honest.
    """
    if not 0.0 < val_frac < 1.0 or train_idx.size < 10:
        return train_idx, np.array([], dtype=int)
    order = np.argsort(ds.decision_idx[train_idx], kind="stable")
    ordered = train_idx[order]
    lo = int(ds.decision_idx[ordered].min())
    hi = int(ds.decision_idx[ordered].max())
    cut = hi - max(1, int((hi - lo + 1) * val_frac)) + 1
    inner_train = ordered[ds.label_idx[ordered] + int(embargo) < cut]
    inner_val = ordered[ds.decision_idx[ordered] >= cut]
    if inner_train.size < 5 or inner_val.size < 5:
        return train_idx, np.array([], dtype=int)
    return inner_train, inner_val


# ---------------------------------------------------------------------------
# Normalisation (fitted on training data only)
# ---------------------------------------------------------------------------
@dataclass
class Standardizer:
    """Per-feature z-score whose mean/std come from ONE fold's training data.

    WHY THIS CLASS EXISTS: the classic way to leak in a time-series project is
    to z-score the whole panel (or the whole fold, train+val) before splitting.
    The validation mean then contains validation-period information, and every
    training input is scaled using the future.  Here `fit()` is only ever
    called with training-fold windows and the result is frozen; `transform()`
    is a pure function of those frozen numbers, so perturbing validation data
    cannot change any model input (test_lstm.py asserts exactly that).
    """
    mean: np.ndarray | None = None
    std: np.ndarray | None = None

    @classmethod
    def fit(cls, X: np.ndarray) -> "Standardizer":
        if X.size == 0:
            raise ValueError("cannot fit a Standardizer on an empty array")
        # Average over samples and timesteps, keeping one statistic per feature.
        axes = tuple(range(X.ndim - 1))
        mean = np.asarray(X, dtype=float).mean(axis=axes)
        std = np.asarray(X, dtype=float).std(axis=axes)
        std = np.where(std < 1e-8, 1.0, std)   # constant feature -> no scaling
        return cls(mean=mean, std=std)

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean is None or self.std is None:
            raise ValueError("Standardizer.transform() called before fit()")
        return ((np.asarray(X, dtype=np.float64) - self.mean) / self.std
                ).astype(np.float32)

    def state_dict(self) -> dict:
        return {"mean": None if self.mean is None else self.mean.tolist(),
                "std": None if self.std is None else self.std.tolist()}

    @classmethod
    def from_state_dict(cls, state: dict) -> "Standardizer":
        mean = state.get("mean")
        std = state.get("std")
        return cls(mean=None if mean is None else np.asarray(mean, dtype=float),
                   std=None if std is None else np.asarray(std, dtype=float))


# ---------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------
if TORCH_AVAILABLE:

    class LSTMForecaster(nn.Module):
        """Small sequence model with two heads: forward return and direction.

        Shape: (batch, seq_len, n_features) -> (ret [batch], dir_logit [batch]).

        `relu` activation is applied on top of the LSTM's last hidden state, as
        in the classic Gu, Kelly & Xiu (2020) "Empirical Asset Pricing via
        Machine Learning" design.  It is deliberately tiny (default 32 units,
        1 layer) because our whole history is ~1.2k bars per symbol and CPU is
        the only hardware available; a big net would memorise noise.
        """

        def __init__(self, n_features: int, hidden: int = 32, layers: int = 1,
                     dropout: float = 0.0):
            super().__init__()
            self.n_features = int(n_features)
            self.hidden = int(hidden)
            self.layers = int(layers)
            self.lstm = nn.LSTM(
                input_size=self.n_features,
                hidden_size=self.hidden,
                num_layers=self.layers,
                batch_first=True,
                # PyTorch ignores dropout on a single-layer LSTM; passing 0
                # avoids a spurious warning.
                dropout=float(dropout) if self.layers > 1 else 0.0,
            )
            self.norm = nn.LayerNorm(self.hidden)
            self.head_ret = nn.Linear(self.hidden, 1)
            self.head_dir = nn.Linear(self.hidden, 1)

        def forward(self, x):
            out, _ = self.lstm(x)
            h = torch.relu(self.norm(out[:, -1, :]))
            return self.head_ret(h).squeeze(-1), self.head_dir(h).squeeze(-1)

else:  # pragma: no cover - only on a machine without torch

    class LSTMForecaster:  # type: ignore[no-redef]
        """Placeholder so importing this module never fails without torch."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "PyTorch is not available "
                f"({TORCH_IMPORT_ERROR}). lstm_model.py imported fine, but the "
                "LSTM itself needs torch. Install the CPU build, or skip the "
                "LSTM path - the rest of the app works without it.")


def build_model(n_features: int, hidden: int = 32, layers: int = 1,
                dropout: float = 0.0) -> "LSTMForecaster":
    """Construct the model.  Raises a readable error when torch is missing."""
    if not TORCH_AVAILABLE:
        raise RuntimeError(
            "PyTorch is not available "
            f"({TORCH_IMPORT_ERROR}); cannot build the LSTM. All other "
            "functions in lstm_model stay usable without it.")
    set_threads(1)
    seed_everything(7)
    return LSTMForecaster(n_features, hidden=hidden, layers=layers,
                          dropout=dropout)


def count_parameters(model) -> int:
    """Trainable parameter count - useful to show that the net stays small."""
    if not TORCH_AVAILABLE:
        return 0
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))


# ---------------------------------------------------------------------------
# Training / prediction
# ---------------------------------------------------------------------------
def train_model(ds: SequenceDataset, train_idx: np.ndarray, epochs: int = 10,
                hidden: int = 32, layers: int = 1, dropout: float = 0.0,
                batch_size: int = 256, lr: float = 1e-3, seed: int = 7,
                threads: int = 1, scaler: "Standardizer | None" = None,
                y_mean: float | None = None, y_std: float | None = None,
                dir_weight: float = 1.0, inner_val_frac: float = 0.0,
                embargo: int = 5, dir_threshold: float = 0.0,
                patience: int | None = None,
                verbose: bool = False):
    """Fit the LSTM on `train_idx` only and return (model, info).

    `scaler`, `y_mean` and `y_std` are fitted on the training fold when not
    supplied.  Anything passed in must already come from training data - the
    caller (lstm_train.py) fits them per fold, which is why the function
    accepts them instead of computing them from whatever X it is handed.

    Direction target: 1 when the forward return clears `dir_threshold` (0.0 by
    default, so plain "up").  Loss = MSE on standardised returns +
    `dir_weight` * BCE on direction.  When the caller uses a train-median
    threshold it is passed in here and used for scoring too, so the label
    definition never differs between fitting and evaluation.

    Honesty note: early stopping, when enabled, monitors an INNER validation
    slice carved out of the training period with the same purge rule
    (`purge_inner_split`).  The outer validation fold never influences training.
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError(
            "PyTorch is not available "
            f"({TORCH_IMPORT_ERROR}); cannot train the LSTM.")
    seed_everything(seed)
    set_threads(threads)

    X_all = ds.X[train_idx]
    y_all = ds.y[train_idx].astype(np.float64)
    if scaler is None:
        scaler = Standardizer.fit(X_all)
    if y_mean is None:
        y_mean = float(y_all.mean())
    if y_std is None or not np.isfinite(y_std) or y_std < 1e-12:
        y_std = float(y_all.std()) or 1.0

    Xs = scaler.transform(X_all)
    ys = (y_all - y_mean) / y_std
    # Direction label: 1 when the forward return clears `dir_threshold`.  The
    # caller passes a threshold learned on this same training fold (or 0.0), so
    # the loss and the later scoring use one and the same definition of "up".
    dir_labels = (y_all > float(dir_threshold)).astype(np.float32)

    # Optional early stopping works on an INNER validation slice taken from the
    # training period, purged by the same embargo rule.  The outer validation
    # fold is never consulted, so the reported OOS number stays honest.
    tr_pos = np.arange(len(train_idx))
    va_pos = np.array([], dtype=int)
    if inner_val_frac > 0:
        inner_tr, inner_va = purge_inner_split(ds, train_idx, embargo,
                                               inner_val_frac)
        if inner_va.size:
            # purge_inner_split returns indices into `ds`; map them to row
            # positions inside Xs (= positions inside train_idx).
            lookup = {int(v): i for i, v in enumerate(train_idx)}
            tr_pos = np.array([lookup[int(v)] for v in inner_tr], dtype=int)
            va_pos = np.array([lookup[int(v)] for v in inner_va
                               if int(v) in lookup], dtype=int)

    model = LSTMForecaster(ds.n_features, hidden=hidden, layers=layers,
                           dropout=dropout)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce = nn.BCEWithLogitsLoss()
    mse = nn.MSELoss()

    n = int(len(tr_pos))
    rng = np.random.default_rng(seed)
    history = {"train_loss": [], "inner_val_loss": []}
    best_state, best_loss, best_epoch, bad_epochs = None, np.inf, -1, 0
    bs = max(1, int(batch_size))

    for epoch in range(1, int(epochs) + 1):
        model.train()
        order = tr_pos[rng.permutation(n)]
        total = 0.0
        for start in range(0, n, bs):
            take = order[start:start + bs]
            xb = torch.from_numpy(Xs[take])
            yb = torch.from_numpy(ys[take].astype(np.float32))
            db = torch.from_numpy(dir_labels[take])
            opt.zero_grad()
            pred_ret, pred_dir = model(xb)
            loss = mse(pred_ret, yb) + dir_weight * bce(pred_dir, db)
            loss.backward()
            # Gradient clipping keeps a small net stable on noisy financial
            # batches without needing a learning-rate schedule.
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total += float(loss.detach()) * len(take)
        history["train_loss"].append(total / max(1, n))

        if va_pos.size:
            model.eval()
            with torch.no_grad():
                _, vlogit = model(torch.from_numpy(Xs[va_pos]))
                vloss = float(bce(vlogit,
                                  torch.from_numpy(dir_labels[va_pos])))
            history["inner_val_loss"].append(vloss)
            if vloss < best_loss - 1e-6:
                best_state = {k: v.detach().clone()
                              for k, v in model.state_dict().items()}
                best_loss, best_epoch, bad_epochs = vloss, epoch, 0
            else:
                bad_epochs += 1
                if patience is not None and bad_epochs >= int(patience):
                    if verbose:
                        print(f"  early stop at epoch {epoch} "
                              f"(best {best_epoch}, inner val loss "
                              f"{best_loss:.4f})")
                    break
        if verbose:
            msg = f"  epoch {epoch:>3} train loss {history['train_loss'][-1]:.4f}"
            if history["inner_val_loss"]:
                msg += f"  inner val loss {history['inner_val_loss'][-1]:.4f}"
            print(msg)

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    info = {"scaler": scaler, "y_mean": float(y_mean), "y_std": float(y_std),
            "history": history, "n_train": n,
            "best_epoch": best_epoch, "best_inner_val_loss": (
                None if best_state is None else float(best_loss)),
            "n_parameters": count_parameters(model),
            "feature_columns": list(ds.feature_columns),
            "seq_len": int(ds.seq_len), "horizon": int(ds.horizon),
            "version": VERSION}
    return model, info


def predict(model, X: np.ndarray, scaler: Standardizer,
            y_mean: float = 0.0, y_std: float = 1.0,
            batch_size: int = 1024) -> dict:
    """Score windows.  Returns de-standardised expected returns and P(up).

    `y_mean`/`y_std` are the TRAINING-fold label statistics; they only undo the
    scaling used during fitting, so the returned `ret` is in the same units as
    the target (a simple forward return, e.g. 0.01 = +1%).
    """
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch is not available; cannot predict.")
    if len(X) == 0:
        return {"ret": np.zeros(0), "prob_up": np.zeros(0)}
    Xs = scaler.transform(X)
    rets, probs = [], []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(Xs), max(1, int(batch_size))):
            xb = torch.from_numpy(Xs[start:start + batch_size])
            r, logit = model(xb)
            rets.append(r.numpy())
            probs.append(torch.sigmoid(logit).numpy())
    ret = np.concatenate(rets) * float(y_std) + float(y_mean)
    return {"ret": ret, "prob_up": np.concatenate(probs)}


# ---------------------------------------------------------------------------
# Integration hook: latest-bar scoring for the live app
# ---------------------------------------------------------------------------
def build_latest_windows(panel: pd.DataFrame,
                         feature_columns: list[str] | None = None,
                         seq_len: int = DEFAULT_SEQ_LEN):
    """One window per symbol, ending on that symbol's most recent bar.

    This is the shape the live app needs: no label, no future bar required.
    Returns (X, symbols, dates) where X is (n_symbols, seq_len, n_features) and
    `dates` is the decision date of each window.  Symbols whose latest window
    contains a NaN feature (e.g. a brand-new listing) are skipped.
    """
    cols = list(feature_columns or DEFAULT_FEATURE_COLUMNS)
    df = panel.sort_values(["symbol", "date"])
    X, syms, dates = [], [], []
    for sym, grp in df.groupby("symbol", sort=True):
        feat = grp[cols].to_numpy(dtype=np.float32)
        if len(grp) < seq_len:
            continue
        window = feat[-seq_len:]
        if not np.isfinite(window).all():
            continue
        X.append(window.astype(np.float32))
        syms.append(sym)
        dates.append(grp["date"].to_numpy()[-1])
    if not X:
        return (np.zeros((0, seq_len, len(cols)), dtype=np.float32), [], [])
    return np.stack(X), syms, dates


def score_latest(panel: pd.DataFrame, model, info: dict,
                 seq_len: int = DEFAULT_SEQ_LEN) -> list[dict]:
    """RECOMMENDED INTEGRATION HOOK.

    Call this from the live path (e.g. daily_update.py or terminal_api.py) to
    add an LSTM column next to the existing ml_score:

        rows = lstm_model.score_latest(panel, model, info)
        # [{"symbol": "TCS", "date": "...", "prob_up": 0.53,
        #   "exp_ret": 0.004, "version": "lstm-v0.1-cpu"}, ...]

    `info` is the dict returned by train_model / load_saved_model.  Nothing here
    writes to the database or touches the network, so wiring it in cannot
    change existing behaviour unless the caller stores the result.
    """
    if not TORCH_AVAILABLE:
        return []
    cols = info.get("feature_columns") or list(DEFAULT_FEATURE_COLUMNS)
    X, syms, dates = build_latest_windows(panel, cols, seq_len)
    if len(X) == 0:
        return []
    out = predict(model, X, info["scaler"], info.get("y_mean", 0.0),
                  info.get("y_std", 1.0))
    return [{"symbol": s,
             "date": pd.Timestamp(d).date().isoformat(),
             "prob_up": float(p),
             "exp_ret": float(r),
             "version": info.get("version", VERSION)}
            for s, d, p, r in zip(syms, dates, out["prob_up"], out["ret"])]


# ---------------------------------------------------------------------------
# Persistence (only used when the CLI is given --save-model)
# ---------------------------------------------------------------------------
def save_bundle(path: str, model, info: dict) -> str:
    """Save weights + fitting metadata so the app can score new bars later."""
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch is not available; nothing to save.")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    payload = {
        "state_dict": model.state_dict(),
        "n_features": int(model.n_features),
        "hidden": int(model.hidden),
        "layers": int(model.layers),
        "feature_columns": list(info.get("feature_columns", FEATURE_COLUMNS)),
        "seq_len": int(info.get("seq_len", DEFAULT_SEQ_LEN)),
        "horizon": int(info.get("horizon", DEFAULT_HORIZON)),
        "scaler": info["scaler"].state_dict(),
        "y_mean": float(info.get("y_mean", 0.0)),
        "y_std": float(info.get("y_std", 1.0)),
        "version": info.get("version", VERSION),
    }
    torch.save(payload, path)
    return path


def load_saved_model(path: str = DEFAULT_MODEL_PATH):
    """Load a bundle written by save_bundle().  Returns (model, info)."""
    if not TORCH_AVAILABLE:
        raise RuntimeError("PyTorch is not available; cannot load the LSTM.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no saved LSTM bundle at {path}")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = LSTMForecaster(payload["n_features"], hidden=payload["hidden"],
                           layers=payload["layers"])
    model.load_state_dict(payload["state_dict"])
    model.eval()
    info = {"scaler": Standardizer.from_state_dict(payload["scaler"]),
            "y_mean": payload["y_mean"], "y_std": payload["y_std"],
            "feature_columns": payload["feature_columns"],
            "seq_len": payload["seq_len"], "horizon": payload["horizon"],
            "version": payload["version"]}
    return model, info
