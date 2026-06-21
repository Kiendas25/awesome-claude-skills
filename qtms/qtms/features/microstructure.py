"""Microstructure features: candle imbalance, wick ratios, volume acceleration."""
from __future__ import annotations

import numpy as np
import pandas as pd


def microstructure_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rng = (h - l).replace(0, np.nan)
    body = (c - o)
    out["candle_imbalance"] = (body / rng).fillna(0.0)
    upper_wick = (h - np.maximum(o, c))
    lower_wick = (np.minimum(o, c) - l)
    out["upper_wick_ratio"] = (upper_wick / rng).fillna(0.0)
    out["lower_wick_ratio"] = (lower_wick / rng).fillna(0.0)
    out["wick_skew"] = out["lower_wick_ratio"] - out["upper_wick_ratio"]
    vol = df["volume"]
    out["volume_accel"] = vol.diff().fillna(0.0) / (vol.rolling(10, min_periods=1).mean() + 1e-9)
    return out.fillna(0.0)
