"""
Paper-Trade Ledger & System Stats (N3).
Reads graded swing_signals and computes system-level performance:
Win Rate, Profit Factor, Expectancy (R), Max Drawdown.
"""
import db

def compute_stats(conn=None):
    own = conn is None
    if own:
        conn = db.get_conn()
    
    rows = conn.execute("""
        SELECT symbol, entry_trigger, stop, target, outcome 
        FROM swing_signals 
        WHERE outcome IN ('WIN', 'LOSS', 'TIMEOUT', 'EXPIRED')
        ORDER BY signal_date
    """).fetchall()
    
    if not rows:
        if own: conn.close()
        return None

    trades = []
    for sym, trig, stop, tgt, out in rows:
        if not trig or not stop or not tgt:
            continue
        risk = trig - stop
        if risk <= 0:
            continue
        if out == 'WIN':
            r_mult = (tgt - trig) / risk
        elif out == 'LOSS':
            r_mult = -1.0
        elif out == 'TIMEOUT':
            r_mult = 0.0
        else: # EXPIRED
            continue
            
        trades.append({'r_mult': r_mult})

    if not trades:
        if own: conn.close()
        return None

    wins = sum(1 for t in trades if t['r_mult'] > 0)
    losses = sum(1 for t in trades if t['r_mult'] < 0)
    total = len(trades)
    win_rate = wins / total if total else 0
    
    gross_profit = sum(t['r_mult'] for t in trades if t['r_mult'] > 0)
    gross_loss = abs(sum(t['r_mult'] for t in trades if t['r_mult'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999.0
    
    total_r = sum(t['r_mult'] for t in trades)
    expectancy = total_r / total if total else 0
    
    cum_r = 0
    peak = 0
    max_dd = 0
    for t in trades:
        cum_r += t['r_mult']
        if cum_r > peak:
            peak = cum_r
        dd = peak - cum_r
        if dd > max_dd:
            max_dd = dd

    stats = {
        'total_trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': round(win_rate * 100, 1),
        'profit_factor': round(profit_factor, 2),
        'expectancy_r': round(expectancy, 2),
        'total_r': round(total_r, 2),
        'max_drawdown_r': round(max_dd, 2)
    }
    
    if own: conn.close()
    return stats

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
         'pullback': r[7], 'impulse': r[8]}
        for r in rows
    ]