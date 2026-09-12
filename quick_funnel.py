"""
Fast funnel diagnostic — where do setups die?
100 symbols, 2 years, step=5. Should run in 60-90 seconds.
"""
import sys
import time
import numpy as np
import pandas as pd
import db
from universe_helper import band_universe
from scanner import Screener
from setup import SetupDetector

N_SYMBOLS = 100
YEARS = 2
STEP = 5


def main():
    t0 = time.time()
    conn = db.get_conn()
    syms = band_universe(conn, limit=N_SYMBOLS)
    print(f"[FUNNEL] {len(syms)} symbols, {YEARS}y, step={STEP}")

    totals = {
        "slices": 0,
        "screener_pass": 0,
        "setup_trigger": 0,
    }
    fails = {
        "history_short": 0,
        "screener": 0,
        "setup": 0,
    }
    setup_samples = []

    for si, sym in enumerate(syms, 1):
        rows = conn.execute(
            "SELECT date, close, high, low, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        if len(rows) < 280:
            fails["history_short"] += 1
            continue
        df = pd.DataFrame(list(rows),
                          columns=["date", "Close", "High", "Low",
                                   "Volume"]).set_index("date")
        df.index = pd.to_datetime(df.index)
        # last 2 years of bars
        cutoff = df.index[-1] - pd.Timedelta(days=365 * YEARS)
        df = df[df.index >= cutoff]

        for i in range(280, len(df), STEP):
            totals["slices"] += 1
            hist = df.iloc[:i]
            sc = Screener.evaluate(hist, sym)
            if not sc.passed:
                fails["screener"] += 1
                continue
            totals["screener_pass"] += 1
            st = SetupDetector.detect(hist, sym)
            if not st.triggered:
                fails["setup"] += 1
                continue
            totals["setup_trigger"] += 1
            if len(setup_samples) < 10:
                setup_samples.append(
                    (sym, str(hist.index[-1].date()),
                     st.impulse_pct, st.entry_price, st.stop_loss))

        if si % 25 == 0:
            print(f"  ...{si}/{len(syms)} symbols, "
                  f"{totals['setup_trigger']} setups so far")

    conn.close()
    dt = time.time() - t0

    print()
    print("=" * 60)
    print(f"FUNNEL RESULT ({dt:.1f}s)")
    print("=" * 60)
    print(f"total slices          : {totals['slices']}")
    print(f"screener passed       : {totals['screener_pass']} "
          f"({totals['screener_pass']/max(1,totals['slices'])*100:.1f}%)")
    print(f"setup triggered       : {totals['setup_trigger']} "
          f"({totals['setup_trigger']/max(1,totals['screener_pass'])*100:.1f}% of screener passes)")
    print()
    print("failures by stage:")
    print(f"  insufficient history: {fails['history_short']} symbols")
    print(f"  failed screener     : {fails['screener']} slices")
    print(f"  failed setup        : {fails['setup']} slices")
    print()
    if setup_samples:
        print("sample setups:")
        for s in setup_samples:
            print(f"  {s[0]:<12} {s[1]}  impulse {s[2]*100:.1f}%  "
                  f"entry {s[3]}  stop {s[4]}")
    else:
        print("NO setups at all in sample")


if __name__ == "__main__":
    main()