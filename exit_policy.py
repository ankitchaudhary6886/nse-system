"""
exit_policy.py — the ONE place that decides where a swing idea gets out, and
what that idea would actually have earned.

WHY THIS FILE EXISTS
--------------------
"Where do we exit?" was answered in three places with three slightly different
answers:

  * setup.py hard-codes a 3R target (entry + 3 x risk),
  * swing_live.update_outcomes() grades a finished idea WIN / LOSS / TIMEOUT,
  * backtest.py and strategy_backtest.py each run their own exit loop.

They disagree exactly where it costs money — the single daily bar that touches
BOTH the stop and the target. Production checks the stop first, so that bar is
graded a LOSS (swing_live.py). A target-first loop would call the same bar a
WIN. Over a few hundred ideas that one convention is worth a lot of R, so it
belongs in one labelled, testable place instead of four silent copies.

This module is deliberately side-effect free: importing it never touches the
database, the network, the scheduler or Telegram. Everything here is arithmetic
plus one optional READ-ONLY SQLite query (house rule: an optional integration is
always wrapped so the UI can never blank).

PLAIN-ENGLISH DEFINITIONS USED EVERYWHERE BELOW
-----------------------------------------------
  1R      = entry - stop, in rupees per share. The money risked on one share.
  entry   = for the Gabani pullback, the mother bar's HIGH (see setup.py).
  stop    = the signal bar's LOW (see setup.py).
  target  = entry + target_r x 1R.
  MFE     = Maximum Favourable Excursion: the best price above entry, in R,
            while the trade was still alive. Answers "was the target even
            reachable?".
  MAE     = Maximum Adverse Excursion: the worst price below entry, in R
            (negative). Answers "how much heat did we take?".
  tie_rule= which line wins when ONE bar touches both stop and target.
            STOP_FIRST is the live production rule (swing_live.update_outcomes)
            and is the default here. TARGET_FIRST exists only for comparison,
            and every result says which rule produced it.

MATCHING THE EXISTING SIMULATORS
--------------------------------
The trigger/hold convention copies setup_sim.py, the research simulator that
build_setup_pool.py and research_cockpit.py already share:

  * the LOSS is the signal bar itself — the trigger is only sought on the bars
    AFTER it (production does the same: swing_live queries date > signal_date),
  * the entry trigger fires on the first of the next 3 bars whose High >= entry,
  * the idea is held for 30 bars from the trigger bar,
  * the stop is checked before the target inside every bar (stop-first).

EXPIRED means the entry was never triggered. OPEN means the data ran out before
the 30-bar window closed (right-censored, never a fabricated TIMEOUT).
"""
import datetime as dt
import math
import os
import sqlite3
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------
# Defaults. The LIVE value of the target multiple still comes from
# strategy_config.SETUP — see resolve_target_r() and setup.py.
# ----------------------------------------------------------------------
DEFAULT_TARGET_R = 3.0            # today's live value (measuring reference)
DEFAULT_HOLD_BARS = 30            # bars held after the trigger bar
DEFAULT_TRIGGER_WINDOW = 3        # bars allowed for the entry trigger to fire
DEFAULT_DB_REL = os.path.join("data", "app.db")

# Which line wins when one bar touches both. STOP_FIRST is production.
STOP_FIRST = "stop_first"
TARGET_FIRST = "target_first"
TIE_RULES = (STOP_FIRST, TARGET_FIRST)

# Target multiples used by the measurement report.
DEFAULT_LEVELS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0)
FINE_LEVELS = tuple(round(0.1 * i, 1) for i in range(1, 31))

# The outcomes the live grader can write, plus the two honest extras this
# module adds: SCRATCH (a breakeven/trailing rule saved us at ~0R) and
# OPEN / EXPIRED (never a completed trade).
GRADED_OUTCOMES = ("WIN", "LOSS", "TIMEOUT", "SCRATCH")
UNTraded_OUTCOMES = ("EXPIRED", "OPEN")


# ======================================================================
# Section 1 — the exit plan
# ======================================================================
def risk_per_share(entry, stop) -> float:
    """1R in rupees per share. Raises ValueError when the levels make no sense."""
    entry = float(entry)
    stop = float(stop)
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be positive prices")
    if stop >= entry:
        raise ValueError("stop must sit below entry for a long trade")
    return entry - stop


def resolve_target_r(explicit=None, cfg: Optional[dict] = None) -> float:
    """The target multiple in R, resolved safely and in a documented order.

    1. an explicit number the caller passed in,
    2. strategy_config.SETUP["TARGET_R_MULTIPLE"] (a .get, so a missing key
       cannot crash the live scan — house rule),
    3. DEFAULT_TARGET_R (3.0) as the last-resort fallback.

    This is why setup.py can keep its current live behaviour (3.0 today) while
    the owner flips one number in strategy_config.
    """
    if explicit is not None:
        try:
            value = float(explicit)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    if cfg is None:
        try:
            from strategy_config import SETUP as cfg        # noqa: F811
        except Exception:
            cfg = None
    if isinstance(cfg, dict):
        try:
            value = float(cfg.get("TARGET_R_MULTIPLE", DEFAULT_TARGET_R))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return DEFAULT_TARGET_R


@dataclass(frozen=True)
class ExitPlan:
    """Everything an exit needs, in one immutable object.

    Built by plan_from(). Nothing here is a live side effect — it is a
    description a backtest, the scanner or a log line can all use.
    """
    entry: float
    stop: float
    target: float
    target_r: float
    risk: float                   # 1R in rupees
    risk_pct: float               # 1R as a share of entry, e.g. 0.032
    hold_bars: int                # the time stop, counted from the trigger bar
    trigger_window: int
    breakeven_at_r: Optional[float] = None
    trail_ema: Optional[int] = None
    trail_after_r: Optional[float] = None
    atr_pct: Optional[float] = None
    notes: Tuple[str, ...] = ()

    def describe(self) -> str:
        """One plain-English line, safe to drop in a log or on screen."""
        bits = [f"entry {self.entry:.2f}", f"stop {self.stop:.2f}",
                f"target {self.target:.2f} ({self.target_r:g}R)",
                f"risk {self.risk_pct:.1%}", f"time stop {self.hold_bars} bars"]
        if self.breakeven_at_r is not None:
            bits.append(f"stop to breakeven at +{self.breakeven_at_r:g}R")
        if self.trail_ema is not None:
            bits.append(f"trail on EMA{self.trail_ema} close after "
                        f"+{self.trail_after_r:g}R")
        if self.notes:
            bits.append("; ".join(self.notes))
        return " | ".join(bits)


