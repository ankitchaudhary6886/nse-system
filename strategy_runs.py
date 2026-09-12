"""
Strategy run ledger — records every fast_wf sweep for comparison.
Every walk-forward run gets logged so future parameter changes can be
compared against a history instead of re-run from scratch.

Table: strategy_runs
"""
import datetime as dt
import json
import db


def _ensure(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS strategy_runs(
        run_at TEXT PRIMARY KEY,
        target_r REAL,
        years REAL,
        symbols INTEGER,
        max_pos INTEGER,
        trades INTEGER,
        wins INTEGER,
        losses INTEGER,
        win_rate REAL,
        avg_win REAL,
        avg_loss REAL,
        expectancy_r REAL,
        pf REAL,
        total_return REAL,
        max_dd REAL,
        holding_days REAL,
        verdict TEXT,
        payload TEXT
    )
    """)


def log(result: dict):
    """result = dict with keys: target_r, years, symbols, max_pos,
    trades, wins, losses, win_rate, avg_win, avg_loss, expectancy_r,
    pf, total_return, max_dd, holding_days, verdict."""
    conn = db.get_conn()
    _ensure(conn)
    conn.execute("""
    INSERT OR REPLACE INTO strategy_runs VALUES
    (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        dt.datetime.now().isoformat(timespec="seconds"),
        result.get("target_r"),
        result.get("years"),
        result.get("symbols"),
        result.get("max_pos"),
        result.get("trades"),
        result.get("wins"),
        result.get("losses"),
        result.get("win_rate"),
        result.get("avg_win"),
        result.get("avg_loss"),
        result.get("expectancy_r"),
        result.get("pf"),
        result.get("total_return"),
        result.get("max_dd"),
        result.get("holding_days"),
        result.get("verdict"),
        json.dumps(result, default=str),
    ))
    conn.commit()
    conn.close()


def history(n=20):
    conn = db.get_conn()
    _ensure(conn)
    rows = conn.execute("""
    SELECT run_at, target_r, years, symbols, trades,
           win_rate, pf, expectancy_r, total_return, max_dd, verdict
    FROM strategy_runs
    ORDER BY run_at DESC LIMIT ?
    """, (n,)).fetchall()
    conn.close()
    cols = ["run_at", "target_r", "years", "symbols", "trades",
            "win_rate", "pf", "expectancy_r", "total_return",
            "max_dd", "verdict"]
    return [dict(zip(cols, r)) for r in rows]


def summary_by_target():
    """Group results by target_r — useful for target selection."""
    conn = db.get_conn()
    _ensure(conn)
    rows = conn.execute("""
    SELECT target_r,
           COUNT(*)            AS runs,
           AVG(pf)             AS avg_pf,
           AVG(win_rate)       AS avg_wr,
           AVG(expectancy_r)   AS avg_exp,
           AVG(max_dd)         AS avg_dd,
           SUM(trades)         AS total_trades
    FROM strategy_runs
    GROUP BY target_r
    ORDER BY target_r
    """).fetchall()
    conn.close()
    cols = ["target_r", "runs", "avg_pf", "avg_wr",
            "avg_exp", "avg_dd", "total_trades"]
    return [dict(zip(cols, r)) for r in rows]


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "history"
    if cmd == "history":
        print("RECENT RUNS")
        print("-" * 100)
        for h in history():
            print(f"{h['run_at']:<20} "
                  f"R={h['target_r']:<4} "
                  f"y={h['years']:<3} "
                  f"n={h['trades']:<4} "
                  f"wr={h['win_rate']:.1%} "
                  f"pf={h['pf']:.2f} "
                  f"exp={h['expectancy_r']:+.3f}R "
                  f"ret={h['total_return']*100:+.1f}% "
                  f"dd={h['max_dd']*100:.1f}% "
                  f"| {h['verdict']}")
    elif cmd == "summary":
        print("SUMMARY BY TARGET_R")
        print("-" * 100)
        for s in summary_by_target():
            print(f"R={s['target_r']:<4} "
                  f"runs={s['runs']:<3} "
                  f"trades={s['total_trades']:<5} "
                  f"avg_pf={s['avg_pf']:.2f} "
                  f"avg_wr={s['avg_wr']:.1%} "
                  f"avg_exp={s['avg_exp']:+.3f}R "
                  f"avg_dd={s['avg_dd']*100:.1f}%")