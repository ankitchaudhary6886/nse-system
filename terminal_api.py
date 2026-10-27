import os
import json
import time
import threading
import datetime as dt
import pandas as pd
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import (FastAPI, HTTPException, status, BackgroundTasks, Header,
                     Query, Body)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import secrets
import db
import scheduler_bg

load_dotenv()
API_HOST = os.getenv("API_HOST", "127.0.0.1")


def _startup_freshness():
    """Repair a gap left by a missed cron or a service restart.

    Delayed two seconds so the web server starts accepting requests first. The
    function is idempotent and lock-guarded, so a portal-open check racing with
    it simply joins the same result instead of fetching twice.
    """
    import time
    import logging
    time.sleep(2)
    try:
        import data_freshness
        result = data_freshness.ensure_fresh(start_background=True)
        logging.getLogger(__name__).info(
            "startup freshness: %s", result.get("message"))
    except Exception:
        logging.getLogger(__name__).exception("startup freshness failed")


@asynccontextmanager
async def lifespan(app):
    # One scheduler per system, not per machine: the VM owns the scheduled
    # chain. A laptop/second instance must set DISABLE_SCHEDULER=1 or it would
    # duplicate every job (and every Telegram alert).
    if os.getenv("DISABLE_SCHEDULER", "").strip() not in ("1", "true", "yes"):
        scheduler_bg.start()
        threading.Thread(target=_startup_freshness, daemon=True,
                         name="startup-freshness").start()
    yield
    scheduler_bg.stop()


app = FastAPI(title="NSE Intelligence Terminal", version="24.1",
              lifespan=lifespan)
app.mount("/static", StaticFiles(directory="terminal/static"),
          name="static")

_TRADER_FULL_SCAN_CACHE = {}
_TRADER_FULL_SCAN_TTL = 1800
_SWING_SCAN_LOCK = threading.Lock()
_SWING_SCAN_STATE = {
    "running": False, "status": "idle", "message": "No swing scan run yet.",
    "started_at": None, "finished_at": None,
}

# Whole-band screener scan (N1). ~855 symbols at ~35ms each is around 30
# seconds, far too long to hold an HTTP request open from a phone, so it runs
# as a background task and the UI polls the status endpoint — same shape as
# the swing scan above.
_BAND_SCAN_LOCK = threading.Lock()
_BAND_SCAN_STATE = {
    "running": False, "status": "idle", "message": "The whole band has not been scanned yet.",
    "scanned": 0, "total": 0, "hits": [],
    "started_at": None, "finished_at": None,
}


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
def root():
    return FileResponse("terminal/static/index.html")


@app.get("/api/health")
def health():
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM prices_daily").fetchone()[0]
    except Exception:
        n = 0
    conn.close()
    return {"ok": True, "prices_rows": n,
            "time": dt.datetime.now().isoformat()}


@app.get("/api/data/health")
def data_health():
    """One-shot health for the ⚡ Data banner: prices, freshness gate, Fyers
    token, today's artifact counts, scheduler and the last refresh run."""
    import refresh_pipeline
    return refresh_pipeline.health()


@app.get("/api/data/freshness")
def data_freshness_status():
    """Read-only freshness assessment plus the guard's current state."""
    import data_freshness
    return data_freshness.status()


@app.get("/api/data/ensure")
def data_ensure(days_back: int = 15, background: bool = True):
    """Self-heal before a portal load.

    The official archive retry is synchronous and fast; if it cannot close the
    gap, the existing full refresh chain is started in the background and the
    caller can poll ``/api/refresh/status``. This is the endpoint the UI calls
    on every page open.
    """
    import data_freshness
    return data_freshness.ensure_fresh(days_back=days_back,
                                       start_background=background)


@app.get("/api/refresh/status")
def refresh_status():
    import refresh_pipeline
    return refresh_pipeline.status()


@app.post("/api/refresh")
def refresh_now():
    """One-click refresh: start the daily chain in a background thread."""
    import refresh_pipeline
    return refresh_pipeline.start_background(trigger="ui")


@app.get("/api/fyers/login-url")
def fyers_login_url():
    """Return the OAuth URL the ⚡ panel opens in a new tab."""
    import fyers_client
    try:
        conf = fyers_client.credentials()
        return {"ok": True, "url": fyers_client.build_auth_url(),
                "app_configured": bool(conf["app_id"])}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@app.post("/api/fyers/exchange")
def fyers_exchange(payload: dict = Body(...)):
    """Save a pasted auth_code. The response never contains the token."""
    import fyers_client
    code = str((payload or {}).get("code") or "").strip()
    if not code:
        return {"ok": False, "error": "missing auth code"}
    return fyers_client.exchange_code(code)


@app.post("/api/fyers/refresh")
def fyers_refresh():
    """Renew the access token from the stored refresh token + FYERS_PIN."""
    import fyers_client
    try:
        return fyers_client.FyersClient().refresh_access_token()
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@app.get("/api/sources")
def source_health():
    from data_sources import get_registry
    return {"sources": get_registry().health(),
            "time": dt.datetime.now().isoformat()}


@app.get("/api/ideals")
def ideals_index():
    """Every ideal value band, so the UI can show "actual vs ideal" anywhere.

    Bands come from the system's own rules first (strategy_config gates,
    scoring/fund_veto thresholds, trader-library thresholds), then from
    long-standing convention where the system is silent. Each carries its
    `source` so the owner can see why a number counts as good.
    """
    import ideal
    return {"ok": True,
            "groups": [{"label": label, "keys": keys}
                       for label, keys in ideal.GROUPS],
            "bands": ideal.catalog()}


