# HybridSwingNet (imports as `stockxpert`) — vendored, run, and measured

**Status: research measurement only. Do not wire this into the live terminal.**

Upstream: <https://github.com/Onkarj012/HybridSwingNet>
Pinned commit: **`901bcd223363a08eab371a8e4903d10201f88f55`**
("Initial HybridSwingNet V3 reproduction artifact", 2026-07-02)

---

## 1. Read this before you trust any number

The upstream authors' own README says their **pre-registered walk-forward
out-of-sample protocol (2018–2026)** returned:

> **−64.3 % return, Sharpe −0.79**

They state explicitly that this is **not a bug** — the in-sample backtest is
profitable and the out-of-sample result is not. That caveat travels with
everything in this folder. This integration exists to **measure the model on our
own data**, not to sell it.

---

## 2. What was vendored

`hybrid_swingnet/upstream/` is the upstream tree copied at the pinned commit.
Its `.git` directory was **not** copied, so our repository history is untouched
and nothing was committed.

```
hybrid_swingnet/upstream/     upstream source tree (src/, scripts/, configs/, tests/, docs/)
hybrid_swingnet/__init__.py   guarded import surface (never raises)
hybrid_swingnet/appdb_dataset.py   our data adapter: data/app.db -> V3 samples
hybrid_swingnet/fast_builder.py    value-identical fast window builder
hybrid_swingnet/oos.py             purged/embargoed walk-forward + measurement
hybrid_swingnet/run_oos.py         CLI entry point
hybrid_swingnet/setup_env.ps1      optional isolated-venv setup
hybrid_swingnet/results/           JSON result artifacts
test_hybrid_swingnet.py            standalone test (repo root)
```

Nothing else in the repository was modified. No production module, no
`terminal_api.py`, no `daily_update.py`, no `strategy_config.py`, no static UI.

---

## 3. Environment — how far it actually gets

**This was not a blocker.** The task brief warned that the pinned dependencies
might not install on Python 3.14. They do, and in fact our production venv
already had everything the model path needs, so **nothing was installed into
`.\env`** — it is used read-only as an interpreter.

Verified with our own interpreter (`env\Scripts\python.exe`, Python 3.14.7):

| Dependency | In `.\env`? | Needed for |
|---|---|---|
| numpy 2.5.2, pandas 3.0.5, scikit-learn, torch 2.13.0+cpu, PyYAML 6.0.3, scipy 1.18.0 | **yes** | the whole core V3 path |
| pyarrow, yfinance, transformers, pytz, rich, tqdm, joblib, requests, dotenv, fastapi | yes | upstream extras |
| matplotlib, seaborn, statsmodels | no | upstream **plot/figure and stats scripts only** |
| sentencepiece | no | upstream FinBERT sentiment path only |

We also checked that a fresh `pip install -r requirements.txt` on Python 3.14 is
viable: every requirement, including `sentencepiece`, publishes a `cp314` wheel
today (`sentencepiece-0.2.2-cp314-cp314-win_amd64.whl`). Upstream pins 3.13 in
`.python-version`, but 3.14 works.

### Two ways to run

**Path A — use the existing production interpreter (what we did, no installs):**

```powershell
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\python.exe test_hybrid_swingnet.py
.\env\Scripts\python.exe -m hybrid_swingnet.run_oos --max-symbols 20 --epochs 2
```

`hybrid_swingnet/__init__.py` puts `hybrid_swingnet\upstream\src` on `sys.path`
at call time. Reading an interpreter and adding a path is not a modification of
the production environment.

**Path B — an isolated venv (only if you want the full upstream toolchain):**

```powershell
powershell -ExecutionPolicy Bypass -File hybrid_swingnet\setup_env.ps1 -PathB
```

That creates `hybrid_swingnet\.venv` (via `uv`, preferring Python 3.13) and
pip-installs `upstream\requirements.txt` there. It downloads ~1 GB for torch.

---

## 4. How we feed it our own data

Upstream loads prices from **yfinance** and sentiment from **GDELT/FinBERT or a
CSV**. Neither is useful for an offline measurement on our data, so
`appdb_dataset.py` reads `data/app.db` (read-only SQLite) and hands frames to the
**unmodified upstream feature builder and window builder**:

