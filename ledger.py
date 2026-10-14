"""
Paper-Trade Ledger & System Stats (N3).
Reads graded swing_signals and computes system-level performance:
Win Rate, Profit Factor, Expectancy (R), Max Drawdown.

Also splits those same numbers month by month (N3), so a bad month is visible
instead of being averaged away by a good one.
"""
import db

# Month label for graded ideas whose signal_date cannot be read as YYYY-MM.
UNKNOWN_MONTH = "Unknown"


def _month_of(date):
    """YYYY-MM for a signal date, or UNKNOWN_MONTH when it is unreadable."""
    s = str(date or "")[:7]
    if len(s) == 7 and s[4] == "-" and s[:4].isdigit() and s[5:].isdigit():
        return s
    return UNKNOWN_MONTH


def _graded_rows(conn):
    """Graded ideas, oldest first: (date, symbol, trigger, stop, target, outcome)."""
    return conn.execute("""
        SELECT signal_date, symbol, entry_trigger, stop, target, outcome 
        FROM swing_signals 
        WHERE outcome IN ('WIN', 'LOSS', 'TIMEOUT', 'EXPIRED')
        ORDER BY signal_date
    """).fetchall()


def _r_of(outcome, trigger, stop, target):
    """Unrounded R for one graded idea, or None when it was never a trade.

    Pulled out of compute_stats so the overall view and the monthly view cannot
    drift apart: same rows, same filters, same arithmetic, one definition.
    """
    if not trigger or not stop or not target:
        return None
    risk = trigger - stop
    if risk <= 0:
        return None
    if outcome == 'WIN':
        return (target - trigger) / risk
    if outcome == 'LOSS':
        return -1.0
    if outcome == 'TIMEOUT':
        return 0.0
    return None                      # EXPIRED — the idea was never a trade


def _stats_from_rs(rs):
    """Aggregate a list of R multiples into the headline stats."""
    total = len(rs)
    if not total:
        return None

    wins = sum(1 for r in rs if r > 0)
    losses = sum(1 for r in rs if r < 0)

    gross_profit = sum(r for r in rs if r > 0)
    gross_loss = abs(sum(r for r in rs if r < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0

    total_r = sum(rs)

    cum_r = 0
    peak = 0
    max_dd = 0
    for r in rs:
        cum_r += r
        if cum_r > peak:
            peak = cum_r
        dd = peak - cum_r
        if dd > max_dd:
            max_dd = dd

    return {
        'total_trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': round(100 * wins / total, 1),
        'profit_factor': round(profit_factor, 2),
        'expectancy_r': round(total_r / total, 2),
        'total_r': round(total_r, 2),
        'max_drawdown_r': round(max_dd, 2)
    }


def compute_stats(conn=None):
    own = conn is None
    if own:
        conn = db.get_conn()
    try:
        rs = [r for r in (_r_of(out, trig, stop, tgt)
                          for _d, _s, trig, stop, tgt, out in _graded_rows(conn))
              if r is not None]
    finally:
        if own:
            conn.close()
    return _stats_from_rs(rs)


def compute_monthly_stats(conn=None, limit_months=24):
    """The same numbers as compute_stats, bucketed by signal month.

    Newest month first, at most `limit_months` rows. Months with no graded
    idea simply do not appear — there is nothing to report for them.

    A graded idea whose signal_date is missing or malformed still counts (in
    compute_stats and in the trade list), so instead of dropping it here it is
    collected under UNKNOWN_MONTH, shown last. That keeps the monthly figures
    reconciling with the overall ones: no trade disappears between the two
    views just because its date is unreadable.
    """
    own = conn is None
    if own:
        conn = db.get_conn()
    try:
        buckets = {}
        for date, _sym, trig, stop, tgt, out in _graded_rows(conn):
            r = _r_of(out, trig, stop, tgt)
            if r is None:
                continue
            buckets.setdefault(_month_of(date), []).append(r)
    finally:
        if own:
            conn.close()

    known = sorted((m for m in buckets if m != UNKNOWN_MONTH),
                   reverse=True)[:max(1, int(limit_months))]
    order = known + ([UNKNOWN_MONTH] if buckets.get(UNKNOWN_MONTH) else [])

    months = []
    for month in order:
        stats = _stats_from_rs(buckets[month])
        if stats:
            months.append(dict(stats, month=month))
    return months

def trade_r_multiple(outcome, trigger, stop, target):
    """Result of one idea measured in R (see explain.py -> 'r_multiple').

    1R is the money risked: the gap between the entry price and the safety line.
    A win that reaches the goal is worth (goal - entry) / that gap. A loss is
    exactly -1R by definition, and a timeout is flat at 0R. EXPIRED ideas were
    never really a trade, so they have no R.
    """
    if outcome in (None, 'EXPIRED', 'OPEN', 'PENDING'):
        return None
    if outcome == 'LOSS':
        return -1.0
    if outcome == 'TIMEOUT':
        return 0.0
    if outcome == 'WIN':
        try:
            risk = float(trigger) - float(stop)
            reward = float(target) - float(trigger)
        except (TypeError, ValueError):
            return None
        if risk <= 0:
            return None
        return round(reward / risk, 2)
    return None


def get_trades(limit=50):
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT signal_date, symbol, entry_trigger, stop, target, 
               risk_pct, outcome, pullback, impulse
        FROM swing_signals
        WHERE outcome IN ('WIN', 'LOSS', 'TIMEOUT', 'EXPIRED', 'OPEN', 'PENDING')
        ORDER BY signal_date DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [
        {'date': r[0], 'symbol': r[1], 'trigger': r[2], 'stop': r[3],
         'target': r[4], 'risk_pct': r[5], 'outcome': r[6], 
         'pullback': r[7], 'impulse': r[8],
         'r_multiple': trade_r_multiple(r[6], r[2], r[3], r[4])}
        for r in rows
    ]