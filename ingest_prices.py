import sys
import time
import datetime as dt
import db
import freshness_gate
import universe_helper as U
from data_sources import PRICE_HISTORY_PROVIDERS, get_registry
from config import HISTORY_YEARS, SLEEP_SECONDS

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _fetch_frame(symbol, start):
    """Provider chain for one symbol, retrying a punctuation-normalized ticker.

    Some project symbols come from exchange masters with an underscore
    (``BOSCH_HCIL``) while Yahoo/other feeds expect ``BOSCH-HCIL``. The rows are
    still stored under the project symbol, so downstream joins are unchanged.
    """
    candidates = [symbol]
    if "_" in symbol:
        candidates.append(symbol.replace("_", "-"))
    last_error = None
    for candidate in candidates:
        try:
            return get_registry().fetch(
                "prices.daily_history", PRICE_HISTORY_PROVIDERS,
                symbol=candidate, start=start)
        except Exception as exc:
            last_error = exc
    raise last_error or RuntimeError(f"no provider returned data for {symbol}")


def fetch_one(conn, symbol):
    meta = conn.execute(
        "SELECT last_date FROM price_meta WHERE symbol=?", (symbol,)).fetchone()
    last = meta[0] if meta else None
    today = dt.datetime.now(IST).date()
    if last:
        start = (dt.date.fromisoformat(last) + dt.timedelta(days=1)).isoformat()
    else:
        start = (today - dt.timedelta(days=365 * HISTORY_YEARS)).isoformat()
    if start > today.isoformat():
        return 0

    result = _fetch_frame(symbol, start)
    df = result.data
    if df.empty:
        return 0

    rows = [(symbol, str(idx.date()), float(o), float(h), float(l), float(c), float(v))
            for idx, o, h, l, c, v in
            zip(df.index, df["Open"], df["High"], df["Low"], df["Close"], df["Volume"])]
    conn.executemany("INSERT OR REPLACE INTO prices_daily VALUES (?,?,?,?,?,?,?)", rows)

    last_row = conn.execute(
        "SELECT MAX(date), COUNT(*) FROM prices_daily WHERE symbol=?",
        (symbol,)).fetchone()
    conn.execute(
        "INSERT OR REPLACE INTO price_meta "
        "(symbol,last_date,rows,updated_at) VALUES (?,?,?,?)",
        (symbol, last_row[0], last_row[1], dt.datetime.now().isoformat()))
    conn.commit()
    return len(rows)

def _stale_symbols(conn, universe, expected=None):
    """Symbols whose last stored bar is behind the market's expected session.

    The old implementation compared every symbol with ``MAX(date)`` in the same
    table. If the whole table stopped advancing, ``MAX(date)`` also stopped, so
    it returned only a handful of laggards and the frozen market looked current
    forever. The reference is now an external trading-session clock.
    """
    market_last = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
    expected = expected or freshness_gate.expected_session().isoformat()
    last = {row[0]: row[1] for row in conn.execute(
        "SELECT symbol, last_date FROM price_meta")}
    if not market_last or market_last < expected:
        # The whole market is behind, not just a few symbols. Returning the
        # full universe is the only way to fetch the missing sessions.
        return list(universe)
    return [s for s in universe if (last.get(s) or "") < (market_last or "")]


def run(show_every=1, force=False):
    conn = db.get_conn()
    # The tradable universe is band + core, NOT the 825-row stocks table: using
    # only stocks.active silently skipped ~40 band symbols every night (the VM's
    # 60-session coverage gap). universe_helper is the single source of truth.
    universe = U.combined_universe(conn)
    expected = freshness_gate.expected_session().isoformat()
    symbols = list(universe) if force else _stale_symbols(conn, universe,
                                                          expected=expected)
    if not symbols:
        print(f"[PRICES] all {len(universe)} universe symbols current "
              f"(expected session {expected})")
        conn.close()
        return []
    market_last = conn.execute("SELECT MAX(date) FROM prices_daily").fetchone()[0]
    if force or not market_last or market_last < expected:
        print(f"[PRICES] market spine {market_last or 'empty'} is behind "
              f"expected {expected}; fetching all {len(symbols)} symbols")
    else:
        print(f"[PRICES] {len(symbols)} of {len(universe)} symbols need bars")
    total = len(symbols)
    failed = []
    for i, sym in enumerate(symbols, 1):
        ok = False
        for attempt in range(3):
            try:
                n = fetch_one(conn, sym)
                if show_every:
                    print(f"[{i}/{total}] {sym}: +{n} rows")
                ok = True
                break
            except Exception as e:
                print(f"[{i}/{total}] {sym} attempt {attempt+1} failed: {e}")
                time.sleep(5 * (attempt + 1))
        if not ok:
            failed.append(sym)
        time.sleep(SLEEP_SECONDS)

    print("FAILED SYMBOLS:", failed if failed else "none")
    total_rows = conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
    print(f"Total price rows in database: {total_rows}")
    conn.close()
    return failed

if len(sys.argv) > 1 and sys.argv[1] == "run":
    run(force="--force" in sys.argv[2:])