1. `prices_daily` → per-symbol OHLCV frames (`DatetimeIndex` named `Date`).
2. Upstream `FeatureBuilder` computes all technical indicators and the
   multi-horizon Z-scored targets (`target_h1 … target_h10`).
3. Point-in-time market context (market return / 5-day / 21-day vol / 60-day
   trend / 5-day breadth) is computed from our own cross-section — we have ~1086
   symbols, so this is a genuine breadth measure.
4. Static V3 stock traits: sector one-hot bits from our `stocks.sector`, beta,
   liquidity rank and volatility percentile.
5. Upstream `SampleBuilder` produces the 7 / 21 / 60-day windows.

### Honest gaps in our input

* **Sentiment is all zeros.** We have no news feed, so the 9-column sentiment
  encoder input is neutral. Upstream's `SentimentEncoder` is a plain MLP, so it
  still runs — but it contributes nothing. **Our result is a 4-encoder result,
  not the authors' 5-encoder result.**
* **No yfinance macro block** (`^NSEI`, `^NSEBANK`, `INR=X`, `CL=F`, `^GSPC`).
  The model's own cross-sectional `market_*` features stand in for it.
* Our data window is **2021-08-17 → 2026-08-26**, not 2018–2026.
* `mcap_rank` / `liquidity_tier` both use the dollar-volume percentile, because
  `prices_daily` has no market cap.

---

## 5. Our out-of-sample protocol

Two reasons we **could not** run the authors' protocol:

1. **Their protocol is not reproducible from this commit.**
   `scripts/walkforward_v3.py` line 25 does
   `from backtest_historical import PROFILES, Prediction`, and
   **`backtest_historical.py` does not exist anywhere in the upstream
   repository**. The pre-registered 144-config grid, `simulate_portfolio` and the
   cost model it needs all live in modules that were not shipped. The −64.3 %
   figure cannot be re-derived from this artifact.
2. Their protocol needs 2018 data; ours starts 2021-08-17.

So we run **our own, simpler, fully documented** protocol:

* **Cross-sectional split with a purged temporal gap**, using upstream's own
  `cross_sectional_split` / `time_split` / `assert_no_leakage`. Held-out stocks
  never appear in training; a **10-day embargo** separates train → val → test.
* Train the **unmodified** V3 model with the **unmodified** `StockXpertV3Loss`
  and upstream's own V3 `Trainer` (CPU, `use_amp=False`).
* Report per-horizon direction accuracy **in-sample (train)** versus
  **out-of-sample (test)**, against an *always-up* baseline.
* Compile a **non-overlapping, equal-weight, long-only top-N cohort backtest** at
  one horizon, net of an India **delivery** round-trip cost derived from
  upstream's `INDIA_DELIVERY_COSTS` (slippage both ways, STT on the sell leg,
  stamp duty on the buy leg, exchange charges, GST on exchange).

Because the protocol is simpler than theirs, **only the sign** of the result is
comparable to −64.3 % / Sharpe −0.79.

### Run it

```powershell
cd C:\Users\Ankit\Desktop\nse_system

# fast smoke test (~2 min)
.\env\Scripts\python.exe -m hybrid_swingnet.run_oos --max-symbols 20 --epochs 2 --stride 4 --threads 2

# the measurement written up below
.\env\Scripts\python.exe -m hybrid_swingnet.run_oos --max-symbols 80 --epochs 6 --stride 3 --threads 2
```

---

## 6. Measured result on OUR data

Raw artifact: `results/oos_full.json`. Reproduce with:

```powershell
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\python.exe -m hybrid_swingnet.run_oos --max-symbols 80 --val-stocks 10 `
    --test-stocks 10 --blind-stocks 10 --epochs 6 --stride 6 --batch-size 384 `
    --threads 2 --horizon 5 --threshold 0.60 --top-n 3 --out hybrid_swingnet\results\oos_full.json
```

Run: **80 symbols, 91,635 samples, 496 s on CPU**, cross-sectional split with a
10-day embargo (train 31,868 / val 1,790 / test 2,960 / blind 4,820 samples;
50 train stocks, 10 test stocks). Sentiment channel is all zeros (section 4).

### 6.1 Direction accuracy — in-sample versus out-of-sample

| | Macro accuracy | vs always-up baseline |
|---|---|---|
| **In-sample (train)** | **0.5460** | — |
| **Out-of-sample (test)** | **0.5004** | 0.4923 → **+0.008** |

