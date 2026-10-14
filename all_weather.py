"""
All-Weather Swing Mode — high-conviction setups during DEFENSIVE regime.
Reads from strategy_config.ALL_WEATHER.
v3 (2026-09-12): migrated to central config.

v4 (2026-10-15) — add the quality gates the SWING path always had
-----------------------------------------------------------------
WHY these gates exist: measured on the graded ledger, 68 of the 71 graded
trades were ALL_WEATHER at a 5.9% win rate — about -52R of the -55R total.
Their entries sat a median 35.5% below the 52-week high and 4.3% above the
52-week low, in a defensive tape. In plain words: this module was buying
falling knives. The SWING path in swing_live.scan requires
Screener.evaluate(...).passed (Stage-2 trend + liquidity) and the sector gate.
This path required none of that, and the fundamental tier that _tier()
computes and detect() stores was never filtered on (dead code).

Four gates are added, each individually switchable in strategy_config.ALL_WEATHER
(every key is read with .get(default), so a missing key can never crash a scan):

  TREND_ENABLED / TREND_EMA / TREND_REQUIRE_RISING / TREND_SLOPE_DAYS
      close must be above a rising EMA (default EMA200, rising over 20 bars).
  LIQ_ENABLED / LIQ_DAYS / MIN_AVG_TURNOVER
      average daily traded value must clear the canonical SCREENER limits.
      Defaults are None = inherit SCREENER, so the number is not copied.
  SECTOR_ENABLED / SECTOR_TOP_N
      the same leadership-sector gate swing_live.scan uses.
  TIER_ENABLED / MIN_TIER
      the fundamental tier _tier() rates must be >= MIN_TIER (default MED).
      "UNK" means we could not rate the name (usually no fundamentals row at
      all); the conservative default treats that as "do not trade".

House rules honoured: every gate is wrapped in try/except and a gate that
fails to run means "do not block", never a blank screen. Nothing in the DB is
dropped; the audit helpers below only read.
"""
import sys
import datetime as dt
import numpy as np
import pandas as pd
import db
import universe_helper as U
from strategy_config import ALL_WEATHER as CFG

try:                                    # central config should exist; never crash
    from strategy_config import SCREENER as SCREENER_CFG
except Exception:
    SCREENER_CFG = {}

BELOW_52W_MIN = CFG["BELOW_52W_MIN"]
NEAR_LOW_MAX = CFG["NEAR_LOW_MAX"]
MAX_RISK_PCT = CFG["MAX_RISK_PCT"]
TARGET_R = CFG["TARGET_R"]
TICK = CFG["TICK"]

# Tier ladder for the fundamental gate. "UNK" = could not rate the name.
TIER_ORDER = {"UNK": 0, "MED": 1, "HIGH": 2}


def _gcfg(key, default, overrides=None):
    """Read one gate setting, falling back safely.

    Missing key, broken config dict or a None value all return `default`, so a
    half-written strategy_config can never crash a scan or an audit.
    `overrides` lets tests flip a gate without editing this file or the config.
    """
    if overrides and key in overrides and overrides[key] is not None:
        return overrides[key]
    try:
        val = CFG.get(key, default)
    except Exception:
        val = default
    return default if val is None else val


def _quality_maps(conn):
    fund = {}
    try:
        rows = conn.execute(
            "SELECT symbol, fundamental_score FROM scan_results "
            "WHERE scan_date=(SELECT MAX(scan_date) FROM scan_results) "
            "AND fundamental_score IS NOT NULL").fetchall()
        for s, sc in rows:
            fund[s] = sc
    except Exception:
        pass
    roce = {}
    try:
        for s, r in conn.execute(
                "SELECT symbol, roce FROM fundamentals "
                "WHERE roce IS NOT NULL").fetchall():
            roce[s] = r
    except Exception:
        pass
    return fund, roce


def _tier(fund_score, roce):
    """
    Fundamental tier. HIGH / MED come straight from the score or ROCE;
    UNK means "we have no usable fundamental data for this name".
    """
    if (fund_score is not None and fund_score >= 70) or \
       (roce is not None and roce >= 15):
        return "HIGH"
    if (fund_score is not None and fund_score >= 50) or \
       (roce is not None and roce >= 10):
        return "MED"
    return "UNK"


def _candle_pattern(o, h, l, c, po, pc):
    body = abs(c - o)
    rng = h - l
    if rng <= 0:
        return None
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)
    if (body / rng < 0.35 and lower_wick / rng > 0.55
            and upper_wick / rng < 0.15):
        return "HAMMER"
    if pc < po and c > o and c >= po and o <= pc:
        return "BULLISH_ENGULFING"
    return None


