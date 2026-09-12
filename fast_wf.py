"""
Fast walk-forward — Backtester path, ~60s.
Runs the current strategy over the last N years of band universe
and reports aggregate win rate / PF / drawdown. Tells us if the
widened thresholds actually produce a positive-expectancy system.
"""
import time
import datetime as dt
import numpy as np
import db
from universe_helper import band_universe
from backtest import Backtester


def main():
    t0 = time.time()
    conn = db.get_conn()
    syms = band_universe(conn, limit=400)
    conn.close()

    end = dt.date.today()
    start = end - dt.timedelta(days=365 * 3)
    print(f"[WF] {len(syms)} symbols, {start.isoformat()} to "
          f"{end.isoformat()}")

    bt = Backtester()
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

    print()
    print("=" * 60)
    print(f"WALK-FORWARD RESULT ({dt_sec:.1f}s)")
    print("=" * 60)
    print(f"trades            : {n}")
    print(f"wins / losses     : {len(wins)} / {len(losses)}")
    print(f"win rate          : {wr:.1%}")
    print(f"avg win           : {avg_w*100:+.2f}%")
    print(f"avg loss          : {avg_l*100:+.2f}%")
    print(f"profit factor     : {pf:.2f}")
    print(f"total return      : {result.total_return*100:+.2f}%")
    print(f"max drawdown      : {result.max_drawdown*100:.2f}%")
    print(f"avg holding days  : {result.avg_holding_days:.1f}")
    print()

    if n < 20:
        print("VERDICT: INSUFFICIENT TRADES (n<20)")
    elif wr >= 0.45 and pf >= 1.5:
        print("VERDICT: EDGE HOLDS")
    elif wr >= 0.40 and pf >= 1.2:
        print("VERDICT: WEAK EDGE — tradeable with sizing")
    else:
        print("VERDICT: NO EDGE at current params")


if __name__ == "__main__":
    main()