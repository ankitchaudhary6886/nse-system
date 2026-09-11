"""
Fundamental Veto Gate — the 'partial fundamentals' identity.
Hard-excludes symbols with weak fundamentals from NEW swing alerts,
stored signals, patterns and Top Picks:
  debt_eq  > 3    -> over-leveraged
  roce     < 8    -> poor capital efficiency
  promoter < 20   -> low promoter skin in the game
Missing fundamentals row = NOT vetoed (absence passes, logged).

Usage:
  python fund_veto.py SYMBOL     -> verdict for one symbol
  python fund_veto.py count      -> how many of universe are vetoed
"""
import sys
import db

DEBT_EQ_MAX = 3.0
ROCE_MIN = 8.0
PROMOTER_MIN = 20.0


def _fund_row(conn, sym):
    try:
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(fundamentals)")]
    except Exception:
        return None
    pick = {}
    for want, aliases in [
        ("roce", ["roce"]),
        ("debt_eq", ["debt_to_equity", "debt_equity",
                     "de_ratio", "de"]),
        ("promoter", ["promoter_holding", "promoter_pct",
                      "promoter"]),
    ]:
        for a in aliases:
            if a in cols:
                pick[want] = a
                break
    if not pick:
        return None
    sel = ", ".join(pick.values())
    row = conn.execute(
        f"SELECT {sel} FROM fundamentals WHERE symbol=?",
        (sym,)).fetchone()
    if not row:
        return None
    return dict(zip(pick.keys(), row))


def vetoed(sym, conn=None):
    """Returns (True, reason) if vetoed, else (False, None)."""
    own = conn is None
    if own:
        conn = db.get_conn()
    f = _fund_row(conn, sym)
    if own:
        conn.close()
    if f is None:
        return False, None

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    de = num(f.get("debt_eq"))
    ro = num(f.get("roce"))
    pr = num(f.get("promoter"))
    if de is not None and de > DEBT_EQ_MAX:
        return True, f"debt/equity {de:.1f} > {DEBT_EQ_MAX}"
    if ro is not None and ro < ROCE_MIN:
        return True, f"ROCE {ro:.1f} < {ROCE_MIN}"
    if pr is not None and pr < PROMOTER_MIN:
        return True, f"promoter {pr:.1f}% < {PROMOTER_MIN}%"
    return False, None


def count_universe(limit=800):
    conn = db.get_conn()
    syms = [r[0] for r in conn.execute(
        "SELECT symbol FROM universe_broad "
        "WHERE mcap_cr BETWEEN 1000 AND 8000 "
        "AND symbol NOT LIKE '%$%' AND symbol NOT LIKE '% %' "
        "ORDER BY mcap_cr DESC LIMIT ?", (limit,)).fetchall()]
    v = 0
    reasons = {}
    for s in syms:
        ok, why = vetoed(s, conn=conn)
        if ok:
            v += 1
            reasons[s] = why
    conn.close()
    print(f"[VETO] {v} of {len(syms)} universe symbols vetoed")
    for s, w in list(reasons.items())[:20]:
        print(f"   {s:<14} {w}")
    return v, reasons


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "count"
    if cmd == "count":
        count_universe()
    else:
        ok, why = vetoed(cmd.upper())
        print(f"{cmd.upper()}: "
              f"{'VETOED — ' + why if ok else 'passes fundamental veto'}")