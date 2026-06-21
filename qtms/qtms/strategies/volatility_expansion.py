"""Volatility expansion: trade in the direction of momentum when volatility
regime is expanding (ATR rising), flat in quiet regimes."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class VolatilityExpansion(Strategy):
    name = "volatility_expansion"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 12}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        vol_regime = features.get("vol_regime", pd.Series(1.0, index=df.index))
        momentum = features["momentum"]
        expanding = np.clip(vol_regime - 1.0, 0, 2) / 2.0
        raw = np.tanh(25 * momentum) * expanding
        return raw.fillna(0.0).clip(-1, 1)

    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        vr = features.get("vol_regime", pd.Series([1.0])).iloc[-1]
        if vr > 1.3:
            return ["volatility_expanding", "ride_momentum"]
        return ["volatility_subdued", "stand_aside"]
