#!/usr/bin/env python
"""CLI: run HybridSwingNet V3 out-of-sample measurement on our own ``app.db``.

Examples
--------
Small, fast smoke run (~2 minutes)::

    .\\env\\Scripts\\python.exe -m hybrid_swingnet.run_oos --max-symbols 20 --epochs 2

The real measurement::

    .\\env\\Scripts\\python.exe -m hybrid_swingnet.run_oos --max-symbols 80 --epochs 6 --stride 3

Writes JSON (and prints a plain-English summary) under
``hybrid_swingnet/results/``. Read ``hybrid_swingnet/README_INTEGRATION.md``
first: the upstream authors' own out-of-sample result is NEGATIVE.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybrid_swingnet.appdb_dataset import DEFAULT_DB_PATH, DatasetSpec  # noqa: E402
from hybrid_swingnet.oos import (  # noqa: E402
    AUTHORS_OOS_RETURN_PCT,
    AUTHORS_OOS_SHARPE,
    BacktestSpec,
    SplitSpec,
    TrainSpec,
    result_to_json,
    run_oos,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="path to app.db (opened read-only)")
    parser.add_argument("--max-symbols", type=int, default=80, help="size of the priced universe")
    parser.add_argument("--min-rows", type=int, default=700, help="minimum history rows per symbol")
    parser.add_argument("--start", default=None, help="ISO start date filter")
    parser.add_argument("--end", default=None, help="ISO end date filter")
    parser.add_argument("--train-end", default="2024-06-30")
    parser.add_argument("--val-end", default="2025-03-31")
    parser.add_argument("--test-end", default="2026-06-30")
    parser.add_argument("--val-stocks", type=int, default=10)
    parser.add_argument("--test-stocks", type=int, default=10)
    parser.add_argument("--blind-stocks", type=int, default=10)
    parser.add_argument("--embargo-days", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--stride", type=int, default=3, help="keep every Nth training sample")
    parser.add_argument("--threads", type=int, default=2, help="torch CPU threads (be polite on a shared box)")
    parser.add_argument("--horizon", type=int, default=5, help="backtest horizon")
    parser.add_argument("--threshold", type=float, default=0.60, help="p_up entry threshold")
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--no-costs", action="store_true", help="zero out transaction costs")
    parser.add_argument("--out", default=None, help="JSON output path")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def summarise(payload: dict) -> str:
    backtest = payload.get("backtest", {}) or {}
    bt = backtest.get("primary", {}) or {}
    acc = payload.get("accuracy", {}) or {}
    train_acc = (acc.get("train_in_sample", {}) or {}).get("macro_accuracy")
    test_acc = (acc.get("test_out_of_sample", {}) or {}).get("macro_accuracy")
    base = (acc.get("test_out_of_sample", {}) or {}).get("macro_always_up_baseline")
    bench = (payload.get("benchmark", {}) or {}).get("total_return_pct")
    lines = [
        "",
        "=" * 78,
        "HybridSwingNet V3 - OUR out-of-sample measurement",
        "=" * 78,
        f"vendored upstream commit : {payload.get('upstream_commit')}",
        f"universe / samples       : {payload.get('dataset', {}).get('symbols_used')} symbols, "
        f"{payload.get('dataset', {}).get('samples')} samples",
        f"splits                   : {payload.get('splits', {}).get('counts')}",
        f"runtime                  : {payload.get('runtime_seconds')} s (CPU only)",
        "",
        f"macro direction accuracy IN-SAMPLE (train) : {train_acc}",
        f"macro direction accuracy OOS (test)        : {test_acc}   (always-up baseline {base})",
        "",
        f"backtest horizon H{bt.get('horizon')}  threshold {bt.get('threshold')}  top_n {bt.get('top_n')}",
        f"  round-trip cost          : {bt.get('round_trip_cost_pct')} %",
        f"  trades / cohorts         : {bt.get('n_trades')} / {bt.get('n_cohorts')}",
        f"  OUR OOS total return     : {bt.get('total_return_pct')} %",
        f"  OUR OOS Sharpe (ann.)    : {bt.get('sharpe_annualised')}",
        f"  max drawdown             : {bt.get('max_drawdown_pct')} %",
        f"  win rate                 : {bt.get('win_rate')}",
        f"equal-weight buy&hold test universe : {bench} %",
    ]
    if bt.get("note"):
        lines.append(f"  NOTE: {bt['note']}")
    by_threshold = backtest.get("by_threshold", {}) or {}
    if by_threshold:
        lines.append("")
        lines.append("  threshold sensitivity (total return %, Sharpe, trades):")
        for key, value in by_threshold.items():
            lines.append(
                f"    {key:<22} {value.get('total_return_pct')} %   Sharpe {value.get('sharpe_annualised')}"
                f"   trades {value.get('n_trades')}"
            )
    lines += [
        "",
        f"AUTHORS' own pre-registered OOS     : {AUTHORS_OOS_RETURN_PCT} % / Sharpe {AUTHORS_OOS_SHARPE}",
        "NOTE: our protocol is simpler and our data window is 2021-2026, not 2018-2026.",
        "Only the SIGN of the result is comparable. Treat this as research, not a signal.",
        "=" * 78,
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_spec = DatasetSpec(
        db_path=Path(args.db),
        max_symbols=args.max_symbols,
        min_rows=args.min_rows,
        start=args.start,
        end=args.end,
    )
    result = run_oos(
        dataset_spec=dataset_spec,
        split_spec=SplitSpec(
            train_end=args.train_end,
            val_end=args.val_end,
            test_end=args.test_end,
            val_stocks=args.val_stocks,
            test_stocks=args.test_stocks,
            blind_stocks=args.blind_stocks,
            embargo_days=args.embargo_days,
        ),
        train_spec=TrainSpec(
            epochs=args.epochs,
            batch_size=args.batch_size,
            train_stride=args.stride,
            threads=args.threads,
        ),
        backtest_spec=BacktestSpec(
            horizon=args.horizon,
            threshold=args.threshold,
            top_n=args.top_n,
            use_costs=not args.no_costs,
        ),
        verbose=not args.quiet,
    )
    stamp = f"symbols{args.max_symbols}_epochs{args.epochs}_stride{args.stride}"
    out_path = Path(args.out) if args.out else RESULTS_DIR / f"oos_{stamp}.json"
    result_to_json(result, out_path)
    payload = asdict(result)
    print(summarise(payload))
    print(f"\nJSON written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