def _entry(prev, last):
    """V3 entry rules on the last two bars, shared by detect() and the replay.

    Both callers must agree, so the rules live here exactly once.
    `prev` / `last` are (open, high, low, close) tuples.
    Returns None when the bar pair is not a tradable ALL_WEATHER entry.
    """
    po, _ph, pl, pc = prev
    o, h, l, c = last
    pat = _candle_pattern(o, h, l, c, po, pc)
    if not pat:
        return None
    entry = float(h) + TICK
    stop = min(float(l), float(pl)) * 0.99
    if stop >= entry:
        return None
    risk_pct = (entry - stop) / entry
    if risk_pct > MAX_RISK_PCT:
        return None
    return {
        "pattern": pat,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(entry + TARGET_R * (entry - stop), 2),
        "risk_pct": round(risk_pct, 4),
    }


# ============================================================
# GATES — each one is switchable and fails "open" (never blocks) on error
# ============================================================

def _trend_ok_closes(closes, overrides=None):
    """Long-term trend must not be broken: close above a rising EMA.

    Default EMA200 + rising is the same Stage-2 trend test the Screener uses.
    On the historic ALL_WEATHER population that rejects every single signal
    (the setup is, by construction, far below its 52-week high), which is the
    honest point: in a broken tape this mode should stand down.
    """
    span = int(_gcfg("TREND_EMA", 200, overrides))
    slope_days = int(_gcfg("TREND_SLOPE_DAYS", 20, overrides))
    require_rising = bool(_gcfg("TREND_REQUIRE_RISING", True, overrides))
    need = max(span, slope_days) + 2
    arr = np.asarray(closes, dtype="float64")
    if arr.size < need:
        return False, f"trend: {arr.size} bars < {need} needed"
    ema = pd.Series(arr).ewm(span=span, adjust=False).mean().values
    close = float(arr[-1])
    if close <= float(ema[-1]):
        return False, f"trend: close {close:.2f} <= EMA{span} {ema[-1]:.2f}"
    if require_rising and float(ema[-1]) <= float(ema[-1 - slope_days]):
        return False, f"trend: EMA{span} not rising over {slope_days} bars"
    return True, ""


def trend_ok(df, overrides=None):
    return _trend_ok_closes(df["Close"].values, overrides)


def _liquidity_ok_values(volumes, close, overrides=None):
    """Average daily traded value (Rs) must clear the SCREENER limit.

    LIQ_DAYS / MIN_AVG_TURNOVER default to None = inherit strategy_config
    .SCREENER, so the canonical numbers are used and not duplicated here.
    """
    days = _gcfg("LIQ_DAYS", None, overrides)
    if days is None:
        days = SCREENER_CFG.get("LIQ_DAYS", 20)
    min_turnover = _gcfg("MIN_AVG_TURNOVER", None, overrides)
    if min_turnover is None:
        min_turnover = SCREENER_CFG.get("MIN_AVG_TURNOVER", 2e7)
    days = int(days)
    vol = np.asarray(volumes, dtype="float64")
    if vol.size < days:
        return False, f"liquidity: {vol.size} bars < {days} needed"
    avg_vol = float(np.mean(vol[-days:]))
    turnover = avg_vol * float(close)
    if not np.isfinite(turnover) or turnover < float(min_turnover):
        return False, (f"liquidity: avg turnover Rs {turnover / 1e7:.2f} cr "
                       f"< Rs {float(min_turnover) / 1e7:.2f} cr")
    return True, ""


def liquidity_ok(df, overrides=None):
    return _liquidity_ok_values(df["Volume"].values,
                                float(df["Close"].values[-1]), overrides)


def sector_ok(sym, allowed=None, lookup=None, overrides=None):
    """Leadership-sector gate — the same rule swing_live.scan applies.

    `allowed` is the set from sector_gate.allowed_sectors(); when it is not
    supplied we ask sector_gate. A symbol with no sector row passes (absence
    of information must not block), exactly like sector_gate.passes().
    `lookup` lets a caller (or a test, or the replay audit) inject a cached
    symbol -> sector map instead of opening one SQLite connection per symbol.
    """
    try:
        import sector_gate
        if allowed is None:
            top = _gcfg("SECTOR_TOP_N", None, overrides)
            if top is None:
                allowed = sector_gate.allowed_sectors()
            else:
                allowed = sector_gate.allowed_sectors(top=int(top))
        if lookup is None:
            if sector_gate.passes(sym, allowed):       # canonical SWING rule
                return True, ""
            return False, (f"sector: {sector_gate.sector_of(sym)} "
                           f"not in the top-{len(allowed)} leadership set")
        if not allowed:
            return True, ""        # gate unavailable -> do not block
        sec = lookup(sym)
        if sec is None:
            return True, ""        # no sector info -> do not block
        if sec in allowed:
            return True, ""
        return False, f"sector: {sec} not in the top-{len(allowed)} leadership set"
    except Exception:
        return True, ""            # gate unavailable -> do not block