@app.get("/api/ideals/{key}")
def ideal_one(key: str, actual: float = None):
    """One measure compared with its ideal. `?actual=` is optional."""
    import ideal
    item = ideal.assess(key, actual)
    if item is None:
        return {"ok": False, "key": key,
                "message": "No ideal band is stored for that measure.",
                "known": sorted(ideal.BANDS)}
    return {"ok": True, "assessment": item}


@app.get("/glossary", response_class=HTMLResponse)
def glossary_page():
    """Every term explained in ordinary words, generated from explain.py."""
    import glossary_ui
    return glossary_ui.render()


@app.get("/api/explain")
def explain_index():
    """List every term that can be explained, for the UI's help index."""
    import explain
    return {"ok": True,
            "sections": [{"key": k, "label": label}
                         for k, label in explain.SECTIONS],
            "terms": explain.catalog()}


@app.get("/api/explain/{key}")
def explain_term(key: str):
    """Plain-language 5W1H for one term.

    Everything the owner sees is meant to be clickable and answerable in
    ordinary words, so this is the single source for those answers.
    """
    import explain
    entry = explain.get(key)
    if entry is None:
        return {"ok": False, "key": key,
                "message": "No explanation is stored for that item yet.",
                "known": explain.all_keys()}
    return {"ok": True, "key": key.strip().lower(), "entry": entry,
            "sections": [{"key": k, "label": label}
                         for k, label in explain.SECTIONS]}


@app.get("/api/deployment-check")
def deployment_check():
    conn = get_conn()
    out = {"checks": [], "fails": 0}
    today = dt.date.today()

    def add(ok, label, detail=""):
        out["checks"].append({"ok": ok, "label": label, "detail": detail})
        if not ok:
            out["fails"] += 1

    def heartbeat(artifact, max_days=3):
        """Last successful writer run, even when it correctly wrote 0 signals."""
        try:
            r = conn.execute(
                "SELECT MAX(run_at) FROM freshness_gate_log WHERE artifact=?",
                (artifact,)).fetchone()
            if not r or not r[0]:
                return None
            d = dt.date.fromisoformat(str(r[0])[:10])
            if (today - d).days <= max_days:
                return str(r[0])[:19]
        except Exception:
            return None
        return None

    def _clean(val):
        s = str(val)
        if ":" in s and s.split(":", 1)[0] in ("tv", "csv", "calc"):
            return s.split(":", 1)[1]
        return s

    for table, col, max_days in [
        ("prices_daily", "date", 5),
        ("technicals_daily", "date", 5),
        ("universe_broad", "updated_at", 30),
        ("fundamentals", "uploaded_at", 30),
        ("swing_signals", "signal_date", 14),
        ("trend_candidates", "date", 5),
        ("value_radar", "date", 30),
        ("positional_picks", "date", 30),
        ("pwin_daily", "date", 14),
    ]:
        try:
            r = conn.execute(f"SELECT MAX({col}) FROM {table}").fetchone()
            latest = r[0] if r else None
            if not latest:
                add(False, table, "empty")
                continue
            cleaned = _clean(latest)
            d = dt.date.fromisoformat(str(cleaned)[:10])
            age = (today - d).days
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if table == "swing_signals" and age > max_days:
                hb = heartbeat("swing_live")
                if hb:
                    n_today = conn.execute(
                        "SELECT COUNT(*) FROM swing_signals WHERE signal_date=?",
                        (today.isoformat(),)).fetchone()[0]
                    add(True, table,
                        f"scanner ran {hb}; {n_today} new signals today")
                    continue
            add(age <= max_days, table,
                f"latest {str(cleaned)[:10]} ({age}d), {n} rows")
        except Exception as e:
            add(False, table, f"err: {e}")

    try:
        n = conn.execute("SELECT COUNT(*) FROM strategy_runs").fetchone()[0]
        add(n > 0, "strategy_runs", f"{n} runs")
    except Exception as e:
        add(False, "strategy_runs", str(e))

    try:
        n = conn.execute("SELECT COUNT(*) FROM setup_pool").fetchone()[0]
        add(n > 0, "setup_pool", f"{n} setups")
    except Exception as e:
        add(False, "setup_pool", str(e))

    try:
        iso = today.isoformat()
        n = conn.execute(
            "SELECT COUNT(*) FROM swing_signals WHERE signal_date=?",
            (iso,)).fetchone()[0]
        add(True, "swing signals today", f"{n} signals")
        n2 = conn.execute(
            "SELECT COUNT(*) FROM trend_candidates WHERE date=?",
            (iso,)).fetchone()[0]
        add(True, "trend candidates today", f"{n2} stocks")
    except Exception as e:
        add(False, "today's activity", str(e))

    conn.close()

    try:
        from alerts import _creds
        tok, chat = _creds()
        add(bool(tok and chat), "telegram creds",
            "secret file" if tok else "MISSING")
    except Exception as e:
        add(False, "telegram creds", str(e))

    out["summary"] = ("ALL CHECKS PASSED" if out["fails"] == 0
                      else f"{out['fails']} checks failed")
    out["time"] = dt.datetime.now().isoformat(timespec="seconds")
    return out


@app.get("/api/regime")
def regime():
    try:
        from regime import MarketRegime
        rg = MarketRegime.compute()
        return {"ok": True, "is_bullish": rg.is_bullish,
                "level": rg.level, "size_mult": rg.size_mult,
                "allows_swing": rg.allows_swing,
                "allows_aw": rg.allows_aw, "stance": rg.level,
                "symbol": rg.symbol, "index_close": rg.index_close,
                "ema10": rg.ema10, "ema20": rg.ema20,
                "ema10_slope_pct": rg.ema10_slope_pct}
    except Exception as e:
        return {"ok": False, "stance": "UNAVAILABLE", "error": str(e)}


