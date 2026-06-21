"""Mean-reversion features: z-score, Bollinger position, VWAP distance."""
from __future__ import annotations

import numpy as np
import pandas as pd


def mean_reversion_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    close = df["close"]
    ma = close.rolling(20, min_periods=2).mean()
    sd = close.rolling(20, min_periods=2).std().replace(0, np.nan)
    out["zscore"] = ((close - ma) / sd).fillna(0.0)
    # Bollinger position in [-1, 1]: -1 at lower band, +1 at upper band.
    out["bollinger_pos"] = (out["zscore"] / 2.0).clip(-1.5, 1.5)
    # Rolling VWAP placeholder (typical price weighted by volume).
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_vp = (tp * df["volume"]).rolling(20, min_periods=1).sum()
    cum_v = df["volume"].rolling(20, min_periods=1).sum().replace(0, np.nan)
    vwap = cum_vp / cum_v
    out["vwap"] = vwap.fillna(close)
    out["vwap_dist"] = ((close - out["vwap"]) / close).fillna(0.0)
    return out.fillna(0.0)