def plan_from(entry, stop, *, target_r=None, cfg: Optional[dict] = None,
              hold_bars=None, trigger_window=DEFAULT_TRIGGER_WINDOW,
              atr_pct=None, breakeven_at_r=None, trail_ema=None,
              trail_after_r=None) -> ExitPlan:
    """Turn (entry, stop, holding context) into an ExitPlan.

    target_r=None means "ask the config" (see resolve_target_r). The ATR is not
    used to move any line — it is recorded so the plan can warn when the stop is
    tighter than one ATR, i.e. inside ordinary daily noise, which is the usual
    reason a good idea gets scratched.
    """
    risk = risk_per_share(entry, stop)
    entry = float(entry)
    stop = float(stop)
    target_r = resolve_target_r(target_r, cfg)
    hold = int(hold_bars) if hold_bars else DEFAULT_HOLD_BARS
    if hold <= 0:
        hold = DEFAULT_HOLD_BARS

    notes: List[str] = []
    risk_pct = risk / entry
    if atr_pct:
        try:
            atr_pct = float(atr_pct)
            if risk_pct < atr_pct:
                notes.append(
                    f"stop is {risk_pct / atr_pct:.2f}x one ATR — inside "
                    f"daily noise, expect scratches")
        except (TypeError, ValueError):
            atr_pct = None
    if risk_pct > 0.05:
        notes.append(f"risk {risk_pct:.1%} is wider than the 5% cap")

    return ExitPlan(
        entry=entry, stop=stop,
        target=entry + target_r * risk, target_r=target_r,
        risk=risk, risk_pct=risk_pct, hold_bars=hold,
        trigger_window=int(trigger_window),
        breakeven_at_r=breakeven_at_r, trail_ema=trail_ema,
        trail_after_r=trail_after_r,
        atr_pct=(float(atr_pct) if atr_pct else None),
        notes=tuple(notes))


# ======================================================================
# Section 2 — scoring a price path
# ======================================================================
@dataclass
class PathScore:
    """The result of grading one idea against a price path.

    `r` is what the trade actually made in R. `r_ledger` repeats the number the
    way ledger.py scores stored rows (a timeout is flat 0R, an EXPIRED idea has
    no R at all), so report figures reconcile with the live ledger.
    """
    outcome: str
    r: Optional[float]
    r_ledger: Optional[float]
    exit_reason: str
    exit_price: Optional[float]
    exit_bar: Optional[int]              # bars from the trigger bar, 0 = trigger
    bars_held: int
    mfe_r: float
    mae_r: float
    mfe_bar: Optional[int]
    mae_bar: Optional[int]
    tie_rule: str
    target_bar: Optional[int]
    stop_bar: Optional[int]
    notes: Tuple[str, ...] = ()


def _normalise_bars(bars) -> List[Tuple[float, float, float, float]]:
    """Accept a pandas frame, dicts or tuples and return (open, high, low, close).

    Backtest code carries DataFrames, the tests carry small tuples; both should
    be able to call the same scorer without a conversion dance at the call site.
    """
    if bars is None:
        return []
    if hasattr(bars, "columns"):                      # pandas DataFrame
        cols = {str(c).lower(): c for c in bars.columns}
        out = []
        for _, row in bars.iterrows():
            o = float(row[cols["open"]]) if "open" in cols else float(row[cols["close"]])
            out.append((o, float(row[cols["high"]]), float(row[cols["low"]]),
                        float(row[cols["close"]])))
        return out
    out = []
    for bar in bars:
        if isinstance(bar, dict):
            low = {str(k).lower(): v for k, v in bar.items()}
            o = float(low.get("open", low["close"]))
            out.append((o, float(low["high"]), float(low["low"]),
                        float(low["close"])))
        else:
            o, h, l, c = (float(x) for x in bar[:4])
            out.append((o, h, l, c))
    return out


def _ema(values: Sequence[float], span: int) -> List[float]:
    """Plain EMA, used only by the optional trailing rule."""
    if not values:
        return []
    k = 2.0 / (span + 1.0)
    out = [float(values[0])]
    for v in values[1:]:
        out.append(float(v) * k + out[-1] * (1 - k))
    return out


