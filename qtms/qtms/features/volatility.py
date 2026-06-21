"""Volatility features: ATR, rolling volatility, volatility regime flag."""
from __future__ import annotations

import numpy as np
import pandas as pd


def volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    out["atr"] = tr.rolling(14, min_periods=1).mean()
    out["atr_pct"] = (out["atr"] / close).fillna(0.0)
    log_ret = np.log(close / close.shift(1))
    out["rolling_vol"] = log_ret.rolling(20, min_periods=2).std().fillna(0.0)
    # Volatility regime: current vol relative to its longer-run median.
    med = out["rolling_vol"].rolling(100, min_periods=10).median()
    out["vol_regime"] = (out["rolling_vol"] / (med + 1e-9)).fillna(1.0)
    return out.fillna(0.0)
