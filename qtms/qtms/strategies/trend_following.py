"""Trend-following: long when fast EMA leads slow EMA with positive momentum."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class TrendFollowing(Strategy):
    name = "trend_following"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 20}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        ma_spread = features["ma_spread"]
        momentum = features["momentum"]
        structure = features.get("structure", pd.Series(0.0, index=df.index))
        raw = np.tanh(80 * ma_spread) * 0.6 + np.tanh(20 * momentum) * 0.3 + structure * 0.1
        return raw.clip(-1, 1)

    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        codes = []
        if features["ma_spread"].iloc[-1] > 0:
            codes.append("fast_ema_above_slow")
        else:
            codes.append("fast_ema_below_slow")
        if features["momentum"].iloc[-1] > 0:
            codes.append("positive_momentum")
        return codes