def score_path(bars, *, entry, stop, target, hold_bars=DEFAULT_HOLD_BARS,
               start_bar=0, tie_rule=STOP_FIRST, gap_exit_at_open=False,
               breakeven_at_r=None, trail_ema=None, trail_after_r=None) -> PathScore:
    """Grade ONE fixed-target exit over bars that BEGIN at the trigger bar.

    bar 0 is the bar the entry fills on (production checks that same bar's low
    against the stop, so a trigger bar that dips to the stop is a LOSS).

    tie_rule=STOP_FIRST is production: inside a bar the stop is checked first,
    so a bar touching both is a LOSS. TARGET_FIRST is the optimistic reading
    and is returned in the result so no caller can confuse the two.

    gap_exit_at_open=True additionally fills a stop that gaps below at that
    bar's open (the conservative rule strategy_backtest._simulate uses). It is
    OFF by default because swing_live.update_outcomes does not model gaps.

    Optional rules (both OFF by default, so the defaults reproduce production):
      breakeven_at_r — once a bar trades at +N R, the stop moves up to entry
                       and stays there from the NEXT bar (never inside the same
                       bar that armed it).
      trail_ema      — once a bar trades at +trail_after_r R, exit at the close
                       of the first later bar that closes below that EMA.
    """
    if tie_rule not in TIE_RULES:
        raise ValueError(f"tie_rule must be one of {TIE_RULES}")
    risk = risk_per_share(entry, stop)
    entry, stop, target = float(entry), float(stop), float(target)
    hold_bars = int(hold_bars)
    rows = _normalise_bars(bars)
    n = len(rows)
    if start_bar < 0 or start_bar >= n or hold_bars <= 0:
        return PathScore("OPEN", None, None, "OPEN", None, None, 0,
                         0.0, 0.0, None, None, tie_rule, None, None,
                         ("no usable bars in the window",))

    end = min(start_bar + hold_bars, n)
    censored = (start_bar + hold_bars) > n
    closes = [r[3] for r in rows]
    ema = _ema(closes, int(trail_ema)) if trail_ema else None

    stop_level = stop
    breakeven_done = False
    trail_armed = False
    mfe = mae = 0.0
    mfe_bar = mae_bar = None
    target_bar = stop_bar = None
    notes: List[str] = []
    outcome = reason = None
    r = exit_price = None
    exit_off = None

    for j in range(start_bar, end):
        o, h, l, c = rows[j]
        off = j - start_bar
        was_armed = trail_armed              # arming only counts from next bar
        up_r = (h - entry) / risk
        dn_r = (l - entry) / risk
        if up_r > mfe:
            mfe, mfe_bar = up_r, off
        if dn_r < mae:
            mae, mae_bar = dn_r, off

        # --- which line wins inside this bar -------------------------------
        target_touched = h >= target
        gap_stop = gap_exit_at_open and o <= stop_level
        stop_touched = l <= stop_level
        want_stop = gap_stop or (stop_touched if tie_rule == STOP_FIRST
                                 else (stop_touched and not target_touched))
        want_target = target_touched and not want_stop
        if want_stop:
            # Record the target touch even though the stop wins: on a tie the
            # bar printed both levels, and a report that hides one half of that
            # is how a stop-first scorer quietly becomes a target-first one.
            if target_touched:
                target_bar = off
            held = stop_level
            if gap_stop:
                held, note = o, "stop gapped open"
            else:
                note = None
            stop_bar, outcome, reason = off, "LOSS", "STOP"
            exit_price, r, exit_off = held, (held - entry) / risk, off
            if note:
                notes.append(f"{note} at bar {off}")
        elif want_target:
            target_bar, outcome, reason = off, "WIN", "TARGET"
            exit_price, r, exit_off = target, (target - entry) / risk, off
        elif was_armed and ema is not None and c < ema[j]:
            # A trail armed on an EARLIER bar exits at this bar's close.
            outcome = "WIN" if c > entry else ("LOSS" if c < entry else "SCRATCH")
            reason, exit_price, exit_off = "TRAIL", c, off
            r = (c - entry) / risk
        if reason:
            break

        # --- rules that only take effect on the NEXT bar -------------------
        if breakeven_at_r is not None and not breakeven_done:
            if h >= entry + float(breakeven_at_r) * risk:
                breakeven_done = True
                stop_level = max(stop_level, entry)
                notes.append(f"stop moved to breakeven at bar {off}")
        if trail_ema and not trail_armed and trail_after_r is not None:
            if h >= entry + float(trail_after_r) * risk:
                trail_armed = True
                notes.append(f"EMA{trail_ema} trail armed at bar {off}")

    if reason is None:                       # window ended without an exit
        last = rows[end - 1]
        if censored:
            outcome, reason, exit_price, r = "OPEN", "OPEN", last[3], None
            notes.append("data ran out before the time stop")
        else:
            outcome, reason, exit_price = "TIMEOUT", "TIME", last[3]
            r = (last[3] - entry) / risk
            exit_off = end - 1 - start_bar

    if reason == "STOP" and abs(r or 0.0) < 1e-12:
        outcome = "SCRATCH"                  # a saved trade is not a WIN
        notes.append("exited at breakeven")

    if r is None:
        r_ledger = None                      # OPEN / EXPIRED: not a trade yet
    elif outcome == "TIMEOUT":
        r_ledger = 0.0                       # ledger.py convention
    elif outcome == "WIN":
        r_ledger = (target - entry) / risk
    else:                                    # LOSS or SCRATCH
        r_ledger = r

    return PathScore(
        outcome=outcome, r=(None if r is None else round(r, 4)),
        r_ledger=(None if r_ledger is None else round(r_ledger, 4)),
        exit_reason=reason,
        exit_price=(None if exit_price is None else float(exit_price)),
        exit_bar=exit_off, bars_held=(0 if exit_off is None else exit_off + 1),
        mfe_r=round(mfe, 4), mae_r=round(mae, 4),
        mfe_bar=mfe_bar, mae_bar=mae_bar, tie_rule=tie_rule,
        target_bar=target_bar, stop_bar=stop_bar, notes=tuple(notes))


def score_idea(bars, *, entry, stop, target=None, target_r=None,
               cfg: Optional[dict] = None, hold_bars=DEFAULT_HOLD_BARS,
               trigger_window=DEFAULT_TRIGGER_WINDOW, tie_rule=STOP_FIRST,
               gap_exit_at_open=False, breakeven_at_r=None, trail_ema=None,
               trail_after_r=None) -> PathScore:
    """Find the entry trigger on `bars`, then grade the idea.

    `bars` must be the bars AFTER the signal bar (ascending). Production looks
    for the trigger only there — the signal bar itself is the loss, see
    swing_live.update_outcomes: `WHERE symbol=? AND date>?`.
    """
    target_r = resolve_target_r(target_r, cfg)
    risk = risk_per_share(entry, stop)
    if target is None:
        target = float(entry) + target_r * risk
    rows = _normalise_bars(bars)
    n = len(rows)
    trig = None
    for j in range(min(int(trigger_window), n)):
        if rows[j][1] >= float(entry):
            trig = j
            break
    if trig is None:
        if n < int(trigger_window):
            # Production leaves a fresh signal PENDING until 3 bars exist.
            return PathScore("OPEN", None, None, "OPEN", None, None, 0, 0.0,
                             0.0, None, None, tie_rule, None, None,
                             ("not enough bars yet to expire the idea",))
        return PathScore("EXPIRED", None, None, "EXPIRED", None, None, 0,
                         0.0, 0.0, None, None, tie_rule, None, None,
                         ("entry never triggered inside the trigger window",))
    return score_path(rows[trig:], entry=entry, stop=stop, target=target,
                      hold_bars=hold_bars, tie_rule=tie_rule,
                      gap_exit_at_open=gap_exit_at_open,
                      breakeven_at_r=breakeven_at_r, trail_ema=trail_ema,
                      trail_after_r=trail_after_r)


