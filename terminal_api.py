import os
import datetime as dt
import pandas as pd
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import secrets

import db
import scheduler_bg
from contextlib import asynccontextmanager

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    scheduler_bg.start()
    yield
    scheduler_bg.stop()

APP_USER = os.getenv("ADMIN_USER", "ankit")
APP_PASS = os.getenv("ADMIN_PASS", "change_this_password")

security = HTTPBasic()

app = FastAPI(title="NSE Intelligence Terminal", version="3.0",
              lifespan=lifespan)

app.mount("/static", StaticFiles(directory="terminal/static"),
          name="static")


def verify_user(credentials: HTTPBasicCredentials = Depends(security)):
    user_ok = secrets.compare_digest(credentials.username, APP_USER)
    pass_ok = secrets.compare_digest(credentials.password, APP_PASS)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def safe_float(v, nd=2):
    try:
        if v is None:
            return None
        return round(float(v), nd)
    except Exception:
        return None


def get_conn():
    return db.get_conn()


@app.get("/")
def root(user: str = Depends(verify_user)):
    return FileResponse("terminal/static/index.html")


@app.get("/api/health")
def health(user: str = Depends(verify_user)):
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
    except Exception:
        n = 0
    conn.close()
    return {
        "ok": True,
        "prices_rows": n,
        "time": dt.datetime.now().isoformat(),
    }


@app.get("/api/regime")
def regime(user: str = Depends(verify_user)):
    try:
        from regime import MarketRegime
        rg = MarketRegime.compute()
        return {
            "ok": True,
            "is_bullish": rg.is_bullish,
            "stance": "BULLISH" if rg.is_bullish else "DEFENSIVE",
            "symbol": rg.symbol,
            "index_close": rg.index_close,
            "ema10": rg.ema10,
        }
    except Exception as e:
        return {
            "ok": False,
            "stance": "UNAVAILABLE",
            "error": str(e),
        }


@app.get("/api/swing/signals")
def swing_signals(limit: int = 80,
                  user: str = Depends(verify_user)):
    import swing_live

    conn = get_conn()
    swing_live.ensure(conn)

    rows = conn.execute(
        "SELECT signal_date, symbol, entry_trigger, stop, target, "
        "risk_pct, pullback, impulse, ema_zone, outcome "
        "FROM swing_signals "
        "ORDER BY signal_date DESC LIMIT ?",
        (limit,),
    ).fetchall()

    signals = []
    for r in rows:
        signals.append({
            "date": r[0],
            "symbol": r[1],
            "trigger": safe_float(r[2]),
            "stop": safe_float(r[3]),
            "target": safe_float(r[4]),
            "risk_pct": safe_float(r[5]),
            "pullback": safe_float(r[6], 3),
            "impulse": safe_float(r[7], 3),
            "ema_zone": r[8],
            "outcome": r[9],
        })

    score = {}
    for outcome, n in conn.execute(
        "SELECT outcome, COUNT(*) FROM swing_signals "
        "GROUP BY outcome"
    ).fetchall():
        score[outcome] = n

    conn.close()

    import meta_model
    for s in signals:
        r = meta_model.score_symbol(s["symbol"], use_yahoo=False)
        s["p_win"] = r["p_win"] if r and r.get("p_win") is not None else None
    signals.sort(key=lambda x: -(x["p_win"] if x["p_win"] is not None else -1))

    wins = score.get("WIN", 0)
    losses = score.get("LOSS", 0)
    graded = wins + losses

    return {
        "signals": signals,
        "scorecard": score,
        "win_rate": round(100 * wins / graded, 1) if graded else None,
    }


@app.post("/api/swing/scan")
def run_swing_scan(bg: BackgroundTasks,
                   user: str = Depends(verify_user)):
    import swing_live
    bg.add_task(swing_live.update_outcomes)
    bg.add_task(swing_live.scan)
    return {"started": True}


@app.get("/api/radar")
def radar(user: str = Depends(verify_user)):
    conn = get_conn()

    rows = conn.execute(
        "SELECT symbol, perf1m, perf3m, relvol, mcap_cr "
        "FROM universe_broad ORDER BY mcap_cr DESC"
    ).fetchall()

    groups = {
        "Momentum": [],
        "Volume Spike": [],
        "Turnaround": [],
    }

    for sym, p1, p3, rv, mc in rows:
        p1v = p1 or 0
        p3v = p3 or 0
        rvv = rv or 0

        item = {
            "symbol": sym,
            "perf1m": safe_float(p1v),
            "perf3m": safe_float(p3v),
            "relvol": safe_float(rvv),
            "mcap_cr": safe_float(mc),
        }

        if rvv >= 2:
            groups["Volume Spike"].append(item)
        elif p1v >= 10 and p3v >= 8:
            groups["Momentum"].append(item)
        elif p1v >= 7 and p3v <= 0:
            groups["Turnaround"].append(item)

    for k in groups:
        groups[k] = groups[k][:40]

    events = []
    try:
        erows = conn.execute(
            "SELECT kind, symbol, text FROM events "
            "WHERE date=(SELECT MAX(date) FROM events) "
            "LIMIT 30"
        ).fetchall()
        for kind, sym, text in erows:
            events.append({
                "kind": kind,
                "symbol": sym,
                "text": text,
            })
    except Exception:
        pass

    conn.close()

    import meta_model
    for k in groups:
        for item in groups[k]:
            r = meta_model.score_symbol(item["symbol"], use_yahoo=False)
            item["p_win"] = r["p_win"] if r and r.get("p_win") is not None else None
        groups[k].sort(key=lambda x: -(x["p_win"] if x["p_win"] is not None else -1))

    return {
        "groups": groups,
        "events": events,
        "total": len(rows),
    }


