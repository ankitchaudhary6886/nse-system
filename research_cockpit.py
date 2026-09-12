"""
Research Cockpit — historical behaviour of setups similar to today's.

For a given symbol:
  1. Walk its price history (step=5 bars), run SetupDetector on each slice
  2. For every historical setup, simulate forward 30 bars:
       - Did it trigger? (high >= entry within 3 bars)
       - MFE (max favorable excursion in R units)
       - MAE (max adverse excursion in R units)
       - Time to +1R / +2R / +3R / +4R (in bars from trigger)
       - Final outcome (WIN/LOSS/TIMEOUT/EXPIRED)
  3. Aggregate into hit-rate + distribution stats
  4. Compare with today's live setup (if any)

Output is descriptive only. No recommendations.

Usage:
  python research_cockpit.py SYMBOL          # analyze one symbol
  python research_cockpit.py SYMBOL --json   # JSON output
"""
import sys
import json
import datetime as dt
import numpy as np
import pandas as pd
import db
from setup import SetupDetector


HISTORY_DAYS = 5 * 365     # 5 years
STEP = 5                    # sampling step for historical scan
MIN_BARS = 280
HOLD_BARS = 30


def _simulate_forward(df, signal_i, trigger, stop):
    """From bar signal_i, look forward HOLD_BARS.
    Returns dict describing what happened.
    """
    n = len(df)
    h = df["High"].values
    l = df["Low"].values
    c = df["Close"].values

    risk = trigger - stop
    if risk <= 0:
        return None

    # trigger within 3 bars after signal
    trig_bar = None
    for j in range(signal_i + 1, min(signal_i + 4, n)):
        if h[j] >= trigger:
            trig_bar = j
            break
    if trig_bar is None:
        return {
            "triggered": False, "outcome": "EXPIRED",
            "mfe_r": 0.0, "mae_r": 0.0,
            "hit_1r": False, "hit_2r": False,
            "hit_3r": False, "hit_4r": False,
            "bars_to_1r": None, "bars_to_2r": None,
            "bars_to_3r": None, "bars_to_4r": None,
        }

    # forward window
    end_bar = min(trig_bar + HOLD_BARS, n)
    mfe = 0.0   # max favorable excursion in R units
    mae = 0.0   # max adverse excursion (negative)
    hit_1r = hit_2r = hit_3r = hit_4r = False
    b_1r = b_2r = b_3r = b_4r = None
    outcome = "TIMEOUT"

    for k in range(trig_bar, end_bar):
        # in R units relative to trigger
        up_r = (h[k] - trigger) / risk
        dn_r = (l[k] - trigger) / risk
        if up_r > mfe:
            mfe = up_r
        if dn_r < mae:
            mae = dn_r

        bars_since = k - trig_bar

        if not hit_1r and up_r >= 1.0:
            hit_1r = True
            b_1r = bars_since
        if not hit_2r and up_r >= 2.0:
            hit_2r = True
            b_2r = bars_since
        if not hit_3r and up_r >= 3.0:
            hit_3r = True
            b_3r = bars_since
        if not hit_4r and up_r >= 4.0:
            hit_4r = True
            b_4r = bars_since

        # stop-first grading (conservative)
        if l[k] <= stop:
            outcome = "LOSS"
            break

    if outcome != "LOSS" and not hit_1r:
        outcome = "TIMEOUT"

    return {
        "triggered": True,
        "outcome": outcome,
        "mfe_r": round(float(mfe), 2),
        "mae_r": round(float(mae), 2),
        "hit_1r": hit_1r, "hit_2r": hit_2r,
        "hit_3r": hit_3r, "hit_4r": hit_4r,
        "bars_to_1r": b_1r, "bars_to_2r": b_2r,
        "bars_to_3r": b_3r, "bars_to_4r": b_4r,
    }


def _load_df(conn, sym, years=5):
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume "
        "FROM prices_daily WHERE symbol=? ORDER BY date",
        (sym,)).fetchall()
    if not rows or len(rows) < MIN_BARS:
        return None
    df = pd.DataFrame(list(rows),
                      columns=["date", "Open", "High", "Low",
                               "Close", "Volume"]).set_index("date")
    df.index = pd.to_datetime(df.index)
    cutoff = df.index[-1] - pd.Timedelta(days=365 * years)
    return df[df.index >= cutoff]