Per horizon, out-of-sample:

| Horizon | OOS accuracy | Always-up baseline | Edge |
|---|---|---|---|
| H1 | 0.5294 | 0.4970 | +0.032 |
| H3 | 0.4990 | 0.4993 | −0.000 |
| H5 | 0.4993 | 0.4909 | +0.008 |
| H7 | 0.4899 | 0.4899 | **0.000** |
| H10 | 0.4845 | 0.4845 | **0.000** |

**The out-of-sample result is a coin flip.** 50.0 % macro accuracy, and at H3, H7
and H10 the model is *exactly* at the always-up base rate. Accuracy collapses
from 54.6 % in-sample to 50.0 % out-of-sample. That is precisely the
in-sample-works / OOS-does-not signature the authors describe.

### 6.2 Cost-aware long-only backtest (H5, top-3, India delivery costs)

Round-trip cost from upstream's `INDIA_DELIVERY_COSTS` model: **0.2231 %**.

| Entry threshold | Total return | Sharpe (ann.) | Trades | Max drawdown | Win rate |
|---|---|---|---|---|---|
| p ≥ 0.50 (= "model thinks up") | **+4.58 %** | **+0.30** | 150 | −26.0 % | 0.493 |
| p ≥ 0.52 | **−10.27 %** | **−0.24** | 98 | — | — |
| p ≥ 0.55 | **no trades** | — | 0 | — | — |
| p ≥ 0.60 (the pre-registered-style threshold) | **no trades** | — | 0 | — | — |
| *equal-weight buy-and-hold, same 10 test stocks* | **+18.66 %** | — | — | — | — |

Two things to read carefully:

1. **Requiring conviction kills it.** At p ≥ 0.55 and p ≥ 0.60 — the authors'
   own paper-trading threshold is 0.60 — the model **never reaches the
   threshold**, so there is nothing to trade at all. At p ≥ 0.52 the strategy
   returns **−10.3 % with Sharpe −0.24**.