def tier_ok(fund_score=None, roce=None, tier=None, overrides=None):
    """The fundamental tier is now a real filter instead of dead code.

    Default MIN_TIER = "MED", so HIGH and MED pass and UNK is rejected.
    UNK usually means "no fundamentals row for this symbol", and the
    conservative reading of missing data is "do not take the trade".
    """
    t = tier if tier else _tier(fund_score, roce)
    floor = str(_gcfg("MIN_TIER", "MED", overrides)).upper()
    if TIER_ORDER.get(t, 0) >= TIER_ORDER.get(floor, 1):
        return True, ""
    return False, f"tier: {t} below MIN_TIER={floor}"


def gate(sym, df, fund_score=None, roce=None, tier=None, allowed=None,
         sector_lookup=None, overrides=None):
    """Run every enabled gate over one candidate.

    Returns (ok, reasons). All failing gates are reported so the owner can see
    exactly why a name was dropped. A gate that raises is treated as passed:
    the terminal must never blank out because one optional check misbehaved.
    """
    checks = (
        ("TREND_ENABLED", lambda: trend_ok(df, overrides)),
        ("LIQ_ENABLED", lambda: liquidity_ok(df, overrides)),
        ("SECTOR_ENABLED",
         lambda: sector_ok(sym, allowed, sector_lookup, overrides)),
        ("TIER_ENABLED",
         lambda: tier_ok(fund_score, roce, tier, overrides)),
    )
    reasons = []
    for key, check in checks:
        if not bool(_gcfg(key, True, overrides)):
            continue                       # switch is off -> not evaluated
        try:
            ok, why = check()
        except Exception as e:
            ok, why = True, f"{key} errored (ignored): {e}"
        if not ok:
            reasons.append(why or key)
    return (not reasons), reasons


def _sector_context(conn, overrides=None, sector_allowed=None):
    """Build (allowed_set, cached_lookup) once per scan.

    Using a cached map keeps the sector gate from opening 600 SQLite
    connections, while applying the same rule as sector_gate.passes().
    """
    if not bool(_gcfg("SECTOR_ENABLED", True, overrides)):
        return None, None
    if sector_allowed is not None:
        allowed = set(sector_allowed)
    else:
        try:
            import sector_gate
            top = _gcfg("SECTOR_TOP_N", None, overrides)
            if top is None:
                allowed = sector_gate.allowed_sectors()
            else:
                allowed = sector_gate.allowed_sectors(top=int(top))
        except Exception:
            allowed = set()                # unavailable -> gate passes all
    try:
        sec_map = {r[0]: r[1] for r in
                   conn.execute("SELECT symbol, sector FROM stocks")}
        lookup = sec_map.get
    except Exception:
        lookup = None
    return allowed, lookup


def _bars_df(rows):
    """Rows are (date, open, high, low, close, volume) -> the dict-shaped df
    every other module in this repo uses (capitalised OHLCV columns)."""
    return pd.DataFrame(list(rows),
                        columns=["date", "Open", "High", "Low",
                                 "Close", "Volume"]).set_index("date")


def _count_reasons(reasons, stats):
    """Bucket gate reasons into the counters the caller asked for."""
    for why in reasons:
        key = str(why).split(":")[0].strip().lower()
        if key in ("trend", "liquidity", "sector", "tier"):
            stats[key] = stats.get(key, 0) + 1


