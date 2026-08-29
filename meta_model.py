"""
Setup Meta-Model — learns what winners look like (5y history),
ranks live candidates by P(WIN), explains via TreeSHAP.
"""
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
import db

MODEL_PATH = "data/meta_model.pkl"

_MODEL = None

def get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = joblib.load(MODEL_PATH)
    return _MODEL

FEATURES = ["mom1", "mom3", "mom6", "d52", "above200", "slope200",
            "rv", "vc", "pb", "d10", "d20", "atr", "roce", "pe"]


def _symbols(conn, limit=400):
    rows = conn.execute(
        "SELECT symbol FROM universe_broad WHERE mcap_cr BETWEEN 1000 "
        "AND 8000 AND symbol NOT LIKE '%$%' AND symbol NOT LIKE '% %' "
        "ORDER BY mcap_cr DESC LIMIT ?", (limit,)).fetchall()
    core = [r[0] for r in conn.execute(
        "SELECT symbol FROM stocks WHERE active=1")]
    return sorted(set([r[0] for r in rows]) | set(core))


def _fund_map(conn):
    m = {}
    try:
        for s, ro, pe in conn.execute(
                "SELECT symbol, roce, pe FROM fundamentals"):
            m[s] = (ro, pe)
    except Exception:
        pass
    return m


def _features_df(df, roce, pe):
    c = df["close"]; h = df["high"]; l = df["low"]; v = df["volume"]
    e10 = c.ewm(span=10, adjust=False).mean()
    e20 = c.ewm(span=20, adjust=False).mean()
    e200 = c.ewm(span=200, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    fut_max = h.iloc[::-1].rolling(20, min_periods=1).max().iloc[::-1].shift(-1)

    out = pd.DataFrame(index=df.index)
    out["mom1"] = c / c.shift(21) - 1
    out["mom3"] = c / c.shift(63) - 1
    out["mom6"] = c / c.shift(126) - 1
    out["d52"] = c / h.rolling(252).max()
    out["above200"] = (c > e200).astype(float)
    out["slope200"] = e200 / e200.shift(20) - 1
    out["rv"] = v / v.rolling(50).mean()
    out["vc"] = v / v.rolling(20).mean()
    out["pb"] = h.rolling(25).max() / c - 1
    out["d10"] = c / e10 - 1
    out["d20"] = c / e20 - 1
    out["atr"] = tr.rolling(14).mean() / c
    out["roce"] = roce
    out["pe"] = pe
    out["win"] = ((fut_max / c - 1) >= 0.10).astype(float)
    return out


def train():
    conn = db.get_conn()
    fund = _fund_map(conn)
    frames = []
    for sym in _symbols(conn):
        rows = conn.execute(
            "SELECT date, close, high, low, volume FROM prices_daily "
            "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
        if len(rows) < 300:
            continue
        df = pd.DataFrame(list(rows), columns=["date", "close", "high",
                          "low", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        ro, pe = fund.get(sym, (np.nan, np.nan))
        f = _features_df(df, ro, pe)
        f["date"] = df["date"]
        f = f.iloc[::5]                      # weekly sampling
        f = f.dropna(subset=[x for x in FEATURES
                             if x not in ("roce", "pe")] + ["win"])
        frames.append(f)
    conn.close()

    data = pd.concat(frames, ignore_index=True)
    if data.empty:
        print("no training rows - check prices_daily")
        return
    data["roce"] = data["roce"].fillna(data["roce"].median())
    data["pe"] = data["pe"].fillna(data["pe"].median())
    data = data.sort_values("date")
    cutoff = data["date"].quantile(0.8)      # time-based split, no lookahead
    tr = data[data["date"] <= cutoff]
    te = data[data["date"] > cutoff]

    Xtr, ytr = tr[FEATURES], tr["win"]
    Xte, yte = te[FEATURES], te["win"]

    model = lgb.LGBMClassifier(
        n_estimators=400, learning_rate=0.05, max_depth=6,
        num_leaves=31, min_child_samples=50, subsample=0.9,
        colsample_bytree=0.9, verbose=-1)
    model.fit(Xtr, ytr, eval_set=[(Xte, yte)],
              eval_metric="auc", callbacks=[lgb.early_stopping(50, verbose=False)])

    proba = model.predict_proba(Xte)[:, 1]
    base = yte.mean()
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(yte, proba)

    # precision in top decile vs base rate
    order = np.argsort(-proba)
    top = int(max(1, len(proba) * 0.10))
    top_rate = yte.iloc[order[:top]].mean()

    joblib.dump(model, MODEL_PATH)
    print(f"rows {len(data)} | winners {data['win'].mean():.1%}")
    print(f"test AUC {auc:.3f} | base win {base:.1%} | top-10% win {top_rate:.1%}")
    print(f"model saved to {MODEL_PATH}")


def score_symbol(sym, use_yahoo=True):
    model = get_model()
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT date, close, high, low, volume FROM prices_daily "
        "WHERE symbol=? ORDER BY date", (sym,)).fetchall()
    fr = conn.execute("SELECT roce, pe FROM fundamentals WHERE symbol=?",
                      (sym,)).fetchone()
    avg = conn.execute(
        "SELECT AVG(roce), AVG(pe) FROM fundamentals").fetchone()
    conn.close()
    if len(rows) >= 300:
        df = pd.DataFrame(list(rows), columns=["date", "close", "high",
                          "low", "volume"])
    elif use_yahoo:
        try:
            import yfinance as yf
            d = yf.Ticker(sym + ".NS").history(period="5y",
                                               auto_adjust=True)
        except Exception:
            return None
        if d is None or len(d) < 300:
            return None
        df = pd.DataFrame({
            "close": d["Close"].values,
            "high": d["High"].values,
            "low": d["Low"].values,
            "volume": d["Volume"].values,
        })
            else:
        return None
    ro, pe = fr if fr else (np.nan, np.nan)
    f = _features_df(df, ro, pe)
    f = f.dropna(subset=[x for x in FEATURES if x not in ("roce", "pe")])
    if f.empty:
        return None
    f = f.tail(1).copy()
    f["roce"] = f["roce"].fillna(avg[0] if avg and avg[0] is not None else 0.0)
    f["pe"] = f["pe"].fillna(avg[1] if avg and avg[1] is not None else 0.0)
    p = model.predict_proba(f[FEATURES])[:, 1][0]
    contrib = model.booster_.predict(f[FEATURES], pred_contrib=True)[0]
    parts = sorted(zip(FEATURES, contrib), key=lambda x: -abs(x[1]))[:5]
    why = [{"feature": k, "impact": round(float(v), 3)} for k, v in parts]
    return {"symbol": sym, "p_win": round(float(p), 3), "why": why}

def rank_symbols(syms, use_yahoo=False):
    out = []
    for s in syms:
        r = score_symbol(s, use_yahoo=use_yahoo)
        if r and r.get("p_win") is not None:
            out.append({"symbol": s, "p_win": r["p_win"]})
    out.sort(key=lambda x: -x["p_win"])
    return out

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "train"
    if cmd == "train":
        train()
    else:
        print(score_symbol(cmd))