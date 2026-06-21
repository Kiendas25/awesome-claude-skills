"""Breakout: trade closes that pierce the recent high/low channel."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class Breakout(Strategy):
    name = "breakout"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 15, "lookback": 20}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        lb = self.params["lookback"]
        # Use prior window (exclude current bar) to avoid trivial lookahead.
        roll_high = df["high"].rolling(lb, min_periods=2).max().shift(1)
        roll_low = df["low"].rolling(lb, min_periods=2).min().shift(1)
        close = df["close"]
        up = (close - roll_high) / close
        down = (roll_low - close) / close
        vol_spike = features.get("volume_spike", pd.Series(1.0, index=df.index))
        conf = np.clip((vol_spike - 1.0) / 2.0, 0, 1) * 0.5 + 0.5
        raw = (np.tanh(200 * up) - np.tanh(200 * down)) * conf
        return raw.fillna(0.0).clip(-1, 1)

    def reason_codes(self, features: pd.DataFrame, df: pd.DataFrame) -> list[str]:
        codes = []
        vs = features.get("volume_spike", pd.Series([1.0])).iloc[-1]
        if vs > 1.5:
            codes.append("volume_confirmed_breakout")
        else:
            codes.append("unconfirmed_breakout")
        return codes