def candidates(conn, limit=600, sector_lookup=None, sector_allowed=None,
               overrides=None, stats=None):
    """ALL_WEATHER candidates that pass the four quality gates.

    Same 52-week band as v3 (>=25% below the 52-week high, within 15% of the
    52-week low) — the gates are added ON TOP, so nothing that v3 rejected is
    suddenly allowed. `stats` (optional dict) is filled with per-gate
    rejection counts; `sector_allowed` / `sector_lookup` let tests run
    without touching the production database.
    """
    fund, roce = _quality_maps(conn)
    syms = U.band_universe(conn, limit)
    allowed, lookup = _sector_context(conn, overrides, sector_allowed)
    if sector_lookup is not None:
        lookup = sector_lookup
    counts = {"raw": 0, "kept": 0, "trend": 0, "liquidity": 0,
              "sector": 0, "tier": 0}
    out = []
    for sym in syms:
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume "
            "FROM prices_daily WHERE symbol=? "
            "ORDER BY date DESC LIMIT 260", (sym,)).fetchall()
        if len(rows) < 200:
            continue
        rows = list(reversed(rows))
        highs = [r[2] for r in rows if r[2] is not None]
        lows = [r[3] for r in rows if r[3] is not None]
        if len(highs) < 200 or len(lows) < 200:
            continue
        hi52 = max(highs[-252:])
        lo52 = min(lows[-252:])
        last = rows[-1][4]
        if hi52 <= 0 or last is None:
            continue
        below = (hi52 - last) / hi52
        if below < BELOW_52W_MIN:
            continue
        near_low = (last - lo52) / max(lo52, 1e-9)
        if near_low > NEAR_LOW_MAX:
            continue
        counts["raw"] += 1
        df = _bars_df(rows)
        tier = _tier(fund.get(sym), roce.get(sym))
        ok, reasons = gate(sym, df, fund.get(sym), roce.get(sym), tier,
                           allowed, lookup, overrides)
        if not ok:
            _count_reasons(reasons, counts)
            continue
        counts["kept"] += 1
        out.append((sym, df, fund.get(sym), roce.get(sym), tier))
    if stats is not None:
        stats.update(counts)
    return out


def detect(sym, df, fund_score=None, roce=None, tier="UNK"):
    if len(df) < 60:
        return None
    o = df["Open"].values
    h = df["High"].values
    l = df["Low"].values
    c = df["Close"].values

    ent = _entry((o[-2], h[-2], l[-2], c[-2]), (o[-1], h[-1], l[-1], c[-1]))
    if not ent:
        return None

    hi52 = float(np.max(h[-252:])) if len(h) >= 252 else float(np.max(h))
    pb_depth = (hi52 - c[-1]) / hi52 if hi52 > 0 else 0
    return {
        "symbol": sym,
        "entry": ent["entry"],
        "stop": ent["stop"],
        "target": ent["target"],
        "pattern": ent["pattern"],
        "risk_pct": ent["risk_pct"],
        "pb_depth": round(pb_depth, 3),
        "impulse": 0.0,
        "fund_score": fund_score,
        "roce": roce,
        "tier": tier,
    }


def scan(conn=None):
    own = conn is None
    if own:
        conn = db.get_conn()
    setups = []
    for sym, df, fs, roce, tier in candidates(conn):
        s = detect(sym, df, fs, roce, tier)
        if s:
            setups.append(s)
    if own:
        conn.close()
    return setups


# ============================================================
# AUDIT — measure what the gates would have rejected (read-only)
# ============================================================

def _setup_at(rows, i):
    """V3 ALL_WEATHER rules evaluated at bar `i`, point in time.

    No DataFrame here on purpose: a replay runs this tens of thousands of
    times. The entry rules themselves come from _entry(), the same code
    detect() uses, so the replay cannot drift away from production.
    """
    if i < 199:
        return None
    window = rows[max(0, i - 251):i + 1]
    highs = [r[2] for r in window if r[2] is not None]
    lows = [r[3] for r in window if r[3] is not None]
    if len(highs) < 200 or len(lows) < 200:
        return None
    hi52 = max(highs)
    lo52 = min(lows)
    last = rows[i][4]
    if hi52 <= 0 or last is None:
        return None
    if (hi52 - last) / hi52 < BELOW_52W_MIN:
        return None
    if (last - lo52) / max(lo52, 1e-9) > NEAR_LOW_MAX:
        return None
    ent = _entry(tuple(rows[i - 1][1:5]), tuple(rows[i][1:5]))
    if not ent:
        return None
    ent["date"] = rows[i][0]
    ent["i"] = i
    return ent


