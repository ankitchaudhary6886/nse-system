"""
Position sizing — half-Kelly with beginner-safe caps.
v3 (2026-09-12): fallback win-rate 0.35 when no cache/graded history;
regime spectrum multiplies alloc AND risk budget.
"""
import db

B_PAYOFF = 2.0
MAX_ALLOC = 0.20
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


def kelly_fraction(w, b=B_PAYOFF):
    if w is None:
        return None
    return max(0.0, (b * w - (1.0 - w)) / b)


def suggest(symbol, trigger=None, stop=None, capital=None, conn=None):
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

    out = {"symbol": symbol, "capital": cap, "p_win": w, "basis": src,
           "payoff_b": B_PAYOFF,
           "regime_level": regime_level,
           "regime_mult": regime_mult,
           "max_alloc_pct": MAX_ALLOC * 100,
           "risk_per_trade_pct": RISK_PER_TRADE * 100}
    f = kelly_fraction(w)
    half = f / 2.0
    alloc = min(half, MAX_ALLOC) * regime_mult
    out.update({"kelly_pct": round(f * 100, 1),
                "half_kelly_pct": round(half * 100, 1),
                "alloc_pct": round(alloc * 100, 1),
                "max_position_value": round(cap * alloc, 0)})
    if trigger and stop and trigger > stop:
        risk_pct = (trigger - stop) / trigger
        risk_value = cap * RISK_PER_TRADE * regime_mult
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
                                    else f"kelly/alloc {round(alloc*100,1)}%")})
    return out


if __name__ == "__main__":
    import sys
    sym = sys.argv[1].upper() if len(sys.argv) > 1 else "DIXON"
    print(suggest(sym))