"""
Rule Engine — generic strategy evaluation.

Strategies are JSON definitions stored in data/strategies.json.
"""
import os
import json
import math
import datetime as dt
import numpy as np
import pandas as pd
import db
from log_utils import get_logger

log = get_logger("rule_engine")

STRATEGIES_PATH = os.path.join("data", "strategies.json")

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
}


# ============================================================
# Strategy file I/O
# ============================================================
def _ensure_file():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(STRATEGIES_PATH):
        with open(STRATEGIES_PATH, "w") as f:
            json.dump({}, f, indent=2)


def load_strategies():
    _ensure_file()
    try:
        with open(STRATEGIES_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"strategies file unreadable: {e}")
        return {}


def save_strategies(strategies):
    _ensure_file()
    with open(STRATEGIES_PATH, "w") as f:
        json.dump(strategies, f, indent=2)


def get_strategy(name):
    return load_strategies().get(name)


def save_strategy(name, definition):
    s = load_strategies()
    s[name] = definition
    save_strategies(s)


def delete_strategy(name):
    s = load_strategies()
    s.pop(name, None)
    save_strategies(s)


# ============================================================
# Feature computation
# ============================================================
def _seq_len(v):
    if v is None:
        return 0
    try:
        return len(v)
    except Exception:
        return 0


def _ema(vals, span):
    if _seq_len(vals) == 0:
        return None
    k = 2.0 / (span + 1.0)
    e = float(vals[0])
    for v in vals[1:]:
        e = float(v) * k + e * (1 - k)
    return e


def _sma(vals, span):
    if _seq_len(vals) < span:
        return None
    return float(np.mean(vals[-span:]))


def _rsi(closes, period=14):
    if _seq_len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(len(closes) - period, len(closes)):
        ch = float(closes[i]) - float(closes[i - 1])
        if ch > 0:
            gains += ch
        else:
            losses -= ch
    if losses == 0:
        return 100.0
    return 100 - (100 / (1 + gains / losses))


def _range_contraction(df, windows=(5, 5, 5, 5)):
    need = sum(windows)
    if len(df) < need:
        return 0
    sub = df.tail(need)
    highs = sub["High"].values
    lows = sub["Low"].values
    ranges = []
    idx = 0
    for w in windows:
        seg_h = highs[idx:idx + w]
        seg_l = lows[idx:idx + w]
        if len(seg_h) < w:
            return 0
        ranges.append(float(np.max(seg_h) - np.min(seg_l)))
        idx += w
    for i in range(1, len(ranges)):
        if ranges[i] >= ranges[i - 1]:
            return 0
    return 1


def _compute_features(sym, df, fund_row, sector, sector_rs):
    if df is None or len(df) < 60:
        return None
    c = df["Close"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    v = df["Volume"].values.astype(float)
    o = df["Open"].values.astype(float)

    close = float(c[-1])
    open_ = float(o[-1])
    high = float(h[-1])
    low = float(l[-1])

    dma20 = _sma(c, 20)
    dma50 = _sma(c, 50)
    dma200 = _sma(c, 200)
    high52 = float(np.max(h[-252:])) if len(h) >= 252 else float(np.max(h))
    low52 = float(np.min(l[-252:])) if len(l) >= 252 else float(np.min(l))

    atr = None
    if len(c) >= 15:
        trs = []
        for i in range(1, len(c)):
            trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]),
                           abs(l[i] - c[i - 1])))
        atr = float(np.mean(trs[-14:]))

    mom_5d = (c[-1] / c[-6] - 1) if len(c) >= 6 else None
    mom_20d = (c[-1] / c[-21] - 1) if len(c) >= 21 else None
    mom_60d = (c[-1] / c[-61] - 1) if len(c) >= 61 else None

    avg_vol_20 = _sma(v, 20)
    vol_ratio_20 = (float(v[-1]) / avg_vol_20) if avg_vol_20 else None

    gap_up_pct = None
    if len(c) >= 2:
        gap_up_pct = (o[-1] / c[-2] - 1)

    inside_day = 0
    if len(h) >= 2:
        if h[-1] < h[-2] and l[-1] > l[-2]:
            inside_day = 1

    features = {
        "close": close,
        "open": open_,
        "high": high,
        "low": low,
        "volume": float(v[-1]),
        "high52": high52,
        "low52": low52,
        "distance_from_52w_high": ((high52 - close) / high52) if high52 > 0 else None,
        "distance_from_52w_low": ((close - low52) / low52) if low52 > 0 else None,
        "dma20": dma20,
        "dma50": dma50,
        "dma200": dma200,
        "above20": 1 if (dma20 and close > dma20) else 0,
        "above50": 1 if (dma50 and close > dma50) else 0,
        "above200": 1 if (dma200 and close > dma200) else 0,
        "mom_5d": mom_5d,
        "mom_20d": mom_20d,
        "mom_60d": mom_60d,
        "rsi": _rsi(c),
        "avg_vol_20": avg_vol_20,
        "vol_ratio_20": vol_ratio_20,
        "gap_up_pct": gap_up_pct,
        "inside_day": inside_day,
        "close_gt_open": 1 if close > open_ else 0,
        "range_contraction": _range_contraction(df),
        "atr_14": atr,
        "atr_pct": (atr / close) if (atr and close) else None,
        "sector_rs": sector_rs,
    }

    if fund_row:
        for k in ["roce", "pe", "pb", "roe", "debt_to_equity",
                  "profit_growth_3y", "sales_growth_3y",
                  "promoter_holding", "dividend_yield",
                  "cfo_positive", "market_cap_cr",
                  "operating_margin", "net_profit_margin"]:
            features[k] = fund_row.get(k)

    features["sector"] = sector
    return features


