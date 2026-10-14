"""Walk-forward, leakage-audited evaluation of the LSTM forward-return model.

WHY THIS FILE EXISTS
--------------------
`lstm_model.py` builds the windows and the net.  This file is the honest
scoreboard: it trains the net the way the literature does (expanding-window
walk-forward) and reports ONLY out-of-sample numbers, always next to a naive
baseline, so a reader can tell skill from luck.

The three ways this evaluation refuses to cheat
-----------------------------------------------
1. PURGE + EMBARGO.  A sample's label is the forward return over `horizon`
   bars, so it is unknown at the decision date.  `walk_forward_folds()` only
   lets a training sample into fold k if its label bar was observed at least
   `embargo` bars before the first validation bar of fold k.  Every fold is
   re-checked with `check_fold_embargo()` before training, and the printed
   report shows the actual bar gap, so the reader can audit it.
2. NORMALISATION FROM THE PAST ONLY.  Feature means/stds and the label
   mean/std are fitted on that fold's training windows and then frozen
   (`Standardizer`, `train_model`).  Validation windows are only ever
   transformed with numbers that came from the past.
3. NO TUNING ON THE OOS FOLD.  Epochs are fixed by the CLI.  Optional early
   stopping uses an inner slice of the *training* period with the same purge
   rule, never the validation fold.

Baselines
---------
Always-up (predict every stock up) and trailing momentum (the `ret_21` feature,
i.e. "buy what went up last month") are scored on exactly the same OOS samples.
Accuracy is also shown against the majority-class rate, which is what a
coin-flip-with-the-base-rate strategy would score.

An LSTM that does not beat these is a normal, publishable-in-the-negative
result.  Report it as such.

USAGE (tiny, safe to run on the shared machine)
----------------------------------------------
    .\\env\\Scripts\\python.exe lstm_train.py --symbols 40 --seq-len 30 ^
        --horizon 5 --folds 3 --epochs 8 --threads 1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings

import numpy as np

import lstm_model as lm

DEFAULT_BASELINE_FEATURE = "ret_21"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def _ranks(x: np.ndarray) -> np.ndarray:
    """Average ranks, ties shared (scipy-free so this file has no extra deps)."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype=float)
    ranks[order] = np.arange(1, len(x) + 1, dtype=float)
    # Average ranks inside groups of equal values.
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 2:
        return float("nan")
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    if denom <= 0:
        return float("nan")
    return float((a * b).sum() / denom)


def spearman_ic(score: np.ndarray, target: np.ndarray) -> float:
    """Spearman rank correlation between a score and the realised return."""
    if len(score) < 3:
        return float("nan")
    return _pearson(_ranks(score), _ranks(target))


def rank_ic_by_date(score: np.ndarray, target: np.ndarray,
                    dates: np.ndarray, min_names: int = 5) -> dict:
    """Rank IC as practiced in equity research: one Spearman per date, averaged.

    WHY PER DATE: pooling all (stock, date) pairs lets a single strong market
    move dominate the correlation and mixes cross-sectional skill with market
    timing.  Averaging per-date rank IC measures the thing a long/short book
    actually uses: can the score order stocks against each other today?
    """
    score = np.asarray(score, dtype=float)
    target = np.asarray(target, dtype=float)
    dates = np.asarray(dates)
    ics, days = [], 0
    for d in np.unique(dates):
        m = dates == d
        if int(m.sum()) < min_names:
            continue
        ic = spearman_ic(score[m], target[m])
        if np.isfinite(ic):
            ics.append(ic)
            days += 1
    if not ics:
        return {"mean_ic": float("nan"), "ic_days": 0, "ic_t_stat": float("nan"),
                "ic_hit_rate": float("nan"), "pooled_spearman": (
                    spearman_ic(score, target) if len(score) >= 3 else float("nan"))}
    ics_arr = np.asarray(ics, dtype=float)
    std = float(ics_arr.std(ddof=1)) if ics_arr.size > 1 else float("nan")
    t_stat = (float(ics_arr.mean()) / (std / np.sqrt(ics_arr.size))
              if std and np.isfinite(std) and std > 0 else float("nan"))
    return {"mean_ic": float(ics_arr.mean()), "ic_days": days,
            "ic_t_stat": float(t_stat),
            "ic_hit_rate": float((ics_arr > 0).mean()),
            "pooled_spearman": spearman_ic(score, target)}