def apply_plan(plan: ExitPlan, bars, *, tie_rule=STOP_FIRST,
               gap_exit_at_open=False) -> PathScore:
    """Grade `bars` (bars after the signal bar) against an ExitPlan."""
    return score_idea(bars, entry=plan.entry, stop=plan.stop,
                      target=plan.target, target_r=plan.target_r,
                      hold_bars=plan.hold_bars,
                      trigger_window=plan.trigger_window, tie_rule=tie_rule,
                      gap_exit_at_open=gap_exit_at_open,
                      breakeven_at_r=plan.breakeven_at_r,
                      trail_ema=plan.trail_ema,
                      trail_after_r=plan.trail_after_r)


# ======================================================================
# Section 3 — MFE / MAE and target sweep over one path
# ======================================================================
def _path_facts(bars, entry, stop, levels, trigger_window, hold_bars,
                tie_rule) -> dict:
    """Scan one price path ONCE and record what happened at every level.

    One scan is enough for every candidate target: in R units the stop is
    always -1R and a target is always +level R, only the first-touch bars
    change. Returns raw facts; `result_at_level` turns them into outcomes.
    """
    rows = _normalise_bars(bars)
    n = len(rows)
    risk = risk_per_share(entry, stop)
    entry = float(entry)
    stop = float(stop)
    levels = [float(x) for x in levels]

    out = {"triggered": False, "trigger_bar": None, "status": "EXPIRED",
           "stop_bar": None, "hit_bar": {}, "mfe_r": 0.0, "mae_r": 0.0,
           "mfe_bar": None, "mae_bar": None, "last_close_r": None,
           "bars_scanned": 0, "levels": levels, "tie_rule": tie_rule}

    trig = None
    for j in range(min(int(trigger_window), n)):
        if rows[j][1] >= entry:
            trig = j
            break
    if trig is None:
        out["status"] = "OPEN" if n < int(trigger_window) else "EXPIRED"
        return out

    out["triggered"] = True
    out["trigger_bar"] = trig
    # A buy-stop at the mother bar high fills at that bar's OPEN when the bar
    # gaps above it. Production does not model that fill (swing_live grades the
    # stored idea), so it is recorded as a flag rather than silently applied:
    # every gapped trigger means the real loss is worse than the -1R this
    # module, and ledger.py, assume.
    trig_open = rows[trig][0]
    out["trigger_open"] = round(trig_open, 4)
    out["entry_gap_r"] = round((trig_open - entry) / risk, 4) if trig_open > entry else 0.0
    end = min(trig + int(hold_bars), n)
    censored = (trig + int(hold_bars)) > n
    mfe = mae = 0.0
    mfe_bar = mae_bar = None
    hit: Dict[float, int] = {}
    stop_bar = None

    for k in range(trig, end):
        _o, h, l, c = rows[k]
        off = k - trig
        up_r = (h - entry) / risk
        dn_r = (l - entry) / risk
        if up_r > mfe:
            mfe, mfe_bar = up_r, off
        if dn_r < mae:
            mae, mae_bar = dn_r, off
        # Levels are recorded before the stop check, exactly like setup_sim.py,
        # so a bar touching both is visible AND still graded a LOSS later.
        for lv in levels:
            if lv not in hit and h >= entry + lv * risk:
                hit[lv] = off
        if l <= stop:                      # stop-first: the trade dies here
            stop_bar = off
            break

    last_row = rows[end - 1]
    # A trade that has already stopped out or reached its target is RESOLVED,
    # even when the data window is short. Calling that "still open" because the
    # snapshots stops 20 bars after the signal silently deletes exactly the
    # trades a short recent window contains — which is most of a live episode.
    resolved = (stop_bar is not None) or bool(hit)
    out.update({
        "status": ("COMPLETE" if (resolved or not censored) else "OPEN"),
        "resolved": resolved,
        "censored": bool(censored),
        "stop_bar": stop_bar, "hit_bar": hit,
        "mfe_r": round(mfe, 4), "mae_r": round(mae, 4),
        "mfe_bar": mfe_bar, "mae_bar": mae_bar,
        "bars_scanned": end - trig,
        # What the idea was worth if it simply timed out at the last close.
        "last_close_r": round((last_row[3] - entry) / risk, 4),
    })
    return out


def result_at_level(facts: dict, level) -> dict:
    """Grade the scanned path as if the target were entry + level x 1R.

    STOP_FIRST (production): if the stop bar is at or before the target bar the
    trade is a LOSS. Both on the same bar is therefore a LOSS — that is the
    intrabar tie this module exists to keep honest.
    TARGET_FIRST: the same bar becomes a WIN, for comparison only.
    """
    level = float(level)
    if not facts.get("triggered"):
        return {"outcome": facts.get("status", "EXPIRED"), "level": level,
                "r": None, "r_ledger": None, "bars_to_exit": None}
    sb = facts.get("stop_bar")
    hb = facts.get("hit_bar", {}).get(level)
    tie_rule = facts.get("tie_rule", STOP_FIRST)

    if tie_rule == TARGET_FIRST:
        win = hb is not None and (sb is None or hb <= sb)
    else:
        win = hb is not None and (sb is None or hb < sb)
    if win:
        return {"outcome": "WIN", "level": level, "r": level,
                "r_ledger": level, "bars_to_exit": hb}
    if sb is not None:
        return {"outcome": "LOSS", "level": level, "r": -1.0,
                "r_ledger": -1.0, "bars_to_exit": sb}
    if facts.get("status") == "OPEN" or facts.get("censored"):
        # Nothing decided at this level and the data window ran out: the idea is
        # genuinely unresolved here, so it must not be scored as a flat timeout.
        return {"outcome": "OPEN", "level": level, "r": None,
                "r_ledger": None, "bars_to_exit": None}
    return {"outcome": "TIMEOUT", "level": level, "r": facts["last_close_r"],
            "r_ledger": 0.0, "bars_to_exit": facts["bars_scanned"]}


# ======================================================================
# Section 4 — reading stored signals (READ ONLY)
# ======================================================================
def default_db_path() -> str:
    """The live database path, with a safe fallback if config is unavailable."""
    try:
        from config import DB_PATH
        if DB_PATH:
            return str(DB_PATH)
    except Exception:
        pass
    return DEFAULT_DB_REL