@app.get("/api/macro")
def macro_flow():
    import macro
    try:
        data = macro.latest()
        if data:
            return data
    except Exception as e:
        print(f"[MACRO] api failed: {e}")
    return {"fii_net": None, "dii_net": None, "net_flow": None}


# ============================================================
# Traders (Phase 3.5 — framework for famous-trader methods)
# ============================================================
@app.get("/api/traders")
def list_traders_api():
    import traders
    try:
        return {"traders": traders.list_traders()}
    except Exception as e:
        return {"traders": [], "error": str(e)}


@app.get("/api/traders/{slug}")
def get_trader_api(slug: str):
    import traders
    t = traders.get_trader(slug)
    if not t:
        raise HTTPException(status_code=404, detail="trader not found")
    return {"slug": t.SLUG, "name": t.NAME, "pillar": t.PILLAR,
            "source": t.SOURCE, "methods": t.METHODS}


@app.get("/api/traders/{slug}/scan")
def scan_trader_api(slug: str, limit: int = 800):
    import traders
    t = traders.get_trader(slug)
    if not t:
        raise HTTPException(status_code=404, detail="trader not found")
    try:
        sigs = t.scan(limit=limit)
        return {"slug": slug, "name": t.NAME, "n_signals": len(sigs),
                "signals": sigs}
    except Exception as e:
        return {"slug": slug, "error": str(e), "signals": []}


@app.get("/api/traders/matches/{symbol}")
def trader_matches_api(symbol: str):
    import re
    import traders
    import db
    from universe_helper import band_universe

    sym = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9&.-]{1,20}", sym):
        raise HTTPException(status_code=422, detail="invalid NSE symbol")

    conn = db.get_conn()
    try:
        prices_as_of = conn.execute(
            "SELECT MAX(date) FROM prices_daily").fetchone()[0]
        universe = set(band_universe(conn, limit=800))
        if sym not in universe:
            return {
                "symbol": sym, "as_of": prices_as_of,
                "in_scan_universe": False, "n_traders_checked": 0,
                "n_methods_matched": 0, "matches": [], "errors": [],
                "message": "Symbol is outside the current 800-symbol trader scan universe.",
            }

        cross_sectional = {
            "oshaughnessy", "quantitative_value",
            "value_investing_made_easy",
        }
        matches = []
        errors = []
        checked = 0
        for trader in traders.REGISTRY:
            try:
                if trader.SLUG in cross_sectional:
                    cache = _TRADER_FULL_SCAN_CACHE.get(trader.SLUG)
                    if (cache and cache[0] == prices_as_of
                            and time.monotonic() - cache[1]
                            < _TRADER_FULL_SCAN_TTL):
                        signals = cache[2]
                    else:
                        signals = trader.scan(conn=conn, limit=800)
                        _TRADER_FULL_SCAN_CACHE[trader.SLUG] = (
                            prices_as_of, time.monotonic(), signals)
                    signals = [signal for signal in signals
                               if signal.get("symbol") == sym]
                else:
                    signals = trader.scan(
                        conn=conn, limit=800, symbols=[sym])
                checked += 1
                methods = {
                    method.get("id"): method
                    for method in trader.METHODS
                    if method.get("id")
                }
                for signal in signals:
                    method_id = signal.get("method")
                    matches.append({
                        "trader": trader.NAME,
                        "slug": trader.SLUG,
                        "source": trader.SOURCE,
                        "method": methods.get(method_id, {
                            "id": method_id,
                            "name": method_id or "Unnamed method",
                            "description": "",
                        }),
                        "signal": _jsonable(signal),
                    })
            except Exception as e:
                errors.append({"trader": trader.NAME,
                               "error": str(e)})
        return {
            "symbol": sym, "as_of": prices_as_of,
            "in_scan_universe": True,
            "n_traders_checked": checked,
            "n_methods_matched": len({
                (item["slug"], item["method"].get("id"))
                for item in matches
            }),
            "matches": _jsonable(matches), "errors": _jsonable(errors),
        }
    finally:
        conn.close()


# ============================================================
# Trader League (#087) — Rs 10 lakh paper league + pre-deployment
# backtest of our system. Engine: trader_league.py. The heavy replay
# runs as a low-priority background process; the rest are DB reads.
# ============================================================
def _jsonable(value):
    """Recursively convert numpy/pandas scalars into plain Python JSON types.

    Trader methods compute with pandas/numpy, so a signal can carry numpy.bool_
    or numpy.float64. Returning those straight from a handler makes FastAPI's
    encoder raise ("'numpy.bool' object is not iterable") and the endpoint
    answers 500 -- which is what broke /api/traders/matches/{symbol}.
    """
    try:
        import numpy as _np
    except Exception:
        _np = None

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if _np is not None:
        if isinstance(value, _np.generic):
            return value.item()
        if isinstance(value, _np.ndarray):
            return [_jsonable(v) for v in value.tolist()]

    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _league_mode(mode, ex):
    return (mode if mode in ("backtest", "live") else "backtest",
            ex if ex in ("book", "common") else "book")


@app.get("/api/league/overview")
def league_overview(mode: str = "backtest",
                    ex: str = Query("book", alias="exit")):
    import trader_league as TL
    mode, ex = _league_mode(mode, ex)
    try:
        return TL.overview(mode, ex)
    except Exception as e:
        return {"mode": mode, "exit": ex, "rows": [], "error": str(e)}