def auc_score(labels: np.ndarray, scores: np.ndarray) -> float:
    """ROC AUC with the Mann-Whitney formula; constant scores -> 0.5."""
    labels = np.asarray(labels).astype(float)
    scores = np.asarray(scores, dtype=float)
    pos, neg = labels == 1, labels == 0
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    if np.all(scores == scores[0]):
        return 0.5
    ranks = _ranks(scores)
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2.0) /
                 (n_pos * n_neg))


def direction_metrics(y_signed: np.ndarray, score: np.ndarray,
                      prob: np.ndarray | None = None,
                      threshold: float = 0.0) -> dict:
    """AUC / accuracy / base rate for the 'up' label.

    `y_signed` is the forward return already shifted by the fold's label
    threshold, so "up" is simply `y_signed > 0`.
    `prob` is P(up) used for the 0.5-threshold accuracy.  For a baseline that
    only has a score, `score > threshold` is used (threshold 0 for momentum:
    "buy what went up last month").
    """
    y_signed = np.asarray(y_signed, dtype=float)
    labels = (y_signed > 0).astype(int)
    base = float(labels.mean()) if labels.size else float("nan")
    if prob is None:
        pred = (np.asarray(score, dtype=float) > float(threshold)).astype(int)
        auc = auc_score(labels, np.asarray(score, dtype=float))
    else:
        pred = (np.asarray(prob, dtype=float) > 0.5).astype(int)
        auc = auc_score(labels, np.asarray(prob, dtype=float))
    acc = float((pred == labels).mean()) if labels.size else float("nan")
    return {"n": int(labels.size), "auc": float(auc), "accuracy": acc,
            "base_rate": base,
            "majority_rate": float(max(base, 1.0 - base)) if labels.size else float("nan"),
            "accuracy_minus_majority": acc - float(max(base, 1.0 - base))
            if labels.size else float("nan")}


