"""Trend features: moving averages, slope, momentum, market structure.

All features are causal (use only past/current data) to avoid lookahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def trend_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    close = df["close"]
    out["sma_fast"] = close.rolling(10, min_periods=1).mean()
    out["sma_slow"] = close.rolling(30, min_periods=1).mean()
    out["ema_fast"] = close.ewm(span=12, adjust=False).mean()
    out["ema_slow"] = close.ewm(span=26, adjust=False).mean()
    out["ma_spread"] = (out["ema_fast"] - out["ema_slow"]) / close
    # Slope of fast EMA over 5 bars, normalized by price.
    out["slope"] = out["ema_fast"].diff(5) / (close + 1e-9)
    # Momentum: log return over 10 bars.
    out["momentum"] = np.log(close / close.shift(10))
    # Market structure: rolling higher-high / lower-low count.
    roll_max = df["high"].rolling(20, min_periods=2).max()
    roll_min = df["low"].rolling(20, min_periods=2).min()
    out["hh"] = (df["high"] >= roll_max).astype(float)
    out["ll"] = (df["low"] <= roll_min).astype(float)
    out["structure"] = out["hh"] - out["ll"]
    return out.fillna(0.0)