@app.get("/api/league/player/{slug}")
def league_player(slug: str, mode: str = "backtest",
                  ex: str = Query("book", alias="exit")):
    import trader_league as TL
    mode, ex = _league_mode(mode, ex)
    try:
        return TL.player_detail(slug, mode, ex)
    except Exception as e:
        return {"slug": slug, "playing": False, "error": str(e)}


@app.get("/api/league/status")
def league_status():
    import trader_league as TL
    try:
        return TL.status()
    except Exception as e:
        return {"players": [], "error": str(e)}


@app.post("/api/league/simulate")
def league_simulate(mode: str = "backtest"):
    import trader_league as TL
    mode, _ = _league_mode(mode, "book")
    return TL.start_simulation(mode)


@app.post("/api/league/replay")
def league_replay(years: float = 3, symbols: int = 300, workers: int = 1):
    import trader_league as TL
    years = min(max(float(years), 0.5), 10.0)
    symbols = min(max(int(symbols), 20), 1500)
    workers = min(max(int(workers), 1), 8)
    try:
        return TL.start_replay_process(years, symbols, workers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Strategies
# ============================================================
@app.get("/api/strategies")
def list_strategies():
    import rule_engine
    return {"strategies": rule_engine.load_strategies()}


@app.post("/api/strategies/seed")
def seed_strategies(force: bool = False):
    import rule_engine
    n = rule_engine.seed_if_empty(force=force)
    return {"seeded": n}


@app.post("/api/strategies/run-all")
def run_all_strategies():
    import rule_engine
    try:
        return {"results": rule_engine.run_all()}
    except Exception as e:
        return {"error": str(e), "results": {}}


@app.post("/api/strategies/backtest-cache/clear")
def clear_backtest_cache(name: str = None):
    import strategy_backtest
    try:
        strategy_backtest.clear_cache(name)
        return {"cleared": True, "name": name}
    except Exception as e:
        return {"cleared": False, "error": str(e)}


@app.get("/api/strategies/{name}")
def get_strategy(name: str):
    import rule_engine
    s = rule_engine.get_strategy(name)
    if not s:
        raise HTTPException(status_code=404, detail="not found")
    return s


@app.post("/api/strategies/{name}")
def save_strategy(name: str, payload: dict):
    import rule_engine
    rule_engine.save_strategy(name, payload)
    return {"saved": True, "name": name}


@app.delete("/api/strategies/{name}")
def delete_strategy(name: str):
    import rule_engine
    rule_engine.delete_strategy(name)
    return {"deleted": True, "name": name}


@app.get("/api/strategies/{name}/run")
def run_strategy_api(name: str, limit: int = 30):
    import rule_engine
    try:
        return rule_engine.run_strategy(name, limit=limit)
    except Exception as e:
        return {"error": str(e), "picks": []}


@app.get("/api/strategies/{name}/backtest")
def backtest_strategy_api(name: str, years: int = 2, step: int = 5,
                          universe_limit: int = 150,
                          stop_pct: float = 0.05,
                          target_r: float = 3.0,
                          hold_bars: int = 30,
                          refresh: bool = False):
    import strategy_backtest
    try:
        return strategy_backtest.backtest_strategy(
            name, years=years, step=step,
            universe_limit=universe_limit,
            stop_pct=stop_pct, target_r=target_r,
            hold_bars=hold_bars, use_cache=not refresh)
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# Research
# ============================================================
@app.get("/api/research/{symbol}")
def research_api(symbol: str):
    import research_cockpit
    try:
        return research_cockpit.analyze_symbol(symbol.upper())
    except Exception as e:
        return {"symbol": symbol.upper(), "error": str(e)}


@app.get("/api/research-universe")
def research_universe_api(compute_missing: bool = False):
    import research_cockpit
    try:
        return research_cockpit.analyze_universe(
            compute_missing=compute_missing)
    except Exception as e:
        return {"error": str(e), "rows": [], "n_setups": 0}


@app.get("/api/research-sector")
def research_sector_api():
    import research_cockpit
    try:
        return research_cockpit.sector_aggregate()
    except Exception as e:
        return {"error": str(e), "sectors": [], "n_sectors": 0}


@app.post("/api/research-cache/clear")
def research_cache_clear(symbol: str = None):
    import research_cockpit
    try:
        research_cockpit.clear_cache(symbol.upper() if symbol else None)
        return {"cleared": True, "symbol": symbol}
    except Exception as e:
        return {"cleared": False, "error": str(e)}


# ============================================================
# Compare
# ============================================================
@app.get("/api/compare")
def compare_api(symbols: str):
    import compare_tool
    try:
        syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not syms:
            return {"error": "no symbols", "rows": []}
        return compare_tool.compare(syms, max_n=4)
    except Exception as e:
        return {"error": str(e), "rows": []}


# ============================================================
# Patterns
# ============================================================
@app.get("/api/patterns/latest")
def patterns_latest(limit: int = 100):
    import patterns
    return {"patterns": patterns.latest(limit=limit)}


@app.get("/api/patterns/stats")
def patterns_stats():
    import pattern_grader
    try:
        return {"stats": pattern_grader.stats()}
    except Exception as e:
        return {"stats": {}, "error": str(e)}


@app.get("/api/patterns/history/{symbol}")
def patterns_history(symbol: str, limit: int = 500):
    import patterns
    try:
        return {"symbol": symbol.upper(),
                "signals": patterns.history_for_symbol(
                    symbol.upper(), limit=limit)}
    except Exception as e:
        return {"symbol": symbol.upper(), "signals": [], "error": str(e)}


@app.post("/api/patterns/scan")
def patterns_scan(bg: BackgroundTasks):
    import patterns
    bg.add_task(patterns.run)
    return {"started": True}


@app.get("/api/patterns/{symbol}")
def patterns_for_symbol(symbol: str, limit: int = 50):
    import patterns
    return {"symbol": symbol.upper(),
            "patterns": patterns.for_symbol(symbol.upper(), limit=limit),
            "live_detect": patterns.detect_symbol(symbol.upper())}


# ============================================================
# Existing endpoints
# ============================================================
@app.get("/api/toppicks")
def toppicks():
    import top_picks
    try:
        top_picks.compute()
    except Exception as e:
        print(f"[TOPPICKS] compute failed: {e}")
    return {"picks": top_picks.top(15)}


@app.post("/api/pwin/refresh")
def pwin_refresh(bg: BackgroundTasks):
    import pwin_cache
    bg.add_task(pwin_cache.refresh_all)
    return {"started": True}


@app.get("/api/swing/signals")
def swing_signals(limit: int = 80):
    import swing_live
    import pwin_cache
    conn = get_conn()
    swing_live.ensure(conn)
    rows = conn.execute(
        "SELECT signal_date, symbol, entry_trigger, stop, target, "
        "risk_pct, pullback, impulse, ema_zone, outcome, mode "
        "FROM swing_signals ORDER BY signal_date DESC LIMIT ?",
        (limit,)).fetchall()
    # The default limit is 80; without this the panel could not tell a quiet
    # book from a truncated one.
    total = conn.execute(
        "SELECT COUNT(*) FROM swing_signals").fetchone()[0]
    signals = [{"date": r[0], "symbol": r[1],
                "trigger": safe_float(r[2]), "stop": safe_float(r[3]),
                "target": safe_float(r[4]),
                "risk_pct": safe_float(r[5]),
                "pullback": safe_float(r[6], 3),
                "impulse": safe_float(r[7], 3),
                "ema_zone": r[8], "outcome": r[9],
                "mode": r[10] or "SWING",
                "p_win": None} for r in rows]
    score = {r[0]: r[1] for r in conn.execute(
        "SELECT outcome, COUNT(*) FROM swing_signals "
        "GROUP BY outcome").fetchall()}
    # Keep the system's trading date (UTC) so this block agrees with every
    # other health check. At 00:30 IST the UTC date is still the prior session.
    today = dt.date.today().isoformat()
    today_n = conn.execute(
        "SELECT COUNT(*) FROM swing_signals WHERE signal_date=?",
        (today,)).fetchone()[0]
    last_run = conn.execute(
        "SELECT MAX(run_at) FROM freshness_gate_log "
        "WHERE artifact='swing_live'").fetchone()[0]
    b = conn.execute(
        "SELECT above50, adv, dec FROM breadth_daily "
        "ORDER BY date DESC LIMIT 1").fetchone()
    breadth = ({"above50": b[0], "adv": b[1], "dec": b[2]} if b else None)
    scan = {
        "last_run": last_run,
        "today": today_n,
        "breadth": breadth,
        "breadth_ok": bool(b and b[0] is not None and b[0] >= 0.5
                           and b[1] >= b[2]),
    }
    pw = pwin_cache.get_map(conn)
    conn.close()
    for s in signals:
        s["p_win"] = pw.get(s["symbol"])
    signals.sort(key=lambda x: -(x["p_win"] if x["p_win"] is not None else -1))
    wins = score.get("WIN", 0)
    graded = wins + score.get("LOSS", 0)
    return {"signals": signals, "total": total, "limit": limit,
            "scorecard": score, "scan": scan,
            "win_rate": round(100 * wins / graded, 1) if graded else None}


@app.post("/api/swing/scan")
def run_swing_scan(bg: BackgroundTasks):
    with _SWING_SCAN_LOCK:
        if _SWING_SCAN_STATE["running"]:
            return {"started": False, "already_running": True}
        _SWING_SCAN_STATE.update({
            "running": True, "status": "running",
            "message": "Updating outcomes and scanning the current universe.",
            "started_at": dt.datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
        })
    bg.add_task(_run_swing_scan_job)
    return {"started": True}


def _run_swing_scan_job():
    import logging
    import swing_live
    try:
        swing_live.update_outcomes()
        swing_live.scan()
    except Exception as error:
        logging.getLogger(__name__).exception("Swing scan failed")
        with _SWING_SCAN_LOCK:
            _SWING_SCAN_STATE.update({
                "running": False, "status": "error",
                "message": str(error),
                "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
            })
        return
    with _SWING_SCAN_LOCK:
        _SWING_SCAN_STATE.update({
            "running": False, "status": "complete",
            "message": "Swing scan completed successfully.",
            "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
        })


@app.get("/api/swing/scan/status")
def swing_scan_status():
    with _SWING_SCAN_LOCK:
        return dict(_SWING_SCAN_STATE)


@app.get("/api/radar")
def radar():
    import pwin_cache
    conn = get_conn()
    rows = conn.execute(
        "SELECT symbol, perf1m, perf3m, relvol, mcap_cr "
        "FROM universe_broad ORDER BY mcap_cr DESC").fetchall()
    groups = {"Momentum": [], "Volume Spike": [], "Turnaround": []}
    for sym, p1, p3, rv, mc in rows:
        p1v, p3v, rvv = p1 or 0, p3 or 0, rv or 0
        item = {"symbol": sym, "perf1m": safe_float(p1v),
                "perf3m": safe_float(p3v), "relvol": safe_float(rvv),
                "mcap_cr": safe_float(mc), "p_win": None}
        if rvv >= 2:
            groups["Volume Spike"].append(item)
        elif p1v >= 10 and p3v >= 8:
            groups["Momentum"].append(item)
        elif p1v >= 7 and p3v <= 0:
            groups["Turnaround"].append(item)
    # Honest caps: this endpoint truncates each group to 40 and the UI renders
    # 18, with no way for the caller to know how much was hidden. Report the
    # full count per group so the panel can say "Showing 18 of N".
    group_totals = {k: len(v) for k, v in groups.items()}
    for k in groups:
        groups[k] = groups[k][:40]
    pw = pwin_cache.get_map(conn)
    conn.close()
    for k in groups:
        for item in groups[k]:
            item["p_win"] = pw.get(item["symbol"])
        groups[k].sort(key=lambda x: -(x["p_win"] if x["p_win"] is not None else -1))
    return {"groups": groups, "total": len(rows),
            "group_totals": group_totals, "group_limit": 40}


@app.get("/api/trend")
def trend_api(n: int = 50):
    import trend_scanner
    try:
        return {"candidates": trend_scanner.top(n)}
    except Exception as e:
        return {"candidates": [], "error": str(e)}


@app.post("/api/trend/scan")
def trend_scan(bg: BackgroundTasks):
    import trend_scanner
    bg.add_task(trend_scanner.compute)
    return {"started": True}


@app.get("/api/templates/latest")
def templates_latest(limit: int = 30):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT date, symbol, template, similarity "
            "FROM template_scores "
            "WHERE date=(SELECT MAX(date) FROM template_scores) "
            "ORDER BY similarity DESC LIMIT ?", (limit,)).fetchall()
    except Exception:
        rows = []
    conn.close()
    return {"matches": [{"date": r[0], "symbol": r[1],
                         "template": r[2], "similarity": r[3]}
                        for r in rows]}