# ---------------------------------------------------------------------------
# One walk-forward run
# ---------------------------------------------------------------------------
def run_walk_forward(ds: "lm.SequenceDataset", args) -> dict:
    """Train one model per fold, collect OOS predictions, return the report."""
    folds = lm.walk_forward_folds(ds, n_folds=args.folds, embargo=args.embargo,
                                 min_train_frac=args.min_train_frac)
    prob = np.full(len(ds), np.nan)
    ret = np.full(len(ds), np.nan)
    thr = np.full(len(ds), np.nan)
    fold_reports = []

    for fold in folds:
        audit = lm.check_fold_embargo(ds, fold, args.embargo)   # raises on leak
        t0 = time.time()
        # The direction threshold is learned from TRAIN labels only ('median'
        # mode) or fixed at zero.  It is passed into train_model so the labels
        # used for the BCE loss and the labels used for scoring are identical.
        threshold = (float(np.median(ds.y[fold.train_idx]))
                     if args.label == "median" else 0.0)
        scaler = lm.Standardizer.fit(ds.X[fold.train_idx])
        model, info = lm.train_model(
            ds, fold.train_idx, epochs=args.epochs, hidden=args.hidden,
            layers=args.layers, batch_size=args.batch_size, lr=args.lr,
            seed=args.seed + fold.index, threads=args.threads, scaler=scaler,
            dir_weight=args.dir_weight, inner_val_frac=args.inner_val_frac,
            embargo=args.embargo, patience=args.patience,
            dir_threshold=threshold, verbose=args.verbose)
        X_val = ds.X[fold.val_idx]
        out = lm.predict(model, X_val, scaler, info["y_mean"], info["y_std"])
        prob[fold.val_idx] = out["prob_up"]
        ret[fold.val_idx] = out["ret"]
        thr[fold.val_idx] = threshold
        y_val = ds.y[fold.val_idx]
        auc = auc_score((y_val > threshold).astype(int), out["prob_up"])
        ic = rank_ic_by_date(out["ret"], y_val, ds.decision_date[fold.val_idx])
        fold_reports.append({
            "fold": fold.index,
            "train_windows": int(fold.train_idx.size),
            "val_windows": int(fold.val_idx.size),
            "train_label_max_date": str(np.datetime_as_string(
                ds.dates[audit["train_label_max_bar"]], unit="D")),
            "val_starts": str(np.datetime_as_string(
                ds.dates[audit["val_decision_min_bar"]], unit="D")),
            "embargo_bars": audit["embargo_bars"],
            "gap_bars_after_last_train_label": audit["gap_bars_after_last_train_label"],
            "decision_gap_bars": audit["decision_gap_bars"],
            "train_seconds": round(time.time() - t0, 1),
            "auc": auc,
            "rank_ic": ic["mean_ic"],
            "parameters": info["n_parameters"],
            "label_threshold": threshold,
            "best_epoch": info["best_epoch"],
        })
        ic_txt = (f"{ic['mean_ic']:+.3f}" if np.isfinite(ic["mean_ic"]) else "n/a")
        print(f"  fold {fold.index}: train {fold.train_idx.size:>6} windows | "
              f"val {fold.val_idx.size:>5} from {fold_reports[-1]['val_starts']} | "
              f"gap after last train label "
              f"{audit['gap_bars_after_last_train_label']:>3} bars "
              f"(embargo {args.embargo}) | AUC {auc:.3f} | rankIC {ic_txt}")

    # OOS samples only: every sample with a stored prediction or a stored ret.
    mask = np.isfinite(prob) & np.isfinite(ret)
    y_all = ds.y[mask]
    summary = {
        "n_oos": int(mask.sum()),
        "y_oos": y_all,
        "y_signed": y_all - thr[mask],
        "prob": prob[mask],
        "ret": ret[mask],
        "dates": ds.decision_date[mask],
        "symbol": ds.symbol[mask],
        "X_last": ds.X[mask][:, -1, :],
        "folds": fold_reports,
    }
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Walk-forward LSTM forward-return evaluation (CPU-only).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--db", default=None, help="path to app.db (default <repo>/data/app.db)")
    p.add_argument("--symbols", type=int, default=40,
                   help="number of symbols with the most complete history")
    p.add_argument("--min-rows", type=int, default=lm.DEFAULT_MIN_ROWS)
    p.add_argument("--seq-len", type=int, default=lm.DEFAULT_SEQ_LEN,
                   help="lookback bars per window")
    p.add_argument("--horizon", type=int, default=lm.DEFAULT_HORIZON,
                   help="forward-return horizon in bars")
    p.add_argument("--folds", type=int, default=3)
    p.add_argument("--embargo", type=int, default=5,
                   help="extra purge bars between train labels and validation")
    p.add_argument("--min-train-frac", type=float, default=0.5,
                   help="share of the date axis kept for the first training window")
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--patience", type=int, default=None,
                   help="early-stop patience on the inner training split")
    p.add_argument("--inner-val-frac", type=float, default=0.15,
                   help="0 disables inner validation / early stopping")
    p.add_argument("--hidden", type=int, default=32)
    p.add_argument("--layers", type=int, default=1)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--dir-weight", type=float, default=1.0,
                   help="weight of the BCE direction loss next to the MSE loss")
    p.add_argument("--label", choices=("zero", "median"), default="zero",
                   help="'up' means return > 0 ('zero') or > train median ('median')")
    p.add_argument("--baseline-feature", default=DEFAULT_BASELINE_FEATURE)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--threads", type=int, default=1,
                   help="torch CPU threads; keep low on the shared machine")
    p.add_argument("--max-samples-per-symbol", type=int, default=None)
    p.add_argument("--save-model", default=None,
                   help="optional path for a bundle the app can load later")
    p.add_argument("--out", default=None, help="optional path for a JSON report")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    warnings.filterwarnings("ignore", category=RuntimeWarning)

    if not lm.TORCH_AVAILABLE:
        print(f"[lstm] torch unavailable ({lm.TORCH_IMPORT_ERROR}); nothing to do.")
        return 2
    lm.seed_everything(args.seed)
    lm.set_threads(args.threads)

    t0 = time.time()
    panel_raw = lm.load_price_panel(args.db, n_symbols=args.symbols,
                                    min_rows=args.min_rows)
    panel = lm.build_price_features(panel_raw)
    print(f"[lstm] {panel['symbol'].nunique()} symbols, {len(panel):,} daily rows, "
          f"{panel['date'].min().date()}..{panel['date'].max().date()}")
    ds = lm.build_sequences(panel, seq_len=args.seq_len, horizon=args.horizon,
                            max_samples_per_symbol=args.max_samples_per_symbol)
    print(f"[lstm] {len(ds):,} windows: seq_len={ds.seq_len}, horizon={ds.horizon}, "
          f"{ds.n_features} features -> {lm.count_parameters(lm.build_model(ds.n_features, args.hidden, args.layers))} params")
    print(f"[lstm] embargo={args.embargo} bars, folds={args.folds}, epochs={args.epochs}, "
          f"threads={args.threads}, seed={args.seed}")

    print("\nWALK-FORWARD (out-of-sample) FOLDS")
    res = run_walk_forward(ds, args)
    if res["n_oos"] == 0:
        print("[lstm] no out-of-sample predictions produced")
        return 1

    y = res["y_oos"]
    y_signed = res["y_signed"]     # forward return shifted by the fold threshold
    prob = res["prob"]
    ret = res["ret"]
    dates = res["dates"]

    model_m = direction_metrics(y_signed, ret, prob=prob)
    model_ic = rank_ic_by_date(ret, y, dates)

    # ---- baselines on exactly the same OOS samples -------------------------
    cols = list(ds.feature_columns)
    base_feat = args.baseline_feature
    if base_feat not in cols:
        base_feat = cols[min(2, len(cols) - 1)]
    mom_score = res["X_last"][:, cols.index(base_feat)].astype(float)
    mom_m = direction_metrics(y_signed, mom_score, threshold=0.0)
    mom_ic = rank_ic_by_date(mom_score, y, dates)

    # Always-up has no ranking at all: AUC is 0.5 by definition, and its
    # accuracy is exactly the base rate.  Computed analytically to avoid a
    # meaningless Spearman on a constant vector.
    up_rate = float((y_signed > 0).mean())
    always_up = {"n": int(len(y)), "auc": 0.5, "accuracy": up_rate,
                 "base_rate": up_rate,
                 "majority_rate": float(max(up_rate, 1 - up_rate)),
                 "accuracy_minus_majority": 0.0}
    always_up_ic = {"mean_ic": 0.0, "ic_days": 0, "ic_t_stat": float("nan"),
                    "ic_hit_rate": float("nan"), "pooled_spearman": float("nan")}

    print(f"\nOUT-OF-SAMPLE RESULTS  (n = {model_m['n']:,} windows, "
          f"{np.unique(dates).size:,} dates, "
          f"{res['folds'][0]['val_starts']}..{str(np.datetime_as_string(max(dates), unit='D'))})")
    hdr = f"{'strategy':<26}{'AUC':>8}{'acc':>8}{'maj.rate':>10}{'acc-maj':>9}{'rankIC':>9}{'IC t':>8}{'IC>0':>7}"
    print(hdr)
    print("-" * len(hdr))
    for name, m, ic in (("LSTM (OOS)", model_m, model_ic),
                        (f"baseline: {base_feat}", mom_m, mom_ic),
                        ("baseline: always-up", always_up, always_up_ic)):
        ic_mean = ic.get("mean_ic", float("nan"))
        ic_t = ic.get("ic_t_stat", float("nan"))
        ic_hit = ic.get("ic_hit_rate", float("nan"))
        print(f"{name:<26}{m['auc']:>8.3f}{m['accuracy']:>8.3f}"
              f"{m['majority_rate']:>10.3f}{m['accuracy_minus_majority']:>+9.3f}"
              f"{ic_mean:>+9.3f}"
              f"{(f'{ic_t:+.2f}' if np.isfinite(ic_t) else 'n/a'):>8}"
              f"{(f'{ic_hit:.2f}' if np.isfinite(ic_hit) else 'n/a'):>7}")
    print(f"\nmean forward return over the OOS window: {y.mean():+.4%}  "
          f"(base rate up: {up_rate:.1%})")

    verdict = []
    if np.isfinite(model_m["auc"]) and model_m["auc"] > mom_m["auc"] + 0.01:
        verdict.append("AUC beats trailing momentum")
    elif np.isfinite(model_m["auc"]) and model_m["auc"] < mom_m["auc"] - 0.01:
        verdict.append("AUC LOSES to trailing momentum")
    else:
        verdict.append("AUC is indistinguishable from trailing momentum")
    icm = model_ic.get("mean_ic", float("nan"))
    if np.isfinite(icm) and icm > 0.01 and (model_ic.get("ic_t_stat") or 0) > 2:
        verdict.append("rank IC is positive and > 2 sigma")
    elif np.isfinite(icm) and icm > 0:
        verdict.append("rank IC is positive but weak / not significant")
    else:
        verdict.append("rank IC is not positive")
    print("VERDICT: " + "; ".join(verdict))

    report = {
        "version": lm.VERSION,
        "config": {k: v for k, v in vars(args).items()},
        "n_windows_total": int(len(ds)),
        "n_oos": int(model_m["n"]),
        "folds": res["folds"],
        "lstm": model_m, "lstm_rank_ic": model_ic,
        "baseline_momentum": {"feature": base_feat, **mom_m, **mom_ic},
        "baseline_always_up": always_up,
        "mean_forward_return": float(y.mean()),
        "verdict": verdict,
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    if args.save_model:
        try:
            lm.save_bundle(args.save_model, *_final_bundle(panel, ds, args))
            print(f"[lstm] bundle written to {args.save_model}")
        except OSError as exc:
            print(f"[lstm] WARNING: could not write {args.save_model}: {exc}")
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(report, fh, indent=2, default=str)
            print(f"[lstm] report written to {args.out}")
        except OSError as exc:
            # The evaluation itself already succeeded and was printed above;
            # do not throw away the numbers because the file could not be saved.
            print(f"[lstm] WARNING: could not write report to {args.out}: {exc}")
    print(f"[lstm] done in {time.time() - t0:.1f}s")
    return 0


def _final_bundle(panel, ds, args):
    """Train one last model on all label-observed samples, for live scoring."""
    y = ds.y
    observed = np.isfinite(y)
    idx = np.where(observed)[0]
    scaler = lm.Standardizer.fit(ds.X[idx])
    model, info = lm.train_model(
        ds, idx, epochs=args.epochs, hidden=args.hidden, layers=args.layers,
        batch_size=args.batch_size, lr=args.lr, seed=args.seed, threads=args.threads,
        scaler=scaler, dir_weight=args.dir_weight, verbose=False)
    return model, info


if __name__ == "__main__":
    sys.exit(main())
