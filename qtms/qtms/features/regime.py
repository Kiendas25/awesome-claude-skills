"""Regime classification: trend_up / trend_down / range / high_vol / low_vol."""
from __future__ import annotations

import numpy as np
import pandas as pd


def classify_regime(features: pd.DataFrame) -> pd.Series:
    """Return a categorical regime label per bar from existing features."""
    slope = features.get("slope", pd.Series(0.0, index=features.index))
    vol_regime = features.get("vol_regime", pd.Series(1.0, index=features.index))
    momentum = features.get("momentum", pd.Series(0.0, index=features.index))

    labels = []
    for s, vr, m in zip(slope, vol_regime, momentum):
        if vr > 1.6:
            labels.append("high_vol")
        elif vr < 0.6:
            labels.append("low_vol")
        elif s > 0.002 and m > 0:
            labels.append("trend_up")
        elif s < -0.002 and m < 0:
            labels.append("trend_down")
        else:
            labels.append("range")
    return pd.Series(labels, index=features.index, name="regime")


def current_regime(features: pd.DataFrame) -> str:
    return str(classify_regime(features).iloc[-1])
