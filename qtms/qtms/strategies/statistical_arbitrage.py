"""Statistical arbitrage PLACEHOLDER.

A real stat-arb needs a second correlated instrument and a cointegration test.
This MVP placeholder builds a synthetic 'fair value' from a longer EMA and
trades the residual — clearly labelled as a placeholder so it is never mistaken
for a validated pairs strategy. It is conservative and low-conviction by design.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class StatisticalArbitrage(Strategy):
    name = "statistical_arbitrage"
    entry_threshold = 0.35

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 10, "placeholder": True}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        fair = close.ewm(span=50, adjust=False).mean()
        resid = (close - fair) / close
        z = (resid - resid.rolling(50, min_periods=5).mean()) / (
            resid.rolling(50, min_periods=5).std() + 1e-9
        )
        # Mean-revert the residual, but damped because this is a placeholder.
        raw = -np.tanh(z) * 0.5
        return raw.fillna(0.0).clip(-1, 1)

    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        return ["placeholder_residual_reversion", "NOT_VALIDATED_PAIRS"]
