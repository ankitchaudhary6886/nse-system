"""Shared forward simulation for a triggered setup.

Extracted 2026-10-05 (batch B5) from two equivalent copies that had drifted in
return shape only:

  * `build_setup_pool._simulate`          -- counted hit_1r/2r/3r as 0/1
  * `research_cockpit._simulate_forward`  -- booleans + hit_4r + bars_to_*

The trading rules were already identical (3-bar trigger window, HOLD_BARS hold,
stop-first break, MFE/MAE in R units). This module keeps ONE rule set and returns
the superset; each caller adapts to the shape it needs, so no numeric behaviour
changes.

Rules (unchanged):
  * trigger fires when High >= trigger within bars (signal_i+1 .. signal_i+3)
  * no trigger                -> EXPIRED
  * hold up to HOLD_BARS bars from the trigger bar
  * Low <= stop at any bar    -> LOSS and the loop breaks (stop-first)
  * otherwise                 -> TIMEOUT
"""

HOLD_BARS = 30          # bars held after the trigger
TRIGGER_WINDOW = 3      # bars allowed for the trigger to fire


def simulate_forward(df, signal_i, trigger, stop, hold_bars=HOLD_BARS):
    """Return the superset result dict, or None when risk <= 0.

    MFE/MAE are in R units relative to (trigger - stop).
    """
    n = len(df)
    high = df["High"].values
    low = df["Low"].values
    risk = trigger - stop
    if risk <= 0:
        return None

    trig_bar = None
    for j in range(signal_i + 1, min(signal_i + 1 + TRIGGER_WINDOW, n)):
        if high[j] >= trigger:
            trig_bar = j
            break

    if trig_bar is None:
        return {
            "triggered": False, "outcome": "EXPIRED",
            "mfe_r": 0.0, "mae_r": 0.0,
            "hit_1r": False, "hit_2r": False, "hit_3r": False, "hit_4r": False,
            "bars_to_1r": None, "bars_to_2r": None,
            "bars_to_3r": None, "bars_to_4r": None,
        }

    end_bar = min(trig_bar + hold_bars, n)
    mfe = 0.0
    mae = 0.0
    hit_1r = hit_2r = hit_3r = hit_4r = False
    b_1r = b_2r = b_3r = b_4r = None
    outcome = "TIMEOUT"

    for k in range(trig_bar, end_bar):
        up_r = (high[k] - trigger) / risk
        dn_r = (low[k] - trigger) / risk
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
        if low[k] <= stop:
            outcome = "LOSS"
            break

    return {
        "triggered": True, "outcome": outcome,
        "mfe_r": round(float(mfe), 2), "mae_r": round(float(mae), 2),
        "hit_1r": hit_1r, "hit_2r": hit_2r,
        "hit_3r": hit_3r, "hit_4r": hit_4r,
        "bars_to_1r": b_1r, "bars_to_2r": b_2r,
        "bars_to_3r": b_3r, "bars_to_4r": b_4r,
    }
