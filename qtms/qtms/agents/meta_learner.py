"""Machine-learning meta-model (off-path research, NOT in the hot path).

Asks one honest question: does a simple ML model find *predictive structure* in
this market's features? It trains a logistic regression to predict the sign of
the forward return, using WALK-FORWARD evaluation so every score is on data the
model never trained on (no leakage). The verdict is conservative: an "edge" is
only claimed if out-of-sample AUC is robustly above 0.5 across folds.

This never trades, never enables live, and runs only after data is in hand.
Most real markets will score ~0.5 (no edge) — and that is the truthful result.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..features.pipeline import compute_features

_FEATURES = [
    "ma_spread", "slope", "momentum", "zscore", "vwap_dist", "atr_pct",
    "vol_regime", "wick_skew", "volume_spike", "bollinger_pos", "candle_imbalance",
]


def train_meta_model(df: pd.DataFrame, horizon: int = 3, folds: int = 4) -> dict:
    """Walk-forward train/score a logistic model predicting forward-return sign."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.preprocessing import StandardScaler
    except Exception:  # pragma: no cover - sklearn is a core dep
        return {"available": False, "note": "scikit-learn not installed"}

    feats = compute_features(df)
    cols = [c for c in _FEATURES if c in feats.columns]
    X = feats[cols].replace([np.inf, -np.inf], 0.0).fillna(0.0).to_numpy()
    fwd = (df["close"].shift(-horizon) / df["close"] - 1.0).to_numpy()
    y = (fwd > 0).astype(int)

    # Drop the last `horizon` rows (their forward return is unknown).
    if len(X) <= horizon + 50:
        return {"available": True, "has_edge": False, "note": "not enough data",
                "n_samples": int(max(0, len(X) - horizon))}
    X, y = X[:-horizon], y[:-horizon]

    n = len(X)
    fold = n // (folds + 1)
    aucs, accs = [], []
    importance_sum = np.zeros(len(cols))
    used = 0
    for i in range(folds):
        tr_end = fold * (i + 1)
        te_end = min(n, tr_end + fold)
        if te_end - tr_end < 25:
            continue
        Xtr, ytr = X[:tr_end], y[:tr_end]
        Xte, yte = X[tr_end:te_end], y[tr_end:te_end]
        if len(set(ytr)) < 2 or len(set(yte)) < 2:
            continue
        scaler = StandardScaler().fit(Xtr)
        model = LogisticRegression(max_iter=300, C=0.5)
        model.fit(scaler.transform(Xtr), ytr)
        proba = model.predict_proba(scaler.transform(Xte))[:, 1]
        try:
            aucs.append(float(roc_auc_score(yte, proba)))
        except ValueError:
            continue
        accs.append(float(((proba > 0.5).astype(int) == yte).mean()))
        importance_sum += np.abs(model.coef_[0])
        used += 1

    if used == 0:
        return {"available": True, "has_edge": False, "note": "insufficient class balance",
                "n_samples": int(n)}

    mean_auc = float(np.mean(aucs))
    min_auc = float(np.min(aucs))
    # Conservative edge test: needs >=2 folds, mean AUC > 0.52, and no fold below 0.5.
    has_edge = used >= 2 and mean_auc > 0.52 and min_auc > 0.5

    imp = importance_sum / used
    top = sorted(zip(cols, imp), key=lambda t: t[1], reverse=True)[:5]

    return {
        "available": True,
        "model": "logistic_regression (walk-forward)",
        "horizon_bars": horizon,
        "folds_used": used,
        "n_samples": int(n),
        "oos_auc_mean": round(mean_auc, 4),
        "oos_auc_min": round(min_auc, 4),
        "oos_accuracy_mean": round(float(np.mean(accs)), 4),
        "has_edge": bool(has_edge),
        "top_features": [{"feature": f, "weight": round(float(w), 3)} for f, w in top],
        "verdict": (
            "predictive structure found out-of-sample"
            if has_edge else "no reliable edge (≈coin flip) — honest null result"
        ),
    }