2. The **only positive cell is the least demanding one** (p ≥ 0.50, i.e. "the
   model leans up"), +4.58 % with Sharpe +0.30 and a −26 % drawdown. It
   **underperforms simply buying and holding the same 10 stocks (+18.66 %)** by
   about 14 points. It is not a signal; it is a coin flip paying costs.

Supplementary: Spearman correlation between the model's up-probability and the
realised Z-scored return was H1 0.216, H3 0.053, H5 0.114, H7 0.124, H10 0.044.
The H1 rank signal is visible but weak, and it does not survive transaction costs
or a conviction filter.

### 6.3 Does our OOS agree with the authors' −64.3 % / Sharpe −0.79?

**Partly — it agrees on substance, and on the sign of every result that requires
conviction.**

| | Authors (2018–2026, their protocol) | Ours (2021–2026, our protocol) |
|---|---|---|
| Headline OOS return | −64.3 % | +4.6 % (p≥0.50) / **−10.3 %** (p≥0.52) / no trades (p≥0.55) |
| Headline OOS Sharpe | −0.79 | +0.30 (p≥0.50) / **−0.24** (p≥0.52) |
| In-sample vs OOS | in-sample profitable, OOS not | **accuracy 54.6 % → 50.0 %** |
| OOS direction edge | none reported as tradeable | **+0.008 macro — a coin flip** |

* We **disagree** with their exact figure: we did not reproduce −64.3 %.
  We also cannot — their pre-registered protocol is unrunnable from this commit
  (defect 1), and our window, universe and strategy construction differ.
* We **agree** with the substance: **the model has no exploitable out-of-sample
  edge on our data, and it loses money (−10.3 %, Sharpe −0.24) as soon as any
  conviction filter is applied.** The only non-negative cell underperforms
  buy-and-hold by ~14 points.

**Do not use this as a trading signal.** It is a measurement of a model whose own
authors report a negative OOS result, reproduced honestly on our data.

---

## 7. Upstream defects found while integrating (none of them hidden)

These are reported because they change what the artifact can claim, and two of
them silently change model behaviour if you do not work around them.

| # | Where | What | Effect | Our handling |
|---|---|---|---|---|
| 1 | `scripts/walkforward_v3.py:25` | imports `backtest_historical`, which is **not in the repo** | the pre-registered OOS protocol **cannot run**; −64.3 % is not reproducible from this commit | documented; we wrote our own protocol |
| 2 | `configs/v3_nifty100.yaml`, `configs/v3_nifty100_swing_oos.yaml` | all five feature groups are **empty lists** | `X_short` becomes shape `(7, 0)` → `Conv1d` fails; those configs cannot train | we read the groups from the one config that declares them, `v3_nifty100_from_nifty500.yaml` |
| 3 | `src/stockxpert/dataset/scaling.py:343` | `ScalerGroup.transform` rebuilds each `Sample` with a positional constructor and **never copies `stock_traits`** | every *scaled* sample loses its traits; `stock_traits_from_sample` silently substitutes **zeros**, defeating V3's whole "static traits replace stock IDs" design | `oos.transform_preserving_traits` re-attaches them; regression-tested |
| 4 | `src/stockxpert/dataset/make_samples.py:143-151` | builds one sample at a time with ~10 full-row `df.iloc[t]` materialisations | measured **~30 ms/sample → ~35 s per symbol** (≈47 min for 80 symbols) before any training | `fast_builder.FastSampleBuilder`: vectorised, **211× faster**, proven **value-identical** on real data by the test |

---

## 8. The test

```powershell
cd C:\Users\Ankit\Desktop\nse_system
.\env\Scripts\python.exe test_hybrid_swingnet.py
```

It exits `0` on pass **or** graceful skip, and `1` only on a real assertion
failure. It skips, with a printed reason, when torch/pandas/scipy or
`data/app.db` are genuinely unavailable. It covers:

1. `import hybrid_swingnet` can never raise; `import_stockxpert()` degrades to a
   **reason string** instead of an exception (the house rule).
2. Vendored `stockxpert` + all V3 entry points import.
3. V3 forward pass shapes `(B, 5)` for direction / magnitude / confidence.
4. The V3 loss runs on CPU.
5. Our adapter's window shapes: `X_short(7,8) X_mid(21,12) X_long(60,8)
   X_context(24,) X_sentiment(9,) y(5,) y_levels(5,3)`, NaN-free.
6. **Leakage-free windows**, proved with a monotonic row-index sentinel: every
   input window starts and ends exactly at the documented offsets from `t`, and
   **nothing after `t` appears anywhere in any input window**.
7. **Target alignment**: `y[h]` reproduces the documented Z-scored forward-return
   contract to < 1e-4 absolute error.
8. Split integrity: disjoint stock sets and a real ≥ 10-day embargo between
   train/val/test.
9. `FastSampleBuilder` output is **identical** to upstream's builder across 9
   arrays plus `close_t`, `vol_ref`, `y_trend` and `stock_traits`.
10. `transform_preserving_traits` keeps `stock_traits` (regression test for
    defect 3).

---

## 9. Using it from application code (optional, and guarded)

Nothing in the live terminal imports this. If you ever want to, use the guard so
a missing dependency can never blank the UI:

```python
from hybrid_swingnet import import_stockxpert_v3

namespace, reason = import_stockxpert_v3()
if reason:
    # show the reason in the UI; do NOT raise
    ...
else:
    model = namespace["StockXpertModelV3"](...)
```

`hybrid_swingnet/__init__.py` imports no heavy dependency at module import time
and every entry point returns `(None, reason)` instead of raising. Verified with
`pandas`, `torch`, `numpy` and `scikit-learn` all blocked on `sys.meta_path`:

```
import hybrid_swingnet OK with pandas/torch/numpy/sklearn all missing
import_stockxpert_v3 -> ({}, 'import stockxpert.v3.models.stockxpert.StockXpertModelV3 failed: ImportError: ...')
```

Note the split of responsibility: the package root (`hybrid_swingnet`) is the
**only** import-safe surface. The submodules `appdb_dataset`, `fast_builder` and
`oos` do import `pandas` / `torch` / the vendor at module level, by design — they
are opt-in research code imported only by `run_oos.py` and the test, and **no
production module imports them**. Keep it that way: if application code ever
needs this model, go through `import_stockxpert_v3()`.

---

## 10. Verdict

HybridSwingNet V3 is a well-structured research artifact whose *own authors*
report a negative out-of-sample result. This integration runs its real model on
our real data and reports what came out — including the in-sample/out-of-sample
gap — **without promoting it to a signal**. See section 6 for the measured
numbers.