def _load_symbol_df(conn, sym, max_bars=300):
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM prices_daily "
        "WHERE symbol=? ORDER BY date DESC LIMIT ?", (sym, max_bars)
    ).fetchall()
    if not rows or len(rows) < 60:
        return None
    rows = list(reversed(rows))
    df = pd.DataFrame(rows, columns=["date", "Open", "High", "Low",
                                     "Close", "Volume"]).set_index("date")
    return df


def _load_fundamentals(conn):
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(fundamentals)")]
    except Exception:
        return {}
    out = {}
    if not cols:
        return out
    sel = ", ".join(cols)
    for row in conn.execute(f"SELECT {sel} FROM fundamentals").fetchall():
        m = dict(zip(cols, row))
        sym = m.get("symbol")
        if sym:
            out[sym] = m
    return out


def _load_sectors(conn):
    out = {}
    try:
        for sym, sec in conn.execute(
                "SELECT symbol, sector FROM stocks "
                "WHERE sector IS NOT NULL"):
            out[sym] = sec
    except Exception:
        pass
    return out


def _load_sector_rs(conn):
    try:
        import sector_gate
        g = sector_gate.sector_perf(conn)
        if g is None or g.empty:
            return {}
        n = len(g)
        rank = {r["sector"]: 1.0 - (i / max(1, n - 1))
                for i, (_, r) in enumerate(g.iterrows())}
        out = {}
        for sym, sec in conn.execute(
                "SELECT symbol, sector FROM stocks WHERE sector IS NOT NULL"):
            out[sym] = rank.get(sec, 0.5)
        return out
    except Exception:
        return {}


def _universe_symbols(conn, universe):
    if universe == "active":
        rows = conn.execute(
            "SELECT symbol FROM stocks WHERE active=1").fetchall()
    elif universe == "band":
        rows = conn.execute(
            "SELECT symbol FROM universe_broad "
            "WHERE mcap_cr BETWEEN 1000 AND 8000 "
            "AND symbol NOT LIKE '%$%' AND symbol NOT LIKE '% %' "
            "ORDER BY mcap_cr DESC LIMIT 800").fetchall()
    elif universe == "combined":
        from universe_helper import combined_universe
        return combined_universe(conn, band_limit=800)
    else:
        rows = conn.execute(
            "SELECT symbol FROM stocks WHERE active=1").fetchall()
    return sorted({r[0] for r in rows})


# ============================================================
# Evaluation
# ============================================================
def _condition_label(cond, features):
    field = cond["field"]
    op = cond["op"]
    want = cond["value"]
    got = features.get(field)
    try:
        ok = OPS[op](got, want) if got is not None else False
    except Exception:
        ok = False
    if got is None:
        got_str = "—"
    elif isinstance(got, float):
        got_str = f"{got:.3f}"
    else:
        got_str = str(got)
    return {"field": field, "op": op, "want": want,
            "got": got_str, "ok": bool(ok)}


def evaluate(strategy, features):
    conditions = strategy.get("conditions", [])
    checks = [_condition_label(c, features) for c in conditions]
    passed = all(c["ok"] for c in checks)
    if not passed:
        return {"passed": False, "score": None, "checks": checks}

    weights = strategy.get("score_weights", {})
    score = 0.0
    have = False
    for field, w in weights.items():
        v = features.get(field)
        if v is None:
            continue
        try:
            score += float(v) * float(w)
            have = True
        except Exception:
            continue
    return {"passed": True,
            "score": round(score, 4) if have else 0.0,
            "checks": checks}


def _diagnose(strategy, all_checks):
    """
    all_checks = list of per-symbol check lists (every symbol that was
    evaluated, whether it passed or not). Returns failure counts per
    condition and per (condition, missing) pair.
    """
    conditions = strategy.get("conditions", [])
    n = len(all_checks)
    if n == 0:
        return {"n_evaluated": 0, "per_condition": []}

    # For each condition, count how many symbols failed it.
    # Also count how many failed because value was missing.
    fails = [0] * len(conditions)
    missing = [0] * len(conditions)
    # Count all-fail (whole strategy failed) — but we want to know
    # per-condition how many failed. We also want to know which condition
    # is "last blocker" (the one where the fewest symbols survive).
    survivor_after = [n] * (len(conditions) + 1)
    for checks in all_checks:
        ok_so_far = True
        for i, c in enumerate(checks):
            if not c["ok"]:
                fails[i] += 1
                if c["got"] == "—":
                    missing[i] += 1
                ok_so_far = False
            if ok_so_far:
                pass  # symbol still alive after this condition
        # recompute survivors step by step (cleaner)
    # Compute survivors per prefix
    survivors = [n]
    for i in range(len(conditions)):
        alive = 0
        for checks in all_checks:
            if all(checks[j]["ok"] for j in range(i + 1)):
                alive += 1
        survivors.append(alive)

    per_condition = []
    for i, c in enumerate(conditions):
        per_condition.append({
            "field": c["field"],
            "op": c["op"],
            "want": c["value"],
            "failed": fails[i],
            "failed_because_missing": missing[i],
            "survived_after": survivors[i + 1],
        })
    return {"n_evaluated": n, "per_condition": per_condition}


def run_strategy(name, limit=50):
    strategies = load_strategies()
    s = strategies.get(name)
    if not s:
        return {"error": f"strategy '{name}' not found"}

    conn = db.get_conn()
    syms = _universe_symbols(conn, s.get("universe", "active"))
    funds = _load_fundamentals(conn)
    sectors = _load_sectors(conn)
    srs = _load_sector_rs(conn)

    results = []
    all_checks = []
    n_checked = 0
    for sym in syms:
        n_checked += 1
        df = _load_symbol_df(conn, sym)
        if df is None:
            continue
        feats = _compute_features(sym, df, funds.get(sym),
                                  sectors.get(sym), srs.get(sym))
        if not feats:
            continue
        r = evaluate(s, feats)
        all_checks.append(r["checks"])
        if not r["passed"]:
            continue
        results.append({
            "symbol": sym,
            "score": r["score"],
            "sector": feats.get("sector"),
            "close": feats.get("close"),
            "distance_from_52w_high": feats.get("distance_from_52w_high"),
            "checks": r["checks"],
            "top_features": {k: feats.get(k)
                             for k in (s.get("score_weights") or {}).keys()},
        })
    conn.close()

    results.sort(key=lambda r: -(r["score"] if r["score"] is not None else 0))
    diag = _diagnose(s, all_checks)

    return {"strategy": name,
            "type": s.get("type", "unknown"),
            "universe": s.get("universe", "active"),
            "n_symbols_checked": n_checked,
            "n_passed": len(results),
            "run_at": dt.datetime.now().isoformat(timespec="seconds"),
            "picks": results[:limit],
            "diagnostic": diag}


def run_all():
    out = {}
    for name in load_strategies():
        try:
            out[name] = run_strategy(name, limit=30)
        except Exception as e:
            out[name] = {"error": str(e)}
    return out


# ============================================================
# Seed strategies
# ============================================================
SEEDS = {
    "Multibagger": {
        "name": "Multibagger",
        "description": "Long-term quality + growth. Holds months to years.",
        "type": "fundamental",
        "universe": "active",
        "conditions": [
            {"field": "roce", "op": ">=", "value": 18},
            {"field": "profit_growth_3y", "op": ">=", "value": 15},
            {"field": "sales_growth_3y", "op": ">=", "value": 12},
            {"field": "debt_to_equity", "op": "<=", "value": 1.0},
            {"field": "cfo_positive", "op": "==", "value": 1},
        ],
        "score_weights": {
            "roce": 0.30,
            "profit_growth_3y": 0.30,
            "sales_growth_3y": 0.20,
            "pe": -0.20,
        },
    },
    "RCP": {
        "name": "RCP — Range Contraction Pattern",
        "description": "Base with successive tightening ranges. Swing setup.",
        "type": "swing",
        "universe": "band",
        "conditions": [
            {"field": "above200", "op": "==", "value": 1},
            {"field": "above50", "op": "==", "value": 1},
            {"field": "distance_from_52w_high", "op": "<=", "value": 0.20},
            {"field": "range_contraction", "op": "==", "value": 1},
            {"field": "vol_ratio_20", "op": "<=", "value": 1.0},
        ],
        "score_weights": {
            "mom_20d": 0.5,
            "sector_rs": 0.3,
            "vol_ratio_20": -0.2,
        },
    },
    "EpisodicPivot": {
        "name": "Episodic Pivot",
        "description": "News-driven gap up + high volume, holding near highs.",
        "type": "swing",
        "universe": "band",
        "conditions": [
            {"field": "gap_up_pct", "op": ">=", "value": 0.04},
            {"field": "vol_ratio_20", "op": ">=", "value": 2.0},
            {"field": "close_gt_open", "op": "==", "value": 1},
            {"field": "distance_from_52w_high", "op": "<=", "value": 0.15},
        ],
        "score_weights": {
            "gap_up_pct": 0.4,
            "vol_ratio_20": 0.4,
            "mom_20d": 0.2,
        },
    },
}


def seed_if_empty(force=False):
    s = load_strategies()
    added = 0
    for name, definition in SEEDS.items():
        if force or name not in s:
            s[name] = definition
            added += 1
    if added:
        save_strategies(s)
        log.info(f"seeded {added} strategies")
    return added


if __name__ == "__main__":
    import sys
    argv = sys.argv[1:]

    if "--seed" in argv:
        n = seed_if_empty(force="--force" in argv)
        print(f"seeded {n} strategies")
        sys.exit(0)

    if "--list" in argv:
        s = load_strategies()
        print(json.dumps(list(s.keys()), indent=2))
        sys.exit(0)

    if "--run" in argv:
        idx = argv.index("--run")
        name = argv[idx + 1] if idx + 1 < len(argv) else None
        if not name:
            print("usage: rule_engine.py --run STRATEGY_NAME")
            sys.exit(1)
        out = run_strategy(name, limit=20)
        if "error" in out:
            print(f"ERROR: {out['error']}")
            sys.exit(1)
        print(f"[{out['strategy']}] {out['n_passed']} passed of "
              f"{out['n_symbols_checked']} checked")
        for p in out["picks"]:
            print(f"  {p['symbol']:<14} score {p['score']:>8.3f}  "
                  f"{p['sector'] or '?'}")
        # Failure breakdown (helpful when n_passed == 0 or very low)
        diag = out.get("diagnostic") or {}
        pc = diag.get("per_condition") or []
        if pc:
            print()
            print(f"  failure breakdown (n={diag.get('n_evaluated')}):")
            for c in pc:
                fb = c["failed_because_missing"]
                print(f"    {c['field']:<24} {c['op']:<3} {str(c['want']):<8}  "
                      f"failed {c['failed']:<5} (missing {fb:<5})  "
                      f"survived {c['survived_after']}")
        sys.exit(0)

    print("commands: --seed [--force] | --list | --run NAME")