@app.get("/api/delivery/top")
def delivery_top(n: int = 30):
    import delivery
    return {"rows": delivery.top(n)}


@app.get("/api/delivery/accum")
def delivery_accum(n: int = 30):
    import delivery
    return {"candidates": delivery.accumulation(n)}


@app.get("/api/delivery/{symbol}")
def delivery_symbol(symbol: str, limit: int = 20):
    import delivery
    return {"symbol": symbol.upper(),
            "history": delivery.for_symbol(symbol.upper(), limit),
            "score": delivery.delivery_score(symbol.upper())}


@app.get("/api/value-radar")
def value_radar_api(n: int = 25, tier: str = None):
    import value_radar
    try:
        return {"picks": value_radar.top(n, tier=tier)}
    except Exception as e:
        return {"picks": [], "error": str(e)}


@app.get("/api/positional")
def positional_api(n: int = 25, tier: str = None):
    import positional_scanner
    try:
        return {"picks": positional_scanner.top(n, tier=tier)}
    except Exception as e:
        return {"picks": [], "error": str(e)}


@app.get("/api/strategy-runs")
def strategy_runs_api(n: int = 20):
    import strategy_runs
    try:
        return {"runs": strategy_runs.history(n)}
    except Exception as e:
        return {"runs": [], "error": str(e)}