def audit_stored(conn=None, overrides=None, sector_allowed=None):
    """Re-run the gates on the ALL_WEATHER rows already in the ledger.

    For each stored signal the price window is rebuilt as of its signal_date
    (nothing after that date is read), so the verdict is point in time.
    """
    own = conn is None
    if own:
        conn = db.get_conn()
    res = {"stored": 0, "passed": 0, "rejected": 0, "no_prices": 0,
           "trend": 0, "liquidity": 0, "sector": 0, "tier": 0}
    try:
        stored = conn.execute(
            "SELECT signal_date, symbol FROM swing_signals "
            "WHERE mode='ALL_WEATHER' ORDER BY signal_date").fetchall()
    except Exception:
        stored = []
    if conn is not None and stored:
        fund, roce = _quality_maps(conn)
        allowed, lookup = _sector_context(conn, overrides, sector_allowed)
        for sd, sym in stored:
            res["stored"] += 1
            px = conn.execute(
                "SELECT date, open, high, low, close, volume FROM prices_daily "
                "WHERE symbol=? AND date<=? ORDER BY date", (sym, sd)).fetchall()
            if len(px) < 60:
                res["no_prices"] += 1
                continue
            fs, rc = fund.get(sym), roce.get(sym)
            ok, reasons = gate(sym, _bars_df(px), fs, rc, _tier(fs, rc),
                               allowed, lookup, overrides)
            if ok:
                res["passed"] += 1
            else:
                res["rejected"] += 1
                _count_reasons(reasons, res)
    if own:
        conn.close()
    return res


def audit_replay(conn=None, limit=600, step=10, overrides=None,
                 sector_allowed=None):
    """Replay the v3 rules over price history and gate every signal found.

    The live path only ever looks at the newest bar, so a fresh ledger holds
    no history. This replays what the live path WOULD have stored, one bar at
    a time, with no look-ahead (only rows up to the signal bar are read).
    """
    own = conn is None
    if own:
        conn = db.get_conn()
    fund, roce = _quality_maps(conn)
    allowed, lookup = _sector_context(conn, overrides, sector_allowed)
    res = {"symbols": 0, "signals": 0, "passed": 0, "rejected": 0,
           "trend": 0, "liquidity": 0, "sector": 0, "tier": 0,
           "with_sector_row": 0, "step": step, "limit": limit}
    for sym in U.band_universe(conn, limit):
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        if len(rows) < 220:
            continue
        res["symbols"] += 1
        if lookup is not None and lookup(sym) is not None:
            res["with_sector_row"] += 1
        fs, rc = fund.get(sym), roce.get(sym)
        tier = _tier(fs, rc)
        for i in range(199, len(rows), step):
            ent = _setup_at(rows, i)
            if not ent:
                continue
            res["signals"] += 1
            df = _bars_df(rows[max(0, i - 269):i + 1])
            ok, reasons = gate(sym, df, fs, rc, tier, allowed, lookup,
                               overrides)
            if ok:
                res["passed"] += 1
            else:
                res["rejected"] += 1
                _count_reasons(reasons, res)
    if own:
        conn.close()
    return res


def _print_audit(stored, replay):
    print("[AW AUDIT] stored ALL_WEATHER signals in the ledger: "
          f"{stored['stored']}")
    if stored["stored"]:
        print(f"  rejected {stored['rejected']} / passed {stored['passed']}"
              f" / no price history {stored['no_prices']}")
        print("  rejected per gate (a signal can fail more than one): "
              f"trend {stored['trend']}, liquidity {stored['liquidity']}, "
              f"sector {stored['sector']}, tier {stored['tier']}")
    else:
        print("  (the ledger currently holds no ALL_WEATHER rows, so the "
              "stored-signal count is 0 — see the replay below)")
    print(f"[AW AUDIT] replay of the v3 rules over {replay['symbols']} symbols "
          f"(step={replay['step']}, band limit={replay['limit']}): "
          f"{replay['signals']} signals would have been stored")
    print(f"  gates reject {replay['rejected']} of {replay['signals']} "
          f"(pass {replay['passed']})")
    print("  rejected per gate (not exclusive): "
          f"trend {replay['trend']}, liquidity {replay['liquidity']}, "
          f"sector {replay['sector']}, tier {replay['tier']}")
    print(f"  symbols with a stocks.sector row: {replay['with_sector_row']}"
          f" / {replay['symbols']} (no row = sector gate lets it through)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "audit":
        _print_audit(audit_stored(), audit_replay())
    else:
        rows = scan()
        print(f"[AW] {len(rows)} all-weather setups")
        for s in rows:
            print(f"  {s['symbol']:<12} {s['pattern']:<18} "
                  f"tier {s['tier']:<4} "
                  f"entry {s['entry']} stop {s['stop']} "
                  f"target {s['target']} risk {s['risk_pct']*100:.1f}% "
                  f"fund {s['fund_score']} roce {s['roce']}")
