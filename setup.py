"""
Hiren Gabani Master Pullback — OFFICIAL v3.3.
6-point checklist + mother-candle trigger + PDL stop + 5% rule.

v3.1 — impulse indexing bug fix.
v3.2 — widened impulse 25-50% -> 18-75%, PB 12-20% -> 8-25%.
v3.3 — EMA10-break tolerance 0.35 -> 0.45; PB floor 8% -> 6%;
       PB days cap 15 -> 20. Diag showed 1c killed 50% of candidates.
"""
from dataclasses import dataclass, field
from typing import List
import numpy as np
import pandas as pd


@dataclass
class Setup:
    symbol: str
    triggered: bool
    signal_date: str
    entry_price: float
    stop_loss: float
    target_price: float
    risk_reward: float
    pullback_depth: float
    pullback_days: int
    mother_bar_high: float
    mother_bar_low: float
    impulse_pct: float
    ema_proximity: str
    shape_score: int = 0
    reasons: List[str] = field(default_factory=list)


class SetupDetector:
    IMPULSE_LOOKBACK = 90
    IMPULSE_MIN_PCT = 0.18
    IMPULSE_MAX_PCT = 0.75
    EMA10_BREAK_TOL = 0.45        # v3.3 was 0.35
    PB_LOOKBACK = 25
    PB_MIN_PCT = 0.06             # v3.3 was 0.08
    PB_MAX_PCT = 0.25
    PB_MIN_DAYS = 6
    PB_MAX_DAYS = 20              # v3.3 was 15
    CRASH_WINDOW = 3
    CRASH_MAX_PCT = 0.15
    EMA10 = 10
    EMA20 = 20
    EMA_TOUCH_MULT = 0.03
    VOL_SMA_DAYS = 20
    TIGHT_ATR_MULT = 0.9
    TIGHT_MAX_RUN_BACK = 4
    TIGHT_MIN = 2
    MAX_STOP_PCT = 0.05
    TARGET_R_MULTIPLE = 2.0
    MAX_SHIFT = 2

    @classmethod
    def detect(cls, df: pd.DataFrame, symbol: str) -> Setup:
        for shift in range(cls.MAX_SHIFT + 1):
            n = len(df) - shift
            if n < cls.IMPULSE_LOOKBACK + cls.PB_LOOKBACK + 10:
                continue
            res = cls._eval(df.iloc[:n], symbol)
            if res is not None:
                return res
        return Setup(symbol, False, "", 0, 0, 0, 0, 0, 0, 0, 0, "", 0,
                     ["no completed pattern in last 3 sessions"])

    @classmethod
    def _eval(cls, df: pd.DataFrame, symbol: str):
        c = df["Close"].values.astype(float)
        h = df["High"].values.astype(float)
        l = df["Low"].values.astype(float)
        v = df["Volume"].values.astype(float)
        n = len(c)

        ema10 = pd.Series(c).ewm(span=cls.EMA10, adjust=False).mean().values
        ema20 = pd.Series(c).ewm(span=cls.EMA20, adjust=False).mean().values
        vol_sma20 = pd.Series(v).rolling(cls.VOL_SMA_DAYS).mean().values

        trs = []
        for i in range(1, n):
            trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]),
                           abs(l[i] - c[i - 1])))
        atr14 = float(np.mean(trs[-14:])) if len(trs) >= 14 else None

        win_end = n - cls.PB_LOOKBACK
        win_start = win_end - cls.IMPULSE_LOOKBACK
        if win_start < 0:
            return None
        seg_h = h[win_start:win_end]
        sh_local = int(np.argmax(seg_h))
        swing_high = float(seg_h[sh_local])
        swing_high_idx = win_start + sh_local
        low_start = max(0, swing_high_idx - 40)
        swing_low_before = float(np.min(l[low_start:swing_high_idx + 1]))
        if swing_low_before <= 0:
            return None
        impulse_pct = (swing_high - swing_low_before) / swing_low_before
        if not (cls.IMPULSE_MIN_PCT <= impulse_pct <= cls.IMPULSE_MAX_PCT):
            return None
        ic = c[swing_high_idx:win_end + 1]
        ie = ema10[swing_high_idx:win_end + 1]
        if int(np.sum(ic < ie)) > max(2, int(cls.EMA10_BREAK_TOL * len(ic))):
            return None

        pb_window = h[win_end:]
        recent_high = float(np.max(pb_window))
        current_low = float(l[-1])
        pb_depth = (recent_high - current_low) / recent_high
        if not (cls.PB_MIN_PCT <= pb_depth <= cls.PB_MAX_PCT):
            return None

        pb_days = len(pb_window) - 1 - int(np.argmax(pb_window))
        if not (cls.PB_MIN_DAYS <= pb_days <= cls.PB_MAX_DAYS):
            return None
        for i in range(-cls.CRASH_WINDOW, 0):
            base = h[i - cls.CRASH_WINDOW + 1]
            if base and (base - l[i]) / base >= cls.CRASH_MAX_PCT:
                return None

        pseg = c[swing_high_idx:]
        shape = 0
        if len(pseg) > 4:
            rts = np.diff(pseg) / np.maximum(pseg[:-1], 1e-9)
            max_drop = float(np.min(rts))
            vol = float(np.std(rts))
            s_drop = max(0.0, min(1.0, 1 - abs(max_drop) / 0.08))
            s_vol = max(0.0, min(1.0, 1 - vol / 0.03))
            shape = int(100 * (0.5 * s_drop + 0.5 * s_vol))

        near10 = abs(current_low - ema10[-1]) / ema10[-1] <= cls.EMA_TOUCH_MULT
        near20 = abs(current_low - ema20[-1]) / ema20[-1] <= cls.EMA_TOUCH_MULT
        in_zone = (current_low <= ema10[-1] * 1.02 and
                   current_low >= ema20[-1] * 0.98)
        if not (near10 or near20 or in_zone):
            return None
        ema_proximity = "EMA10" if near10 else ("EMA20" if near20
                                                else "ZONE")

        vol_now = vol_sma20[-1]
        avg3 = float(np.mean(v[-3:]))
        if np.isnan(vol_now) or not (avg3 < 0.8 * vol_now or
                                     v[-1] < 0.7 * vol_now):
            return None

        def is_tight(i):
            inside = h[i] < h[i - 1] and l[i] > l[i - 1]
            narrow = (atr14 is not None and
                      (h[i] - l[i]) <= cls.TIGHT_ATR_MULT * atr14)
            return inside or narrow

        inside_last = bool(h[-1] < h[-2] and l[-1] > l[-2])
        tight_run = 0
        i = -1
        while i >= -cls.TIGHT_MAX_RUN_BACK and is_tight(i):
            tight_run += 1
            i -= 1
        if inside_last:
            mother_idx = -2
        elif tight_run >= cls.TIGHT_MIN:
            mother_idx = i
        else:
            return None
        mother_bar_high = float(h[mother_idx])
        mother_bar_low = float(l[mother_idx])

        entry_price = mother_bar_high
        stop_loss = float(l[-1])
        if stop_loss >= entry_price:
            return None
        risk_pct = (entry_price - stop_loss) / entry_price
        if risk_pct > cls.MAX_STOP_PCT:
            return None

        risk = entry_price - stop_loss
        return Setup(
            symbol=symbol, triggered=True,
            signal_date=str(df.index[-1].date()),
            entry_price=round(entry_price, 2),
            stop_loss=round(stop_loss, 2),
            target_price=round(entry_price +
                               cls.TARGET_R_MULTIPLE * risk, 2),
            risk_reward=cls.TARGET_R_MULTIPLE,
            pullback_depth=round(pb_depth, 3),
            pullback_days=int(pb_days),
            mother_bar_high=round(mother_bar_high, 2),
            mother_bar_low=round(mother_bar_low, 2),
            impulse_pct=round(impulse_pct, 3),
            ema_proximity=ema_proximity,
            shape_score=shape,
            reasons=["OFFICIAL v3.3: 1c widened, PB floor 6%, days cap 20"])