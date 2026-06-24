"""Extended strategy building blocks (genuinely distinct signal families).

These expand the universe the learning agent searches over. Each is a real,
deterministic signal — momentum, RSI reversion, Donchian breakout, MACD trend,
Bollinger bounce, VWAP reversion. They reuse the feature pipeline where possible
and compute the rest causally inline. As always: strategies only emit signals;
they never place orders, and none is trusted until it survives validation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Strategy


class Momentum(Strategy):
    name = "momentum"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 12, "lookback": 14}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        lb = int(self.params["lookback"])
        roc = df["close"] / df["close"].shift(lb) - 1.0
        return np.tanh(30 * roc).fillna(0.0).clip(-1, 1)

    def reason_codes(self, features, df):
        return ["positive_roc"] if self.score(features, df).iloc[-1] > 0 else ["negative_roc"]


class RSIReversion(Strategy):
    name = "rsi_reversion"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 8, "period": 14}

    def _rsi(self, close: pd.Series) -> pd.Series:
        p = int(self.params["period"])
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(p, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).rolling(p, min_periods=1).mean()
        rs = gain / (loss + 1e-9)
        return 100 - 100 / (1 + rs)

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        rsi = self._rsi(df["close"])
        # Oversold (<30) -> long; overbought (>70) -> short. Map to [-1,1].
        return ((50 - rsi) / 30).fillna(0.0).clip(-1, 1)

    def reason_codes(self, features, df):
        r = self._rsi(df["close"]).iloc[-1]
        if r < 30:
            return ["rsi_oversold"]
        if r > 70:
            return ["rsi_overbought"]
        return ["rsi_neutral"]


class DonchianBreakout(Strategy):
    name = "donchian_breakout"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 18, "lookback": 25}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        lb = int(self.params["lookback"])
        hh = df["high"].rolling(lb, min_periods=2).max().shift(1)
        ll = df["low"].rolling(lb, min_periods=2).min().shift(1)
        close = df["close"]
        up = (close - hh) / close
        down = (ll - close) / close
        return (np.tanh(150 * up) - np.tanh(150 * down)).fillna(0.0).clip(-1, 1)

    def reason_codes(self, features, df):
        s = self.score(features, df).iloc[-1]
        return ["donchian_break_up"] if s > 0 else (["donchian_break_down"] if s < 0 else ["inside_channel"])


class MACDTrend(Strategy):
    name = "macd_trend"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 16}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        close = df["close"]
        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal = macd.ewm(span=9, adjust=False).mean()
        return np.tanh(120 * (macd - signal) / close).fillna(0.0).clip(-1, 1)

    def reason_codes(self, features, df):
        return ["macd_above_signal"] if self.score(features, df).iloc[-1] > 0 else ["macd_below_signal"]


class BollingerBounce(Strategy):
    name = "bollinger_bounce"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 7}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        pos = features.get("bollinger_pos", pd.Series(0.0, index=df.index))
        vol_regime = features.get("vol_regime", pd.Series(1.0, index=df.index))
        # Fade only strong band touches, and stand aside in high-vol regimes.
        raw = -pos.clip(-1.5, 1.5) / 1.5
        raw = raw * (pos.abs() > 0.8).astype(float) * (vol_regime < 1.4).astype(float)
        return raw.fillna(0.0).clip(-1, 1)

    def reason_codes(self, features, df):
        pos = features.get("bollinger_pos", pd.Series([0.0])).iloc[-1]
        if pos > 0.8:
            return ["upper_band_fade"]
        if pos < -0.8:
            return ["lower_band_bounce"]
        return ["mid_band"]


class VWAPReversion(Strategy):
    name = "vwap_reversion"
    entry_threshold = 0.3

    @staticmethod
    def default_params() -> dict:
        return {"holding_bars": 6}

    def score(self, features: pd.DataFrame, df: pd.DataFrame) -> pd.Series:
        dist = features.get("vwap_dist", pd.Series(0.0, index=df.index))
        # Price above VWAP -> fade short; below -> fade long.
        return (-np.tanh(60 * dist)).fillna(0.0).clip(-1, 1)

    def reason_codes(self, features, df):
        d = features.get("vwap_dist", pd.Series([0.0])).iloc[-1]
        return ["above_vwap_fade"] if d > 0 else (["below_vwap_fade"] if d < 0 else ["at_vwap"])
