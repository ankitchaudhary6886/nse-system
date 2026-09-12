"""
Canonical universe queries (ID7 consolidation, 2026-09-12).

Every module that needs a symbol list should call one of these instead
of writing its own SQL WHERE clause.

Universe layers:
  band_universe   — smallcap/midcap band (1000-8000 cr) from universe_broad
  active_universe — Nifty 500 core (stocks.active=1)
  combined_universe — union of both, deduped, garbage filtered
"""
import db

BAND_MIN = 1000
BAND_MAX = 8000


def _clean(symbols):
    """Drop $ prefixed, spaces, empty. Uppercase."""
    out = set()
    for s in symbols:
        if not s:
            continue
        s = str(s).strip().upper()
        if not s or "$" in s or " " in s:
            continue
        out.add(s)
    return out


def band_universe(conn, limit=1000):
    """Smallcap/midcap band, mcap descending."""
    rows = conn.execute(
        "SELECT symbol FROM universe_broad "
        "WHERE mcap_cr BETWEEN ? AND ? "
        "AND symbol NOT LIKE '%$%' AND symbol NOT LIKE '% %' "
        "ORDER BY mcap_cr DESC LIMIT ?",
        (BAND_MIN, BAND_MAX, limit)).fetchall()
    return sorted(_clean(r[0] for r in rows))


def active_universe(conn):
    """Nifty 500 core — active stocks."""
    rows = conn.execute(
        "SELECT symbol FROM stocks WHERE active=1").fetchall()
    return sorted(_clean(r[0] for r in rows))


def combined_universe(conn, band_limit=1000):
    """Union of band + active, deduped."""
    return sorted(set(band_universe(conn, band_limit)) |
                  set(active_universe(conn)))


if __name__ == "__main__":
    conn = db.get_conn()
    b = band_universe(conn)
    a = active_universe(conn)
    c = combined_universe(conn)
    print(f"band_universe   : {len(b)}")
    print(f"active_universe : {len(a)}")
    print(f"combined        : {len(c)}")
    conn.close()