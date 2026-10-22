"""
On-Demand Screener — baseline (Stage-2 + momentum + volume) + VCP/pullback checks.
DB-first (prices_daily), Yahoo fallback for unknown symbols (single-symbol mode only).

Usage:
  python screener_engine.py RELIANCE   -> full check breakdown for one stock
  python screener_engine.py scan       -> run over top smallcap band (DB-only)
  python screener_engine.py scan-all   -> run over the WHOLE band (~855 names)
"""
import sys
import json
import datetime as dt
import pandas as pd
from data_sources import fetch_price_history
import db
import universe_helper as U
from scanner import Screener
from setup import SetupDetector


# ==========================================
# 1. DATA FETCHING (DB-first, on-demand)
# ==========================================
def _from_db(ticker):
    try:
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT date, open, high, low, close, volume "
            "FROM prices_daily WHERE symbol=? ORDER BY date",
            (ticker,)).fetchall()
        conn.close()
    except Exception:
        return None
    if len(rows) < 240:
        return None
    df = pd.DataFrame(list(rows),
                      columns=["date", "Open", "High", "Low",
                               "Close", "Volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Close"])


def _from_yahoo(ticker, period_days=550):
    try:
        # One shared chain (data_sources, F-15/ID52): it repairs the yfinance
        # tz cache before fetching (a broken cache returns an EMPTY frame,
        # indistinguishable from "no such symbol") and falls back to the
        # NSE-backed providers when Yahoo fails.
        end = dt.date.today()
        start = end - dt.timedelta(days=period_days)
        df = fetch_price_history(ticker,
                                 start=start.isoformat(),
                                 end=end.isoformat())
        if df is None or df.empty or len(df) < 240:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None


def fetch_stock_data(ticker, period_days=550, allow_yahoo=True):
    """18 months (~550 days) ensures enough history for EMA200 + 52W high."""
    df = _from_db(ticker)
    if df is None and allow_yahoo:
        df = _from_yahoo(ticker, period_days=period_days)
    return df


def fetch_index_data(index_ticker=None):
    """Benchmark data for the global regime filter.
    Tries multiple index candidates if none specified."""
    candidates = ([index_ticker] if index_ticker else
                  ["^CNXSMALLCAP", "^CNXSC",
                   "NIFTY_SMALLCAP_100.NS", "^NSEI"])
    for sym in candidates:
        try:
            df = fetch_price_history(sym, period="1mo")
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df
        except Exception:
            continue
    return None


# ==========================================
# 2. GLOBAL REGIME FILTER (top-down gatekeeper)
# ==========================================
def check_global_regime():
    idx_df = fetch_index_data()
    if idx_df is None or len(idx_df) < 10:
        return False, "Index Data Unavailable"
    idx_df["EMA_10"] = idx_df["Close"].ewm(span=10, adjust=False).mean()
    latest_close = idx_df["Close"].iloc[-1]
    latest_ema = idx_df["EMA_10"].iloc[-1]
    is_bullish = bool(latest_close > latest_ema)
    status = ("BULLISH (Entries Allowed)" if is_bullish
              else "DEFENSIVE (Cash Mode)")
    return is_bullish, status