@app.get("/api/cockpit/{symbol}/chart")
def cockpit_chart(symbol: str,
                  user: str = Depends(verify_user)):
    sym = symbol.upper()
    conn = get_conn()

    rows = conn.execute(
        "SELECT date, open, high, low, close, volume "
        "FROM prices_daily WHERE symbol=? ORDER BY date",
        (sym,),
    ).fetchall()

    conn.close()

    if not rows:
        return {
            "symbol": sym,
            "candles": [],
            "ema10": [],
            "ema20": [],
            "ema50": [],
            "ema200": [],
            "swing": None,
        }

    df = pd.DataFrame(
        list(rows),
        columns=["date", "open", "high", "low", "close", "volume"],
    )
    df["date"] = pd.to_datetime(df["date"])

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.tail(420).copy()

    df["ema10"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    candles = []
    for _, r in df.iterrows():
        candles.append({
            "time": r["date"].strftime("%Y-%m-%d"),
            "open": safe_float(r["open"]),
            "high": safe_float(r["high"]),
            "low": safe_float(r["low"]),
            "close": safe_float(r["close"]),
        })

    def line(col):
        out = []
        for _, r in df.iterrows():
            val = safe_float(r[col])
            if val is not None:
                out.append({
                    "time": r["date"].strftime("%Y-%m-%d"),
                    "value": val,
                })
        return out

    swing = None
    try:
        from setup import SetupDetector
        raw = df.rename(columns={
            "close": "Close",
            "high": "High",
            "low": "Low",
            "volume": "Volume",
        })
        raw = raw.set_index("date")
        st = SetupDetector.detect(raw, sym)
        if st.triggered:
            swing = {
                "trigger": st.entry_price,
                "stop": st.stop_loss,
                "target": st.target_price,
                "pullback": st.pullback_depth,
                "impulse": st.impulse_pct,
                "zone": st.ema_proximity,
            }
    except Exception:
        swing = None

    return {
        "symbol": sym,
        "candles": candles,
        "ema10": line("ema10"),
        "ema20": line("ema20"),
        "ema50": line("ema50"),
        "ema200": line("ema200"),
        "swing": swing,
    }


@app.get("/api/cockpit/{symbol}/summary")
def cockpit_summary(symbol: str,
                    user: str = Depends(verify_user)):
    sym = symbol.upper()
    conn = get_conn()

    sector = None
    mcap = None
    fund_score = None
    status = None

    r = conn.execute("SELECT sector FROM stocks WHERE symbol=?",
                     (sym,)).fetchone()
    if r:
        sector = r[0]

    r = conn.execute("SELECT mcap_cr FROM universe_broad WHERE symbol=?",
                     (sym,)).fetchone()
    if r:
        mcap = safe_float(r[0])

    r = conn.execute(
        "SELECT fundamental_score FROM scan_results "
        "WHERE symbol=? ORDER BY scan_date DESC LIMIT 1",
        (sym,),
    ).fetchone()
    if r:
        fund_score = safe_float(r[0])

    r = conn.execute(
        "SELECT status FROM pipeline WHERE symbol=?",
        (sym,),
    ).fetchone()
    if r:
        status = r[0]

    news = []
    try:
        rows = conn.execute(
            "SELECT title, age_days, label FROM sentiment_headlines "
            "WHERE symbol=? ORDER BY age_days LIMIT 8",
            (sym,),
        ).fetchall()
        for title, age, label in rows:
            news.append({
                "title": title,
                "age_days": age,
                "label": label,
            })
    except Exception:
        pass

    conn.close()

    return {
        "symbol": sym,
        "sector": sector,
        "mcap_cr": mcap,
        "fund_score": fund_score,
        "status": status,
        "news": news,
    }

@app.get("/api/meta/{symbol}")
def meta_score(symbol: str, user: str = Depends(verify_user)):
    import meta_model
    try:
        r = meta_model.score_symbol(symbol.upper())
        return r or {"symbol": symbol, "p_win": None, "why": []}
    except Exception as e:
        return {"symbol": symbol, "p_win": None, "why": [],
                "error": str(e)}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "terminal_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )