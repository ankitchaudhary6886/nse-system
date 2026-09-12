"""
Fast diagnostic — which of the 6 SetupDetector checks kills setups?
Same 100-symbol 2-year sample as quick_funnel. Runs in ~10s.
"""
import time
import numpy as np
import pandas as pd
import db
from universe_helper import band_universe
from scanner import Screener

N = 100
STEP = 5
YEARS = 2


def check_slice(df):
    c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    v = df["Volume"].values.astype(float)
    n = len(c)

    ema10 = pd.Series(c).ewm(span=10, adjust=False).mean().values
    ema20 = pd.Series(c).ewm(span=20, adjust=False).mean().values
    vol_sma20 = pd.Series(v).rolling(20).mean().values

    trs = []
    for i in range(1, n):
        trs.append(max(h[i] - l[i],
                       abs(h[i] - c[i - 1]),
                       abs(l[i] - c[i - 1])))
    atr14 = float(np.mean(trs[-14:])) if len(trs) >= 14 else None

    # 1. impulse 25-50%
    win_end = n - 25
    win_start = win_end - 90
    if win_start < 0:
        return "1_window_short"
    seg_h = h[win_start:win_end]
    sh_local = int(np.argmax(seg_h))
    swing_high = float(seg_h[sh_local])
    swing_high_idx = win_start + sh_local
    low_start = max(0, swing_high_idx - 40)
    swing_low = float(np.min(l[low_start:swing_high_idx + 1]))
    if swing_low <= 0:
        return "1_low_zero"
    impulse = (swing_high - swing_low) / swing_low
    if impulse < 0.25:
        return "1a_impulse_below_25"
    if impulse > 0.50:
        return "1b_impulse_above_50"
    ic = c[swing_high_idx:win_end + 1]
    ie = ema10[swing_high_idx:win_end + 1]
    if int(np.sum(ic < ie)) > max(2, int(0.25 * len(ic))):
        return "1c_ema10_breaks"

    # 2. pullback depth
    pb_window = h[win_end:]
    recent_high = float(np.max(pb_window))
    current_low = float(l[-1])
    pb_depth = (recent_high - current_low) / recent_high
    if pb_depth < 0.12:
        return "2a_pb_shallow"
    if pb_depth > 0.20:
        return "2b_pb_deep"

    # 3. pullback days
    pb_days = len(pb_window) - 1 - int(np.argmax(pb_window))
    if pb_days < 6:
        return "3a_days_fast"
    if pb_days > 15:
        return "3b_days_slow"

    # 3b. no crash
    for i in range(-3, 0):
        base = h[i - 2]
        if base and (base - l[i]) / base >= 0.15:
            return "3c_crash"

    # 4. ema zone
    near10 = abs(current_low - ema10[-1]) / ema10[-1] <= 0.03
    near20 = abs(current_low - ema20[-1]) / ema20[-1] <= 0.03
    in_zone = (current_low <= ema10[-1] * 1.02 and
               current_low >= ema20[-1] * 0.98)
    if not (near10 or near20 or in_zone):
        return "4_ema_zone"

    # 5. volume dry-up
    vn = vol_sma20[-1]
    avg3 = float(np.mean(v[-3:]))
    if np.isnan(vn) or not (avg3 < 0.8 * vn or v[-1] < 0.7 * vn):
        return "5_vol_not_dry"

    # 6. mother bar
    inside_last = bool(h[-1] < h[-2] and l[-1] > l[-2])
    tight = 0
    i = -1
    while i >= -4:
        ins = h[i] < h[i - 1] and l[i] > l[i - 1]
        narrow = atr14 is not None and (h[i] - l[i]) <= 0.9 * atr14
        if not (ins or narrow):
            break
        tight += 1
        i -= 1
    if not (inside_last or tight >= 2):
        return "6_mother_bar"

    # 7. risk cap
    entry = float(h[-2] if inside_last else h[i])
    stop = float(l[-1])
    if stop >= entry:
        return "7_stop_ge_entry"
    risk = (entry - stop) / entry
    if risk > 0.05:
        return "7_risk_above_5pct"

    return "PASSED"


def main():
    t0 = time.time()
    conn = db.get_conn()
    syms = band_universe(conn, limit=N)

    counts = {}
    screener_pass = 0
    total_slices = 0

    for sym in syms:
        rows = conn.execute(
            "SELECT date, close, high, low, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        if len(rows) < 280:
            continue
        df = pd.DataFrame(list(rows),
                          columns=["date", "Close", "High", "Low",
                                   "Volume"]).set_index("date")
        df.index = pd.to_datetime(df.index)
        cutoff = df.index[-1] - pd.Timedelta(days=365 * YEARS)
        df = df[df.index >= cutoff]

        for i in range(280, len(df), STEP):
            total_slices += 1
            hist = df.iloc[:i]
            if not Screener.evaluate(hist, sym).passed:
                counts["0_screener_fail"] = \
                    counts.get("0_screener_fail", 0) + 1
                continue
            screener_pass += 1
            result = check_slice(hist)
            counts[result] = counts.get(result, 0) + 1

    conn.close()
    dt = time.time() - t0

    print(f"[DIAG] {len(syms)} symbols, {total_slices} slices, "
          f"{dt:.1f}s")
    print(f"[DIAG] passed screener: {screener_pass} "
          f"({screener_pass / max(1, total_slices) * 100:.1f}%)")
    print()
    print("setup-stage failures (sorted by count):")
    ranked = sorted(counts.items(), key=lambda x: -x[1])
    for k, v in ranked:
        pct = v / max(1, screener_pass) * 100
        print(f"  {v:>5}  ({pct:>5.1f}%)  {k}")


if __name__ == "__main__":
    main()