class PriceStore:
    """Read-only window onto prices_daily, cached per symbol.

    Opened with SQLite's mode=ro URI so a measurement run physically cannot
    write to the live database another teammate is using.
    """

    def __init__(self, db_path=None, conn=None):
        self.db_path = str(db_path or default_db_path())
        self._conn = conn
        self._owns = conn is None
        self._cache: Dict[str, List[tuple]] = {}

    def connection(self):
        if self._conn is None:
            path = self.db_path.replace("\\", "/")
            self._conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        return self._conn

    def close(self):
        if self._owns and self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def all_bars(self, symbol) -> List[tuple]:
        """Every stored bar: (date, open, high, low, close, volume), ascending."""
        if symbol not in self._cache:
            try:
                rows = self.connection().execute(
                    "SELECT date, open, high, low, close, volume "
                    "FROM prices_daily WHERE symbol=? ORDER BY date",
                    (symbol,)).fetchall()
            except Exception:
                rows = []
            self._cache[symbol] = [tuple(r) for r in rows]
        return self._cache[symbol]

    def bars_after(self, symbol, date_str) -> List[Tuple[float, float, float, float]]:
        """Bars strictly after `date_str`, as (open, high, low, close) tuples.

        Production grades exactly these bars (swing_live.update_outcomes reads
        `WHERE symbol=? AND date>?`), so this is the window every scorer here
        works on. Dates are stored as ISO YYYY-MM-DD text, so a string compare
        is safe.
        """
        return [(float(r[1]), float(r[2]), float(r[3]), float(r[4]))
                for r in self.all_bars(symbol) if str(r[0]) > str(date_str)]

    def symbols_with_history(self, min_bars=300, limit=100, offset=0,
                             spread=True, by_mcap=True) -> List[str]:
        """Pick a sample of symbols that have enough stored history.

        Two biases this tries to remove, because either one can invent a result:

          * alphabet bias — `ORDER BY symbol LIMIT n` is an A-Z slice, not a
            market. by_mcap=True orders by universe_broad.mcap_cr instead, and
            spread=True then strides across that whole list so the sample is
            not just the very largest names.
          * one lucky symbol — offset shifts the stride phase, so two runs with
            different offsets are near-disjoint samples of the same universe.
        """
        try:
            if by_mcap:
                rows = self.connection().execute(
                    "SELECT p.symbol, u.mcap_cr FROM (SELECT symbol "
                    "FROM prices_daily GROUP BY symbol "
                    "HAVING COUNT(*) >= ?) p "
                    "LEFT JOIN universe_broad u ON u.symbol = p.symbol "
                    "ORDER BY (u.mcap_cr IS NULL), u.mcap_cr DESC",
                    (int(min_bars),)).fetchall()
            else:
                rows = [(r[0], None) for r in self.connection().execute(
                    "SELECT symbol FROM prices_daily GROUP BY symbol "
                    "HAVING COUNT(*) >= ? ORDER BY symbol",
                    (int(min_bars),)).fetchall()]
        except Exception:
            return []
        syms = [r[0] for r in rows]
        if not spread or len(syms) <= limit:
            return syms[int(offset):int(offset) + int(limit)]
        stride = max(1, len(syms) // int(limit))
        return syms[int(offset) % stride::stride][:int(limit)]


@dataclass
class Idea:
    """One idea to measure: a stored row, or one regenerated from history."""
    symbol: str
    signal_date: str
    entry: float
    stop: float
    target: Optional[float] = None
    outcome: Optional[str] = None
    mode: str = "SWING"
    rowid: Optional[int] = None
    source: str = "stored"


def load_stored_signals(db_path=None, conn=None, modes=None,
                        outcomes=None) -> List[Idea]:
    """Read swing_signals as Ideas. Read-only; never raises on a missing table."""
    own = conn is None
    if own:
        path = str(db_path or default_db_path()).replace("\\", "/")
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except Exception:
            return []
    try:
        sql = ("SELECT rowid, mode, symbol, signal_date, entry_trigger, "
               "stop, target, outcome FROM swing_signals")
        clauses, params = [], []
        if modes:
            clauses.append("mode IN (%s)" % ",".join("?" * len(modes)))
            params.extend(list(modes))
        if outcomes:
            clauses.append("outcome IN (%s)" % ",".join("?" * len(outcomes)))
            params.extend(list(outcomes))
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY signal_date, symbol"
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        rows = []
    finally:
        if own and conn is not None:
            conn.close()
    ideas = []
    for rowid, mode, sym, date, trig, stop, tgt, out in rows:
        if trig is None or stop is None:
            continue
        ideas.append(Idea(symbol=sym, signal_date=str(date), entry=float(trig),
                          stop=float(stop),
                          target=(float(tgt) if tgt is not None else None),
                          outcome=out, mode=(mode or "SWING"), rowid=rowid))
    return ideas


# ======================================================================
# Section 5 — measuring a population
# ======================================================================
def _dist(values) -> Optional[dict]:
    """Small distribution summary (no numpy needed, keeps the import light)."""
    vals = sorted(float(v) for v in values if v is not None)
    if not vals:
        return None

    def pct(p):
        if len(vals) == 1:
            return round(vals[0], 2)
        pos = (len(vals) - 1) * (p / 100.0)
        lo, hi = int(math.floor(pos)), int(math.ceil(pos))
        if lo == hi:
            return round(vals[lo], 2)
        frac = pos - lo
        return round(vals[lo] * (1 - frac) + vals[hi] * frac, 2)

    return {"n": len(vals), "mean": round(sum(vals) / len(vals), 3),
            "p5": pct(5), "p25": pct(25), "p50": pct(50), "p75": pct(75),
            "p90": pct(90), "p95": pct(95), "min": round(vals[0], 2),
            "max": round(vals[-1], 2)}


def measure_ideas(ideas, store=None, *, levels=DEFAULT_LEVELS,
                  hold_bars=DEFAULT_HOLD_BARS,
                  trigger_window=DEFAULT_TRIGGER_WINDOW,
                  tie_rule=STOP_FIRST) -> List[dict]:
    """Grade every idea: path facts, MFE/MAE, and the result at each level.

    The idea's OWN stored target is always added to the levels being scanned.
    Stored targets are rarely round numbers (a 3R target can work out as 2.9997R
    after the entry and stop are rounded to paise), and a level that was never
    scanned cannot be graded — which would silently turn every stored WIN into a
    LOSS and make the reconciliation below meaningless.
    """
    store = store or PriceStore()
    levels = tuple(float(x) for x in levels)
    records = []
    for idea in ideas:
        if idea.entry <= idea.stop or idea.entry <= 0:
            records.append({"idea": idea, "skip": "entry/stop not tradeable"})
            continue
        bars = store.bars_after(idea.symbol, idea.signal_date)
        if not bars:
            records.append({"idea": idea, "skip": "no price history after signal"})
            continue
        risk = idea.entry - idea.stop
        scan_levels = set(levels)
        stored_level = None
        if idea.target is not None:
            stored_level = round((idea.target - idea.entry) / risk, 4)
            scan_levels.add(stored_level)
        facts = _path_facts(bars, idea.entry, idea.stop,
                            tuple(sorted(scan_levels)),
                            trigger_window, hold_bars, tie_rule)
        rec = {"idea": idea, "facts": facts}
        rec["level_results"] = {lv: result_at_level(facts, lv) for lv in levels}
        if stored_level is not None:
            rec["stored_level"] = stored_level
            rec["stored_result"] = result_at_level(facts, stored_level)
        records.append(rec)
    return records


def summarise(records, levels=DEFAULT_LEVELS, modes=None) -> dict:
    """Per-mode summary: MFE/MAE shape, reachability, and R at each target."""
    levels = [float(x) for x in levels]
    out: Dict[str, dict] = {}
    for mode in (modes or sorted({r["idea"].mode for r in records})):
        mine = [r for r in records if r["idea"].mode == mode]
        usable = [r for r in mine if "facts" in r]
        traded = [r for r in usable if r["facts"]["triggered"]
                  and r["facts"]["status"] == "COMPLETE"]
        expired = [r for r in usable if r["facts"]["status"] == "EXPIRED"]
        openish = [r for r in usable if r["facts"]["status"] == "OPEN"]
        skipped = [r for r in mine if "skip" in r]

        mfes = [r["facts"]["mfe_r"] for r in traded]
        maes = [r["facts"]["mae_r"] for r in traded]
        reach = {str(lv): (round(100.0 * sum(
            1 for r in traded if r["facts"]["mfe_r"] >= lv) / len(traded), 1)
            if traded else None) for lv in levels}

        # The same question asked the way a trader asks it: of the ideas that
        # were STOPPED OUT, how many had already printed +1R/+2R/+3R before the
        # stop? A level touched on the stop bar itself does NOT count.
        losers = [r for r in traded if r["facts"]["stop_bar"] is not None]
        losers_reach = {}
        for lv in levels:
            if not losers:
                losers_reach[str(lv)] = None
                continue
            touched = sum(
                1 for r in losers
                if r["facts"]["hit_bar"].get(lv) is not None
                and r["facts"]["hit_bar"][lv] < r["facts"]["stop_bar"])
            losers_reach[str(lv)] = round(100.0 * touched / len(losers), 1)

        by_target = {}
        for lv in levels:
            ledger = [r["level_results"][lv]["r_ledger"] for r in traded]
            close_r = [r["level_results"][lv]["r"] for r in traded]
            # A resolved trade can still be unresolved AT A HIGHER LEVEL (the
            # data window ended before that level mattered) — drop those Nones.
            ledger = [x for x in ledger if x is not None]
            close_r = [x for x in close_r if x is not None]
            outcomes = [r["level_results"][lv]["outcome"] for r in traded]
            by_target[str(lv)] = {
                "n": len(ledger),
                "mean_r_ledger": round(sum(ledger) / len(ledger), 4) if ledger else None,
                "mean_r_close": (round(sum(close_r) / len(close_r), 4)
                                 if close_r else None),
                "total_r_ledger": round(sum(ledger), 2) if ledger else None,
                "wins": outcomes.count("WIN"),
                "losses": outcomes.count("LOSS"),
                "timeouts": outcomes.count("TIMEOUT"),
                "profit_factor": _profit_factor(ledger),
            }

        # Does our stop-first re-score reproduce what the live grader stored?
        match = total = 0
        for r in traded:
            if r["idea"].outcome not in ("WIN", "LOSS", "TIMEOUT"):
                continue
            res = r.get("stored_result")
            if not res:
                continue
            total += 1
            if res["outcome"] == r["idea"].outcome:
                match += 1

        out[mode] = {
            "n_signals": len(mine),
            "n_symbols": len({r["idea"].symbol for r in mine}),
            "n_traded": len(traded),
            "n_expired": len(expired),
            "n_open": len(openish),
            "n_skipped": len(skipped),
            # Share of traded ideas whose trigger bar opened ABOVE the entry, so
            # the real fill (and the real loss) was worse than this arithmetic.
            "entry_gapped_pct": (round(100.0 * sum(
                1 for r in traded
                if (r["facts"].get("entry_gap_r") or 0) > 0) / len(traded), 1)
                if traded else None),
            "mfe_r": _dist(mfes),
            "mae_r": _dist(maes),
            "reach_pct": reach,
            "losers_reach_pct": losers_reach,
            "by_target": by_target,
            "stored_match": (f"{match}/{total}" if total else "n/a"),
        }
    return out


def symbol_concentration(records, level, mode=None) -> Optional[dict]:
    """How much of a level's total R comes from its single best symbol.

    A high share means "this target looks good because of one name", which is
    the fastest way for a calibration number to be a fluke. Reported next to
    every recommendation so the reader can discount it.
    """
    level = float(level)
    per_symbol: Dict[str, float] = {}
    for r in records:
        if "facts" not in r or not r["facts"]["triggered"]:
            continue
        if r["facts"]["status"] != "COMPLETE":
            continue
        if mode and r["idea"].mode != mode:
            continue
        res = r.get("level_results", {}).get(level)
        if not res or res.get("r_ledger") is None:
            continue
        per_symbol[r["idea"].symbol] = per_symbol.get(r["idea"].symbol, 0.0) \
            + float(res["r_ledger"])
    if not per_symbol:
        return None
    total = sum(per_symbol.values())
    top_sym, top_r = max(per_symbol.items(), key=lambda kv: kv[1])
    return {"symbol": top_sym, "symbol_r": round(top_r, 2),
            "share_of_total_pct": (round(100.0 * top_r / total, 1)
                                   if abs(total) > 1e-9 else None),
            "n_symbols": len(per_symbol)}


def _profit_factor(rs) -> Optional[float]:
    gross_win = sum(x for x in rs if x > 0)
    gross_loss = abs(sum(x for x in rs if x < 0))
    if gross_loss <= 0:
        return None if gross_win <= 0 else 999.0
    return round(gross_win / gross_loss, 2)


def split_walk_forward(records, parts=2) -> List[Tuple[str, List[dict]]]:
    """Split graded records into consecutive time buckets (oldest first).

    A walk-forward read: if the best target changes between the first and the
    second half of history, the "best" number is curve-fitted, not an edge.
    """
    usable = [r for r in records if "facts" in r]
    ordered = sorted(usable, key=lambda r: (str(r["idea"].signal_date),
                                            r["idea"].symbol))
    size = max(1, len(ordered) // max(1, int(parts)))
    chunks = [ordered[i:i + size] for i in range(0, len(ordered), size)]
    labels = []
    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
        labels.append((f"part{i + 1} "
                       f"{chunk[0]['idea'].signal_date}.."
                       f"{chunk[-1]['idea'].signal_date}", chunk))
    return labels


def best_level(summary: dict, key="mean_r_ledger") -> Optional[dict]:
    """The target multiple with the best average R in a summary block."""
    best = None
    for level, stats in summary.get("by_target", {}).items():
        value = stats.get(key)
        if value is None:
            continue
        if best is None or value > best["mean_r_ledger"]:
            best = {"level": float(level), "mean_r_ledger": value,
                    "wins": stats["wins"], "losses": stats["losses"],
                    "timeouts": stats["timeouts"],
                    "profit_factor": stats["profit_factor"]}
    return best


def instrument_report(db_path=None, conn=None, ideas=None, modes=None,
                      levels=DEFAULT_LEVELS, fine_levels=FINE_LEVELS,
                      hold_bars=DEFAULT_HOLD_BARS,
                      trigger_window=DEFAULT_TRIGGER_WINDOW,
                      tie_rule=STOP_FIRST, store=None) -> dict:
    """The one-call measurement: MFE/MAE + reachability + R per target.

    Reads the stored swing_signals (SWING and ALL_WEATHER kept apart), grades
    every idea against its own price path, and answers the two questions that
    matter: how far do these trades actually travel (MFE/MAE), and what would
    the same entries have earned at other targets (with the production
    stop-first rule).
    """
    store = store or PriceStore(db_path=db_path, conn=conn)
    if ideas is None:
        ideas = load_stored_signals(db_path=db_path, conn=conn, modes=modes)
    records = measure_ideas(ideas, store, levels=levels, hold_bars=hold_bars,
                           trigger_window=trigger_window, tie_rule=tie_rule)
    fine = measure_ideas(ideas, store, levels=fine_levels, hold_bars=hold_bars,
                         trigger_window=trigger_window, tie_rule=tie_rule)
    summary = summarise(records, levels=levels)
    fine_summary = summarise(fine, levels=fine_levels)

    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "db": str(db_path or default_db_path()),
        "hold_bars": hold_bars, "trigger_window": trigger_window,
        "tie_rule": tie_rule,
        "n_ideas": len(ideas),
        "by_mode": summary,
        "fine_grid": {m: best_level(s) for m, s in fine_summary.items()},
        "walk_forward": {},
        "broad_grid": {m: best_level(s) for m, s in summary.items()},
        "concentration": {},
    }
    for mode, best in report["broad_grid"].items():
        if best:
            report["concentration"][mode] = symbol_concentration(
                records, best["level"], mode=mode)
    for mode in summary:
        chunks = []
        for label, chunk in split_walk_forward(
                [r for r in records if r["idea"].mode == mode]):
            block = summarise(chunk, levels=levels, modes=[mode])[mode]
            chunks.append({"window": label, "n_traded": block["n_traded"],
                           "best": best_level(block),
                           "by_target": {k: v["mean_r_ledger"]
                                         for k, v in block["by_target"].items()},
                           "mfe_r": block["mfe_r"], "mae_r": block["mae_r"]})
        report["walk_forward"][mode] = chunks
    return report


def format_report(report: dict) -> str:
    """Plain-English printout of instrument_report()."""
    lines = []
    lines.append("=" * 72)
    lines.append(f"EXIT CALIBRATION REPORT  (generated {report['generated_at']})")
    lines.append(f"db={report['db']}  ideas={report['n_ideas']}  "
                 f"hold={report['hold_bars']} bars  "
                 f"trigger window={report['trigger_window']} bars  "
                 f"tie rule={report['tie_rule']}")
    lines.append("=" * 72)
    for mode, s in report["by_mode"].items():
        lines.append("")
        lines.append(f"--- {mode} ---")
        lines.append(f"signals {s['n_signals']}  traded {s['n_traded']}  "
                     f"symbols {s['n_symbols']}  "
                     f"expired-never-triggered {s['n_expired']}  "
                     f"still-open {s['n_open']}  skipped {s['n_skipped']}  "
                     f"entry gapped above trigger: {s['entry_gapped_pct']}%  "
                     f"stop-first re-score matches stored outcome: "
                     f"{s['stored_match']}")
        for name in ("mfe_r", "mae_r"):
            d = s[name]
            if not d:
                lines.append(f"{name.upper():>6}: none")
                continue
            lines.append(f"{name.upper():>6}: mean {d['mean']:+.2f}  "
                         f"p5 {d['p5']:+.2f}  p25 {d['p25']:+.2f}  "
                         f"p50 {d['p50']:+.2f}  p75 {d['p75']:+.2f}  "
                         f"p90 {d['p90']:+.2f}  p95 {d['p95']:+.2f}  "
                         f"min {d['min']:+.2f}  max {d['max']:+.2f}")
        if s["n_traded"]:
            reach = "  ".join(f"+{lv}R {s['reach_pct'][lv]}%"
                              for lv in s["reach_pct"])
            lines.append(f"reachable (share of traded ideas whose best price "
                         f"reached): {reach}")
            lreach = "  ".join(f"+{lv}R {s['losers_reach_pct'][lv]}%"
                               for lv in s["losers_reach_pct"])
            lines.append(f"of the STOPPED-OUT ideas, share that had already "
                         f"printed: {lreach}")
        lines.append(f"{'target':>7} {'meanR':>8} {'totalR':>8} "
                     f"{'W':>4} {'L':>4} {'TO':>4} {'PF':>6}")
        for lv, t in s["by_target"].items():
            if t["mean_r_ledger"] is None:
                continue
            lines.append(f"{lv:>7} {t['mean_r_ledger']:>8.3f} "
                         f"{t['total_r_ledger']:>8.2f} {t['wins']:>4} "
                         f"{t['losses']:>4} {t['timeouts']:>4} "
                         f"{str(t['profit_factor']):>6}")
    lines.append("")
    lines.append("BEST OVER THE COARSE GRID (by average R per idea, ledger rule):")
    for mode, best in report["broad_grid"].items():
        lines.append(f"  {mode:<12} {best}")
        conc = report.get("concentration", {}).get(mode)
        if conc:
            lines.append(f"  {'':<12} top symbol {conc['symbol']} carries "
                         f"{conc['symbol_r']}R of the total "
                         f"({conc['share_of_total_pct']}%) across "
                         f"{conc['n_symbols']} symbols")
    lines.append("BEST OVER THE FINE 0.1R GRID (watch for curve fitting):")
    for mode, best in report["fine_grid"].items():
        lines.append(f"  {mode:<12} {best}")
    lines.append("")
    lines.append("WALK-FORWARD (halves of history, oldest first):")
    for mode, chunks in report["walk_forward"].items():
        for ch in chunks:
            lines.append(f"  {mode:<12} {ch['window']}  traded={ch['n_traded']}"
                         f"  best={ch['best']}")
    lines.append("")
    return "\n".join(lines)


# ======================================================================
# Section 6 — regenerating a population from stored history (optional)
# ======================================================================
def history_signals(mode="SWING", limit=60, step=20, min_bars=300,
                    min_gap=None, offset=0, by_mcap=True,
                    verbose=False) -> List[Idea]:
    """Walk stored history and re-detect signals, for a bigger sample.

    This is how the calibration gets its evidence when only a handful of live
    rows exist. It re-uses the SAME detectors the live system uses
    (setup.SetupDetector for SWING, all_weather.detect for ALL_WEATHER) and
    imports them lazily, so exit_policy.py stays importable on its own and
    setup.py can import exit_policy without a circular import.

    min_gap (default: the hold window) de-overlaps the sample: new signals for
    the same symbol are dropped while an earlier one would still be open. Two
    overlapping signals are not two independent pieces of evidence, and treating
    them as such is the easiest way to invent a result that does not exist.

    Every detector call is wrapped: one broken slice must never kill the run
    (house rule for optional integrations).
    """
    try:
        import pandas as pd
    except Exception:
        return []
    if min_gap is None:
        min_gap = DEFAULT_HOLD_BARS
    store = PriceStore()
    try:
        syms = store.symbols_with_history(min_bars=min_bars, limit=limit,
                                          offset=offset, by_mcap=by_mcap)
        ideas: List[Idea] = []
        detector = None
        if mode == "SWING":
            from setup import SetupDetector
        else:
            try:
                import all_weather
                detector = all_weather
            except Exception:
                return []

        for si, sym in enumerate(syms, 1):
            rows = store.all_bars(sym)
            if len(rows) < min_bars:
                continue
            df = pd.DataFrame([(r[0], r[1], r[2], r[3], r[4], r[5])
                               for r in rows],
                              columns=["date", "Open", "High", "Low", "Close",
                                       "Volume"]).set_index("date")
            df.index = pd.to_datetime(df.index)
            last_kept = -10 ** 9
            for i in range(min_bars, len(df) - 1, step):
                window = df.iloc[:i + 1]
                try:
                    if mode == "SWING":
                        st = SetupDetector.detect(window, sym)
                        if not st.triggered:
                            continue
                        idea = Idea(sym, st.signal_date, st.entry_price,
                                    st.stop_loss, st.target_price,
                                    mode="SWING", source="history")
                    else:
                        s = detector.detect(sym, window)
                        if not s:
                            continue
                        idea = Idea(sym, str(window.index[-1].date()),
                                    s["entry"], s["stop"], s["target"],
                                    mode="ALL_WEATHER", source="history")
                except Exception:
                    continue
                if i - last_kept < int(min_gap):
                    continue                 # still inside an earlier idea
                ideas.append(idea)
                last_kept = i
            if verbose and si % 25 == 0:
                print(f"   ...scanned {si}/{len(syms)} symbols, "
                      f"{len(ideas)} signals")
        return ideas
    finally:
        store.close()


# ======================================================================
# CLI — a read-only report, safe to run any time
# ======================================================================
def _parse_levels(text) -> tuple:
    return tuple(float(x) for x in str(text).split(",") if x.strip())


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    modes = ["SWING", "ALL_WEATHER"]
    limit, step, offset, gap = 60, 20, 0, None
    by_mcap = True
    scan = False
    report_kw = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--scan":
            scan = True
            if i + 1 < len(argv) and argv[i + 1].isdigit():
                limit = int(argv[i + 1]); i += 1
            if i + 1 < len(argv) and argv[i + 1].isdigit():
                step = int(argv[i + 1]); i += 1
        elif arg == "--offset" and i + 1 < len(argv):
            offset = int(argv[i + 1]); i += 1
        elif arg == "--gap" and i + 1 < len(argv):
            gap = int(argv[i + 1]); i += 1
        elif arg == "--nomcap":
            by_mcap = False
        elif arg == "--levels" and i + 1 < len(argv):
            report_kw["levels"] = _parse_levels(argv[i + 1]); i += 1
        elif arg == "--mode" and i + 1 < len(argv):
            modes = [argv[i + 1]]; i += 1
        i += 1

    if scan:
        print(f"scanning stored history: limit={limit} symbols, step={step} "
              f"bars, offset={offset}, gap={gap}, by_mcap={by_mcap} "
              f"(bounded, read-only)...")
        ideas = []
        for mode in modes:
            found = history_signals(mode=mode, limit=limit, step=step,
                                    min_gap=gap, offset=offset,
                                    by_mcap=by_mcap, verbose=True)
            print(f"   {mode}: {len(found)} regenerated signals "
                  f"(de-overlapped)")
            ideas.extend(found)
        report = instrument_report(ideas=ideas, **report_kw)
    else:
        report = instrument_report(modes=modes, **report_kw)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
