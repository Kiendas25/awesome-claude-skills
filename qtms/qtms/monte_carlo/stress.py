"""Stress scenarios: deterministic shocks applied to a price path."""
from __future__ import annotations

import numpy as np
import pandas as pd

SCENARIOS = ["flash_crash", "vol_spike", "liquidity_drain", "trend_reversal"]


def apply_stress(df: pd.DataFrame, scenario: str, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    d = df.copy()
    n = len(d)
    if scenario == "flash_crash":
        cut = int(n * 0.7)
        shock = np.ones(n)
        shock[cut : cut + 3] = [0.9, 0.85, 0.92]
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] * np.cumprod(np.where(np.arange(n) == cut, 0.88, 1.0))
    elif scenario == "vol_spike":
        noise = np.exp(rng.normal(0.0, 0.03, size=n))
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] * noise
    elif scenario == "liquidity_drain":
        d["volume"] = d["volume"] * 0.2
        if "spread" in d.columns:
            d["spread"] = d["spread"] * 5.0
    elif scenario == "trend_reversal":
        ramp = np.linspace(1.0, 0.85, n)
        for c in ("open", "high", "low", "close"):
            d[c] = d[c] * ramp
    d.attrs.update(df.attrs)
    d.attrs["stress"] = scenario
    return d
