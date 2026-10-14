"""Dataset adapter: our SQLite ``data/app.db`` -> HybridSwingNet V3 samples.

Why this exists
---------------
Upstream loads prices with yfinance (``stockxpert.mdata.prices.download_prices``)
and news sentiment from GDELT/FinBERT or a CSV. Neither is reachable/useful for
an offline measurement on our own data, and our house rule is to keep runs small
and local. So this adapter feeds OUR ``prices_daily`` table into the *unmodified*
upstream feature builder and sample builder, which keeps the model input contract
identical to the authors' while swapping only the data source.

What is upstream and what is ours
---------------------------------
* Upstream, unmodified: ``stockxpert.features.builder.FeatureBuilder`` (all
  technical indicators + the multi-horizon Z-scored targets), and
  ``stockxpert.v3.dataset.make_samples.SampleBuilder`` (window construction).
* Ours: reading OHLCV from SQLite, the point-in-time market/breadth context, the
  static stock traits, and zero-filled sentiment columns.

KNOWN GAPS (deliberate, reported, not hidden)
---------------------------------------------
1. SENTIMENT IS ALL ZEROS. We have no news feed for our 1086 symbols, so the
   9-column sentiment encoder input is neutral/zero. Upstream's SentimentEncoder
   is a plain MLP over those 9 numbers, so the encoder still runs, but it
   contributes no information. Any result from this adapter is therefore a
   *4-encoder* result, not the authors' 5-encoder result.
2. FEATURE GROUPS COME FROM THE AUTHORS' CANONICAL CONFIG
   (``configs/v3_nifty100_from_nifty500.yaml``). The two other shipped configs
   (``v3_nifty100.yaml``, ``v3_nifty100_swing_oos.yaml``) leave every feature
   group EMPTY, which makes ``X_short`` a ``(7, 0)`` array and the model fail on
   ``Conv1d``. See README_INTEGRATION.md.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from hybrid_swingnet import UPSTREAM_DIR, ensure_scripts_path, ensure_upstream_path, import_stockxpert_v3

# Upstream's canonical experiment config - the ONLY shipped config that actually
# declares the five feature groups.
CANONICAL_CONFIG = UPSTREAM_DIR / "configs" / "v3_nifty100_from_nifty500.yaml"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "app.db"

#: Upstream's sentiment block (scripts/train_v3.py::SENTIMENT_FEATURES). We feed
#: zeros because we have no news data - see module docstring gap (1).
SENTIMENT_FEATURES = [
    "sentiment_mean",
    "sentiment_count",
    "sentiment_std",
    "sentiment_rolling_5d",
    "sentiment_momentum",
    "sentiment_spike",
    "sentiment_rolling_10d",
    "sentiment_rolling_21d",
    "sentiment_trend",
]

PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class DatasetSpec:
    """Everything needed to reproduce a dataset build."""

    db_path: Path = DEFAULT_DB_PATH
    max_symbols: int = 80
    min_rows: int = 700
    horizons: tuple[int, ...] = (1, 3, 5, 7, 10)
    window_short: int = 7
    window_mid: int = 21
    window_long: int = 60
    start: str | None = None
    end: str | None = None
    extra_columns: tuple[str, ...] = ()
    """Extra frame columns to expose as the FIRST short/mid/long feature.

    Used by the leakage test to carry a row-index sentinel through the window
    builder; empty for normal runs.
    """


@dataclass
class DatasetBundle:
    samples: list[Any]
    price_data: dict[str, pd.DataFrame]
    feature_data: dict[str, pd.DataFrame]
    short_features: list[str]
    mid_features: list[str]
    long_features: list[str]
    context_features: list[str]
    sentiment_features: list[str]
    horizons: list[int]
    symbols: list[str] = field(default_factory=list)


def connect_readonly(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open ``app.db`` read-only. We only ever SELECT from production data."""
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"app.db not found: {path}")
    uri = f"file:{path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_sector_map(con: sqlite3.Connection) -> dict[str, str]:
    """Symbol -> sector from our ``stocks`` table (feeds the static traits)."""
    try:
        rows = con.execute("SELECT symbol, sector FROM stocks").fetchall()
    except sqlite3.Error:
        return {}
    return {str(sym): str(sec) for sym, sec in rows if sym and sec}


