import numpy as np
import pandas as pd
import lightgbm as lgb
import db
import joblib
from ml_features import FEATURE_COLUMNS, feature_frame

MODEL_VERSION = "v0.2-pit-safe"
LABEL_HORIZONS = {"ret_6m_fwd": 126, "ret_12m_fwd": 252}

def build_dataset(conn):
    q = """SELECT symbol, date, close, volume
           FROM prices_daily ORDER BY symbol, date"""
    df = pd.read_sql(q, conn)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    return df

def make_features(group):
    g = group.sort_values("date").copy()
    if len(g) < 250:
        return None
    return feature_frame(g)

def make_targets(group):
    g = group.sort_values("date").copy()
    if len(g) < 250 + 252:
        return None
    g["ret_6m_fwd"] = g["close"].shift(-126) / g["close"] - 1
    g["ret_12m_fwd"] = g["close"].shift(-252) / g["close"] - 1
    # The label is available only after the horizon has elapsed.  Keeping the
    # availability date makes purging around time split boundaries explicit.
    g["label_available_date"] = g["date"].shift(-252)
    return g


def _time_split(df, train_fraction=0.70, val_fraction=0.15):
    """Global-date split with embargo/purge for forward-label availability."""
    dates = np.sort(df["date"].dropna().unique())
    if len(dates) < 3:
        raise ValueError("not enough global dates for time split")
    train_date = dates[max(0, int(len(dates) * train_fraction) - 1)]
    val_date = dates[min(len(dates) - 1,
                         int(len(dates) * (train_fraction + val_fraction)))]
    tr = df[df["date"] <= train_date]
    va = df[(df["date"] > train_date) & (df["date"] < val_date)]
    te = df[df["date"] >= val_date]
    # A row remains in a split only when its future label is known before the
    # next split starts. This prevents overlapping labels leaking across folds.
    tr = tr[tr["label_available_date"] < va["date"].min()] if not va.empty else tr.iloc[0:0]
    va = va[va["label_available_date"] < te["date"].min()] if not te.empty else va.iloc[0:0]
    return tr, va, te

def train():
    conn = db.get_conn()
    df = build_dataset(conn)
    print(f"Loaded {len(df):,} price rows for {df['symbol'].nunique()} stocks")

    feats = []
    for sym, grp in df.groupby("symbol"):
        fg = make_features(grp)
        tg = make_targets(grp)
        if fg is None or tg is None:
            continue
        merged = fg.merge(tg, on=["symbol", "date"], suffixes=("", "_y"))
        feats.append(merged)
    df2 = pd.concat(feats, ignore_index=True)
    print(f"Feature rows: {len(df2):,}")

    feat_cols = FEATURE_COLUMNS
    df2 = df2.dropna(subset=feat_cols + ["ret_6m_fwd", "ret_12m_fwd"])
    df2 = df2.sort_values(["date", "symbol"]).reset_index(drop=True)
    print(f"Training rows: {len(df2):,}")

    tr, va, te = _time_split(df2)
    if min(len(tr), len(va), len(te)) == 0:
        raise ValueError("purged global-date split has an empty fold")
    # Thresholds are learned from training labels only.
    thresholds = {"6m": float(tr["ret_6m_fwd"].median()),
                  "12m": float(tr["ret_12m_fwd"].median())}
    y6_train = (tr["ret_6m_fwd"] > thresholds["6m"]).astype(int).values
    y6_val = (va["ret_6m_fwd"] > thresholds["6m"]).astype(int).values
    y6_test = (te["ret_6m_fwd"] > thresholds["6m"]).astype(int).values
    y12_train = (tr["ret_12m_fwd"] > thresholds["12m"]).astype(int).values
    y12_val = (va["ret_12m_fwd"] > thresholds["12m"]).astype(int).values
    y12_test = (te["ret_12m_fwd"] > thresholds["12m"]).astype(int).values
    medians = tr[feat_cols].median().fillna(0.0).to_dict()
    X_train = tr[feat_cols].fillna(medians).values
    X_val = va[feat_cols].fillna(medians).values
    X_test = te[feat_cols].fillna(medians).values

    dtrain6 = lgb.Dataset(X_train, label=y6_train)
    dval6 = lgb.Dataset(X_val, label=y6_val, reference=dtrain6)
    m6 = lgb.train({"objective": "binary", "metric": "auc",
                    "verbosity": -1},
                    dtrain6, valid_sets=[dval6], num_boost_round=200,
                    callbacks=[lgb.early_stopping(25, verbose=False)])

    dtrain12 = lgb.Dataset(X_train, label=y12_train)
    dval12 = lgb.Dataset(X_val, label=y12_val, reference=dtrain12)
    m12 = lgb.train({"objective": "binary", "metric": "auc",
                     "verbosity": -1},
                    dtrain12, valid_sets=[dval12], num_boost_round=200,
                    callbacks=[lgb.early_stopping(25, verbose=False)])

    joblib.dump({"m6": m6, "m12": m12, "feat_cols": feat_cols,
                  "version": MODEL_VERSION,
                  "metadata": {"features": feat_cols,
                               "label_thresholds": thresholds,
                               "imputation_medians": medians,
                               "split": "global_date_purged",
                               "validation": "early_stopping_only",
                               "test": "final_holdout"}},
                 "data/ml_models.pkl")

    preds6 = m6.predict(X_test)
    preds12 = m12.predict(X_test)
    from sklearn.metrics import roc_auc_score
    auc6 = roc_auc_score(y6_test, preds6)
    auc12 = roc_auc_score(y12_test, preds12)
    print(f"Test AUC 6M: {auc6:.3f}")
    print(f"Test AUC 12M: {auc12:.3f}")
    conn.close()

if __name__ == "__main__":
    train()
