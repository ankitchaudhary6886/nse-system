"""
Fast walk-forward — Backtester path, ~80s.
Verdict is PF-driven, not win-rate-driven.

Usage:
  python fast_wf.py               -> current params (TARGET_R=3.0)
  python fast_wf.py 2.5           -> override Backtester.TARGET_R = 2.5
  python fast_wf.py 2.5 5         -> target 2.5, max_positions 5
"""
import sys
import time
import datetime as dt
import numpy as np
import db
from universe_helper import band_universe
from backtest import Backtester, BacktestResult


def _verdict(n, wr, pf):
    if n < 30:
        return f"INSUFFICIENT TRADES (n={n}, need >=30)"
    if pf >= 1.60 and wr >= 0.38:
        return "STRONG EDGE"
    if pf >= 1.40 and wr >= 0.33:
        return "SOLID EDGE"
    if pf >= 1.20 and wr >= 0.35:
        return "TRADEABLE EDGE — size carefully"
    if pf >= 1.00:
        return "MARGINAL — positive expectancy, small edge"
    return "NO EDGE — negative expectancy"


def main():
    t0 = time.time()
    target_r = float(sys.argv[1]) if len(sys.argv) > 1 else None
    max_pos = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if target_r is not None:
        Backtester.TARGET_R = target_r
        print(f"[WF] override Backtester.TARGET_R = {target_r}")

    conn = db.get_conn()
    syms = band_universe(conn, limit=400)
    conn.close()

    end = dt.date.today()
    start = end - dt.timedelta(days=365 * 3)

    result_obj = BacktestResult()
    if max_pos is not None:
        result_obj.max_positions = max_pos
    print(f"[WF] {len(syms)} symbols, {start.isoformat()} to "
          f"{end.isoformat()}")

    bt = Backtester(result=result_obj)
    result = bt.run([s + ".NS" for s in syms],
                    start.isoformat(), end.isoformat())

    trades = result.trades
    n = len(trades)
    dt_sec = time.time() - t0

    if n == 0:
        print(f"[WF] NO TRADES in {dt_sec:.1f}s")
        return

    wins = [t for t in trades if t.pnl_pct > 0]
    losses = [t for t in trades if t.pnl_pct <= 0]
    wr = len(wins) / n
    avg_w = float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0
    avg_l = float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0
    pf = (sum(t.pnl_pct for t in wins) /
          abs(sum(t.pnl_pct for t in losses))) if losses and \
        sum(t.pnl_pct for t in losses) else 999.0
    expectancy_r = wr * abs(avg_w / avg_l) - (1 - wr) if avg_l else 0.0

    print()
    print("=" * 60)
    print(f"WALK-FORWARD RESULT ({dt_sec:.1f}s)")
    print("=" * 60)
    print(f"trades            : {n}")
    print(f"wins / losses     : {len(wins)} / {len(losses)}")
    print(f"win rate          : {wr:.1%}")
    print(f"avg win           : {avg_w*100:+.2f}%")
    print(f"avg loss          : {avg_l*100:+.2f}%")
    print(f"R-multiple (avg)  : {abs(avg_w/avg_l):.2f}")
    print(f"expectancy / trade: {expectancy_r:+.3f} R")
    print(f"profit factor     : {pf:.2f}")
    print(f"total return      : {result.total_return*100:+.2f}%")
    print(f"max drawdown      : {result.max_drawdown*100:.2f}%")
    print(f"avg holding days  : {result.avg_holding_days:.1f}")
    print()
    print(f"VERDICT: {_verdict(n, wr, pf)}")


if __name__ == "__main__":
    main()