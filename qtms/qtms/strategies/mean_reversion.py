"""Mean reversion: fade extreme z-scores back toward the moving average."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class MeanReversion(Strategy):
    name = "mean_reversion"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 8, "z_entry": 1.5}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        z = features["zscore"]
        vwap_dist = features.get("vwap_dist", pd.Series(0.0, index=df.index))
        # Negative of z: high price -> short, low price -> long.
        raw = -np.tanh(z / self.params["z_entry"]) * 0.7 - np.tanh(50 * vwap_dist) * 0.3
        # Suppress in strong trend regimes where reversion is dangerous.
        vol_regime = features.get("vol_regime", pd.Series(1.0, index=df.index))
        raw = raw * (vol_regime < 1.5).astype(float)
        return raw.clip(-1, 1)

    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        z = features["zscore"].iloc[-1]
        if z > 1.5:
            return ["overbought_zscore", "fade_long_extension"]
        if z < -1.5:
            return ["oversold_zscore", "fade_short_extension"]
        return ["within_band"]
