"""Liquidity features: volume spikes, spread placeholder, fake-liquidity risk."""
from __future__ import annotations

import numpy as np
import pandas as pd


def liquidity_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    vol = df["volume"]
    vol_ma = vol.rolling(20, min_periods=1).mean()
    out["volume_spike"] = (vol / (vol_ma + 1e-9)).fillna(1.0)
    if "spread" in df.columns:
        out["spread"] = df["spread"]
    else:
        out["spread"] = (df["close"] * 0.0001)
    out["spread_pct"] = (out["spread"] / df["close"]).fillna(0.0)
    # Fake-liquidity risk placeholder: large price move on below-average volume
    # is a warning sign of thin / spoofed liquidity.
    ret = np.log(df["close"] / df["close"].shift(1)).abs().fillna(0.0)
    out["fake_liquidity_risk"] = (ret / (out["volume_spike"] + 1e-9)).clip(0, 5)
    return out.fillna(0.0)