def _historical_setups(df):
    """Walk the price history, return every triggered setup + forward stats."""
    setups = []
    for i in range(MIN_BARS, len(df) - 1, STEP):
        slice_df = df.iloc[:i + 1]
        st = SetupDetector.detect(slice_df, "X")
        if not st.triggered:
            continue
        sim = _simulate_forward(df, i, st.entry_price, st.stop_loss)
        if sim is None:
            continue
        setups.append({
            "signal_date": str(slice_df.index[-1].date()),
            "entry": st.entry_price,
            "stop": st.stop_loss,
            "target_3r": round(st.entry_price +
                               3.0 * (st.entry_price - st.stop_loss), 2),
            "risk_pct": round((st.entry_price - st.stop_loss) /
                              st.entry_price * 100, 2),
            "pullback_pct": round(st.pullback_depth * 100, 1),
            "pullback_days": int(st.pullback_days),
            "impulse_pct": round(st.impulse_pct * 100, 1),
            "ema_zone": st.ema_proximity,
            "shape_score": int(st.shape_score),
            **sim,
        })
    return setups


def _aggregate(setups):
    if not setups:
        return {
            "n_setups": 0, "n_triggered": 0,
            "p_trigger": None,
            "p_1r_given_trigger": None, "p_2r_given_trigger": None,
            "p_3r_given_trigger": None, "p_4r_given_trigger": None,
            "median_bars_to_1r": None, "median_bars_to_2r": None,
            "median_bars_to_3r": None, "median_bars_to_4r": None,
            "median_mfe_r": None, "median_mae_r": None,
            "p5_mfe_r": None, "p95_mfe_r": None,
            "p5_mae_r": None, "p95_mae_r": None,
            "outcome_mix": {},
        }

    n = len(setups)
    triggered = [s for s in setups if s["triggered"]]
    nt = len(triggered)

    def _hitrate(level):
        if not nt:
            return None
        key = f"hit_{level}r"
        return round(sum(1 for s in triggered if s[key]) / nt, 3)

    def _median_bars(level):
        key = f"bars_to_{level}r"
        arr = [s[key] for s in triggered
               if s[key] is not None]
        if not arr:
            return None
        return round(float(np.median(arr)), 1)

    mfes = [s["mfe_r"] for s in triggered]
    maes = [s["mae_r"] for s in triggered]
    outcome_mix = {}
    for s in setups:
        outcome_mix[s["outcome"]] = outcome_mix.get(s["outcome"], 0) + 1

    def _pct(arr, q):
        if not arr:
            return None
        return round(float(np.percentile(arr, q)), 2)

    return {
        "n_setups": n,
        "n_triggered": nt,
        "p_trigger": round(nt / n, 3) if n else None,
        "p_1r_given_trigger": _hitrate(1),
        "p_2r_given_trigger": _hitrate(2),
        "p_3r_given_trigger": _hitrate(3),
        "p_4r_given_trigger": _hitrate(4),
        "median_bars_to_1r": _median_bars(1),
        "median_bars_to_2r": _median_bars(2),
        "median_bars_to_3r": _median_bars(3),
        "median_bars_to_4r": _median_bars(4),
        "median_mfe_r": _pct(mfes, 50),
        "median_mae_r": _pct(maes, 50),
        "p5_mfe_r": _pct(mfes, 5),
        "p95_mfe_r": _pct(mfes, 95),
        "p5_mae_r": _pct(maes, 5),
        "p95_mae_r": _pct(maes, 95),
        "outcome_mix": outcome_mix,
    }