@app.get("/api/strategy-summary")
def strategy_summary_api():
    import strategy_runs
    try:
        return {"summary": strategy_runs.summary_by_target()}
    except Exception as e:
        return {"summary": [], "error": str(e)}


@app.post("/api/webhook/ingest")
def webhook_ingest(payload: dict,
                   x_webhook_token: str = Header(default="")):
    token = os.getenv("WEBHOOK_TOKEN")
    if not token:
        conn = get_conn()
        row = conn.execute(
            "SELECT value FROM settings WHERE key='webhook_token'"
        ).fetchone()
        conn.close()
        token = row[0] if row else None
    if not token:
        raise HTTPException(status_code=503, detail="webhook not configured")
    got_hdr = x_webhook_token or ""
    got_body = str(payload.get("token", ""))
    ok = (secrets.compare_digest(got_hdr, token) or
          secrets.compare_digest(got_body, token))
    if not ok:
        raise HTTPException(status_code=401, detail="bad webhook token")
    conn = get_conn()
    conn.execute("""CREATE TABLE IF NOT EXISTS webhook_events(
        created_at TEXT, source TEXT, symbol TEXT, kind TEXT,
        price REAL, payload TEXT)""")
    conn.execute(
        "INSERT INTO webhook_events VALUES (?,?,?,?,?,?)",
        (dt.datetime.now().isoformat(timespec="seconds"),
         str(payload.get("source", "unknown"))[:40],
         str(payload.get("symbol", "")).upper()[:20],
         str(payload.get("kind", "alert"))[:40],
         safe_float(payload.get("price")),
         json.dumps(payload, default=str)[:2000]))
    conn.commit()
    conn.close()
    try:
        from alerts import send
        send(f"📡 WEBHOOK {payload.get('source')} "
             f"{str(payload.get('symbol', '')).upper()} "
             f"{payload.get('kind')} @ {payload.get('price')}")
    except Exception:
        pass
    return {"stored": True}


