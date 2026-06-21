"""Liquidity sweep: detect stop-hunt wicks beyond recent extremes that reverse,
then fade in the opposite direction of the sweep."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class LiquiditySweep(Strategy):
    name = "liquidity_sweep"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 6, "lookback": 20}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        lb = self.params["lookback"]
        prior_high = df["high"].rolling(lb, min_periods=2).max().shift(1)
        prior_low = df["low"].rolling(lb, min_periods=2).min().shift(1)
        # Swept above prior high but closed back below -> bearish (fade short).
        swept_high = (df["high"] > prior_high) & (df["close"] < prior_high)
        swept_low = (df["low"] < prior_low) & (df["close"] > prior_low)
        wick_skew = features.get("wick_skew", pd.Series(0.0, index=df.index))
        raw = (
            swept_low.astype(float) * (0.5 + 0.5 * wick_skew.clip(0, 1))
            - swept_high.astype(float) * (0.5 + 0.5 * (-wick_skew).clip(0, 1))
        )
        return raw.fillna(0.0).clip(-1, 1)

    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        return ["liquidity_sweep_reversal"]