def analyze_symbol(sym):
    """Main entrypoint. Returns full research payload."""
    sym = sym.upper()
    conn = db.get_conn()

    df = _load_df(conn, sym, years=5)
    if df is None:
        conn.close()
        return {"symbol": sym, "error": "insufficient history"}

    # current setup
    current_setup = None
    st = SetupDetector.detect(df, sym)
    if st.triggered:
        current_setup = {
            "signal_date": st.signal_date,
            "entry": st.entry_price,
            "stop": st.stop_loss,
            "target_3r": round(st.entry_price +
                               3.0 * (st.entry_price - st.stop_loss), 2),
            "risk_pct": round((st.entry_price - st.stop_loss) /
                              st.entry_price * 100, 2),
            "pullback_pct": round(st.pullback_depth * 100, 1),
            "pullback_days": int(st.pullback_days),
            "impulse_pct": round(st.impulse_pct * 100, 1),
            "ema_zone": st.ema_proximity,
            "shape_score": int(st.shape_score),
        }

    # latest close + context
    latest_close = float(df["Close"].iloc[-1])
    high_52w = float(df["High"].tail(252).max())
    low_52w = float(df["Low"].tail(252).min())
    pct_from_52w_high = round((high_52w - latest_close) / high_52w * 100, 1)
    pct_from_52w_low = round((latest_close - low_52w) / low_52w * 100, 1)

    # historical setups
    setups = _historical_setups(df)
    agg = _aggregate(setups)

    # recent setups (last 5 for display)
    recent = sorted(setups, key=lambda s: s["signal_date"],
                    reverse=True)[:5]

    # sector
    sector = None
    row = conn.execute(
        "SELECT sector FROM stocks WHERE symbol=?", (sym,)).fetchone()
    if row:
        sector = row[0]

    conn.close()

    return {
        "symbol": sym,
        "sector": sector,
        "as_of": str(df.index[-1].date()),
        "latest_close": latest_close,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "pct_from_52w_high": pct_from_52w_high,
        "pct_from_52w_low": pct_from_52w_low,
        "current_setup": current_setup,
        "historical": agg,
        "recent_setups": recent,
        "history_bars_tested": len(df),
        "history_years": 5,
        "step": STEP,
    }


if __name__ == "__main__":
    sym = sys.argv[1].upper() if len(sys.argv) > 1 else "RELIANCE"
    result = analyze_symbol(sym)
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("=" * 70)
        print(f"RESEARCH COCKPIT — {result['symbol']}")
        print("=" * 70)
        if "error" in result:
            print(f"  ERROR: {result['error']}")
            sys.exit(1)
        print(f"  Sector: {result['sector']}")
        print(f"  As of: {result['as_of']}  close: {result['latest_close']}")
        print(f"  {result['pct_from_52w_high']}% from 52w high  |  "
              f"{result['pct_from_52w_low']}% from 52w low")
        print()
        if result["current_setup"]:
            cs = result["current_setup"]
            print("  CURRENT SETUP:")
            print(f"    signal {cs['signal_date']}  entry {cs['entry']}  "
                  f"stop {cs['stop']}  target3R {cs['target_3r']}")
            print(f"    risk {cs['risk_pct']}%  PB {cs['pullback_pct']}% "
                  f"({cs['pullback_days']}d)  impulse {cs['impulse_pct']}%  "
                  f"zone {cs['ema_zone']}  shape {cs['shape_score']}")
        else:
            print("  CURRENT SETUP: none triggered today")
        print()
        h = result["historical"]
        print(f"  HISTORICAL ({h['n_setups']} setups over "
              f"{result['history_years']}y, step {result['step']}):")
        print(f"    triggered: {h['n_triggered']} "
              f"(P={h['p_trigger']})")
        print(f"    P(+1R | triggered): {h['p_1r_given_trigger']}  "
              f"median bars {h['median_bars_to_1r']}")
        print(f"    P(+2R | triggered): {h['p_2r_given_trigger']}  "
              f"median bars {h['median_bars_to_2r']}")
        print(f"    P(+3R | triggered): {h['p_3r_given_trigger']}  "
              f"median bars {h['median_bars_to_3r']}")
        print(f"    P(+4R | triggered): {h['p_4r_given_trigger']}  "
              f"median bars {h['median_bars_to_4r']}")
        print(f"    MFE R: p5={h['p5_mfe_r']}  p50={h['median_mfe_r']}  "
              f"p95={h['p95_mfe_r']}")
        print(f"    MAE R: p5={h['p5_mae_r']}  p50={h['median_mae_r']}  "
              f"p95={h['p95_mae_r']}")
        print(f"    outcome mix: {h['outcome_mix']}")
        print()
        if result["recent_setups"]:
            print("  RECENT HISTORICAL SETUPS:")
            for s in result["recent_setups"]:
                print(f"    {s['signal_date']}  entry {s['entry']}  "
                      f"trig={s['triggered']}  "
                      f"MFE {s['mfe_r']}R  MAE {s['mae_r']}R  "
                      f"{s['outcome']}")