@app.get("/api/cockpit/{symbol}/chart")
def cockpit_chart(symbol: str):
    sym = symbol.upper()
    conn = get_conn()
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM prices_daily "
        "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
    conn.close()
    if not rows:
        return {"symbol": sym, "candles": [], "ema10": [], "ema20": [],
                "ema50": [], "ema200": [], "swing": None}
    df = pd.DataFrame(list(rows),
                      columns=["date", "open", "high", "low",
                               "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).tail(420).copy()
    df["ema10"] = df["close"].ewm(span=10, adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()
    candles = [{"time": r["date"].strftime("%Y-%m-%d"),
                "open": safe_float(r["open"]),
                "high": safe_float(r["high"]),
                "low": safe_float(r["low"]),
                "close": safe_float(r["close"])}
               for _, r in df.iterrows()]

    def line(col):
        return [{"time": r["date"].strftime("%Y-%m-%d"),
                 "value": safe_float(r[col])}
                for _, r in df.iterrows()
                if safe_float(r[col]) is not None]

    swing = None
    try:
        from setup import SetupDetector
        raw = df.rename(columns={"close": "Close", "high": "High",
                                 "low": "Low", "volume": "Volume"})
        raw = raw.set_index("date")
        st = SetupDetector.detect(raw, sym)
        if st.triggered:
            swing = {"trigger": st.entry_price, "stop": st.stop_loss,
                     "target": st.target_price,
                     "pullback": st.pullback_depth,
                     "impulse": st.impulse_pct,
                     "zone": st.ema_proximity,
                     "shape": st.shape_score}
    except Exception:
        swing = None
    return {"symbol": sym, "candles": candles,
            "ema10": line("ema10"), "ema20": line("ema20"),
            "ema50": line("ema50"), "ema200": line("ema200"),
            "swing": swing}


@app.get("/api/cockpit/{symbol}/summary")
def cockpit_summary(symbol: str):
    sym = symbol.upper()
    conn = get_conn()
    sector = mcap = fund_score = status = None
    r = conn.execute("SELECT sector FROM stocks WHERE symbol=?",
                     (sym,)).fetchone()
    if r:
        sector = r[0]
    r = conn.execute("SELECT mcap_cr FROM universe_broad WHERE symbol=?",
                     (sym,)).fetchone()
    if r:
        mcap = safe_float(r[0])
    r = conn.execute(
        "SELECT fundamental_score FROM scan_results WHERE symbol=? "
        "ORDER BY scan_date DESC LIMIT 1", (sym,)).fetchone()
    if r:
        fund_score = safe_float(r[0])
    r = conn.execute("SELECT status FROM pipeline WHERE symbol=?",
                     (sym,)).fetchone()
    if r:
        status = r[0]
    news = []
    try:
        nrows = conn.execute(
            "SELECT title, age_days, label FROM sentiment_headlines "
            "WHERE symbol=? ORDER BY age_days LIMIT 8", (sym,)).fetchall()
        for title, age, label in nrows:
            news.append({"title": title, "age_days": age, "label": label})
    except Exception:
        pass
    conn.close()
    return {"symbol": sym, "sector": sector, "mcap_cr": mcap,
            "fund_score": fund_score, "status": status, "news": news}


@app.get("/api/meta/{symbol}")
def meta_score(symbol: str):
    import meta_model
    try:
        r = meta_model.score_symbol(symbol.upper())
        return r or {"symbol": symbol, "p_win": None, "why": []}
    except Exception as e:
        return {"symbol": symbol, "p_win": None, "why": [], "error": str(e)}


@app.get("/api/model/runs")
def model_runs(n: int = 10):
    import model_report
    return {"runs": model_report.history(n)}


@app.get("/api/ledger/stats")
def ledger_stats():
    import ledger
    return ledger.compute_stats() or {"total_trades": 0}


@app.get("/api/ledger/trades")
def ledger_trades(limit: int = 100):
    import ledger
    return {"trades": ledger.get_trades(limit)}


@app.get("/api/ledger/monthly")
def ledger_monthly(months: int = 24):
    """Same figures as /api/ledger/stats, split month by month (N3)."""
    import ledger
    try:
        return {"months": ledger.compute_monthly_stats(
            limit_months=min(max(months, 1), 120))}
    except Exception as e:
        return {"months": [], "error": str(e)}


@app.get("/api/validate/latest")
def validate_latest():
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT mode, run_date, payload FROM validation_log "
            "ORDER BY run_date DESC").fetchall()
    except Exception:
        rows = []
    conn.close()
    out = {}
    for mode, d, payload in rows:
        if mode not in out:
            try:
                out[mode] = dict(json.loads(payload), run_date=d)
            except Exception:
                out[mode] = {"run_date": d}
    return out


@app.get("/api/sizing/{symbol}")
def sizing(symbol: str, trigger: float = None, stop: float = None,
           shape: float = None):
    import sizing as sz
    try:
        return sz.suggest(symbol.upper(), trigger=trigger, stop=stop,
                          shape_score=shape)
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@app.post("/api/sizing/capital")
def sizing_capital(payload: dict):
    import sizing as sz
    try:
        v = float(payload.get("capital", 0))
        if v <= 0:
            raise ValueError("capital must be > 0")
        return {"capital": sz.set_capital(v)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/screener/scan")
def screener_scan(limit: int = 40):
    import screener_engine
    try:
        n = min(max(limit, 10), 100)
        hits = screener_engine.screen_universe(limit=n, show=False)
        return {"scanned": n, "hits": hits}
    except Exception as e:
        return {"scanned": 0, "hits": [], "error": str(e)}


@app.get("/api/screener/{symbol}")
def screener_check(symbol: str):
    import screener_engine
    try:
        return screener_engine.evaluate_stock(symbol.upper())
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/screener/scan-universe")
def screener_scan_universe(bg: BackgroundTasks):
    """Start the whole-band screener scan in the background (N1).

    Use /api/screener/scan for the quick top-of-band check; this one walks all
    ~855 names, which takes around half a minute, so it never blocks a request.
    """
    with _BAND_SCAN_LOCK:
        if _BAND_SCAN_STATE["running"]:
            return {"started": False, "already_running": True}
        _BAND_SCAN_STATE.update({
            "running": True, "status": "running",
            "message": "Scanning the whole smallcap/midcap band.",
            "scanned": 0, "total": 0, "hits_count": 0, "hits": [],
            "started_at": dt.datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
        })
    bg.add_task(_run_band_scan_job)
    return {"started": True}


def _run_band_scan_job():
    import logging
    import screener_engine

    def report(done, total, hits):
        # Called once per symbol from the background thread; never let a status
        # update take the scan down.
        try:
            with _BAND_SCAN_LOCK:
                _BAND_SCAN_STATE.update({
                    "scanned": done, "total": total, "hits_count": hits,
                    "message": f"Scanned {done} of {total} companies, "
                               f"{hits} matched so far.",
                })
        except Exception:
            pass

    try:
        # limit=None means the WHOLE band, not the usual top slice.
        results = screener_engine.screen_universe(
            limit=None, show=False, progress=report)
    except Exception as error:
        logging.getLogger(__name__).exception("Whole-band screener scan failed")
        with _BAND_SCAN_LOCK:
            _BAND_SCAN_STATE.update({
                "running": False, "status": "error", "message": str(error),
                "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
            })
        return

    with _BAND_SCAN_LOCK:
        scanned = _BAND_SCAN_STATE.get("total") or len(results)
        _BAND_SCAN_STATE.update({
            "running": False, "status": "complete",
            "hits": results[:300],
            "hits_count": len(results),
            "message": f"Scanned {scanned} companies, "
                       f"found {len(results)} matches.",
            "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
        })


@app.get("/api/screener/scan-universe/status")
def screener_scan_universe_status():
    with _BAND_SCAN_LOCK:
        state = dict(_BAND_SCAN_STATE)
    state["hits_count"] = state.get("hits_count") or len(state.get("hits") or [])
    return state


# ============================================================
# Playbook — rule catalogue, per-stock tags, one-click search, backtest
# ============================================================
@app.get("/api/playbook/strategies")
def playbook_strategies():
    """Every rule with its book, exact formula, params, live tags and the
    latest backtest row. This is the one call the Playbook tab renders."""
    import playbook_engine as pe
    conn = get_conn()
    try:
        return pe.strategies_with_stats(conn)
    finally:
        conn.close()


@app.get("/api/playbook/signals")
def playbook_signals(strategy: str | None = None,
                     symbol: str | None = None,
                     direction: str | None = None,
                     as_of: str | None = None,
                     limit: int = 500):
    """Tags for the latest scan (or a named date), filtered server-side so a
    phone never has to download the whole book to answer one click."""
    import playbook_engine as pe
    conn = get_conn()
    try:
        rows = pe.signals(conn, strategy=strategy, symbol=symbol,
                          direction=direction, as_of=as_of,
                          limit=min(max(int(limit), 1), 2000))
        return {"as_of": as_of or pe.latest_as_of(conn),
                "count": len(rows), "signals": rows}
    finally:
        conn.close()


@app.get("/api/playbook/symbol/{symbol}")
def playbook_symbol(symbol: str):
    """All strategy tags carried by one stock on the latest scan date."""
    import playbook_engine as pe
    conn = get_conn()
    try:
        return pe.symbol_tags(conn, symbol)
    finally:
        conn.close()


@app.post("/api/playbook/scan")
def playbook_scan(limit: int = Query(900, ge=10, le=2000)):
    """Start a whole-universe scan in a daemon thread; poll the status route."""
    import playbook_engine as pe
    return pe.start_scan(limit=limit)


@app.get("/api/playbook/scan/status")
def playbook_scan_status():
    import playbook_engine as pe
    return pe.scan_status()


@app.post("/api/playbook/backtest")
def playbook_backtest(payload: dict = Body(None)):
    """Walk the selected rules forward. Body: {limit, years, step, strategies}."""
    import playbook_engine as pe
    payload = payload or {}
    try:
        limit = int(payload.get("limit") or pe.DEFAULT_BACKTEST_LIMIT)
        years = float(payload.get("years") or pe.DEFAULT_BACKTEST_YEARS)
        step = int(payload.get("step") or pe.DEFAULT_STEP)
        strategies = payload.get("strategies") or None
        if isinstance(strategies, str):
            strategies = [s.strip() for s in strategies.split(",") if s.strip()]
        return pe.start_backtest(limit=limit, years=years,
                                 strategies=strategies, step=step)
    except (TypeError, ValueError) as exc:
        return {"started": False,
                "error": f"bad backtest parameters: {exc}"}


@app.get("/api/playbook/backtest/status")
def playbook_backtest_status():
    import playbook_engine as pe
    return pe.backtest_status()


@app.get("/api/playbook/backtests")
def playbook_backtests(strategy: str | None = None, limit: int = 100):
    """Latest row per strategy plus the raw run history."""
    import playbook_engine as pe
    conn = get_conn()
    try:
        latest = [x for x in pe._latest_backtests(conn).values()
                  if pe.is_backtestable(x["strategy"])
                  and (not strategy or x["strategy"] == strategy)]
        rows = [r for r in pe.backtests(conn, strategy=strategy,
                                        limit=min(max(int(limit), 1), 500))
                if pe.is_backtestable(r["strategy"])]
        return {"latest": latest, "rows": rows}
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("terminal_api:app", host=API_HOST, port=8000, reload=True)