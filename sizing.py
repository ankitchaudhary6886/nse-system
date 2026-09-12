"""
Position sizing — half-Kelly with beginner-safe caps.
v4 (2026-09-12): adds shape-score quality multiplier.
                 - shape_score 80-100  -> 1.20x
                 - shape_score 60-79   -> 1.00x
                 - shape_score 40-59   -> 0.80x
                 - shape_score 0-39    -> 0.60x
                 - no shape (from pwin only) -> 1.00x
                 Absolute cap raised to 25% (from 20%).
Regime multiplier applied on top (from regime.py).

Basis:
  W = meta-model P(WIN) for the symbol (fallback: graded system win-rate,
      then conservative 0.35 if neither available)
  b = payoff ratio 3.0 (2R stop / 3R target as of v3.4)
  Kelly f* = (b*W - (1-W)) / b ; half-Kelly = f*/2
Caps:
  MAX_ALLOC      = 25% of capital per position (before quality/regime)
  RISK_PER_TRADE = 1% of capital max loss at stop
Suggested value = min(half-kelly value, risk-based value, max-alloc value)
                  * regime_mult * quality_mult
"""
import db

B_PAYOFF = 3.0
MAX_ALLOC = 0.25
RISK_PER_TRADE = 0.01
DEFAULT_CAPITAL = 1_000_000
FALLBACK_WINRATE = 0.35


def get_capital(conn=None):
    own = conn is None
    if own:
        conn = db.get_conn()
    cap = DEFAULT_CAPITAL
    try:
        r = conn.execute(
            "SELECT value FROM settings WHERE key='capital'"
        ).fetchone()
        if r and r[0]:
            cap = float(r[0])
    except Exception:
        pass
    if own:
        conn.close()
    return cap


def set_capital(value):
    v = float(value)
    conn = db.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings(key,value) "
        "VALUES('capital',?)", (str(v),))
    conn.commit()
    conn.close()
    return v


def _system_winrate(conn):
    try:
        row = conn.execute(
            "SELECT SUM(outcome='WIN'), SUM(outcome='LOSS') "
            "FROM swing_signals").fetchone()
        w = row[0] or 0
        l = row[1] or 0
        if w + l >= 10:
            return round(w / (w + l), 3)
    except Exception:
        pass
    return None


def _regime_scale():
    try:
        from regime import MarketRegime
        reg = MarketRegime.compute()
        return reg.size_mult, reg.level
    except Exception:
        return 1.0, "UNKNOWN"


def _quality_mult(shape_score):
    """Shape score 0-100 -> capital multiplier 0.60x - 1.20x."""
    if shape_score is None:
        return 1.0
    try:
        s = float(shape_score)
    except (TypeError, ValueError):
        return 1.0
    if s >= 80:
        return 1.20
    if s >= 60:
        return 1.00
    if s >= 40:
        return 0.80
    return 0.60


def kelly_fraction(w, b=B_PAYOFF):
    if w is None:
        return None
    return max(0.0, (b * w - (1.0 - w)) / b)


def suggest(symbol, trigger=None, stop=None, capital=None,
            shape_score=None, conn=None):
    """
    Suggest a position size for `symbol`.

    Args:
      symbol:       NSE symbol
      trigger:      entry trigger price (optional)
      stop:         stop loss price (optional)
      capital:      override capital (optional; else reads from settings)
      shape_score:  0-100 setup quality from SetupDetector (optional)
    """
    own = conn is None
    if own:
        conn = db.get_conn()
    cap = float(capital) if capital else get_capital(conn)
    w = None
    src = None
    try:
        import pwin_cache
        pw = pwin_cache.get_map(conn)
        if symbol in pw:
            w, src = pw[symbol], "meta-model (daily cache)"
    except Exception:
        pass
    if w is None:
        wr = _system_winrate(conn)
        if wr is not None:
            w, src = wr, "graded system win-rate"
    if w is None:
        w, src = FALLBACK_WINRATE, "conservative fallback (no data yet)"
    if own:
        conn.close()

    regime_mult, regime_level = _regime_scale()
    quality_mult = _quality_mult(shape_score)

    out = {"symbol": symbol, "capital": cap, "p_win": w, "basis": src,
           "payoff_b": B_PAYOFF,
           "regime_level": regime_level,
           "regime_mult": regime_mult,
           "shape_score": shape_score,
           "quality_mult": quality_mult,
           "max_alloc_pct": MAX_ALLOC * 100,
           "risk_per_trade_pct": RISK_PER_TRADE * 100}
    f = kelly_fraction(w)
    half = f / 2.0
    raw_alloc = min(half, MAX_ALLOC)
    alloc = raw_alloc * regime_mult * quality_mult
    out.update({"kelly_pct": round(f * 100, 1),
                "half_kelly_pct": round(half * 100, 1),
                "alloc_pct": round(alloc * 100, 2),
                "max_position_value": round(cap * alloc, 0)})
    if trigger and stop and trigger > stop:
        risk_pct = (trigger - stop) / trigger
        risk_value = cap * RISK_PER_TRADE * regime_mult * quality_mult
        value_by_risk = risk_value / risk_pct if risk_pct > 0 else 0.0
        value = min(cap * alloc, value_by_risk)
        shares = int(value // trigger) if trigger > 0 else 0
        out.update({"trigger": trigger, "stop": stop,
                    "risk_pct": round(risk_pct * 100, 2),
                    "value_by_risk_cap": round(value_by_risk, 0),
                    "suggested_value": round(value, 0),
                    "shares": shares,
                    "risk_amount": round(shares * trigger * risk_pct, 0),
                    "binding_cap": ("risk-based" if value_by_risk < cap * alloc
                                    else f"kelly/alloc {round(alloc*100,2)}%")})
    return out


if __name__ == "__main__":
    import sys
    sym = sys.argv[1].upper() if len(sys.argv) > 1 else "DIXON"
    shape = float(sys.argv[2]) if len(sys.argv) > 2 else None
    print(suggest(sym, shape_score=shape))