def select_symbols(
    con: sqlite3.Connection,
    max_symbols: int,
    min_rows: int,
    start: str | None = None,
    end: str | None = None,
) -> list[str]:
    """Deterministically pick the ``max_symbols`` longest histories.

    Ordered by row count desc then symbol asc so repeated runs pick the same
    universe (no hidden randomness in the data selection).
    """
    where = []
    params: list[Any] = []
    if start:
        where.append("date >= ?")
        params.append(start)
    if end:
        where.append("date <= ?")
        params.append(end)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    sql = (
        f"SELECT symbol, COUNT(*) AS n FROM prices_daily {clause} "
        "GROUP BY symbol HAVING n >= ? ORDER BY n DESC, symbol ASC LIMIT ?"
    )
    params.append(int(min_rows))
    params.append(int(max_symbols))
    return [str(r[0]) for r in con.execute(sql, params).fetchall()]


def load_price_frames(
    con: sqlite3.Connection,
    symbols: Sequence[str],
    start: str | None = None,
    end: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Load OHLCV for ``symbols`` into upstream-shaped frames.

    Upstream expects a ``DatetimeIndex`` named ``Date`` with columns
    ``Open/High/Low/Close/Volume`` (see train_v3.normalize_price_frames).
    """
    frames: dict[str, pd.DataFrame] = {}
    if not symbols:
        return frames
    placeholders = ",".join("?" for _ in symbols)
    where = [f"symbol IN ({placeholders})"]
    params: list[Any] = list(symbols)
    if start:
        where.append("date >= ?")
        params.append(start)
    if end:
        where.append("date <= ?")
        params.append(end)
    sql = (
        "SELECT symbol, date, open, high, low, close, volume FROM prices_daily "
        f"WHERE {' AND '.join(where)} ORDER BY symbol, date"
    )
    frame = pd.read_sql_query(sql, con, params=params)
    if frame.empty:
        return frames
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.rename(
        columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )
    for symbol, group in frame.groupby("symbol", sort=False):
        sub = group.drop(columns=["symbol"]).set_index("Date").sort_index()
        sub = sub[~sub.index.duplicated(keep="last")]
        sub[PRICE_COLUMNS] = sub[PRICE_COLUMNS].apply(pd.to_numeric, errors="coerce")
        sub = sub.replace([np.inf, -np.inf], np.nan).dropna(subset=["Open", "High", "Low", "Close"])
        sub = sub[(sub[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
        sub["Volume"] = sub["Volume"].fillna(0.0)
        if not sub.empty:
            frames[str(symbol)] = sub
    return frames


def load_feature_groups(config_path: Path | str = CANONICAL_CONFIG) -> dict[str, list[str]]:
    """Read the five feature groups from the authors' canonical YAML config."""
    import yaml

    with Path(config_path).open("r") as handle:
        data = yaml.safe_load(handle) or {}
    features = data.get("features", {}) or {}
    groups = {
        name: list(features.get(name) or [])
        for name in ("short_features", "mid_features", "long_features", "context_features")
    }
    empty = [name for name, cols in groups.items() if not cols]
    if empty:
        raise ValueError(
            f"config {config_path} declares no columns for {empty}; the model needs "
            "non-empty feature groups (X_short would be (7, 0) -> Conv1d fails)"
        )
    return groups


def add_market_context(price_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Point-in-time universe context: market return / vol / trend / breadth.

    Reimplemented from train_v3.add_market_context (pure pandas, ~10 lines) so
    that importing the vendored research scripts is not required just to build a
    dataset. Semantics are identical: per-date cross-sectional means of daily
    returns, all strictly backward-looking.
    """
    close = pd.DataFrame({symbol: df["Close"] for symbol, df in price_data.items()}).sort_index()
    returns = close.pct_change().replace([np.inf, -np.inf], np.nan)

    market_return_1d = returns.mean(axis=1).fillna(0.0)
    context = pd.DataFrame(index=close.index)
    context["market_return_1d"] = market_return_1d
    context["market_return_5d"] = market_return_1d.rolling(5, min_periods=1).sum().fillna(0.0)
    context["market_vol_21d"] = market_return_1d.rolling(21, min_periods=2).std().fillna(0.0)
    context["market_trend_60d"] = market_return_1d.rolling(60, min_periods=5).mean().fillna(0.0)
    context["market_breadth_5d"] = (returns > 0).mean(axis=1).rolling(5, min_periods=1).mean().fillna(0.5)

    columns = list(context.columns)
    enriched = {}
    for symbol, df in price_data.items():
        frame = df.join(context, how="left")
        frame[columns] = frame[columns].ffill().bfill().fillna(0.0)
        enriched[symbol] = frame
    return enriched


def add_sentiment_placeholders(price_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Neutral (zero) sentiment columns - we have no news data. Gap (1) above."""
    for frame in price_data.values():
        for column in SENTIMENT_FEATURES:
            frame[column] = 0.0
    return price_data


def add_static_stock_traits(
    price_data: dict[str, pd.DataFrame],
    sector_map: dict[str, str] | None = None,
) -> dict[str, pd.DataFrame]:
    """V3 static traits: sector bits + mcap/liquidity rank + beta + vol percentile.

    Reimplemented from train_v3.add_static_stock_traits (pure pandas) so the two
    ``sector_enc_*`` one-hot bits reflect OUR sector map from ``stocks``.
    ``mcap_rank`` and ``liquidity_tier`` both use the dollar-volume percentile
    because ``prices_daily`` carries no market cap (documented limitation).
    """
    sector_map = sector_map or {}
    liquidity: dict[str, float] = {}
    volatility: dict[str, float] = {}
    beta: dict[str, float] = {}

    market_return = pd.DataFrame(
        {symbol: df["Close"].pct_change() for symbol, df in price_data.items()}
    ).mean(axis=1).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    market_var = float(market_return.var()) or 1e-8

    for symbol, df in price_data.items():
        returns = df["Close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        volume = df["Volume"] if "Volume" in df.columns else pd.Series(0.0, index=df.index)
        dollar_volume = (df["Close"] * volume).replace([np.inf, -np.inf], np.nan)
        liquidity[symbol] = float(dollar_volume.median()) if not dollar_volume.empty else 0.0
        volatility[symbol] = float(returns.rolling(21, min_periods=5).std().median() or 0.0)
        aligned = pd.concat([returns, market_return], axis=1).dropna()
        beta[symbol] = (
            float(aligned.iloc[:, 0].cov(aligned.iloc[:, 1]) / market_var) if len(aligned) > 2 else 1.0
        )

    liquidity_rank = pd.Series(liquidity).rank(pct=True).fillna(0.5)
    volatility_rank = pd.Series(volatility).rank(pct=True).fillna(0.5)
    sectors = sorted({sector for sector in sector_map.values() if sector})
    sector_ids = {sector: idx + 1 for idx, sector in enumerate(sectors)}

    enriched = {}
    for symbol, df in price_data.items():
        frame = df.copy()
        sector_id = sector_ids.get(sector_map.get(symbol, ""), 0)
        frame["sector_enc_0"] = float((sector_id >> 0) & 1)
        frame["sector_enc_1"] = float((sector_id >> 1) & 1)
        frame["sector_enc_2"] = float((sector_id >> 2) & 1)
        frame["mcap_rank"] = float(liquidity_rank.get(symbol, 0.5))
        frame["beta"] = float(np.clip(beta.get(symbol, 1.0), -3.0, 3.0))
        frame["vol_pct"] = float(volatility_rank.get(symbol, 0.5))
        frame["liquidity_tier"] = float(liquidity_rank.get(symbol, 0.5))
        enriched[symbol] = frame
    return enriched


def build_feature_data(
    price_data: dict[str, pd.DataFrame],
    horizons: Iterable[int],
    sector_map: dict[str, str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Run the unmodified upstream feature builder over our price frames."""
    namespace, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)

    prepared = add_sentiment_placeholders(price_data)
    prepared = add_market_context(prepared)
    prepared = add_static_stock_traits(prepared, sector_map)

    builder = namespace["FeatureBuilder"](horizons=list(horizons))
    return builder.build_features(prepared)


def build_samples(
    feature_data: dict[str, pd.DataFrame],
    spec: DatasetSpec | None = None,
    feature_groups: dict[str, list[str]] | None = None,
    fast: bool = True,
) -> tuple[list[Any], dict[str, list[str]]]:
    """Run the upstream ``SampleBuilder`` over our feature frames.

    ``fast=True`` (default) uses :class:`hybrid_swingnet.fast_builder.FastSampleBuilder`,
    a value-identical drop-in that avoids upstream's ~30 ms/sample row
    materialisation. Pass ``fast=False`` to run the vendor's own builder - used by
    the equivalence test.
    """
    namespace, reason = import_stockxpert_v3()
    if reason:
        raise RuntimeError(reason)

    spec = spec or DatasetSpec()
    groups = feature_groups or load_feature_groups()
    short = list(groups["short_features"])
    mid = list(groups["mid_features"])
    long = list(groups["long_features"])
    context = list(groups["context_features"])
    if spec.extra_columns:
        # Sentinel column first so it always lands in the window arrays.
        short = list(spec.extra_columns) + short
        mid = list(spec.extra_columns) + mid
        long = list(spec.extra_columns) + long

    builder_cls = namespace["SampleBuilder"]
    if fast:
        # Imported lazily: this module must stay importable without the vendor.
        from hybrid_swingnet.fast_builder import FastSampleBuilder

        builder_cls = FastSampleBuilder

    builder = builder_cls(
        window_short=spec.window_short,
        window_mid=spec.window_mid,
        window_long=spec.window_long,
        short_features=short,
        mid_features=mid,
        long_features=long,
        context_features=context,
        sentiment_features=SENTIMENT_FEATURES,
        horizons=list(spec.horizons),
    )
    symbols = list(feature_data.keys())
    symbol_map = {symbol: idx for idx, symbol in enumerate(symbols)}
    samples = builder.build_samples(feature_data, symbol_map)
    resolved = {
        "short_features": short,
        "mid_features": mid,
        "long_features": long,
        "context_features": context,
        "sentiment_features": list(SENTIMENT_FEATURES),
    }
    return samples, resolved


def build_dataset(spec: DatasetSpec | None = None, fast: bool = True) -> DatasetBundle:
    """End-to-end: app.db -> feature frames -> V3 ``Sample`` objects."""
    spec = spec or DatasetSpec()
    con = connect_readonly(spec.db_path)
    try:
        sector_map = load_sector_map(con)
        symbols = select_symbols(con, spec.max_symbols, spec.min_rows, spec.start, spec.end)
        price_data = load_price_frames(con, symbols, spec.start, spec.end)
    finally:
        con.close()

    if not price_data:
        raise RuntimeError("no price rows loaded from app.db for the requested universe")

    feature_data = build_feature_data(price_data, spec.horizons, sector_map)
    groups = load_feature_groups()

    if spec.extra_columns:
        # The sentinel is injected AFTER the builder, so its value is the row
        # position *within the frame the windows are cut from* (the builder has
        # already trimmed the warm-up rows). That is exactly what the leakage
        # test compares against, and it lets the test prove that no row after t
        # can appear in any input window.
        for frame in feature_data.values():
            for name in spec.extra_columns:
                frame[name] = np.arange(len(frame), dtype=float)

    samples, resolved = build_samples(feature_data, spec, groups, fast=fast)
    return DatasetBundle(
        samples=samples,
        price_data=price_data,
        feature_data=feature_data,
        horizons=list(spec.horizons),
        symbols=list(feature_data.keys()),
        **resolved,
    )


__all__ = [
    "CANONICAL_CONFIG",
    "DEFAULT_DB_PATH",
    "SENTIMENT_FEATURES",
    "DatasetBundle",
    "DatasetSpec",
    "add_market_context",
    "add_sentiment_placeholders",
    "add_static_stock_traits",
    "build_dataset",
    "build_feature_data",
    "build_samples",
    "connect_readonly",
    "load_feature_groups",
    "load_price_frames",
    "load_sector_map",
    "select_symbols",
]
