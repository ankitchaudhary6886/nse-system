"""
Deployment verification — single command to check system health.

Usage:
  python verify_deployment.py               # checks only
  python verify_deployment.py --scan        # run full daily pipeline first
  python verify_deployment.py --sweep       # run 2y/3y/4y walk-forward sweep
  python verify_deployment.py --scan --sweep
"""
import sys
import time
import datetime as dt
import os
import json
import db


def _check(ok, label, detail=""):
    mark = "✓" if ok else "✗"
    color = "\033[92m" if ok else "\033[91m"
    reset = "\033[0m"
    line = f"  {color}{mark}{reset}  {label:<40}"
    if detail:
        line += f"  {detail}"
    print(line)
    return ok


def _table_fresh(conn, table, col="date", max_days=5):
    try:
        r = conn.execute(
            f"SELECT MAX({col}) FROM {table}").fetchone()
        latest = r[0] if r else None
        if not latest:
            return False, "empty", 0
        d = dt.date.fromisoformat(str(latest)[:10])
        age = (dt.date.today() - d).days
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return age <= max_days, f"latest {latest} ({age}d), {n} rows", n
    except Exception as e:
        return False, f"err: {e}", 0


def run_checks():
    print("=" * 70)
    print("DEPLOYMENT VERIFICATION")
    print(f"Time: {dt.datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)
    print()

    conn = db.get_conn()
    fails = 0

    # ---- Data tables ----
    print("DATA TABLES")
    for table, col, days in [
        ("prices_daily", "date", 5),
        ("technicals_daily", "date", 5),
        ("universe_broad", "updated_at", 30),
        ("fundamentals", "uploaded_at", 30),
        ("swing_signals", "signal_date", 14),
        ("trend_candidates", "date", 5),
        ("value_radar", "date", 30),
        ("positional_picks", "date", 30),
        ("pwin_daily", "date", 14),
    ]:
        ok, detail, n = _table_fresh(conn, table, col, days)
        if not ok:
            fails += 1
        _check(ok, table, detail)

    # strategy_runs is event-based, just check non-empty
    try:
        n = conn.execute("SELECT COUNT(*) FROM strategy_runs").fetchone()[0]
        _check(n > 0, "strategy_runs", f"{n} runs logged")
        if n == 0:
            fails += 1
    except Exception as e:
        _check(False, "strategy_runs", f"err: {e}")
        fails += 1

    conn.close()
    print()

    # ---- Today's activity ----
    print("TODAY'S ACTIVITY")
    conn = db.get_conn()
    today = dt.date.today().isoformat()
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM swing_signals WHERE signal_date=?",
            (today,)).fetchone()[0]
        _check(True, "swing signals today", f"{n} signals")
    except Exception as e:
        _check(False, "swing signals today", str(e))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM trend_candidates WHERE date=?",
            (today,)).fetchone()[0]
        _check(True, "trend candidates today", f"{n} stocks")
    except Exception as e:
        _check(False, "trend candidates today", str(e))
    conn.close()
    print()

    # ---- Config ----
    print("CONFIG SANITY")
    try:
        from strategy_config import SETUP, BACKTEST, SIZING
        _check(True, "strategy_config loads",
               f"TARGET_R={BACKTEST['TARGET_R']}, "
               f"impulse={SETUP['IMPULSE_MIN_PCT']}-"
               f"{SETUP['IMPULSE_MAX_PCT']}, "
               f"max_alloc={SIZING['MAX_ALLOC']}")
    except Exception as e:
        _check(False, "strategy_config loads", str(e))
        fails += 1
    print()

    # ---- Alerts ----
    print("ALERTS")
    try:
        from alerts import _creds
        token, chat = _creds()
        _check(bool(token and chat), "Telegram credentials",
               "secret file or env")
        if not (token and chat):
            fails += 1
    except Exception as e:
        _check(False, "Telegram credentials", str(e))
        fails += 1
    print()

    # ---- API ----
    print("API")
    try:
        import requests
        r = requests.get("http://127.0.0.1:8000/api/health",
                         auth=("ankit", "ankitc21"), timeout=5)
        if r.status_code == 200:
            d = r.json()
            _check(True, "API /api/health",
                   f"{d.get('prices_rows', 0):,} price rows")
        else:
            _check(False, "API /api/health",
                   f"status {r.status_code}")
            fails += 1
    except Exception as e:
        _check(False, "API /api/health", str(e))
        fails += 1

    print()
    print("=" * 70)
    if fails == 0:
        print("\033[92m✓ ALL CHECKS PASSED\033[0m — ready for live monitoring")
    else:
        print(f"\033[91m{fails} checks failed\033[0m — see above")
    print("=" * 70)
    return fails


def run_scan():
    print("RUNNING FULL DAILY PIPELINE")
    print("-" * 70)
    try:
        import daily_update
        daily_update.run()
    except Exception as e:
        print(f"Pipeline failed: {e}")
    print("-" * 70)
    print()


def run_sweep():
    print("WALK-FORWARD SWEEP (2y / 3y / 4y)")
    print("-" * 70)
    import subprocess
    for years in [2, 3, 4]:
        print(f"\n--- {years}-year window ---")
        subprocess.run(
            ["python", "fast_wf.py", "--years", str(years)],
            check=False)
    print()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--scan" in args:
        run_scan()
    if "--sweep" in args:
        run_sweep()
    fails = run_checks()
    sys.exit(0 if fails == 0 else 1)