# ==========================================
# 3. MAIN SCREENER ENGINE (baseline + VCP)
# ==========================================
def evaluate_stock(ticker, allow_yahoo=True):
    """Evaluate one stock with the SAME rules the live strategy trades on.

    Until 2026-10-23 this function carried its own copy of the Stage-2/VCP
    logic. It drifted from the official engine: measured over 745 symbols the
    two disagreed on the baseline for 33 names and on the VCP setup for 50
    (this copy passed 13, the official engine 41). The tab could therefore
    contradict the scan that actually generates the signals.

    It now delegates to the two modules swing_live composes:

        Screener.evaluate    -> Stage-2 + liquidity + momentum + volume
        SetupDetector.detect -> VCP / pullback setup

    so there is exactly one definition of "a setup". Display metrics that
    neither engine returns (52-week proximity, recent range) are measured from
    the same frame and are presentation only - they never decide pass/fail.
    """
    df = _from_db(ticker)
    source = "prices_daily"
    if df is None and allow_yahoo:
        df = _from_yahoo(ticker)
        source = "Yahoo Finance"
    if df is None:
        return {"error": "Insufficient data or invalid ticker."}

    df = df.copy()
    as_of = str(df.index[-1].date())

    base = Screener.evaluate(df, ticker)
    if base.close is None:
        return {"error": "Insufficient history for the official screener "
                         "(needs about 272 sessions)."}
    st = SetupDetector.detect(df, ticker)

    close = float(df["Close"].iloc[-1])
    high_52w = float(df["High"].tail(252).max())
    prox_52w = (close / high_52w * 100) if high_52w else 0.0
    recent = df.tail(3)
    range_pct = (float((recent["High"] - recent["Low"]).max()) / close * 100
                 if close else 0.0)

    # swing_live also requires the setup to be on the latest bar, so a stale
    # pattern must not count as actionable here either.
    setup_today = bool(st.triggered and st.signal_date == as_of)
    if st.triggered and not setup_today:
        setup_reason = f"last setup on {st.signal_date}, not today's bar"
    elif st.triggered:
        setup_reason = "triggered on today's bar"
    else:
        setup_reason = " · ".join(st.reasons) if st.reasons else "no setup"

    def _pct(value):
        return f"{value * 100:.2f}%" if value is not None else "—"

    return {
        "ticker": ticker,
        "as_of": as_of,
        "source": source,
        "overall_signal": bool(base.passed and setup_today),
        "current_price": f"{close:.2f}",
        "ema_200": (f"{base.ema200:.2f}" if base.ema200 is not None
                    else "N/A"),
        "momentum_1m": _pct(base.mom_1m),
        "momentum_3m": _pct(base.mom_3m),
        "proximity_52w": f"{prox_52w:.2f}%",
        "impulse_gain": _pct(st.impulse_pct) if st.triggered else "—",
        "pullback_depth": _pct(st.pullback_depth) if st.triggered else "—",
        "days_since_high": int(st.pullback_days) if st.triggered else "—",
        "tightness_pct": f"{range_pct:.2f}%",
        "setup_reason": setup_reason,
        "checks": {
            "Baseline (official strategy)": bool(base.passed),
            "Stage 2 trend": bool(base.mandatory),
            "Liquidity": bool(base.liquid),
            "Momentum trigger": bool(base.momentum_hit),
            "Volume spike": bool(base.volume_explosive),
            "VCP / pullback setup": setup_today,
        },
    }

def screen_universe(limit=60, show=True, allow_yahoo=False, progress=None):
    """Run the screener over the smallcap/midcap band (DB-only = fast).

    `limit=None` scans the WHOLE band instead of the top slice — ~855 names,
    roughly 30 seconds on the laptop, which is why the API runs it in the
    background rather than inside the request.

    `progress(done, total, hits)` is called after every symbol if supplied.
    It is wrapped so a broken progress callback can never abort a scan that is
    already half finished.
    """
    conn = db.get_conn()
    try:
        syms = U.band_universe(conn, limit)
    finally:
        conn.close()
    total = len(syms)
    hits = []
    for done, sym in enumerate(syms, 1):
        try:
            r = evaluate_stock(sym, allow_yahoo=allow_yahoo)
        except Exception as e:
            # One bad symbol must never kill the whole band scan.
            r = {"error": str(e)}
        if r.get("overall_signal"):
            hits.append(r)
            if show:
                print(f"   ✅ {sym}: price {r['current_price']}  "
                      f"PB {r['pullback_depth']}  "
                      f"tight {r['tightness_pct']}")
        if progress is not None:
            try:
                progress(done, total, len(hits))
            except Exception:
                pass
    if show:
        print(f"screener hits: {len(hits)} / {len(syms)}")
    return hits


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        screen_universe()
    elif len(sys.argv) > 1 and sys.argv[1] == "scan-all":
        # Whole band. Prints a progress line every 50 names so a long run
        # never looks hung when it is run by hand.
        screen_universe(
            limit=None,
            progress=lambda done, total, hits: (
                print(f"  ... {done}/{total} scanned, {hits} hits")
                if done % 50 == 0 or done == total else None))
    elif len(sys.argv) > 1:
        print(json.dumps(evaluate_stock(sys.argv[1].upper()), indent=1))
    else:
        ok, status = check_global_regime()
        print(status)